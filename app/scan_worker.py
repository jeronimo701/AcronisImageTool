from PySide6.QtCore import QThread, Signal

from .scanner import scan_images


class ScanThread(QThread):
    loaded = Signal(object, object)
    failed = Signal(str)

    def __init__(self, config, cached=False, parent=None):
        super().__init__(parent)
        self.config = config
        self.cached = cached

    def run(self):
        try:
            self.loaded.emit(scan_images(self.config, cached=self.cached), self.config)
        except Exception as exc:
            self.failed.emit(str(exc))
