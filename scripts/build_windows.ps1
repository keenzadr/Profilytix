<#
.SYNOPSIS
Build the Windows x64 one-folder app and optionally its per-user Inno installer.
.EXAMPLE
pwsh -File scripts/build_windows.ps1 -InstallDependencies -Installer
#>
[CmdletBinding()]
param(
    [string]$Python = "",
    [switch]$InstallDependencies,
    [switch]$Installer,
    [string]$InnoCompiler = "",
    [ValidatePattern('^\d+\.\d+\.\d+([.-][A-Za-z0-9]+)*$')]
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $projectRoot ".venv-build\Scripts\python.exe" }
if (-not (Test-Path -LiteralPath $Python)) {
    if (-not $InstallDependencies) {
        throw "Build Python missing: $Python. Use -InstallDependencies or -Python <existing-python.exe>."
    }
    $existingPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $existingPython) {
        & $existingPython -m venv (Join-Path $projectRoot ".venv-build")
    } else {
        & py -3.12 -m venv (Join-Path $projectRoot ".venv-build")
    }
    if ($LASTEXITCODE -ne 0) { throw "Could not create the Python 3.12 build environment." }
}
$Python = (Resolve-Path -LiteralPath $Python).Path
& $Python -c "import sys,struct; assert sys.version_info >= (3,12), 'Python 3.12+ required'; assert struct.calcsize('P') == 8, '64-bit Python required'"
if ($LASTEXITCODE -ne 0) { throw "Unsupported build interpreter." }

Push-Location $projectRoot
try {
    if ($InstallDependencies) {
        & $Python -m pip install -r packaging/requirements-windows.lock -r requirements-build.txt
        if ($LASTEXITCODE -ne 0) { throw "Build dependencies could not be installed." }
    }
    & $Python -c "import PyInstaller; assert PyInstaller.__version__ == '6.16.0', 'Use requirements-build.txt'"
    if ($LASTEXITCODE -ne 0) { throw "Pinned PyInstaller missing. Install requirements-build.txt." }
    $generatedRoot = Join-Path $projectRoot "build\generated"
    $demoFile = Join-Path $generatedRoot "demo\demo_finances.csv"
    & $Python packaging/generate_demo.py $demoFile
    if ($LASTEXITCODE -ne 0) { throw "Offline demo generation failed." }
    & $Python -m PyInstaller --noconfirm --clean --distpath dist --workpath build/pyinstaller packaging/Profilytix.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

    # Expose a visible copy next to the EXE as well as the internal smoke resource.
    $visibleDemo = Join-Path $projectRoot "dist\Profilytix\demo"
    New-Item -ItemType Directory -Path $visibleDemo -Force | Out-Null
    Copy-Item -LiteralPath $demoFile -Destination $visibleDemo -Force
    & $Python -m pip freeze | Set-Content -LiteralPath "dist\Profilytix\build-dependencies.txt" -Encoding UTF8
    & $Python -c "import json,platform,sys; print(json.dumps({'version':sys.argv[1], 'python':sys.version, 'platform':platform.platform()}, indent=2))" $Version |
        Set-Content -LiteralPath "dist\Profilytix\build-info.json" -Encoding UTF8

    $smokeDirectory = Join-Path $projectRoot "build\frozen-smoke"
    $smokeResult = Join-Path $smokeDirectory "smoke-results.json"
    if (Test-Path -LiteralPath $smokeResult) { Remove-Item -LiteralPath $smokeResult }
    # Windowed EXEs require Start-Process -Wait to obtain a reliable exit code.
    $executable = Join-Path $projectRoot "dist\Profilytix\Profilytix.exe"
    $smokeProcess = Start-Process -FilePath $executable -ArgumentList @("--smoke-test", ('"' + $smokeDirectory + '"')) -Wait -PassThru -WindowStyle Hidden
    if ($smokeProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $smokeResult)) {
        throw "Frozen smoke test failed. See %LOCALAPPDATA%\Profilytix\logs\startup.log."
    }
    $smokeEvidence = Get-Content -LiteralPath $smokeResult -Raw | ConvertFrom-Json
    if ($smokeEvidence.status -ne "passed" -or -not $smokeEvidence.frozen) {
        throw "Frozen smoke test did not confirm a packaged application."
    }
    Write-Host "Frozen smoke test passed: Qt, demo, Polars, IsolationForest, PDF/font/chart and five exports."

    if ($Installer) {
        if (-not $InnoCompiler) {
            $innoCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
            if ($innoCommand) { $InnoCompiler = $innoCommand.Source }
        }
        if (-not $InnoCompiler) {
            $innoCandidates = @(
                "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
                "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
                "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
            )
            $InnoCompiler = $innoCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        }
        if (-not $InnoCompiler -or -not (Test-Path -LiteralPath $InnoCompiler)) {
            throw "Inno Setup 6 ISCC.exe missing. Install it or pass -InnoCompiler <path>. EXE bundle is ready."
        }
        & $InnoCompiler "/DAppVersion=$Version" "/DSourceRoot=$projectRoot" "packaging\Profilytix.iss"
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed." }
    }
    Write-Host "Build complete: $projectRoot\dist\Profilytix"
} finally {
    Pop-Location
}
