param([string]$BaseUrl = 'http://127.0.0.1:8000', [string]$ApiKey = $env:API_KEY)
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($ApiKey)) { throw 'Set API_KEY to your own backend key before verifying live business APIs.' }
$headers = @{ 'X-API-Key' = $ApiKey }
$paths = @(
    '/health', '/api/clients', '/api/clients/CLI-001', '/api/firms',
    '/api/accounts/ACC-SRC-001', '/api/transfers', '/api/transfers/TRF-1001',
    '/api/transfers/TRF-1001/assets', '/api/delivering/accounts/ACC-SRC-001/positions',
    '/api/receiving/accounts/ACC-DST-001/positions', '/api/securities', '/api/securities/SEC-001',
    '/docs', '/openapi.json'
)
$responses = @{}
foreach ($path in $paths) {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl$path" -Headers $headers
    if ($response.StatusCode -ne 200) { throw "GET $path failed: $($response.StatusCode)" }
    if ($path -ne '/docs') { $responses[$path] = $response.Content | ConvertFrom-Json }
    Write-Output "PASS GET $path : $($response.StatusCode)"
}
if ($responses['/health'].database -ne 'ok') { throw 'Database health failed' }
if ($responses['/api/clients/CLI-001'].clientId -ne 'CLI-001') { throw 'Seed client missing' }
if ($responses['/api/transfers/TRF-1001'].transferId -ne 'TRF-1001') { throw 'Seed transfer missing' }
$source = $responses['/api/delivering/accounts/ACC-SRC-001/positions']
$destination = $responses['/api/transfers/TRF-1001/assets']
if ($source.total -ne 7 -or $destination.total -ne 7) { throw 'Expected seven seeded source and staging positions' }
if ($destination.settledHoldings -ne $false) { throw 'Staging must not be reported as settled custody' }
foreach ($position in $source.items) {
    $matching = @($destination.items | Where-Object { $_.securityId -eq $position.securityId })
    if ($matching.Count -ne 1 -or $matching[0].quantity -ne $position.quantity) {
        throw "Seed staging quantity mismatch: $($position.securityId)"
    }
}
Write-Output 'PASS: all 14 HTTP requests; seven matching fictional source/staging positions; no settlement.'
