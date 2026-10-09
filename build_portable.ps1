$ErrorActionPreference = 'Stop'
$python = 'C:\laragon\bin\python\python-3.10\python.exe'

& $python -m pip install -r requirements.txt
& $python -m PyInstaller excel_translator.spec --noconfirm --clean

if (Test-Path .env.example) {
    Copy-Item .env.example dist\.env.example -Force
}
New-Item -ItemType Directory -Force -Path dist\uploads, dist\outputs | Out-Null
Write-Host "Portable app created: $PWD\dist\ExcelTranslator.exe"
