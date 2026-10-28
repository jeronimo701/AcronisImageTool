$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
  python -m PyInstaller --noconfirm --clean --onedir --windowed --name AcronisImageTool --icon assets/jeronimo701_icon.ico --add-data "assets;assets" --add-data "packaging/notices;notices" main.py
  if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
  foreach ($name in @("README.md", "LICENSE.txt", "LICENSE-SCOPE.md", "THIRD-PARTY.md")) {
    Copy-Item -LiteralPath $name -Destination "dist/AcronisImageTool/$name" -Force
  }
  Copy-Item -LiteralPath "assets" -Destination "dist/AcronisImageTool/assets" -Recurse -Force
} finally { Pop-Location }
