$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Push-Location $repoRoot
try {
  $venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
  $python = if (Test-Path $venvPython) { $venvPython } else { 'python' }
  $itemsData = Resolve-Path (Join-Path $repoRoot 'extension\data\items.min.json')
  $icon = Resolve-Path (Join-Path $repoRoot 'extension\image\favicon.ico')

  & $python -m pip install -r companion\requirements-windows.txt
  & $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --specpath build\pyinstaller-spec `
    --name TheBazaarLiveBoardCompanion `
    --add-data "$itemsData;extension\data" `
    --add-data "$icon;extension\image" `
    --icon "$icon" `
    --collect-submodules companion `
    companion\desktop_app.py

  Write-Host "Built dist\TheBazaarLiveBoardCompanion\TheBazaarLiveBoardCompanion.exe"
}
finally {
  Pop-Location
}
