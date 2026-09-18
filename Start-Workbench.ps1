param([int]$Port=8766,[string]$State='runs/site-launch/2026-09-18-pony-20/state.json')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$stateFile=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot $State))
if(-not $stateFile.StartsWith((Join-Path $PSScriptRoot 'runs/site-launch') + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'State must be under runs/site-launch.'}
if(-not (Test-Path $stateFile)){throw 'Batch state missing; restore the batch record before starting.'}
if(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue){
    $current=Invoke-RestMethod "http://127.0.0.1:$Port/api/status"
    if($current.program.mode -ne 'tdk_only'){throw 'Port occupied by another application'}
    Write-Output "Workbench already listening at http://127.0.0.1:$Port";exit
}
$p=Start-Process -FilePath (Join-Path $PSScriptRoot '.venv/Scripts/python.exe') -ArgumentList '-u','workbench.py','--state',$stateFile,'--port',$Port -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput 'runs/workbench.stdout.log' -RedirectStandardError 'runs/workbench.stderr.log' -PassThru
Write-Output "Started workflow program PID $($p.Id): http://127.0.0.1:$Port"
