from __future__ import annotations

from pathlib import Path, PurePosixPath
import re

from .config import DEST_ROOT_NAME
from .metadata_service import apply_override, load_overrides
from .models import ImageEntry
from .name_parser import parse_image_metadata
from .source_service import SourceConfig, list_source_files


def scan_images(config: SourceConfig, cached: bool = False) -> list[ImageEntry]:
    from .catalog_service import load_catalog, save_catalog
    files = load_catalog(config) if cached else list_source_files(config)
    if not cached:
        save_catalog(config, files)
    items: list[ImageEntry] = []
    overrides = load_overrides()

    for source_file in files:
        relative_path = source_file.relative_path
        source_group = _source_group(relative_path)
        parsed = parse_image_metadata(source_file.name, relative_path, source_file.modified_at)
        entry = ImageEntry(
            source_protocol=source_file.protocol,
            source_root=source_file.root,
            source_endpoint=source_file.endpoint,
            source_locator=source_file.locator,
            source_name=source_file.name,
            relative_path=relative_path,
            size=source_file.size,
            extension=PurePosixPath(source_file.name).suffix.lower(),
            source_group=source_group,
            os_label=parsed.os_label,
            display_name=parsed.display_name,
            device_family=parsed.device_family,
            device_model=parsed.device_model,
            cpu_model=parsed.cpu_model,
            os_display=parsed.os_display,
            image_datetime=parsed.image_datetime,
            search_blob=parsed.search_blob,
        )
        override = overrides.get(entry.source_key)
        if override:
            apply_override(entry, override)
        items.append(entry)
    return items


def _source_group(relative_path: PurePosixPath) -> str:
    parts = relative_path.parts[:-1]
    if not parts:
        return "ROOT"
    return parts[0]


def safe_segment(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "_", value).strip().rstrip(".")
    return cleaned or "unnamed"


def build_target_path(target_root: Path, entry: ImageEntry) -> Path:
    type_folder = classify_target_folder(entry)
    return target_root.joinpath(DEST_ROOT_NAME, safe_segment(type_folder), entry.source_name)


def classify_target_folder(entry: ImageEntry) -> str:
    family = entry.device_family.strip().upper()
    if family == "BOX":
        return "POSPC"
    if family in {"POS", "KSO", "SCO", "TBANK", "POINDUS"}:
        return family
    if entry.source_group and entry.source_group != "ROOT":
        return entry.source_group
    return "OTHER"
