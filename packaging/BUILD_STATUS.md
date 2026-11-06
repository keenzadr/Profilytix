# Packaging verification — 2026-11-06

Environment: Windows x64, CPython 3.12.7 in `.venv`.

- Packaging unit/integration checks: `3 passed` using
  `.venv/Scripts/python.exe -m pytest tests/test_packaging.py -q --basetemp=.pytest-tmp-packaging`.
- PowerShell build script parsed without errors using the PowerShell AST parser.
- PyInstaller spec parsed without Python syntax errors.
- Source smoke check: Qt window constructed and closed offscreen; synthetic
  180-row Russian CSV loaded through pandas and Polars; IsolationForest fitted;
  Agg chart and all five exports generated, including Cyrillic PDF/font loading.

**No Windows bundle or installer was produced in this environment.**

PyInstaller and its hooks are not installed and no cached wheel is available.
Attempted `.venv/Scripts/python.exe -m pip install pyinstaller==6.16.0` failed
after DNS retries: `Failed to resolve 'pypi.org' ([Errno 11001] getaddrinfo failed)`.
Pip consequently reported `No matching distribution found for pyinstaller==6.16.0`;
this reflects the inaccessible package index, not a determination that the
requested version does not exist.

Inno Setup's `ISCC.exe` was absent from PATH and the checked installation paths
under Program Files, Program Files (x86), and the user's Local Programs directory.

The source checks do not verify PyInstaller dependency discovery or the installer.
On a Windows build machine with those tools available, run
`scripts/build_windows.ps1 -InstallDependencies -Installer`; this must finish the
frozen smoke check before an installer is compiled. Complete the interactive
manual checks and visually inspect the generated Cyrillic PDF before release.
