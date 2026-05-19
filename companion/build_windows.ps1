$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Push-Location $repoRoot
try {
  $venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
  $python = if (Test-Path $venvPython) { $venvPython } else { 'python' }

  $node = Get-Command node -ErrorAction SilentlyContinue
  if ($node) {
    Write-Host "Syncing items.min.json from bazaardb..."
    try {
      & $node.Source 'tools\sync-bazaardb-data.mjs'
    } catch {
      Write-Host "WARN: bazaardb sync failed, using existing data: $_"
    }
  } else {
    Write-Host "node not found - skipping bazaardb sync, will use existing extension\data\items.min.json"
  }

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

  $iscc = $null
  foreach ($candidate in @(
      'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
      'C:\Program Files\Inno Setup 6\ISCC.exe',
      "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
  )) {
    if (Test-Path $candidate) { $iscc = $candidate; break }
  }
  if (-not $iscc) {
    $isccCmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($isccCmd) { $iscc = $isccCmd.Source }
  }
  if ($iscc) {
    Write-Host "Found Inno Setup at $iscc, building installer..."
    & $iscc 'companion\installer.iss'
    Write-Host "Installer in dist\TheBazaarLiveBoardCompanion-<version>-setup.exe"
  } else {
    Write-Host "Inno Setup not found - skipping installer build."
    Write-Host "Install via 'winget install JRSoftware.InnoSetup' and re-run this script."
  }
}
finally {
  Pop-Location
}
