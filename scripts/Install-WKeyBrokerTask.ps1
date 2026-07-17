# File name is legacy (from the retired Rust wkey-broker). It installs the
# direct-python scheduled task (scripts\Start-WhisperKeyboard.ps1, hidden) —
# the broker is retired; input ownership is Kanata (F23/F24) -> Python pynput.
param(
    [string]$TaskName = "Whisper",
    [switch]$RunAfterInstall
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$Launcher = Join-Path $ScriptDir "Start-WhisperKeyboard.ps1"
$LauncherArguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $Launcher + '"'

if (-not (Test-Path -LiteralPath $Launcher)) {
    throw "Python launcher not found: $Launcher"
}

function New-WKeyBrokerTaskXml {
    param(
        [string]$TaskName,
        [string]$Launcher,
        [string]$LauncherArguments
    )

    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $userName = [System.Security.SecurityElement]::Escape($identity.Name)
    $sid = [System.Security.SecurityElement]::Escape($identity.User.Value)
    $command = [System.Security.SecurityElement]::Escape("powershell.exe")
    $arguments = [System.Security.SecurityElement]::Escape($LauncherArguments)
    $author = $userName
    $now = (Get-Date).ToString("s")
    $uri = [System.Security.SecurityElement]::Escape("\$TaskName")

    return @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Date>$now</Date>
    <Author>$author</Author>
    <URI>$uri</URI>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>$userName</UserId>
      <Delay>PT1M</Delay>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$sid</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <DisallowStartOnRemoteAppSession>false</DisallowStartOnRemoteAppSession>
    <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$command</Command>
      <Arguments>$arguments</Arguments>
    </Exec>
  </Actions>
</Task>
"@
}

$existing = Get-ScheduledTask -TaskName $TaskName -TaskPath "\" -ErrorAction SilentlyContinue
$xml = New-WKeyBrokerTaskXml -TaskName $TaskName -Launcher $Launcher -LauncherArguments $LauncherArguments
Register-ScheduledTask -TaskName $TaskName -TaskPath "\" -Xml $xml -Force -ErrorAction Stop | Out-Null

if ($existing) {
    Write-Host "Reconciled scheduled task \$TaskName -> $Launcher $LauncherArguments"
}
else {
    Write-Host "Created scheduled task \$TaskName -> $Launcher $LauncherArguments"
}

$exportedXml = Export-ScheduledTask -TaskName $TaskName -TaskPath "\" -ErrorAction Stop
if ($exportedXml -notlike "*Start-WhisperKeyboard.ps1*" -or
    $exportedXml -notlike "*IgnoreNew*" -or
    $exportedXml -notlike "*-WindowStyle Hidden*" -or
    $exportedXml -like "*-Console*" -or
    $exportedXml -like "*EventTrigger*") {
    throw "Scheduled task XML verification failed for $TaskName"
}

$task = Get-ScheduledTask -TaskName $TaskName -TaskPath "\" -ErrorAction Stop
$task.Actions | Select-Object Execute,Arguments,WorkingDirectory | Format-List

if ($RunAfterInstall) {
    Start-ScheduledTask -TaskName $TaskName -TaskPath "\" -ErrorAction Stop
    Write-Host "Started scheduled task \$TaskName"
}
