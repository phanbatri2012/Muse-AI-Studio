param(
    [string]$PythonExe = "python",
    [switch]$SkipInstaller,
    [switch]$Obfuscate   # bật PyArmor obfuscation trước khi build
)

$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "build_windows.ps1 must run on Windows."
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BuildAssetsRoot = Join-Path $ProjectRoot "build-assets\\windows"
$BuildBinRoot = Join-Path $BuildAssetsRoot "bin"
$PrereqRoot = Join-Path $BuildAssetsRoot "prereqs"
$VcRedistPath = Join-Path $PrereqRoot "VC_redist.x64.exe"
$VcRedistUrl = "https://aka.ms/vc14/vc_redist.x64.exe"
$InstallerScript = Join-Path $ProjectRoot "installer\\windows\\muse_ai_studio.iss"
$SpecFile = Join-Path $ProjectRoot "Muse_AI_Studio.spec"
$RequirementsFile = Join-Path $ProjectRoot "requirements-windows.txt"
$BuildVenv = Join-Path $ProjectRoot ".venv-winbuild"

if ($PythonExe -eq "python" -and (Test-Path (Join-Path $ProjectRoot ".venv\\Scripts\\python.exe"))) {
    $PythonExe = Join-Path $ProjectRoot ".venv\\Scripts\\python.exe"
}

New-Item -ItemType Directory -Force -Path $BuildBinRoot | Out-Null
New-Item -ItemType Directory -Force -Path $PrereqRoot | Out-Null

Write-Host "==> Preparing build virtualenv"
if (-not (Test-Path (Join-Path $BuildVenv "Scripts\\python.exe"))) {
    & $PythonExe -m venv $BuildVenv
}
$VenvPython = Join-Path $BuildVenv "Scripts\\python.exe"
$VenvPip = Join-Path $BuildVenv "Scripts\\pip.exe"

& $VenvPip install -r $RequirementsFile

$StageMediaScript = @'
from pathlib import Path
import os
import shutil

from runtime_media import resolve_ffmpeg_executable, resolve_ffprobe_executable

project_root = Path(r"__PROJECT_ROOT__")
bin_root = project_root / "build-assets" / "windows" / "bin"
bin_root.mkdir(parents=True, exist_ok=True)

ffmpeg_src = resolve_ffmpeg_executable()
if not ffmpeg_src:
    raise SystemExit("Cannot locate ffmpeg for packaging.")
shutil.copy2(ffmpeg_src, bin_root / "ffmpeg.exe")

ffprobe_src = resolve_ffprobe_executable()
if ffprobe_src and Path(ffprobe_src).is_file():
    shutil.copy2(ffprobe_src, bin_root / "ffprobe.exe")
else:
    print("WARNING: ffprobe.exe not found. QC features will rely on fallback behavior.")
'@.Replace("__PROJECT_ROOT__", $ProjectRoot.Replace("\", "\\"))

Write-Host "==> Staging bundled media tools"
Push-Location $ProjectRoot
try {
    & $VenvPython -c $StageMediaScript
}
finally {
    Pop-Location
}

# ---- Bước tùy chọn: PyArmor obfuscation (dùng -Obfuscate khi build release) ----
$ObfDir = Join-Path $ProjectRoot "dist_obf"
$ObfBackups = @{}
if ($Obfuscate) {
    Write-Host "==> Installing PyArmor"
    & $VenvPip install pyarmor | Out-Null

    Write-Host "==> Obfuscating source files with PyArmor"
    $FilesToObf = @("License.py", "branding_config.py", "runtime_paths.py")
    Push-Location $ProjectRoot
    try {
        & $VenvPython -m pyarmor gen --output $ObfDir $FilesToObf
    } finally { Pop-Location }

    # Thay thế file gốc bằng file obfuscated (backup trước)
    foreach ($f in $FilesToObf) {
        $src = Join-Path $ProjectRoot $f
        $obf = Join-Path $ObfDir $f
        if (Test-Path $obf) {
            $bak = "$src.build_bak"
            Copy-Item $src $bak -Force
            $ObfBackups[$src] = $bak
            Copy-Item $obf $src -Force
            Write-Host "    Replaced: $f"
        }
    }
    # Copy pyarmor_runtime vào project root để PyInstaller gói vào EXE
    $RuntimeSrc = Join-Path $ObfDir "pyarmor_runtime_000000"
    if (Test-Path $RuntimeSrc) {
        Copy-Item $RuntimeSrc (Join-Path $ProjectRoot "pyarmor_runtime_000000") -Recurse -Force
    }
}

Write-Host "==> Building PyInstaller bundle"
Push-Location $ProjectRoot
try {
    & $VenvPython -m PyInstaller --noconfirm --clean $SpecFile
}
finally {
    Pop-Location
    # Khôi phục file gốc sau khi build xong
    if ($Obfuscate) {
        foreach ($entry in $ObfBackups.GetEnumerator()) {
            Move-Item $entry.Value $entry.Key -Force
        }
        $rtDir = Join-Path $ProjectRoot "pyarmor_runtime_000000"
        if (Test-Path $rtDir) { Remove-Item $rtDir -Recurse -Force }
        if (Test-Path $ObfDir) { Remove-Item $ObfDir -Recurse -Force }
        Write-Host "==> Restored original sources"
    }
}

if (-not (Test-Path $VcRedistPath)) {
    Write-Host "==> Downloading Microsoft Visual C++ Redistributable (x64)"
    try {
        Invoke-WebRequest -Uri $VcRedistUrl -OutFile $VcRedistPath
    }
    catch {
        throw "Cannot stage VC_redist.x64.exe from $VcRedistUrl. Download it manually and place it at build-assets\\windows\\prereqs\\VC_redist.x64.exe."
    }
}

if ($SkipInstaller) {
    Write-Host "==> Skipping installer compilation as requested"
    exit 0
}

function Resolve-Iscc {
    $command = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        "${env:ProgramFiles(x86)}\\Inno Setup 6\\ISCC.exe",
        "${env:ProgramFiles}\\Inno Setup 6\\ISCC.exe",
        "${env:LOCALAPPDATA}\\Programs\\Inno Setup 6\\ISCC.exe"
    )
    # Thử tìm theo mẫu đường dẫn trong LocalAppData nếu Antigravity IDE cài ở user khác
    if ($env:LOCALAPPDATA) {
        $ideCandidate = Join-Path $env:LOCALAPPDATA "Programs\\Antigravity IDE\\resources\\app\\node_modules\\innosetup\\bin\\ISCC.exe"
        $candidates += $ideCandidate
    }

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }
    return $null
}

function Ensure-Iscc {
    $resolved = Resolve-Iscc
    if ($resolved) {
        return $resolved
    }

    Write-Host "==> Inno Setup not found, attempting automatic install"
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($winget) {
        try {
            & $winget.Source install --id JRSoftware.InnoSetup -e --accept-package-agreements --accept-source-agreements --silent
        }
        catch {
            Write-Host "WARNING: winget install failed: $($_.Exception.Message)"
        }
    }
    else {
        $choco = Get-Command choco.exe -ErrorAction SilentlyContinue
        if ($choco) {
            try {
                & $choco.Source install innosetup --no-progress -y
            }
            catch {
                Write-Host "WARNING: choco install failed: $($_.Exception.Message)"
            }
        }
    }

    return (Resolve-Iscc)
}

Push-Location $ProjectRoot
try {
    $rawVersion = & $VenvPython -c "from branding_config import APP_VERSION; print(APP_VERSION)"
    $AppVersion = $rawVersion.Trim().TrimStart('v','V')
    if (-not $AppVersion) { $AppVersion = "1.0.0" }
}
finally {
    Pop-Location
}
$IsccExe = Ensure-Iscc
if (-not $IsccExe) {
    throw "Cannot find ISCC.exe. Install Inno Setup 6, then rerun scripts/build_windows.ps1."
}

Write-Host "==> Building Setup.exe with Inno Setup"
& $IsccExe "/DMyAppVersion=$AppVersion" $InstallerScript

Write-Host "==> Windows package is ready in dist-installer\\Muse_AI_Studio_Setup.exe"
