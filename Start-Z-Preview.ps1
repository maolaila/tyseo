$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if(Get-NetTCPConnection -LocalPort 8771 -State Listen -ErrorAction SilentlyContinue){
    $status=Invoke-RestMethod 'http://127.0.0.1:8771/health'
    if($status.mode -ne 'z_manual_review'){throw 'Port 8771 is occupied by another application'}
    $repo=(Get-Content 'tasks/bootstrap.json' -Raw | ConvertFrom-Json).repo_root
    if($status.commit -ne (git -C $repo rev-parse HEAD)){throw 'Business commit changed; restart the preview before reviewing the new version'}
    Write-Output 'Preview already running: http://127.0.0.1:8771/'
    exit
}
$logs=Join-Path $PSScriptRoot 'runs/z-manual-preview'
New-Item -ItemType Directory -Path $logs -Force | Out-Null
$process=Start-Process -FilePath (Join-Path $PSScriptRoot '.venv/Scripts/python.exe') -ArgumentList '-B','-u','src/z_manual_preview.py' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'launcher.stdout.log') -RedirectStandardError (Join-Path $logs 'launcher.stderr.log') -PassThru
Write-Output "Starting z1-z17 preview, PID $($process.Id): http://127.0.0.1:8771/"
