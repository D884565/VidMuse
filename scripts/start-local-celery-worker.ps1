$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = 'C:\ProgramData\anaconda3\python.exe'

if (-not (Test-Path $pythonExe)) {
  throw "Python executable not found: $pythonExe"
}

Set-Location $repoRoot

& $pythonExe -m celery `
  -A backend.v1.app.generate.tasks.celery_app.celery_app `
  worker `
  --loglevel=info `
  --pool=solo
