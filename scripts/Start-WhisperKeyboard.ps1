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
    # Prefer a project venv that actually has the deps. The real one lives beside
    # the repo at <parent>\openai\Scripts\python.exe (same as the old broker used).
    $candidates = @(
        (Join-Path $RepoRoot ".venv\Scripts\python.exe"),
        (Join-Path (Split-Path -Parent $RepoRoot) "openai\Scripts\python.exe")
    )
    $Python = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $Python) {
        # Bare PATH python only if it actually imports the app deps (avoid a silent
        # ModuleNotFoundError crash-and-vanish).
        $onPath = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
        if ($onPath) { & $onPath -c "import groq" 2>$null; if ($LASTEXITCODE -eq 0) { $Python = $onPath } }
    }
    if (-not $Python) {
        throw "No Python with app dependencies found. Set WKEY_PYTHON, or create the venv at $((Join-Path (Split-Path -Parent $RepoRoot) 'openai\Scripts\python.exe'))."
    }
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
