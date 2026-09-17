<#
.SYNOPSIS
  Register (or replace) the Windows scheduled task that pushes new parsivel
  rows to the AWS dashboard twice a day.

.DESCRIPTION
  Creates a task named "Parsivel dashboard sync" that runs
  backend\scripts\sync_to_aws.py with the repo's virtualenv Python at the
  given times, appending output to backend\logs\sync.log. The task runs
  whether or not you are logged on, so it asks for your Windows password once.

  Settings for the sync itself live in backend\.sync.env (see .sync.env.example).

.EXAMPLE
  cd <repo>\backend
  powershell -ExecutionPolicy Bypass -File scripts\register_sync_task.ps1

.EXAMPLE
  # custom times (24h, local) and a different Python
  powershell -ExecutionPolicy Bypass -File scripts\register_sync_task.ps1 -Times 05:30,17:30 -Python C:\Python312\python.exe

.EXAMPLE
  # also run once about two minutes after every boot (no login needed)
  powershell -ExecutionPolicy Bypass -File scripts\register_sync_task.ps1 -AtStartup
#>
[CmdletBinding()]
param(
    [string[]]$Times = @("06:00", "18:00"),
    [string]$Python = "",
    [string]$TaskName = "Parsivel dashboard sync",
    [switch]$AtStartup,
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"

$backendDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $backendDir "scripts\sync_to_aws.py"
$envFile = Join-Path $backendDir ".sync.env"
$logDir = Join-Path $backendDir "logs"
$logFile = Join-Path $logDir "sync.log"

if ($Unregister) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed task '$TaskName'."
    exit 0
}

if (-not $Python) {
    $Python = Join-Path $backendDir ".venv\Scripts\python.exe"
}
if (-not (Test-Path $Python)) { throw "Python not found at $Python (use -Python)" }
if (-not (Test-Path $script)) { throw "sync script not found at $script" }
if (-not (Test-Path $envFile)) { throw "settings file not found at $envFile (copy .sync.env.example)" }
New-Item -ItemType Directory -Force $logDir | Out-Null

# Lock the .pem key down to the current user, or OpenSSH refuses to use it.
$keyLine = Get-Content $envFile | Where-Object { $_ -match '^\s*PARSIVEL_SSH_KEY\s*=' } | Select-Object -First 1
if ($keyLine) {
    $keyPath = ($keyLine -split "=", 2)[1].Trim().Trim('"').Trim("'")
    if (Test-Path $keyPath) {
        icacls $keyPath /inheritance:r /grant:r "$($env:USERNAME):R" | Out-Null
        Write-Host "Restricted permissions on $keyPath"
    } else {
        Write-Warning "PARSIVEL_SSH_KEY points to $keyPath which does not exist"
    }
}

# cmd /c so stdout+stderr append to the log file.
$cmdLine = "/c `"`"$Python`" `"$script`" --env-file `"$envFile`" >> `"$logFile`" 2>&1`""
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $cmdLine -WorkingDirectory $backendDir

$triggers = @(foreach ($t in $Times) { New-ScheduledTaskTrigger -Daily -At $t })
if ($AtStartup) {
    $boot = New-ScheduledTaskTrigger -AtStartup
    $boot.Delay = "PT2M"   # give the network a moment before reaching SQL Server and AWS
    $triggers += $boot
}

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3) `
    -MultipleInstances IgnoreNew `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 30)

$cred = Get-Credential -UserName "$env:USERDOMAIN\$env:USERNAME" `
    -Message "Windows password for the account that will run the sync task"

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $triggers `
    -Settings $settings `
    -User $cred.UserName `
    -Password $cred.GetNetworkCredential().Password `
    -RunLevel Limited `
    -Force | Out-Null

$when = "$($Times -join ', ') daily"
if ($AtStartup) { $when += ", and 2 minutes after each boot" }
Write-Host "Registered '$TaskName' at $when."
Write-Host "Log: $logFile"
Write-Host "Run it now with:  Start-ScheduledTask -TaskName '$TaskName'"
