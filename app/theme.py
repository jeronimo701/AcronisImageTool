from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#111318"))
    palette.setColor(QPalette.WindowText, QColor("#f3f6fb"))
    palette.setColor(QPalette.Base, QColor("#0d1015"))
    palette.setColor(QPalette.AlternateBase, QColor("#151922"))
    palette.setColor(QPalette.ToolTipBase, QColor("#1d2230"))
    palette.setColor(QPalette.ToolTipText, QColor("#f3f6fb"))
    palette.setColor(QPalette.Text, QColor("#f3f6fb"))
    palette.setColor(QPalette.Button, QColor("#1a1f2b"))
    palette.setColor(QPalette.ButtonText, QColor("#f3f6fb"))
    palette.setColor(QPalette.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.Highlight, QColor("#18c5d8"))
    palette.setColor(QPalette.HighlightedText, QColor("#0b1116"))
    app.setPalette(palette)

    app.setStyleSheet(
        """
        QWidget {
            font-size: 11pt;
        }
        QTableWidget, QPlainTextEdit, QLineEdit, QComboBox {
            border: 1px solid #243042;
            background: #0d1015;
        }
        QPushButton {
            background: #1a1f2b;
            border: 1px solid #243042;
            padding: 8px 12px;
        }
        QPushButton:hover {
            background: #232a38;
        }
        QPushButton:disabled {
            color: #677487;
        }
        QHeaderView::section {
            background: #171d27;
            border: 0;
            border-bottom: 1px solid #243042;
            padding: 6px;
        }
        QProgressBar {
            border: 1px solid #243042;
            text-align: center;
            background: #0d1015;
            min-height: 18px;
        }
        QProgressBar::chunk {
            background: #18c5d8;
        }
        """
    )
