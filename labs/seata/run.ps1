$ErrorActionPreference = 'Stop'

$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$maven = Join-Path $root '.toolchain\maven\bin\mvn.cmd'
$javaHome = Join-Path $root '.toolchain\jdk'
$mysqlClient = if ($env:PARALLAX_MYSQL_CLIENT) { $env:PARALLAX_MYSQL_CLIENT } else { 'mysql' }
$dbHost = if ($env:PARALLAX_SEATA_DB_HOST) { $env:PARALLAX_SEATA_DB_HOST } else { '127.0.0.1' }
$dbPort = if ($env:PARALLAX_SEATA_DB_PORT) { $env:PARALLAX_SEATA_DB_PORT } else { '3307' }
$dbUser = if ($env:PARALLAX_SEATA_DB_USER) { $env:PARALLAX_SEATA_DB_USER } else { 'parallax' }
$dbPassword = if ($env:PARALLAX_SEATA_DB_PASSWORD) { $env:PARALLAX_SEATA_DB_PASSWORD } else { 'parallax' }
$dbName = if ($env:PARALLAX_SEATA_DB_NAME) { $env:PARALLAX_SEATA_DB_NAME } else { 'seata_lab' }

Write-Output "applying schema to ${dbHost}:${dbPort}/${dbName}"
$env:MYSQL_PWD = $dbPassword
Get-Content (Join-Path $PSScriptRoot 'sql\schema.sql') -Raw |
    & $mysqlClient --protocol=TCP "--host=$dbHost" "--port=$dbPort" "--user=$dbUser" $dbName
if ($LASTEXITCODE -ne 0) { throw 'schema init failed' }

$env:JAVA_HOME = $javaHome
Push-Location $PSScriptRoot
try {
    & $maven -B test
    if ($LASTEXITCODE -ne 0) { throw 'seata lab failed' }
} finally {
    Pop-Location
}
Write-Output 'seata AT/TCC lab completed'
