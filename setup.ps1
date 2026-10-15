$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Install Python 3.11-3.14 and add it to PATH first.'
}
python -c 'import sys; sys.exit(not ((3, 11) <= sys.version_info[:2] <= (3, 14)))'
if ($LASTEXITCODE -ne 0) { throw 'Unsupported Python version.' }
$dllPath = if ($env:WEASYPRINT_DLL_DIRECTORIES) { $env:WEASYPRINT_DLL_DIRECTORIES } else { 'C:\msys64\ucrt64\bin' }
if (-not ($dllPath.Split(';') | Where-Object { Test-Path (Join-Path $_ 'libpango-1.0-0.dll') })) {
    throw 'Install MSYS2, then run pacman -S mingw-w64-ucrt-x86_64-pango in its UCRT64 shell. For a custom install, set WEASYPRINT_DLL_DIRECTORIES.'
}
$env:WEASYPRINT_DLL_DIRECTORIES = $dllPath
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv.' }
}
& $python -c 'import sys; sys.exit(not ((3, 11) <= sys.version_info[:2] <= (3, 14)))'
if ($LASTEXITCODE -ne 0) { throw 'Existing .venv uses an unsupported Python version.' }
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $python -m weasyprint --info
if ($LASTEXITCODE -ne 0) { throw 'PDF libraries could not be loaded.' }
Write-Host 'Setup complete. Run .\run.ps1'
