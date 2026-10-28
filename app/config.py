from pathlib import Path
import sys

APP_NAME = "Acronis Image Tool"
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
SMB_SHARE = ""
SMB_USERNAME = ""
SMB_PASSWORD = ""
SOURCE_ROOT = ""
DEST_ROOT_NAME = "Acronis"
OVERRIDES_PATH = PROJECT_ROOT / "metadata_overrides.json"
SETTINGS_PATH = PROJECT_ROOT / "app_settings.json"
APP_ICON_ICO = PROJECT_ROOT / "assets" / "jeronimo701_icon.ico"
APP_ICON_PNG = PROJECT_ROOT / "assets" / "jeronimo701_icon.png"
SUPPORTED_EXTENSIONS = {".tib", ".tibx"}
COPY_CHUNK_SIZE = 8 * 1024 * 1024

# Папки, которые считаем служебными и не показываем как часть логики назначения.
IGNORED_DIR_NAMES = {"System Volume Information", "$RECYCLE.BIN"}
