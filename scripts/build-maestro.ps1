[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$project = Join-Path $PSScriptRoot '../maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation'
Push-Location $project
try {
    & uip maestro flow check .flow-sdk/TransferIQ_Reconciliation.flow.ts --source
    if ($LASTEXITCODE -ne 0) { throw 'Flow source check failed' }
    & uip maestro flow compile .flow-sdk/TransferIQ_Reconciliation.flow.ts -o TransferIQ_Reconciliation.flow
    if ($LASTEXITCODE -ne 0) { throw 'Flow compilation failed' }
    & uip maestro flow format TransferIQ_Reconciliation.flow --output json
    if ($LASTEXITCODE -ne 0) { throw 'Flow formatting failed' }
    & uip maestro flow validate TransferIQ_Reconciliation.flow --output json
    if ($LASTEXITCODE -ne 0) { throw 'Flow validation failed' }
} finally { Pop-Location }
