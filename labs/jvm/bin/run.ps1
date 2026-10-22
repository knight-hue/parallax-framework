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
& $java -cp $out JmmVisibilityLab
if ($LASTEXITCODE -ne 0) { throw 'JmmVisibilityLab failed' }
& $java -cp $out VolatileCounterRace
if ($LASTEXITCODE -ne 0) { throw 'VolatileCounterRace failed' }
& $java -cp $out SafePublicationLab
if ($LASTEXITCODE -ne 0) { throw 'SafePublicationLab failed' }
& $java -cp $out ClassLoaderLab
if ($LASTEXITCODE -ne 0) { throw 'ClassLoaderLab failed' }
& $java -Xlog:gc -cp $out GcLab
if ($LASTEXITCODE -ne 0) { throw 'GcLab failed' }
& $java -Xmx32m -cp $out OomLab
if ($LASTEXITCODE -ne 0) { throw 'OomLab failed' }
Write-Output 'jvm labs completed'
