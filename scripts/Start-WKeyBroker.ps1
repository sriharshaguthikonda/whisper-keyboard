param(
    [int]$Seconds = 0,
    [switch]$SkipBuild,
    [switch]$SkipStopExisting
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$BrokerManifest = Join-Path $RepoRoot "native\wkey-broker\Cargo.toml"
$BrokerExe = Join-Path $RepoRoot "native\wkey-broker\target\release\wkey-broker.exe"
$BackendHealthPath = Join-Path $RepoRoot "wkey\backend_health_status.json"
$RuntimeLockPath = Join-Path $RepoRoot "wkey\wkey_runtime.lock"
$LogDir = Join-Path $RepoRoot "logs"
$LogPath = Join-Path $LogDir "wkey-broker-startup.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-LauncherLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date).ToString("s"), $Message
    Write-Host $line
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
}

function Test-BrokerBuildStale {
    if (-not (Test-Path -LiteralPath $BrokerExe)) {
        return $true
    }
    $exeTime = (Get-Item -LiteralPath $BrokerExe).LastWriteTimeUtc
    $inputs = @(
        Get-Item -LiteralPath $BrokerManifest
        Get-Item -LiteralPath (Join-Path $RepoRoot "native\wkey-broker\Cargo.lock")
        Get-ChildItem -LiteralPath (Join-Path $RepoRoot "native\wkey-broker\src") -Filter "*.rs" -Recurse
    )
    return [bool]($inputs | Where-Object { $_.LastWriteTimeUtc -gt $exeTime } | Select-Object -First 1)
}

function Build-BrokerIfNeeded {
    if ($SkipBuild) {
        if (-not (Test-Path -LiteralPath $BrokerExe)) {
            throw "Broker exe missing and -SkipBuild was set: $BrokerExe"
        }
        return
    }

    if (-not (Test-BrokerBuildStale)) {
        Write-LauncherLog "Broker build current: $BrokerExe"
        return
    }

    $cargo = Get-Command cargo -ErrorAction SilentlyContinue
    if (-not $cargo) {
        throw "cargo.exe not found on PATH; cannot build $BrokerExe"
    }

    Write-LauncherLog "Building broker release binary..."
    Push-Location $RepoRoot
    try {
        & $cargo.Source build --manifest-path $BrokerManifest --release
        if ($LASTEXITCODE -ne 0) {
            throw "cargo build failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

function Stop-ExistingWKeyProcesses {
    if ($SkipStopExisting) {
        return
    }

    $targets = @()
    if (Test-Path -LiteralPath $BackendHealthPath) {
        try {
            $health = Get-Content -LiteralPath $BackendHealthPath -Raw | ConvertFrom-Json
            $healthPid = [int]$health.pid
            $healthProc = Get-CimInstance Win32_Process -Filter "ProcessId=$healthPid" -ErrorAction SilentlyContinue
            if ($healthProc -and $healthProc.Name -in @("python.exe", "pythonw.exe")) {
                $targets += $healthProc
                $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($healthProc.ParentProcessId)" -ErrorAction SilentlyContinue
                if ($parent -and $parent.Name -in @("python.exe", "pythonw.exe") -and $parent.ProcessId -ne $PID) {
                    $targets += $parent
                }
            }
        }
        catch {
            Write-LauncherLog "Backend health PID scan unavailable: $($_.Exception.Message)"
        }
    }

    try {
        $targets += Get-CimInstance Win32_Process |
            Where-Object {
                $_.ProcessId -ne $PID -and
                $_.CommandLine -and
                (
                    ($_.Name -in @("python.exe", "pythonw.exe") -and $_.CommandLine -like "*faster_whisper_Mother_of_all_wkey.py*") -or
                    $_.Name -eq "wkey-broker.exe" -or
                    ($_.Name -eq "cmd.exe" -and $_.CommandLine -like "*$BrokerExe*")
                )
            }
    }
    catch {
        Write-LauncherLog "Process command-line scan unavailable: $($_.Exception.Message)"
    }

    $stoppedPids = @()
    foreach ($proc in ($targets | Sort-Object ProcessId -Unique)) {
        Write-LauncherLog "Stopping old WKEY process PID $($proc.ProcessId): $($proc.Name)"
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 250
        if (Get-Process -Id $proc.ProcessId -ErrorAction SilentlyContinue) {
            Write-LauncherLog "Force-killing old WKEY process tree PID $($proc.ProcessId)"
            & taskkill.exe /PID $proc.ProcessId /T /F | Out-Null
        }
        $stoppedPids += [int]$proc.ProcessId
    }

    if (-not $targets) {
        Get-Process -Name "wkey-broker" -ErrorAction SilentlyContinue |
            Where-Object { $_.Id -ne $PID } |
            ForEach-Object {
                Write-LauncherLog "Stopping old WKEY broker PID $($_.Id)"
                Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
                $stoppedPids += [int]$_.Id
            }
    }

    foreach ($pidToWait in ($stoppedPids | Sort-Object -Unique)) {
        for ($attempt = 0; $attempt -lt 20; $attempt++) {
            if (-not (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue)) {
                break
            }
            Start-Sleep -Milliseconds 250
        }
    }

    if (Test-Path -LiteralPath $RuntimeLockPath) {
        for ($attempt = 0; $attempt -lt 20; $attempt++) {
            try {
                Remove-Item -LiteralPath $RuntimeLockPath -Force
                Write-LauncherLog "Removed stale runtime lock: $RuntimeLockPath"
                break
            }
            catch {
                if ($attempt -eq 19) {
                    Write-LauncherLog "Runtime lock remains locked after cleanup: $($_.Exception.Message)"
                }
                else {
                    Start-Sleep -Milliseconds 250
                }
            }
        }
    }
}

function Quote-CmdArg {
    param([string]$Value)
    return '"' + ($Value -replace '"', '\"') + '"'
}

if (-not (Test-Path -LiteralPath $BrokerManifest)) {
    throw "Broker manifest not found: $BrokerManifest"
}

Build-BrokerIfNeeded
Stop-ExistingWKeyProcesses

$brokerArgs = @("--run")
if ($Seconds -gt 0) {
    $brokerArgs += @("--seconds", [string]$Seconds)
}

$env:PYTHONUNBUFFERED = "1"
Write-LauncherLog "Starting broker: $BrokerExe $($brokerArgs -join ' ')"

Push-Location $RepoRoot
try {
    $brokerCommand = @(
        Quote-CmdArg $BrokerExe
        ($brokerArgs | ForEach-Object { Quote-CmdArg $_ })
        ">>"
        Quote-CmdArg $LogPath
        "2>&1"
    ) -join " "
    & $env:ComSpec /d /c $brokerCommand
    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

Write-LauncherLog "Broker exited with code $exitCode"
exit $exitCode
