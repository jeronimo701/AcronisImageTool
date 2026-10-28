from __future__ import annotations

import json

from .config import SETTINGS_PATH, SMB_PASSWORD, SMB_USERNAME
from .web_source import WEB_ENDPOINT, WEB_FOLDER


DEFAULT_SETTINGS = {
    "protocol": "web",
    "source_root": WEB_FOLDER,
    "endpoint": WEB_ENDPOINT,
    "username": SMB_USERNAME,
    "password": SMB_PASSWORD,
    "anonymous": True,
    "source_profiles": {},
}


def load_settings() -> dict[str, object]:
    if not SETTINGS_PATH.exists():
        return DEFAULT_SETTINGS.copy()
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_SETTINGS.copy()
    if not isinstance(data, dict):
        return DEFAULT_SETTINGS.copy()
    settings = DEFAULT_SETTINGS.copy()
    if "smb_share" in data and "endpoint" not in data:
        data["endpoint"] = data["smb_share"]
    settings.update({key: data[key] for key in DEFAULT_SETTINGS if key in data})
    return settings


def save_settings(settings: dict[str, object]) -> None:
    payload = DEFAULT_SETTINGS.copy()
    payload.update(settings)
    SETTINGS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
