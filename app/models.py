from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath


@dataclass(slots=True)
class ImageEntry:
    source_protocol: str
    source_root: str
    source_endpoint: str
    source_locator: str
    source_name: str
    relative_path: PurePosixPath
    size: int
    extension: str
    source_group: str
    os_label: str
    display_name: str
    device_family: str
    device_model: str
    cpu_model: str
    os_display: str
    image_datetime: datetime
    search_blob: str

    @property
    def stem(self) -> str:
        return PurePosixPath(self.source_name).stem

    @property
    def source_key(self) -> str:
        return f"{self.source_protocol}|{self.source_endpoint}|{self.source_root}|{self.relative_path.as_posix()}"


@dataclass(slots=True)
class DriveInfo:
    root: Path
    label: str
    free_bytes: int
    total_bytes: int
    drive_type: str
    is_ventoy: bool = False

    @property
    def display_name(self) -> str:
        label = f" [{self.label}]" if self.label else ""
        ventoy = " [Ventoy]" if self.is_ventoy else ""
        return f"{self.root.drive.rstrip(':')}:\\{label}{ventoy} ({self.drive_type}, {format_bytes(self.free_bytes)} free)"


def format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"
