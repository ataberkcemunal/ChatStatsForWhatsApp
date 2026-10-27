$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
# Keep the project folder free of __pycache__ folders.
$env:PYTHONDONTWRITEBYTECODE = '1'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw 'Python environment missing. Run .\setup.ps1 first.'
}
if (-not $env:WEASYPRINT_DLL_DIRECTORIES) {
    $dllPath = 'C:\msys64\ucrt64\bin'
    if (Test-Path $dllPath) { $env:WEASYPRINT_DLL_DIRECTORIES = $dllPath }
}
if ($args.Count -eq 0) {
    & $python 'ChatStatsForWhatsApp.py' '_chat.txt'
} else {
    & $python 'ChatStatsForWhatsApp.py' @args
}
exit $LASTEXITCODE
