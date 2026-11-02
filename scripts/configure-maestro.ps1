[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][uri]$BackendBaseUrl,
    [Parameter(Mandatory=$true)][guid]$ConnectionId
)
$ErrorActionPreference = 'Stop'
if ($BackendBaseUrl.Scheme -ne 'https' -or $BackendBaseUrl.UserInfo -or $BackendBaseUrl.Query -or $BackendBaseUrl.Fragment) {
    throw 'Use the HTTPS API base URL without credentials, query or fragment.'
}
# Read-only discovery. Never accept guessed IDs or store an API key in project files.
$listing = & uip is connections list uipath-uipath-http --all-folders --refresh --output json
if ($LASTEXITCODE -ne 0) { throw 'UiPath HTTP connection discovery failed' }
$response = $listing | ConvertFrom-Json
$connection = @($response.Data | Where-Object { $_.Id -eq $ConnectionId.ToString() })
if ($connection.Count -ne 1 -or $connection[0].State -ne 'Enabled') { throw 'Selected HTTP connection was not found or is not Enabled' }
$ping = & uip is connections ping $ConnectionId.ToString() --force-refresh --output json
if ($LASTEXITCODE -ne 0) { throw 'HTTP connection health check failed' }
$health = $ping | ConvertFrom-Json
if ($health.Result -ne 'Success' -or $health.Data.Status -ne 'Enabled') { throw 'HTTP connection health check failed' }
$folderKey = [guid]$connection[0].FolderKey
$work = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation/.flow-sdk'))
$binding = @{ schemaVersion='1'; bindings=@(
    @{ name='transferiqHttp'; resource='Connection'; propertyAttribute='ConnectionId'; resourceKey=$ConnectionId.ToString() },
    @{ name='transferiqFolder'; resource='Connection'; propertyAttribute='FolderKey'; resourceKey=$folderKey.ToString() }
) } | ConvertTo-Json -Depth 5
$config = @{ backendBaseUrl=$BackendBaseUrl.AbsoluteUri.TrimEnd('/') } | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $work 'bindings.json'), $binding)
[IO.File]::WriteAllText((Join-Path $work 'runtime.local.json'), $config)
Write-Host 'Saved verified resource references (no secrets). Confirm the HTTP connection uses this same base URL, then rebuild.'
