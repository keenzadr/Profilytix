# Build with scripts/build_windows.ps1; no project/customer data is collected.
from pathlib import Path

import matplotlib
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

root = Path(SPECPATH).parent
generated = root / "build" / "generated" / "demo" / "demo_finances.csv"
if not generated.is_file():
    raise RuntimeError("Generate the offline demo first: use scripts/build_windows.ps1")

datas = [(str(generated), "demo")]
datas += collect_data_files("matplotlib", excludes=["mpl-data/sample_data/**", "**/tests/**"])
datas += collect_data_files("reportlab")
datas += collect_data_files("openpyxl")
datas += collect_data_files("xlrd")
datas += collect_data_files("polars")
# PDF export resolves these through matplotlib.get_data_path(). Fail early if missing.
for font in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
    source = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / font
    if not source.is_file():
        raise RuntimeError(f"Required Cyrillic PDF font missing: {source}")
    datas.append((str(source), "matplotlib/mpl-data/fonts/ttf"))

hiddenimports = [
    "matplotlib.backends.backend_agg",
    "matplotlib.backends.backend_qtagg",
    "pandas.io.excel._openpyxl",
    "pandas.io.excel._xlrd",
    "sklearn.ensemble._iforest",
    "openpyxl",
    "xlrd",
]
# Polars chooses its binary runtime dynamically, outside static import analysis.
hiddenimports += collect_submodules("_polars_runtime_32")
binaries = collect_dynamic_libs("polars") + collect_dynamic_libs("_polars_runtime_32")

a = Analysis(
    [str(root / "packaging" / "launcher.py")],
    pathex=[str(root), str(root / "packaging")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={"matplotlib": {"backends": ["QtAgg", "Agg"]}},
    runtime_hooks=[],
    excludes=["pytest", "IPython", "notebook", "tkinter", "PyQt5", "PyQt6", "PySide2"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Profilytix",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Profilytix")
