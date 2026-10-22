$ErrorActionPreference = 'Stop'
$jdk = Resolve-Path (Join-Path $PSScriptRoot '..\..\.toolchain\jdk')
$mvn = Resolve-Path (Join-Path $PSScriptRoot '..\..\.toolchain\maven\bin\mvn.cmd')
$env:JAVA_HOME = $jdk.Path
Push-Location $PSScriptRoot
try {
    & $mvn -o test
    if ($LASTEXITCODE -ne 0) { throw 'spring lab failed' }
} finally {
    Pop-Location
}
Write-Output 'spring lab completed'
