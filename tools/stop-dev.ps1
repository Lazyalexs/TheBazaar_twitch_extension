param(
  [int[]]$Ports = @(8000, 5173)
)

$ErrorActionPreference = "SilentlyContinue"

$processIds = Get-NetTCPConnection -LocalPort $Ports -State Listen |
  Where-Object { $_.OwningProcess -ne 0 } |
  Select-Object -ExpandProperty OwningProcess -Unique

foreach ($processId in $processIds) {
  Stop-Process -Id $processId -Force
  Write-Host "Stopped PID $processId"
}
