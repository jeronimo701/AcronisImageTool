from __future__ import annotations

from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from .config import COPY_CHUNK_SIZE, SUPPORTED_EXTENSIONS

WEB_ENDPOINT = "https://fs.poscenter.org"
WEB_FOLDER = "09.Моноблоки и POS-ПК/Образы ОС Windows (Acronis)/"


def resolve_location(endpoint: str, folder: str) -> tuple[str, str]:
    location = folder if folder.startswith(("https://", "http://")) else endpoint
    parsed = urlsplit(location)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Укажите HTTPS-адрес публичного каталога.")
    origin = f"{parsed.scheme}://{parsed.netloc}"
    prefix = unquote(parsed.fragment.lstrip("/")) if parsed.fragment else unquote(parsed.path.lstrip("/"))
    if location == endpoint and folder and not folder.startswith(("https://", "http://")):
        prefix = unquote(folder.strip().lstrip("/"))
    if prefix and not PurePosixPath(prefix).suffix.lower() in SUPPORTED_EXTENSIONS:
        prefix = prefix.rstrip("/") + "/"
    return origin, prefix


def list_web_files(config):
    from .source_service import SourceFile

    origin, prefix = resolve_location(config.endpoint, config.root)
    bucket = urlsplit(origin).hostname
    api = f"https://storage.yandexcloud.net/{bucket}"
    token = ""
    seen_tokens = set()
    files = {}
    while True:
        params = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if token:
            params["continuation-token"] = token
        with urlopen(Request(api + "?" + urlencode(params)), timeout=30) as response:
            root = ET.fromstring(response.read())
        ns = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
        if root.tag != "{http://s3.amazonaws.com/doc/2006-03-01/}ListBucketResult":
            raise ValueError("Сервер не вернул публичный каталог ListObjectsV2.")
        for item in root.findall("s:Contents", ns):
            key = item.findtext("s:Key", "", ns)
            name = PurePosixPath(key).name
            if PurePosixPath(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            relative = key[len(prefix):] if prefix.endswith("/") else name
            if not relative or any(part in {".", ".."} for part in relative.split("/")):
                continue
            stamp = item.findtext("s:LastModified", "", ns)
            modified = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
            files[key] = SourceFile(
                protocol="web", endpoint=config.endpoint, root=config.root,
                relative_path=PurePosixPath(relative), locator=origin + "/" + quote(key, safe="/"),
                name=name, size=int(item.findtext("s:Size", "0", ns)), modified_at=modified,
            )
        if root.findtext("s:IsTruncated", "false", ns).lower() != "true":
            break
        token = root.findtext("s:NextContinuationToken", "", ns)
        if not token or token in seen_tokens:
            raise ValueError("Сервер не вернул корректную следующую страницу каталога.")
        seen_tokens.add(token)
    return sorted(files.values(), key=lambda item: str(item.relative_path).casefold())


def copy_web_file(source_file, target_path: Path, progress_cb, cancel_cb) -> None:
    from .source_service import TransferCancelled

    temp = target_path.with_suffix(target_path.suffix + ".part")
    done = 0
    try:
        with urlopen(Request(source_file.locator), timeout=30) as response, temp.open("wb") as output:
            while True:
                if cancel_cb():
                    raise TransferCancelled
                block = response.read(COPY_CHUNK_SIZE)
                if not block:
                    break
                output.write(block)
                done += len(block)
                progress_cb(done, source_file.size)
        if done != source_file.size:
            raise OSError(f"Размер загрузки отличается: {done} / {source_file.size}")
        temp.replace(target_path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
