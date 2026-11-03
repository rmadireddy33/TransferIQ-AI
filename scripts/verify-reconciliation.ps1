param(
    [string]$BaseUrl = 'http://127.0.0.1:8000',
    [string]$ApiKey = $env:API_KEY
)
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($ApiKey)) { throw 'Set API_KEY to the same key used by the running backend.' }
$headers = @{ 'X-API-Key' = $ApiKey }
$expected = @{
    'TRF-1001' = @(7, 7, 0, 0, 0)
    'TRF-1002' = @(7, 5, 1, 1, 0)
    'TRF-1003' = @(1, 0, 1, 0, 0)
    'TRF-1004' = @(7, 7, 0, 0, 1)
    'TRF-1005' = @(1, 0, 0, 1, 0)
}
foreach ($transferId in ($expected.Keys | Sort-Object)) {
    $transfer = Invoke-RestMethod "$BaseUrl/api/transfers/$transferId" -Headers $headers
    $positionsUrl = "$BaseUrl/api/delivering/accounts/$($transfer.sourceAccountId)/positions"
    $stagingUrl = "$BaseUrl/api/transfers/$transferId/assets"
    $sourceBefore = Invoke-RestMethod $positionsUrl -Headers $headers | ConvertTo-Json -Depth 20 -Compress
    $stagingBefore = Invoke-RestMethod $stagingUrl -Headers $headers | ConvertTo-Json -Depth 20 -Compress
    $result = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/transfers/$transferId/reconcile" -Headers $headers -ContentType 'application/json' -Body '{}'
    $s = $result.summary
    $actual = @($s.totalPositions, $s.directlyMatched, $s.evidenceExplained, $s.unresolved, $s.costBasisIssues)
    if (($actual -join ',') -ne ($expected[$transferId] -join ',')) { throw "Unexpected summary for $transferId : $($actual -join ',')" }
    $repeated = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/transfers/$transferId/reconcile" -Headers $headers -ContentType 'application/json' -Body '{}'
    if ($result.reconciliationRunId -ne $repeated.reconciliationRunId) { throw "Unchanged input created another run for $transferId" }
    $latest = Invoke-RestMethod "$BaseUrl/api/transfers/$transferId/reconciliation" -Headers $headers
    $history = Invoke-RestMethod "$BaseUrl/api/reconciliation-runs/$($result.reconciliationRunId)" -Headers $headers
    $exceptions = Invoke-RestMethod "$BaseUrl/api/transfers/$transferId/exceptions" -Headers $headers
    if ($exceptions.total -ne @($result.exceptions).Count) { throw 'Exception count changed after replay' }
    if (($exceptions.items.exceptionId -join ',') -ne ($result.exceptions.exceptionId -join ',')) { throw 'Exception identities changed on replay' }
    if ($latest.reconciliationRunId -ne $history.reconciliationRunId) { throw 'Latest and historical run do not agree' }
    $sourceAfter = Invoke-RestMethod $positionsUrl -Headers $headers | ConvertTo-Json -Depth 20 -Compress
    $stagingAfter = Invoke-RestMethod $stagingUrl -Headers $headers | ConvertTo-Json -Depth 20 -Compress
    if ($sourceBefore -ne $sourceAfter -or $stagingBefore -ne $stagingAfter) { throw 'Reconciliation changed position data' }
    Write-Output "PASS $transferId : total=$($s.totalPositions) direct=$($s.directlyMatched) explained=$($s.evidenceExplained) unresolved=$($s.unresolved) basisIssues=$($s.costBasisIssues); replay reused run; positions unchanged"
}
foreach ($path in @('/api/corporate-actions', '/api/securities/SEC-103/corporate-actions', '/api/securities/SEC-201/identifier-mappings')) {
    $response = Invoke-WebRequest -UseBasicParsing "$BaseUrl$path" -Headers $headers
    if ($response.StatusCode -ne 200) { throw "Reference endpoint failed: $path" }
    Write-Output "PASS GET $path : HTTP 200"
}
