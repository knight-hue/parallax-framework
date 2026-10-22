$ErrorActionPreference = 'Stop'
$name = 'parallax-redis-lab'
$python = Resolve-Path (Join-Path $PSScriptRoot '..\..\backend\.venv\Scripts\python.exe')
if (-not (docker image inspect redis:latest 2>$null)) {
    throw 'redis:latest is not cached locally; this lab never pulls images'
}
docker rm -f $name 2>$null | Out-Null
docker run --rm -d --name $name --pull never -p 127.0.0.1:6390:6379 redis:latest | Out-Null
try {
    Start-Sleep -Seconds 1
    & $python (Join-Path $PSScriptRoot 'redis_lab.py')
    if ($LASTEXITCODE -ne 0) { throw 'redis lab failed' }
} finally {
    docker rm -f $name 2>$null | Out-Null
}
Write-Output 'redis lab wrapper completed'
