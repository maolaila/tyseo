param(
    [string]$BusinessRepo = 'C:/tyseo/cms-sport-tpl-bing',
    [string]$KeyFile,
    [switch]$RestoreData
)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    & py -3.10 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.10 first; business repository is not installed or changed by this script.' }
}
& ./.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'External dependency install failed' }
& ./.venv/Scripts/python.exe -m playwright install chromium firefox webkit
if ($LASTEXITCODE -ne 0) { throw 'Browser install failed' }
& npm.cmd install --prefix .runtime-cli --save-exact '@playwright/cli@0.1.20'
if ($LASTEXITCODE -ne 0) { throw 'CLI 0.1.20 install failed; Node.js/npm is required.' }
if ($RestoreData) {
    if (-not $KeyFile) { throw 'Pass -KeyFile with the separately transferred migration key.' }
    & ./.venv/Scripts/python.exe scripts/migrate.py restore --key-file $KeyFile --destination restored
    if ($LASTEXITCODE -ne 0) { throw 'Restore failed; existing files are never overwritten.' }
}
if (-not (Test-Path (Join-Path $BusinessRepo 'run.py'))) {
    Write-Warning 'Business checkout is unavailable. Obtain it using your company access; no substitute project was created.'
}
$taskConfig = Get-Content -LiteralPath config/task.example.json -Raw | ConvertFrom-Json
$taskConfig.workflow_root = $PSScriptRoot.Replace('\','/')
$taskConfig.repo_root = [IO.Path]::GetFullPath($BusinessRepo).Replace('\','/')
$taskConfig | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath tasks/local.json -Encoding utf8
& ./.venv/Scripts/python.exe pipeline.py list
Write-Output 'External tools ready. Use --task tasks/local.json. Credentials, if restored, are under restored/private/business; existing business .env is unchanged.'
