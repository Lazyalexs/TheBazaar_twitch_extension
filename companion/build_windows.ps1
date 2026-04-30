$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Push-Location $repoRoot
try {
  $venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
  $python = if (Test-Path $venvPython) { $venvPython } else { 'python' }

  & $python -m pip install -r companion\requirements-windows.txt
  & $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --specpath build\pyinstaller-spec `
    --name TheBazaarLiveBoardCompanion `
    --collect-submodules companion `
    companion\desktop_app.py

  Write-Host "Built dist\TheBazaarLiveBoardCompanion\TheBazaarLiveBoardCompanion.exe"
}
finally {
  Pop-Location
}
