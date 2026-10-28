from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from ..metadata_service import DEFAULT_OS_CHOICES, build_standardized_filename
from ..models import ImageEntry


class MetadataDialog(QDialog):
    def __init__(self, entry: ImageEntry, parent=None) -> None:
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle("Редактирование метаданных")
        self.resize(560, 260)

        self.family_edit = QLineEdit(entry.device_family)
        self.model_edit = QLineEdit(entry.device_model)
        self.cpu_edit = QLineEdit(entry.cpu_model)
        self.os_combo = QComboBox()
        self.os_combo.setEditable(True)
        self.os_combo.addItems(DEFAULT_OS_CHOICES)
        self.os_combo.setCurrentText(entry.os_display)
        self.preview_label = QLabel(build_standardized_filename(entry))
        self.preview_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Семейство", self.family_edit)
        form.addRow("Модель", self.model_edit)
        form.addRow("CPU", self.cpu_edit)
        form.addRow("ОС", self.os_combo)
        form.addRow("Новое имя", self.preview_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(entry.source_name))
        layout.addLayout(form)
        layout.addWidget(buttons)

        self.family_edit.textChanged.connect(self.update_preview)
        self.model_edit.textChanged.connect(self.update_preview)
        self.cpu_edit.textChanged.connect(self.update_preview)
        self.os_combo.currentTextChanged.connect(self.update_preview)

    def values(self) -> dict[str, str]:
        return {
            "device_family": self.family_edit.text().strip(),
            "device_model": self.model_edit.text().strip(),
            "cpu_model": self.cpu_edit.text().strip(),
            "os_display": self.os_combo.currentText().strip(),
        }

    def update_preview(self) -> None:
        preview_entry = ImageEntry(
            source_protocol=self.entry.source_protocol,
            source_root=self.entry.source_root,
            source_endpoint=self.entry.source_endpoint,
            source_locator=self.entry.source_locator,
            source_name=self.entry.source_name,
            relative_path=self.entry.relative_path,
            size=self.entry.size,
            extension=self.entry.extension,
            source_group=self.entry.source_group,
            os_label=self.entry.os_label,
            display_name=self.entry.display_name,
            device_family=self.family_edit.text().strip(),
            device_model=self.model_edit.text().strip(),
            cpu_model=self.cpu_edit.text().strip(),
            os_display=self.os_combo.currentText().strip(),
            image_datetime=self.entry.image_datetime,
            search_blob=self.entry.search_blob,
        )
        self.preview_label.setText(build_standardized_filename(preview_entry))
