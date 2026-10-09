$ErrorActionPreference = 'Stop'

$compilerCandidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
    'C:\Program Files\Inno Setup 6\ISCC.exe'
)
$compiler = $compilerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $compiler) {
    throw 'Inno Setup 6 is not installed. Install JRSoftware.InnoSetup, then run this script again.'
}
if (-not (Test-Path -LiteralPath 'dist\ExcelTranslator.exe')) {
    throw 'dist\ExcelTranslator.exe is missing. Run build_portable.ps1 first.'
}
if (-not (Test-Path -LiteralPath 'dist\.env')) {
    throw 'dist\.env is missing. The installer needs Azure settings beside the executable.'
}

& $compiler 'installer.iss'
Write-Host "Installer created: $PWD\installer\ExcelTranslatorSetup.exe"
