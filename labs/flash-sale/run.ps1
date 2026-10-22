$ErrorActionPreference = 'Stop'
$name = 'parallax-redis-flash-sale'
$python = Resolve-Path (Join-Path $PSScriptRoot '..\..\backend\.venv\Scripts\python.exe')
if (-not (docker image inspect redis:latest 2>$null)) {
    throw 'redis:latest is not cached locally; this lab never pulls images'
}
docker rm -f $name 2>$null | Out-Null
docker run --rm -d --name $name --pull never -p 127.0.0.1:6391:6379 redis:latest | Out-Null
try {
    Start-Sleep -Seconds 1
    $env:PARALLAX_LAB_REDIS_PORT = '6391'
    & $python (Join-Path $PSScriptRoot 'flash_sale_lab.py')
    if ($LASTEXITCODE -ne 0) { throw 'flash-sale lab failed' }
} finally {
    Remove-Item Env:\PARALLAX_LAB_REDIS_PORT -ErrorAction SilentlyContinue
    docker rm -f $name 2>$null | Out-Null
}
Write-Output 'flash-sale lab wrapper completed'
