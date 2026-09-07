<#
    Register the clip worker to start with Windows.

    The page that queues videos lives on Railway; the worker that actually
    downloads and cuts them runs here, because YouTube refuses datacenter
    addresses. A browser cannot start a process on this machine, so the next
    best thing is for the worker to already be running whenever the page is
    opened: a scheduled task at logon, restarted if it ever falls over.

    Install:    powershell -ExecutionPolicy Bypass -File install-autostart.ps1
    Remove:     powershell -ExecutionPolicy Bypass -File install-autostart.ps1 -Uninstall
#>
param([switch]$Uninstall)

$TaskName = "ClipGenerator Worker"

if ($Uninstall) {
    try {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
        Write-Host "Arranque automatico desinstalado."
    } catch {
        Write-Host "No habia nada instalado con el nombre '$TaskName'."
    }
    return
}

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $here "run_local_worker.py"

if (-not (Test-Path $script)) { throw "No encuentro run_local_worker.py en $here" }

# pythonw runs without a console window, so the worker does not leave a black
# box sitting on the desktop all day. It writes to worker.log instead.
$python = (Get-Command python -ErrorAction Stop).Source
$pythonw = Join-Path (Split-Path -Parent $python) "pythonw.exe"
if (-not (Test-Path $pythonw)) { $pythonw = $python }

$action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`"" -WorkingDirectory $here
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

# Never time out: the worker is meant to sit there for days. Come back up on
# its own if it dies, and never run two copies, which is what happened by
# hand and left two workers fighting over the same queue.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Procesa los videos del Clip Generator" -Force | Out-Null

Write-Host "Listo. El worker arranca solo al iniciar sesion en Windows."
Write-Host "  Arrancarlo ahora:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  Ver el log:        $here\worker.log"
Write-Host "  Quitarlo:          install-autostart.ps1 -Uninstall"
