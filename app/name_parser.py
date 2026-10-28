from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
import re


KNOWN_FAMILIES = {
    "POS",
    "BOX",
    "SCO",
    "KSO",
    "TBANK",
    "POINDUS",
}

OS_MARKERS = {
    "WIN11",
    "WIN10",
    "WIN7",
    "WIN8",
    "WINXP",
    "WINDOWS",
    "LTSC",
    "IOT",
    "SERVER",
}


@dataclass(slots=True)
class ParsedName:
    display_name: str
    device_family: str
    device_model: str
    cpu_model: str
    os_label: str
    os_display: str
    image_datetime: datetime
    search_blob: str


def parse_image_metadata(filename: str, relative_path: PurePosixPath, modified_at: datetime) -> ParsedName:
    stem = PurePosixPath(filename).stem
    tokens = [token for token in re.split(r"[_\s]+", stem) if token]
    upper_tokens = [token.upper() for token in tokens]
    source_text = " ".join(part.upper() for part in relative_path.parts)

    os_index = _find_os_index(upper_tokens)
    pre_os_tokens = tokens[:os_index] if os_index is not None else tokens
    post_os_tokens = tokens[os_index:] if os_index is not None else []

    device_family, device_model, cpu_model = _parse_device(pre_os_tokens)
    os_label, os_display = _parse_os(source_text, post_os_tokens)
    display_name = _build_display_name(device_family, device_model, cpu_model, os_display)
    image_datetime = modified_at

    blob_parts = [
        stem,
        " ".join(relative_path.parts),
        device_family,
        device_model,
        cpu_model,
        os_label,
        os_display,
        image_datetime.strftime("%Y-%m-%d %H:%M:%S"),
    ]
    search_blob = " ".join(part for part in blob_parts if part).lower()

    return ParsedName(
        display_name=display_name,
        device_family=device_family,
        device_model=device_model,
        cpu_model=cpu_model,
        os_label=os_label,
        os_display=os_display,
        image_datetime=image_datetime,
        search_blob=search_blob,
    )


def _find_os_index(tokens: list[str]) -> int | None:
    for index, token in enumerate(tokens):
        normalized = token.upper()
        if normalized in OS_MARKERS:
            return index
        if re.fullmatch(r"WIN(7|8|10|11|XP).*", normalized):
            return index
        if re.fullmatch(r"\d{4}", normalized) and index > 0 and tokens[index - 1].upper() in {"IOT", "LTSC"}:
            return index - 1
    return None


def _parse_device(tokens: list[str]) -> tuple[str, str, str]:
    if not tokens:
        return "", "", ""

    family = ""
    remaining = tokens[:]
    first_upper = tokens[0].upper()
    if first_upper in KNOWN_FAMILIES:
        family = tokens[0]
        remaining = tokens[1:]
    elif first_upper.startswith("POS"):
        family = "POS"
    elif first_upper.startswith("BOX"):
        family = "BOX"
    elif first_upper.startswith("SCO"):
        family = "SCO"

    cpu_models: list[str] = []
    model_tokens: list[str] = []
    for token in remaining:
        normalized_parts = _split_token_parts(token)
        cpu_parts = [part for part in normalized_parts if _is_cpu_token(part)]
        non_cpu_parts = [part for part in normalized_parts if not _is_cpu_token(part)]

        for cpu in cpu_parts:
            upper_cpu = cpu.upper()
            if upper_cpu not in cpu_models:
                cpu_models.append(upper_cpu)

        if non_cpu_parts:
            model_tokens.append(" ".join(_prettify_token(part) for part in non_cpu_parts))

    cpu_model = " ".join(cpu_models)
    device_model = " ".join(token for token in model_tokens if token).strip()
    if not device_model and remaining:
        device_model = " ".join(_prettify_token(token) for token in remaining).strip()

    return family, device_model, cpu_model


def _parse_os(source_text: str, post_os_tokens: list[str]) -> tuple[str, str]:
    upper_tail = " ".join(token.upper() for token in post_os_tokens)
    combined = f"{source_text} {upper_tail}"

    if re.search(r"\b(WIN11|WINDOWS 11|IOT 2024|24H)\b", combined):
        return "Windows 11", "Windows 11 IoT LTSC 2024"
    if re.search(r"\b(WIN10|W10|WINDOWS 10|LTSC2021|LTSC 2021|IOT 2021|21H)\b", combined):
        return "Windows 10", "Windows 10 IoT LTSC 2021"
    if re.search(r"\b(WIN7|WINDOWS 7)\b", combined):
        return "Windows 7", "Windows 7"
    if re.search(r"\b(WIN8\.1|WINDOWS 8\.1)\b", combined):
        return "Windows 8.1", "Windows 8.1"
    if re.search(r"\b(WIN8|WINDOWS 8)\b", combined):
        return "Windows 8", "Windows 8"
    if re.search(r"\b(XP|WINXP|WINDOWS XP)\b", combined):
        return "Windows XP", "Windows XP"
    return "Other", "Other"


def _build_display_name(device_family: str, device_model: str, cpu_model: str, os_display: str) -> str:
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
    return os_display


def _is_cpu_token(token: str) -> bool:
    upper = token.upper().strip("()[]{}")
    patterns = [
        r"J\d{4,5}[A-Z]*",
        r"N\d{3,4}[A-Z]*",
        r"I[3579][-_]?\d{3,5}[A-Z]*",
        r"A\d[-_]?\d{3,5}",
        r"N[45]\d{3}",
        r"1215U",
        r"1253U",
        r"1315G",
        r"4030",
        r"6360",
        r"8260",
        r"5095",
    ]
    return any(re.fullmatch(pattern, upper) for pattern in patterns)


def _prettify_token(token: str) -> str:
    clean = token.replace("-", " ").strip("()[]{} ").strip()
    if clean.upper() in {"WB", "RST", "AG", "ES"}:
        return clean.upper()
    return clean


def _split_token_parts(token: str) -> list[str]:
    parts = [part for part in re.split(r"[_\s()\[\]{}]+", token) if part]
    return parts or [token]


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
