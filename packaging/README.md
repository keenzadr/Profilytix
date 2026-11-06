# Windows packaging

Use 64-bit Python 3.12 (tested interpreter: 3.12.7) on Windows. The application
is an offline, windowed PySide6 desktop program. A complete one-folder bundle
is required; copying only the EXE will not work.

```powershell
pwsh -File scripts/build_windows.ps1 -InstallDependencies
# Also compile the installer when Inno Setup 6 is installed:
pwsh -File scripts/build_windows.ps1 -Installer -Version 0.1.0
```

The first command creates an isolated `.venv-build` and installs the exact
runtime versions in `packaging/requirements-windows.lock` and build tools in
`requirements-build.txt`. An existing environment can be selected with
`-Python .venv/Scripts/python.exe`. Updating the lock requires rerunning the
application tests and the frozen smoke check. Dependencies must be downloaded
on the build machine or installed from a prepopulated local wheel cache;
the installed application needs no network or Python installation.

Outputs:

- `dist/Profilytix/Profilytix.exe` and its `_internal` dependencies.
- `dist/Profilytix/demo/demo_finances.csv`: deterministic 180-row synthetic
  Russian example. Select this file using the application's open dialog.
- `dist/Profilytix/build-dependencies.txt` and `build-info.json`: build provenance.
- `dist/installer/Profilytix-<version>-Setup.exe` when `-Installer` is used.
- `build/frozen-smoke/smoke-results.json` and five exported reports: smoke evidence.

The script fails if its frozen smoke test fails. This check opens and closes the
Qt window offscreen, loads the bundled demo through pandas and Polars, fits
IsolationForest, renders a chart through Agg and exports all five formats,
including a Cyrillic PDF using bundled DejaVu Sans fonts. It is a dependency
and resource check; complete the interactive checklist in `docs/MANUAL_TESTING.md`
and visually inspect the smoke PDF before distributing a release.

The Inno installer uses `PrivilegesRequired=lowest` and installs only for the
current Windows user under `%LOCALAPPDATA%\Programs\Profilytix`. It creates
Start menu links for the app, offline example and diagnostic logs. Reports,
settings and logs are not removed by the installer. The release is unsigned;
code signing requires a publisher certificate supplied by the project owner.

Startup and uncaught callback errors are written to
`%LOCALAPPDATA%\Profilytix\logs\startup.log` with bounded log rotation. A
Windows error dialog shows the log path. The launcher also supports:

```powershell
Start-Process -FilePath dist/Profilytix/Profilytix.exe -ArgumentList '--smoke-test', 'C:\Temp\Profilytix-smoke' -Wait
```

Only application modules and explicitly selected dependency resources are
collected. The repository's `tests`, `sample_data`, prior reports, virtual
environment, and build directories are never included as data directories.
