$ErrorActionPreference = 'Stop'
$python = Resolve-Path (Join-Path $PSScriptRoot '..\..\backend\.venv\Scripts\python.exe')
& $python (Join-Path $PSScriptRoot 'distributed_tx_lab.py')
if ($LASTEXITCODE -ne 0) { throw 'distributed transaction lab failed' }
Write-Output 'distributed transaction lab completed'
