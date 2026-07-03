param(
    [string]$TaskName = "Whisper",
    [switch]$RunAfterInstall
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$Launcher = Join-Path $RepoRoot "Start-WKeyBroker.bat"
$LauncherArguments = "--log"

if (-not (Test-Path -LiteralPath $Launcher)) {
    throw "Broker launcher not found: $Launcher"
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
    $command = [System.Security.SecurityElement]::Escape($Launcher)
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
    <EventTrigger>
      <Enabled>true</Enabled>
      <Subscription>&lt;QueryList&gt;&lt;Query Id="0" Path="System"&gt;&lt;Select Path="System"&gt;*[System[Provider[@Name='Microsoft-Windows-Power-Troubleshooter'] and EventID=1]]&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;</Subscription>
      <Delay>PT30S</Delay>
    </EventTrigger>
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
    <MultipleInstancesPolicy>StopExisting</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>true</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <IdleSettings>
      <StopOnIdleEnd>true</StopOnIdleEnd>
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
if ($exportedXml -notlike "*Start-WKeyBroker.bat*" -or $exportedXml -notlike "*--log*") {
    throw "Scheduled task XML verification failed for $TaskName"
}

$task = Get-ScheduledTask -TaskName $TaskName -TaskPath "\" -ErrorAction Stop
$task.Actions | Select-Object Execute,Arguments,WorkingDirectory | Format-List

if ($RunAfterInstall) {
    Start-ScheduledTask -TaskName $TaskName -TaskPath "\" -ErrorAction Stop
    Write-Host "Started scheduled task \$TaskName"
}
