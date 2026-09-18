param([int]$Port=8766)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$stateFile=Join-Path $PSScriptRoot 'runs/site-launch/2026-09-18-pony-20/state.json'
if(-not (Test-Path $stateFile)){throw 'Batch state missing; restore the batch record before starting.'}
if(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue){
    $current=Invoke-RestMethod "http://127.0.0.1:$Port/api/status"
    if($current.monitor.executor -ne 'local_program'){throw 'Port occupied by another application'}
    Write-Output "Workbench already listening at http://127.0.0.1:$Port";exit
}
$p=Start-Process -FilePath (Join-Path $PSScriptRoot '.venv/Scripts/python.exe') -ArgumentList '-u','workbench.py','--port',$Port -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput 'runs/workbench.stdout.log' -RedirectStandardError 'runs/workbench.stderr.log' -PassThru
Write-Output "Started workflow program PID $($p.Id): http://127.0.0.1:$Port"
