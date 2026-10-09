# PyInstaller configuration for the portable Windows executable.
# Build with: pyinstaller excel_translator.spec --noconfirm
from pathlib import Path

project_dir = Path(SPECPATH)

a = Analysis(
    [str(project_dir / "app.py")],
    pathex=[str(project_dir)],
    datas=[
        (str(project_dir / "assets" / "feather.png"), "assets"),
        (str(project_dir / "templates" / "index.html"), "templates"),
    ],
    hiddenimports=["xlrd", "openpyxl", "pandas", "usage_tracker", "flask"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="ExcelTranslator",
    console=False,
    icon=None,
)
