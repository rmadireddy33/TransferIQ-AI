[CmdletBinding()]
param([Parameter(Mandatory=$true)][uri]$BackendBaseUrl)
$ErrorActionPreference = 'Stop'
if ($BackendBaseUrl.Scheme -ne 'https' -or $BackendBaseUrl.UserInfo -or $BackendBaseUrl.Query -or $BackendBaseUrl.Fragment) {
    throw 'Use the HTTPS API base URL without credentials, query or fragment.'
}
$work = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation/.flow-sdk'))
$config = @{ backendBaseUrl=$BackendBaseUrl.AbsoluteUri.TrimEnd('/') } | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $work 'runtime.local.json'), $config)
Write-Host 'Saved HTTPS host override. No connection or credentials needed. Run scripts/build-maestro.ps1.'
