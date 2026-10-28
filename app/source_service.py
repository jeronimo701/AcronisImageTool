from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from ftplib import FTP
from pathlib import Path, PurePosixPath
import posixpath
import shutil
import tempfile

from .config import COPY_CHUNK_SIZE, SUPPORTED_EXTENSIONS
from .smb_service import ensure_connection


@dataclass(slots=True)
class SourceConfig:
    protocol: str
    endpoint: str
    root: str
    username: str
    password: str
    anonymous: bool


@dataclass(slots=True)
class SourceFile:
    protocol: str
    endpoint: str
    root: str
    relative_path: PurePosixPath
    locator: str
    name: str
    size: int
    modified_at: datetime


class TransferCancelled(Exception):
    pass


def list_source_files(config: SourceConfig) -> list[SourceFile]:
    if config.protocol == "web":
        from .web_source import list_web_files
        return list_web_files(config)
    if config.protocol == "smb":
        return _list_smb_files(config)
    if config.protocol == "ftp":
        return _list_ftp_files(config)
    raise ValueError(f"Unsupported protocol: {config.protocol}")


def copy_source_file(
    source_file: SourceFile,
    config: SourceConfig,
    target_path: Path,
    progress_cb,
    cancel_cb,
) -> None:
    if source_file.protocol == "web":
        from .web_source import copy_web_file
        copy_web_file(source_file, target_path, progress_cb, cancel_cb)
        return
    if source_file.protocol == "smb":
        _copy_smb_file(source_file, config, target_path, progress_cb, cancel_cb)
        return
    if source_file.protocol == "ftp":
        _copy_ftp_file(source_file, config, target_path, progress_cb, cancel_cb)
        return
    raise ValueError(f"Unsupported protocol: {source_file.protocol}")


def rename_source_file(source_file: SourceFile, config: SourceConfig, new_name: str) -> str:
    if source_file.protocol == "web":
        raise ValueError("Публичный веб-каталог доступен только для чтения.")
    if source_file.protocol == "smb":
        old_path = Path(source_file.locator)
        new_path = old_path.with_name(new_name)
        old_path.rename(new_path)
        return str(new_path)
    if source_file.protocol == "ftp":
        with _open_ftp(config) as ftp:
            old_remote = _ftp_join(config.root, source_file.relative_path.as_posix())
            new_relative = source_file.relative_path.with_name(new_name)
            new_remote = _ftp_join(config.root, new_relative.as_posix())
            ftp.rename(old_remote, new_remote)
            return f"ftp://{config.endpoint}{new_remote}"
    raise ValueError(f"Unsupported protocol: {source_file.protocol}")


def _list_smb_files(config: SourceConfig) -> list[SourceFile]:
    ensure_connection(config.root, config.endpoint, config.username, config.password, config.anonymous)
    root_path = Path(config.root)
    items: list[SourceFile] = []
    for path in sorted(root_path.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        relative = PurePosixPath(path.relative_to(root_path).as_posix())
        stat = path.stat()
        items.append(
            SourceFile(
                protocol="smb",
                endpoint=config.endpoint,
                root=config.root,
                relative_path=relative,
                locator=str(path),
                name=path.name,
                size=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime),
            )
        )
    return items


def _list_ftp_files(config: SourceConfig) -> list[SourceFile]:
    items: list[SourceFile] = []
    with _open_ftp(config) as ftp:
        _walk_ftp(ftp, config, config.root, PurePosixPath("."), items)
    return items


def _walk_ftp(ftp: FTP, config: SourceConfig, remote_dir: str, relative_dir: PurePosixPath, items: list[SourceFile]) -> None:
    try:
        entries = list(ftp.mlsd(remote_dir, facts=["type", "size", "modify"]))
    except Exception:
        names = ftp.nlst(remote_dir)
        entries = []
        for full_name in names:
            name = posixpath.basename(full_name.rstrip("/"))
            if not name or name in {".", ".."}:
                continue
            is_dir = _ftp_is_dir(ftp, full_name)
            entries.append((name, {"type": "dir" if is_dir else "file"}))

    for name, facts in entries:
        if name in {".", ".."}:
            continue
        entry_type = facts.get("type", "")
        rel = relative_dir / name if str(relative_dir) != "." else PurePosixPath(name)
        full_remote = _ftp_join(remote_dir, name)
        if entry_type == "dir":
            _walk_ftp(ftp, config, full_remote, rel, items)
            continue
        if PurePosixPath(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        size = int(facts.get("size", ftp.size(full_remote) or 0))
        modified = _parse_ftp_mtime(facts.get("modify")) or _ftp_mdtm(ftp, full_remote)
        items.append(
            SourceFile(
                protocol="ftp",
                endpoint=config.endpoint,
                root=config.root,
                relative_path=rel,
                locator=f"ftp://{config.endpoint}{full_remote}",
                name=name,
                size=size,
                modified_at=modified,
            )
        )


def _copy_smb_file(source_file: SourceFile, config: SourceConfig, target_path: Path, progress_cb, cancel_cb) -> None:
    ensure_connection(config.root, config.endpoint, config.username, config.password, config.anonymous)
    temp_path = target_path.with_suffix(target_path.suffix + ".part")
    if temp_path.exists():
        temp_path.unlink()
    done = 0
    with Path(source_file.locator).open("rb") as src, temp_path.open("wb") as dst:
        while True:
            if cancel_cb():
                raise TransferCancelled
            chunk = src.read(COPY_CHUNK_SIZE)
            if not chunk:
                break
            dst.write(chunk)
            done += len(chunk)
            progress_cb(done, source_file.size)
    shutil.move(str(temp_path), str(target_path))


def _copy_ftp_file(source_file: SourceFile, config: SourceConfig, target_path: Path, progress_cb, cancel_cb) -> None:
    temp_path = target_path.with_suffix(target_path.suffix + ".part")
    if temp_path.exists():
        temp_path.unlink()
    done = 0

    def on_chunk(chunk: bytes) -> None:
        nonlocal done
        if cancel_cb():
            raise TransferCancelled
        with temp_path.open("ab") as dst:
            dst.write(chunk)
        done += len(chunk)
        progress_cb(done, source_file.size)

    with _open_ftp(config) as ftp:
        remote_path = _ftp_join(config.root, source_file.relative_path.as_posix())
        try:
            ftp.retrbinary(f"RETR {remote_path}", on_chunk, blocksize=COPY_CHUNK_SIZE)
        except TransferCancelled:
            if temp_path.exists():
                temp_path.unlink()
            raise
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise
    shutil.move(str(temp_path), str(target_path))


def _open_ftp(config: SourceConfig) -> FTP:
    host, port = _parse_ftp_endpoint(config.endpoint)
    ftp = FTP()
    ftp.connect(host, port, timeout=30)
    if config.anonymous:
        ftp.login()
    else:
        ftp.login(config.username, config.password)
    return ftp


def _parse_ftp_endpoint(endpoint: str) -> tuple[str, int]:
    if ":" in endpoint:
        host, port_text = endpoint.rsplit(":", 1)
        return host.strip(), int(port_text)
    return endpoint.strip(), 21


def _ftp_join(base: str, leaf: str) -> str:
    if not base:
        base = "/"
    if leaf in {"", "."}:
        return base
    return posixpath.join(base, leaf).replace("\\", "/")


def _ftp_is_dir(ftp: FTP, remote_path: str) -> bool:
    current = ftp.pwd()
    try:
        ftp.cwd(remote_path)
        ftp.cwd(current)
        return True
    except Exception:
        try:
            ftp.cwd(current)
        except Exception:
            pass
        return False


def _ftp_mdtm(ftp: FTP, remote_path: str) -> datetime:
    response = ftp.sendcmd(f"MDTM {remote_path}")
    stamp = response.split()[-1]
    return datetime.strptime(stamp, "%Y%m%d%H%M%S")


def _parse_ftp_mtime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%d%H%M%S")
    except Exception:
        return None
