from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .models import ImageEntry
from .scanner import build_target_path
from .source_service import SourceConfig, TransferCancelled, copy_source_file


@dataclass(slots=True)
class SyncRequest:
    source_config: SourceConfig
    target_root: Path
    items: list[ImageEntry]


class SyncWorker(QObject):
    log = Signal(str)
    item_started = Signal(int, str)
    item_progress = Signal(object, object)
    total_progress = Signal(object, object)
    item_finished = Signal(int, str)
    finished = Signal(dict)

    def __init__(self, request: SyncRequest) -> None:
        super().__init__()
        self.request = request
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        self.log.emit("Остановка поставлена в очередь...")

    def run(self) -> None:
        copied = 0
        skipped = 0
        failed = 0
        total_bytes = sum(item.size for item in self.request.items)
        done_bytes = 0
        self.total_progress.emit(0, total_bytes)

        for index, item in enumerate(self.request.items):
            if self._cancelled:
                break

            self.item_started.emit(index, item.source_name)
            target_path = build_target_path(self.request.target_root, item)
            target_path.parent.mkdir(parents=True, exist_ok=True)

            if target_path.exists() and target_path.stat().st_size == item.size:
                skipped += 1
                done_bytes += item.size
                self.item_progress.emit(item.size, item.size)
                self.total_progress.emit(done_bytes, total_bytes)
                self.item_finished.emit(index, "Уже есть")
                self.log.emit(f"Пропуск: {target_path}")
                continue

            try:
                copy_source_file(
                    item_to_source_file(item),
                    self.request.source_config,
                    target_path,
                    lambda done, total: self._emit_progress(done_bytes, done, total_bytes, total),
                    lambda: self._cancelled,
                )
                copied += 1
                done_bytes += item.size
                self.item_finished.emit(index, "Скопирован")
                self.log.emit(f"Скопирован: {target_path}")
            except TransferCancelled:
                failed += 1
                self.item_finished.emit(index, "Остановлено")
                self.log.emit("Копирование остановлено пользователем.")
                break
            except Exception as exc:
                failed += 1
                self.item_finished.emit(index, f"Ошибка: {exc}")
                self.log.emit(f"Ошибка для {item.source_name}: {exc}")

        self.finished.emit(
            {
                "copied": copied,
                "skipped": skipped,
                "failed": failed,
                "cancelled": self._cancelled,
            }
        )

    def _emit_progress(self, done_bytes_before: int, item_done: int, total_bytes: int, item_total: int) -> None:
        self.item_progress.emit(item_done, item_total)
        self.total_progress.emit(done_bytes_before + item_done, total_bytes)


def item_to_source_file(item: ImageEntry):
    from .source_service import SourceFile

    return SourceFile(
        protocol=item.source_protocol,
        endpoint=item.source_endpoint,
        root=item.source_root,
        relative_path=item.relative_path,
        locator=item.source_locator,
        name=item.source_name,
        size=item.size,
        modified_at=item.image_datetime,
    )
