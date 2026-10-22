$ErrorActionPreference = 'Stop'

$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$maven = Join-Path $root '.toolchain\maven\bin\mvn.cmd'
$env:JAVA_HOME = Join-Path $root '.toolchain\jdk'

Push-Location $PSScriptRoot
try {
    & $maven -B -o test
    if ($LASTEXITCODE -ne 0) { throw 'mysql lab failed' }
} finally {
    Pop-Location
}
Write-Output 'mysql lab completed'
