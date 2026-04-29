param(
  [int]$EbsPort = 8000,
  [int]$ExtensionPort = 5173
)

$ErrorActionPreference = "Stop"

function Test-PortFree([int]$Port) {
  $connection = Get-NetTCPConnection `
    -LocalPort $Port `
    -State Listen `
    -ErrorAction SilentlyContinue
  return $null -eq $connection
}

function Start-HiddenPython($Name, [string[]]$PythonArgs, [int]$Port) {
  if (-not (Test-PortFree $Port)) {
    Write-Host "$Name port $Port is already in use"
    return
  }

  $out = Join-Path $env:TEMP "bazaar-$Name-out.log"
  $err = Join-Path $env:TEMP "bazaar-$Name-err.log"
  Remove-Item -LiteralPath $out, $err -ErrorAction SilentlyContinue

  $process = Start-Process `
    -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList $PythonArgs `
    -WorkingDirectory (Get-Location) `
    -WindowStyle Hidden `
    -RedirectStandardOutput $out `
    -RedirectStandardError $err `
    -PassThru

  Write-Host "$Name started on port $Port with PID $($process.Id)"
  Write-Host "  stdout: $out"
  Write-Host "  stderr: $err"
}

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Host "Creating .venv"
  python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install -r ebs\requirements-dev.txt

$env:EBS_DRY_RUN = "1"
Start-HiddenPython `
  -Name "ebs" `
  -Port $EbsPort `
  -PythonArgs @("-m", "uvicorn", "ebs.app.main:app", "--host", "127.0.0.1", "--port", "$EbsPort")

Start-HiddenPython `
  -Name "extension" `
  -Port $ExtensionPort `
  -PythonArgs @("-m", "http.server", "$ExtensionPort", "-d", "extension")

Write-Host ""
Write-Host "EBS health:"
Write-Host "  http://127.0.0.1:$EbsPort/health"
Write-Host "Viewer demo:"
Write-Host "  http://127.0.0.1:$ExtensionPort/viewer.html?demo=1"
Write-Host "Viewer polling EBS:"
Write-Host "  http://127.0.0.1:$ExtensionPort/viewer.html?ebs=http://127.0.0.1:$EbsPort&channel=dev-channel"
Write-Host "Live dashboard:"
Write-Host "  http://127.0.0.1:$ExtensionPort/live.html"
