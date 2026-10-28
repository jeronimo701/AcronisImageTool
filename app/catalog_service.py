from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
from pathlib import PurePosixPath
import json

from .config import PROJECT_ROOT


def catalog_path(config):
    key = json.dumps([config.protocol, config.endpoint, config.root], ensure_ascii=False)
    return PROJECT_ROOT / "catalogs" / (sha256(key.encode()).hexdigest() + ".json")


def save_catalog(config, files):
    path = catalog_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in files:
        row = asdict(item)
        row["relative_path"] = item.relative_path.as_posix()
        row["modified_at"] = item.modified_at.isoformat()
        rows.append(row)
    data = {"updated_at": datetime.now().isoformat(), "files": rows}
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def load_catalog(config):
    from .source_service import SourceFile

    path = catalog_path(config)
    if not path.exists():
        raise FileNotFoundError("Сохранённого каталога нет. Нажмите «Пересканировать».")
    data = json.loads(path.read_text(encoding="utf-8"))
    files = []
    for row in data["files"]:
        row["relative_path"] = PurePosixPath(row["relative_path"])
        row["modified_at"] = datetime.fromisoformat(row["modified_at"])
        files.append(SourceFile(**row))
    return files
