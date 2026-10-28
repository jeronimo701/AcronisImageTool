from __future__ import annotations

from pathlib import Path
from typing import Any
import winsound

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config import APP_ICON_ICO, APP_ICON_PNG, APP_NAME
from ..drive_service import list_target_drives
from ..metadata_service import (
    apply_override,
    build_standardized_filename,
    load_overrides,
    move_override_key,
    save_overrides,
)
from ..models import DriveInfo, ImageEntry, format_bytes
from ..scanner import build_target_path, scan_images
from ..scan_worker import ScanThread
from ..web_source import WEB_ENDPOINT, WEB_FOLDER
from ..settings_service import load_settings, save_settings
from ..source_service import SourceConfig, rename_source_file
from ..sync_worker import SyncRequest, SyncWorker
from ..theme import apply_dark_theme
from .metadata_dialog import MetadataDialog


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1680, 960)
        self._apply_window_icon()

        self.settings = load_settings()
        self.source_profiles = dict(self.settings.get("source_profiles", {}))
        self.active_protocol = str(self.settings["protocol"])
        self.loaded_source_config = None
        self.scan_thread = None
        self.images: list[ImageEntry] = []
        self.entry_by_key: dict[str, ImageEntry] = {}
        self.drives: list[DriveInfo] = []
        self.selected_rows_for_sync: list[int] = []
        self.thread: QThread | None = None
        self.worker: SyncWorker | None = None

        self.protocol_combo = QComboBox()
        self.protocol_combo.addItem("SMB", "smb")
        self.protocol_combo.addItem("FTP", "ftp")
        self.protocol_combo.addItem("Web / HTTPS", "web")
        self.protocol_combo.setCurrentIndex(self.protocol_combo.findData(self.settings["protocol"]))

        self.source_edit = QLineEdit(str(self.settings["source_root"]))
        self.endpoint_edit = QLineEdit(str(self.settings["endpoint"]))
        self.username_edit = QLineEdit(str(self.settings["username"]))
        self.password_edit = QLineEdit(str(self.settings["password"]))
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.anonymous_box = QCheckBox("Анонимно")
        self.anonymous_box.setChecked(bool(self.settings["anonymous"]))

        self.rescan_button = QPushButton("Пересканировать")
        self.cached_button = QPushButton("Сохранённый каталог")
        self.drive_combo = QComboBox()
        self.refresh_drives_button = QPushButton("Обновить флешки")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск: модель, процессор, ОС, год, имя файла...")
        self.os_filter_combo = QComboBox()
        self.family_filter_combo = QComboBox()
        self.cpu_filter_combo = QComboBox()
        self.select_all_box = QCheckBox("Выбрать все")
        self.edit_button = QPushButton("Дополнить")
        self.rename_button = QPushButton("Переименовать")
        self.copy_button = QPushButton("Скачать на флешку")
        self.cancel_button = QPushButton("Стоп")
        self.cancel_button.setEnabled(False)

        self.summary_label = QLabel("Нет данных")
        self.space_label = QLabel("")
        self.item_progress = QProgressBar()
        self.total_progress = QProgressBar()
        self._init_progress_bar(self.item_progress)
        self._init_progress_bar(self.total_progress)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["", "Устройство", "Процессор", "ОС", "Дата образа", "Исходная папка", "Размер", "На флешке", "Цель"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSortingEnabled(True)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)

        self._build_ui()
        self._wire_events()
        self._sync_auth_controls()
        self._sync_protocol_placeholders()
        self.refresh_drives()
        if self.current_protocol() == "web":
            from ..catalog_service import catalog_path
            self.refresh_images(cached=catalog_path(self.current_source_config()).exists())
        else:
            self.refresh_images()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        top = QGridLayout()
        top.addWidget(QLabel("Протокол"), 0, 0)
        top.addWidget(self.protocol_combo, 0, 1)
        top.addWidget(QLabel("Источник"), 0, 2)
        top.addWidget(self.source_edit, 0, 3, 1, 3)
        top.addWidget(self.rescan_button, 0, 6)
        top.addWidget(self.cached_button, 1, 6)
        top.addWidget(QLabel("Подключение"), 1, 0)
        top.addWidget(self.endpoint_edit, 1, 1, 1, 3)
        top.addWidget(self.anonymous_box, 1, 4)
        top.addWidget(QLabel("Логин"), 2, 0)
        top.addWidget(self.username_edit, 2, 1)
        top.addWidget(QLabel("Пароль"), 2, 2)
        top.addWidget(self.password_edit, 2, 3)
        top.addWidget(QLabel("Флешка"), 3, 0)
        top.addWidget(self.drive_combo, 3, 1, 1, 5)
        top.addWidget(self.refresh_drives_button, 3, 6)
        top.addWidget(QLabel("Поиск"), 4, 0)
        top.addWidget(self.search_edit, 4, 1, 1, 6)
        top.addWidget(QLabel("ОС"), 5, 0)
        top.addWidget(self.os_filter_combo, 5, 1)
        top.addWidget(QLabel("Семейство"), 5, 2)
        top.addWidget(self.family_filter_combo, 5, 3)
        top.addWidget(QLabel("CPU"), 5, 4)
        top.addWidget(self.cpu_filter_combo, 5, 5)
        layout.addLayout(top)

        actions = QHBoxLayout()
        actions.addWidget(self.select_all_box)
        actions.addWidget(self.edit_button)
        actions.addWidget(self.rename_button)
        actions.addStretch(1)
        actions.addWidget(self.summary_label)
        actions.addSpacing(16)
        actions.addWidget(self.space_label)
        actions.addStretch(1)
        actions.addWidget(self.copy_button)
        actions.addWidget(self.cancel_button)
        layout.addLayout(actions)

        layout.addWidget(self.table, 1)
        layout.addWidget(QLabel("Текущий файл"))
        layout.addWidget(self.item_progress)
        layout.addWidget(QLabel("Общий прогресс"))
        layout.addWidget(self.total_progress)
        layout.addWidget(QLabel("Журнал"))
        layout.addWidget(self.log_output, 1)

    def _apply_window_icon(self) -> None:
        for candidate in (APP_ICON_ICO, APP_ICON_PNG):
            if candidate.exists():
                self.setWindowIcon(QIcon(str(candidate)))
                break

    def _wire_events(self) -> None:
        self.protocol_combo.currentIndexChanged.connect(self._on_protocol_changed)
        self.anonymous_box.toggled.connect(self._sync_auth_controls)
        self.rescan_button.clicked.connect(self.refresh_images)
        self.cached_button.clicked.connect(lambda: self.refresh_images(cached=True))
        self.refresh_drives_button.clicked.connect(self.refresh_drives)
        self.search_edit.textChanged.connect(self.apply_filter)
        self.os_filter_combo.currentIndexChanged.connect(self.apply_filter)
        self.family_filter_combo.currentIndexChanged.connect(self.apply_filter)
        self.cpu_filter_combo.currentIndexChanged.connect(self.apply_filter)
        self.select_all_box.toggled.connect(self.toggle_all)
        self.edit_button.clicked.connect(self.edit_selected_entry)
        self.rename_button.clicked.connect(self.rename_selected_entry)
        self.copy_button.clicked.connect(self.start_sync)
        self.cancel_button.clicked.connect(self.cancel_sync)
        self.drive_combo.currentIndexChanged.connect(self.update_drive_view)

    def _on_protocol_changed(self) -> None:
        previous = self.current_source_config()
        self.source_profiles[self.active_protocol] = {
            "source_root": previous.root, "endpoint": previous.endpoint,
            "username": previous.username, "password": previous.password,
            "anonymous": self.anonymous_box.isChecked(),
        }
        self.active_protocol = self.current_protocol()
        defaults = {"endpoint": "", "source_root": "/", "username": "", "password": "", "anonymous": False}
        if self.active_protocol == "web":
            defaults.update(endpoint=WEB_ENDPOINT, source_root=WEB_FOLDER, anonymous=True)
        profile = self.source_profiles.get(self.active_protocol, defaults)
        self.endpoint_edit.setText(str(profile["endpoint"]))
        self.source_edit.setText(str(profile["source_root"]))
        self.username_edit.setText(str(profile["username"]))
        self.password_edit.setText(str(profile["password"]))
        self.anonymous_box.setChecked(bool(profile["anonymous"]))
        self._sync_protocol_placeholders()
        self._sync_auth_controls()
        self.persist_settings()

    def _sync_protocol_placeholders(self) -> None:
        if self.current_protocol() == "web":
            self.endpoint_edit.setPlaceholderText(WEB_ENDPOINT)
            self.source_edit.setPlaceholderText("Ссылка на каталог или путь папки")
        elif self.current_protocol() == "ftp":
            self.endpoint_edit.setPlaceholderText("ftp.example.local:21")
            self.source_edit.setPlaceholderText("/share/_IMAGES/ACR_IMAGES")
        else:
            self.endpoint_edit.setPlaceholderText(r"\\server\share")
            self.source_edit.setPlaceholderText(r"\\server\share\_IMAGES\ACR_IMAGES")

    def _sync_auth_controls(self) -> None:
        anonymous = self.anonymous_box.isChecked() or self.current_protocol() == "web"
        self.anonymous_box.setEnabled(self.current_protocol() != "web")
        self.username_edit.setEnabled(not anonymous)
        self.password_edit.setEnabled(not anonymous)

    def current_protocol(self) -> str:
        return str(self.protocol_combo.currentData())

    def current_source_config(self) -> SourceConfig:
        return SourceConfig(
            protocol=self.current_protocol(),
            endpoint=self.endpoint_edit.text().strip(),
            root=self.source_edit.text().strip(),
            username=self.username_edit.text().strip(),
            password=self.password_edit.text(),
            anonymous=self.anonymous_box.isChecked() or self.current_protocol() == "web",
        )

    def persist_settings(self) -> None:
        self.source_profiles[self.current_protocol()] = {
            "source_root": self.source_edit.text().strip(), "endpoint": self.endpoint_edit.text().strip(),
            "username": self.username_edit.text().strip(), "password": self.password_edit.text(),
            "anonymous": self.anonymous_box.isChecked(),
        }
        self.settings = {
            "source_profiles": self.source_profiles,
            "protocol": self.current_protocol(),
            "source_root": self.source_edit.text().strip(),
            "endpoint": self.endpoint_edit.text().strip(),
            "username": self.username_edit.text().strip(),
            "password": self.password_edit.text(),
            "anonymous": self.anonymous_box.isChecked(),
        }
        save_settings(self.settings)

    def refresh_images(self, _checked=False, *, cached=False) -> None:
        if self.scan_thread is not None or self.thread is not None:
            return
        self.persist_settings()
        config = self.current_source_config()
        self.scan_thread = ScanThread(config, cached, self)
        self.scan_thread.loaded.connect(self._catalog_loaded)
        self.scan_thread.failed.connect(self._catalog_failed)
        self.scan_thread.finished.connect(self._scan_finished)
        self.rescan_button.setEnabled(False)
        self.cached_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.rename_button.setEnabled(False)
        self.edit_button.setEnabled(False)
        self.log("Чтение сохранённого каталога..." if cached else "Проверка источника и обновление каталога...")
        self.scan_thread.start()

    def _catalog_loaded(self, images, config) -> None:
        self.images = images
        self.loaded_source_config = config
        self.entry_by_key = {entry.source_key: entry for entry in self.images}
        self.populate_filter_values()
        self.populate_table()
        self.log(f"Сканирование завершено. Найдено образов: {len(self.images)}")

    def _catalog_failed(self, message) -> None:
        self.log(f"Ошибка чтения источника: {message}")
        QMessageBox.warning(self, APP_NAME, message)

    def _scan_finished(self) -> None:
        thread = self.scan_thread
        self.scan_thread = None
        thread.deleteLater()
        self.rescan_button.setEnabled(True)
        self.cached_button.setEnabled(True)
        self.copy_button.setEnabled(True)
        self.edit_button.setEnabled(True)
        self.rename_button.setEnabled(self.loaded_source_config is not None and self.loaded_source_config.protocol != "web")

    def closeEvent(self, event) -> None:
        if self.scan_thread is not None or self.thread is not None:
            event.ignore()
            return
        self.persist_settings()
        super().closeEvent(event)

    def refresh_drives(self) -> None:
        self.drives = list_target_drives()
        self.drive_combo.clear()
        for drive in self.drives:
            self.drive_combo.addItem(drive.display_name, drive)
        if not self.drives:
            self.space_label.setText("Флешки не найдены")
            self.log("Не найдено подходящих дисков для назначения.")
            return
        self.update_drive_view()

    def populate_filter_values(self) -> None:
        self._fill_combo(self.os_filter_combo, sorted({entry.os_display for entry in self.images if entry.os_display}))
        self._fill_combo(self.family_filter_combo, sorted({entry.device_family for entry in self.images if entry.device_family}))
        self._fill_combo(self.cpu_filter_combo, sorted({part for entry in self.images for part in entry.cpu_model.split() if part}))

    def populate_table(self) -> None:
        drive = self.current_drive()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.images))
        for row, entry in enumerate(self.images):
            checkbox = QCheckBox()
            checkbox.toggled.connect(self.update_summary)
            wrapper = QWidget()
            box = QHBoxLayout(wrapper)
            box.setContentsMargins(8, 0, 0, 0)
            box.addWidget(checkbox)
            box.addStretch(1)
            self.table.setCellWidget(row, 0, wrapper)

            name_item = QTableWidgetItem(entry.display_name)
            name_item.setData(Qt.UserRole, entry.source_key)
            self.table.setItem(row, 1, name_item)
            self.table.setItem(row, 2, QTableWidgetItem(entry.cpu_model or "-"))
            self.table.setItem(row, 3, QTableWidgetItem(entry.os_display))
            self.table.setItem(row, 4, QTableWidgetItem(entry.image_datetime.strftime("%d.%m.%Y %H:%M")))
            self.table.setItem(row, 5, QTableWidgetItem(entry.source_group))
            self.table.setItem(row, 6, QTableWidgetItem(format_bytes(entry.size)))
            self.table.setItem(row, 7, QTableWidgetItem(self._presence_text(entry, drive)))
            self.table.setItem(row, 8, QTableWidgetItem(str(build_target_path(drive.root, entry)) if drive else "-"))

        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)
        self.apply_filter()
        self.update_summary()

    def update_drive_view(self) -> None:
        drive = self.current_drive()
        if drive is None:
            self.space_label.setText("Флешка не выбрана")
            return
        self.space_label.setText(f"Свободно: {format_bytes(drive.free_bytes)}")
        for row in range(self.table.rowCount()):
            entry = self.entry_for_row(row)
            if entry is None:
                continue
            self.table.item(row, 7).setText(self._presence_text(entry, drive))
            self.table.item(row, 8).setText(str(build_target_path(drive.root, entry)))

    def toggle_all(self, checked: bool) -> None:
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            checkbox = self.row_checkbox(row)
            if checkbox is not None:
                checkbox.setChecked(checked)
        self.update_summary()

    def edit_selected_entry(self) -> None:
        entry = self.current_entry()
        if entry is None:
            QMessageBox.information(self, APP_NAME, "Сначала выберите образ в таблице.")
            return
        dialog = MetadataDialog(entry, self)
        if not dialog.exec():
            return
        override = dialog.values()
        overrides = load_overrides()
        overrides[entry.source_key] = override
        save_overrides(overrides)
        apply_override(entry, override)
        self.log(f"Сохранены ручные правки: {entry.source_name}")
        self.refresh_images()

    def rename_selected_entry(self) -> None:
        entry = self.current_entry()
        if entry is None:
            QMessageBox.information(self, APP_NAME, "Сначала выберите образ в таблице.")
            return

        self.persist_settings()
        config = self.loaded_source_config
        new_name = build_standardized_filename(entry)
        if new_name == entry.source_name:
            QMessageBox.information(self, APP_NAME, "Файл уже имеет стандартизированное имя.")
            return

        answer = QMessageBox.question(
            self,
            APP_NAME,
            f"Переименовать файл?\n\n{entry.source_name}\n->\n{new_name}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            rename_source_file(source_file_from_entry(entry), config, new_name)
            overrides = load_overrides()
            old_key = entry.source_key
            new_rel = entry.relative_path.with_name(new_name)
            new_key = f"{entry.source_protocol}|{entry.source_endpoint}|{entry.source_root}|{new_rel.as_posix()}"
            move_override_key(overrides, old_key, new_key)
            save_overrides(overrides)
            self.log(f"Файл переименован: {entry.source_name} -> {new_name}")
            self.refresh_images()
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, f"Не удалось переименовать файл:\n{exc}")
            self.log(f"Ошибка переименования {entry.source_name}: {exc}")

    def start_sync(self) -> None:
        drive = self.current_drive()
        if drive is None:
            QMessageBox.warning(self, APP_NAME, "Не выбрана флешка.")
            return
        selected = self.selected_entries()
        if not selected:
            QMessageBox.warning(self, APP_NAME, "Не выбраны образы.")
            return

        bytes_to_copy = self._bytes_to_copy(selected, drive)
        if bytes_to_copy > drive.free_bytes:
            QMessageBox.warning(
                self,
                APP_NAME,
                f"Недостаточно места.\nНужно: {format_bytes(bytes_to_copy)}\nСвободно: {format_bytes(drive.free_bytes)}",
            )
            return

        self.persist_settings()
        request = SyncRequest(source_config=self.loaded_source_config, target_root=drive.root, items=selected)
        self.selected_rows_for_sync = [
            row for row in range(self.table.rowCount())
            if not self.table.isRowHidden(row) and (self.row_checkbox(row).isChecked() if self.row_checkbox(row) else False)
        ]

        self.thread = QThread(self)
        self.worker = SyncWorker(request)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.log)
        self.worker.item_started.connect(self.on_item_started)
        self.worker.item_progress.connect(self.on_item_progress)
        self.worker.total_progress.connect(self.on_total_progress)
        self.worker.item_finished.connect(self.on_item_finished)
        self.worker.finished.connect(self.on_finished)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)

        self.copy_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.rescan_button.setEnabled(False)
        self.refresh_drives_button.setEnabled(False)
        self.edit_button.setEnabled(False)
        self.rename_button.setEnabled(False)
        self.cached_button.setEnabled(False)
        self.table.setSortingEnabled(False)
        self.thread.start()
        self.log(f"Запуск копирования. Выбрано: {len(selected)}")

    def cancel_sync(self) -> None:
        if self.worker is not None:
            self.worker.cancel()

    def on_item_started(self, _: int, name: str) -> None:
        self.item_progress.setValue(0)
        self.item_progress.setFormat(f"{name} - 0%")

    def on_item_progress(self, done: object, total: object) -> None:
        self._set_progress(self.item_progress, int(done), int(total))

    def on_total_progress(self, done: object, total: object) -> None:
        self._set_progress(self.total_progress, int(done), int(total))

    def on_item_finished(self, row_index: int, status: str) -> None:
        if row_index < len(self.selected_rows_for_sync):
            row_index = self.selected_rows_for_sync[row_index]
        if 0 <= row_index < self.table.rowCount():
            item = self.table.item(row_index, 7)
            if item is not None:
                item.setText(status)

    def on_finished(self, summary: dict[str, Any]) -> None:
        self.copy_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.rescan_button.setEnabled(True)
        self.refresh_drives_button.setEnabled(True)
        self.edit_button.setEnabled(True)
        self.rename_button.setEnabled(self.loaded_source_config is not None and self.loaded_source_config.protocol != "web")
        self.cached_button.setEnabled(True)
        self.table.setSortingEnabled(True)
        self.refresh_drives()

        text = f"Готово. Скопировано: {summary['copied']}, пропущено: {summary['skipped']}, ошибок: {summary['failed']}"
        if summary.get("cancelled"):
            text += ", операция остановлена."
        self.log(text)
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
        QMessageBox.information(self, APP_NAME, text)

        self.thread = None
        self.worker = None

    def selected_entries(self) -> list[ImageEntry]:
        entries: list[ImageEntry] = []
        for row in range(self.table.rowCount()):
            checkbox = self.row_checkbox(row)
            entry = self.entry_for_row(row)
            if entry is not None and checkbox is not None and checkbox.isChecked() and not self.table.isRowHidden(row):
                entries.append(entry)
        return entries

    def row_checkbox(self, row: int) -> QCheckBox | None:
        wrapper = self.table.cellWidget(row, 0)
        return None if wrapper is None else wrapper.findChild(QCheckBox)

    def current_drive(self) -> DriveInfo | None:
        index = self.drive_combo.currentIndex()
        return None if index < 0 else self.drive_combo.currentData()

    def current_entry(self) -> ImageEntry | None:
        row = self.table.currentRow()
        return None if row < 0 else self.entry_for_row(row)

    def entry_for_row(self, row: int) -> ImageEntry | None:
        item = self.table.item(row, 1)
        if item is None:
            return None
        key = item.data(Qt.UserRole)
        return None if not key else self.entry_by_key.get(str(key))

    def update_summary(self, *_: object, visible_override: int | None = None) -> None:
        selected = self.selected_entries()
        total_size = sum(item.size for item in selected)
        visible = visible_override if visible_override is not None else sum(
            1 for row in range(self.table.rowCount()) if not self.table.isRowHidden(row)
        )
        self.summary_label.setText(f"Показано: {visible} / {len(self.images)} | Выбрано: {len(selected)} ({format_bytes(total_size)})")

    def apply_filter(self) -> None:
        query = self.search_edit.text().strip().lower()
        os_filter = self.os_filter_combo.currentData()
        family_filter = self.family_filter_combo.currentData()
        cpu_filter = self.cpu_filter_combo.currentData()
        visible = 0
        for row in range(self.table.rowCount()):
            entry = self.entry_for_row(row)
            if entry is None:
                self.table.setRowHidden(row, True)
                continue
            match = True
            if query and query not in entry.search_blob:
                match = False
            if os_filter and entry.os_display != os_filter:
                match = False
            if family_filter and entry.device_family != family_filter:
                match = False
            if cpu_filter and cpu_filter not in entry.cpu_model.split():
                match = False
            self.table.setRowHidden(row, not match)
            if match:
                visible += 1
        self.update_summary(visible_override=visible)

    def log(self, message: str) -> None:
        self.log_output.appendPlainText(message)

    def _presence_text(self, entry: ImageEntry, drive: DriveInfo | None) -> str:
        if drive is None:
            return "-"
        target_path = build_target_path(drive.root, entry)
        if not target_path.exists():
            return "Нет"
        if target_path.stat().st_size == entry.size:
            return "Есть"
        return "Размер отличается"

    def _bytes_to_copy(self, entries: list[ImageEntry], drive: DriveInfo) -> int:
        total = 0
        for entry in entries:
            target_path = build_target_path(drive.root, entry)
            if target_path.exists() and target_path.stat().st_size == entry.size:
                continue
            total += entry.size
        return total

    @staticmethod
    def _init_progress_bar(bar: QProgressBar) -> None:
        bar.setMinimum(0)
        bar.setMaximum(1000)
        bar.setValue(0)

    @staticmethod
    def _set_progress(bar: QProgressBar, done: int, total: int) -> None:
        total = max(total, 1)
        scaled = int(done * 1000 / total)
        percent = done * 100.0 / total
        bar.setMaximum(1000)
        bar.setValue(min(max(scaled, 0), 1000))
        bar.setFormat(f"{format_bytes(done)} / {format_bytes(total)} ({percent:.1f}%)")

    @staticmethod
    def _fill_combo(combo: QComboBox, values: list[str]) -> None:
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Все", None)
        for value in values:
            combo.addItem(value, value)
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)


def source_file_from_entry(entry: ImageEntry):
    from ..source_service import SourceFile

    return SourceFile(
        protocol=entry.source_protocol,
        endpoint=entry.source_endpoint,
        root=entry.source_root,
        relative_path=entry.relative_path,
        locator=entry.source_locator,
        name=entry.source_name,
        size=entry.size,
        modified_at=entry.image_datetime,
    )


def run() -> int:
    app = QApplication.instance() or QApplication([])
    apply_dark_theme(app)
    for candidate in (APP_ICON_ICO, APP_ICON_PNG):
        if candidate.exists():
            app.setWindowIcon(QIcon(str(candidate)))
            break
    window = MainWindow()
    window.show()
    return app.exec()
