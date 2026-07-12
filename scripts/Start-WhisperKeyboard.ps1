param([switch]$Console)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$EntryPoint = Join-Path $RepoRoot "wkey\faster_whisper_Mother_of_all_wkey.py"
$RuntimeDir = if ($env:WKEY_RUNTIME_DIR) { $env:WKEY_RUNTIME_DIR } else { Join-Path $env:LOCALAPPDATA "WhisperKeyboard\runtime" }
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
$env:WKEY_RUNTIME_DIR = $RuntimeDir
$env:WKEY_INPUT_OWNER = "python"
$env:PYTHONUNBUFFERED = "1"

$Python = $env:WKEY_PYTHON
if ([string]::IsNullOrWhiteSpace($Python)) {
    $venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    $Python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { (Get-Command python.exe -ErrorAction Stop).Source }
}
if (-not (Test-Path -LiteralPath $EntryPoint)) { throw "Backend entry point not found: $EntryPoint" }

Push-Location $RepoRoot
try {
    if ($Console) {
        & $Python $EntryPoint
    } else {
        $LogPath = Join-Path $RuntimeDir "whisper-keyboard-startup.log"
        & $Python $EntryPoint *>> $LogPath
    }
    exit $(if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE })
} finally {
    Pop-Location
}
