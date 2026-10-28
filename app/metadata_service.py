from __future__ import annotations

import json
import re

from .config import OVERRIDES_PATH
from .models import ImageEntry


DEFAULT_OS_CHOICES = [
    "Windows 11 IoT LTSC 2024",
    "Windows 10 IoT LTSC 2021",
    "Windows 7",
    "Windows 8.1",
    "Windows 8",
    "Windows XP",
    "Other",
]


def load_overrides() -> dict[str, dict[str, str]]:
    if not OVERRIDES_PATH.exists():
        return {}
    try:
        data = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(data, dict):
        return {str(key): value for key, value in data.items() if isinstance(value, dict)}
    return {}


def save_overrides(overrides: dict[str, dict[str, str]]) -> None:
    OVERRIDES_PATH.write_text(
        json.dumps(overrides, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def apply_override(entry: ImageEntry, override: dict[str, str]) -> None:
    family = override.get("device_family", entry.device_family).strip()
    model = override.get("device_model", entry.device_model).strip()
    cpu = override.get("cpu_model", entry.cpu_model).strip()
    os_display = override.get("os_display", entry.os_display).strip() or "Other"

    entry.device_family = family
    entry.device_model = model
    entry.cpu_model = cpu
    entry.os_display = os_display
    entry.os_label = os_label_from_display(os_display)
    entry.display_name = build_display_name(family, model, cpu, os_display)
    entry.search_blob = build_search_blob(entry)


def build_display_name(device_family: str, device_model: str, cpu_model: str, os_display: str) -> str:
    family = device_family.strip()
    model = _strip_duplicate_family_prefix(device_model, family)
    left_parts = [part for part in [family, model] if part]
    left = " ".join(left_parts).strip()
    if cpu_model:
        left = f"{left} ({cpu_model})".strip()
    if left and os_display and os_display != "Other":
        return f"{left} - {os_display}"
    if left:
        return left
    return os_display or "Unnamed"


def build_search_blob(entry: ImageEntry) -> str:
    parts = [
        entry.stem,
        " ".join(entry.relative_path.parts),
        entry.device_family,
        entry.device_model,
        entry.cpu_model,
        entry.os_label,
        entry.os_display,
        entry.display_name,
        entry.image_datetime.strftime("%Y-%m-%d %H:%M:%S"),
    ]
    return " ".join(part for part in parts if part).lower()


def os_label_from_display(os_display: str) -> str:
    upper = os_display.upper()
    if "WINDOWS 11" in upper:
        return "Windows 11"
    if "WINDOWS 10" in upper:
        return "Windows 10"
    if "WINDOWS 8.1" in upper:
        return "Windows 8.1"
    if "WINDOWS 8" in upper:
        return "Windows 8"
    if "WINDOWS 7" in upper:
        return "Windows 7"
    if "XP" in upper:
        return "Windows XP"
    return "Other"


def build_standardized_filename(entry: ImageEntry) -> str:
    parts: list[str] = []
    family_norm = _norm(entry.device_family) if entry.device_family else ""
    model_norm = _norm(entry.device_model) if entry.device_model else ""

    if family_norm and not _model_already_has_family_prefix(model_norm, family_norm):
        parts.append(family_norm)
    if model_norm:
        parts.append(model_norm)
    if entry.cpu_model:
        parts.append(_norm(entry.cpu_model))
    if entry.os_display:
        parts.append(_norm(os_token_from_display(entry.os_display)))
    filename = "_".join(part for part in parts if part)
    return f"{filename or 'IMAGE'}{entry.extension}"


def os_token_from_display(os_display: str) -> str:
    mapping = {
        "Windows 11 IoT LTSC 2024": "WIN11_LTSC_IOT_2024",
        "Windows 10 IoT LTSC 2021": "WIN10_LTSC_IOT_2021",
        "Windows 7": "WIN7",
        "Windows 8.1": "WIN8_1",
        "Windows 8": "WIN8",
        "Windows XP": "WINXP",
        "Other": "OTHER",
    }
    return mapping.get(os_display, _norm(os_display))


def move_override_key(overrides: dict[str, dict[str, str]], old_key: str, new_key: str) -> None:
    if old_key == new_key or old_key not in overrides:
        return
    overrides[new_key] = overrides.pop(old_key)


def _norm(value: str) -> str:
    text = re.sub(r"[()]+", " ", value)
    text = re.sub(r"[^A-Za-z0-9]+", "_", text.strip())
    text = re.sub(r"_+", "_", text).strip("_")
    return text.upper()


def _model_already_has_family_prefix(model_norm: str, family_norm: str) -> bool:
    if not model_norm or not family_norm:
        return False
    return model_norm == family_norm or model_norm.startswith(family_norm)


def _strip_duplicate_family_prefix(device_model: str, device_family: str) -> str:
    model = device_model.strip()
    family = device_family.strip()
    if not model or not family:
        return model
    if model.upper() == family.upper():
        return model
    if model.upper().startswith(family.upper()):
        tail = model[len(family):].lstrip(" _-")
        if tail:
            return tail
    return model
