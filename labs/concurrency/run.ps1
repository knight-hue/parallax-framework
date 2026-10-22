$ErrorActionPreference = 'Stop'
$jdk = Resolve-Path (Join-Path $PSScriptRoot '..\..\.toolchain\jdk')
$java = Join-Path $jdk 'bin\java.exe'
$javac = Join-Path $jdk 'bin\javac.exe'
$out = Join-Path $PSScriptRoot 'out'
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Path $out | Out-Null
Get-ChildItem $PSScriptRoot -Filter '*.java' | ForEach-Object {
    & $javac -d $out $_.FullName
    if ($LASTEXITCODE -ne 0) { throw "javac failed: $($_.Name)" }
}
& $java -cp $out AqsLockLab
if ($LASTEXITCODE -ne 0) { throw 'AqsLockLab failed' }
& $java -cp $out ThreadPoolRejectionLab
if ($LASTEXITCODE -ne 0) { throw 'ThreadPoolRejectionLab failed' }
& $java -cp $out InterruptCancelLab
if ($LASTEXITCODE -ne 0) { throw 'InterruptCancelLab failed' }
& $java -cp $out BackpressureLab
if ($LASTEXITCODE -ne 0) { throw 'BackpressureLab failed' }
Write-Output 'concurrency labs completed'
