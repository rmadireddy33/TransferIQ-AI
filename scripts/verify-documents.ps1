param(
    [string]$BaseUrl = 'http://127.0.0.1:8000',
    [string]$ApiKey = $env:API_KEY
)
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($ApiKey)) { throw 'Set API_KEY to the same key used by the running backend.' }
$headers = @{ 'X-API-Key' = $ApiKey }
$expected = @{ 'TRF-1001'=2; 'TRF-1002'=3; 'TRF-1003'=2; 'TRF-1004'=3; 'TRF-1005'=2 }
foreach ($transferId in ($expected.Keys | Sort-Object)) {
    $list = Invoke-RestMethod "$BaseUrl/api/transfers/$transferId/documents" -Headers $headers
    $samples = @($list.items | Where-Object { $_.isSample -and -not $_.evaluationOnly })
    if ($samples.Count -lt $expected[$transferId]) { throw "Missing primary documents for $transferId" }
    if (@($samples | Where-Object { $_.documentStatus -ne 'READY' }).Count) { throw "Sample is not ready for $transferId" }
    Write-Output "PASS $transferId : $($samples.Count) primary sample documents"
}
$statements = Invoke-RestMethod "$BaseUrl/api/transfers/TRF-1002/documents?documentType=ACCOUNT_STATEMENT" -Headers $headers
$document = @($statements.items | Where-Object { $_.isSample -and -not $_.evaluationOnly })[-1]
$metadata = Invoke-RestMethod "$BaseUrl/api/documents/$($document.documentId)" -Headers $headers
if ($metadata.PSObject.Properties.Name -contains 'storagePath') { throw 'API exposed a storage path' }
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $projectRoot '.venv/Scripts/python.exe'
Push-Location $projectRoot
try { $dataDirectory = & $pythonExecutable -c "from backend.core.config import Settings; print(Settings.from_environment().data_dir)" }
finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve DATA_DIR' }
$downloadDirectory = Join-Path $dataDirectory 'verification'
New-Item -ItemType Directory -Path $downloadDirectory -Force | Out-Null
$downloadPath = Join-Path $downloadDirectory "$($document.documentId).pdf"
Invoke-WebRequest -UseBasicParsing "$BaseUrl/api/transfers/TRF-1002/documents/$($document.documentId)/download" -Headers $headers -OutFile $downloadPath
$digest = (Get-FileHash -Algorithm SHA256 -LiteralPath $downloadPath).Hash.ToLowerInvariant()
if ($digest -ne $metadata.checksumSha256) { throw 'Downloaded checksum differs from metadata' }
if ((Get-Item -LiteralPath $downloadPath).Length -ne $metadata.fileSize) { throw 'Downloaded size differs from metadata' }
$manifest = Get-Content -Raw -LiteralPath (Join-Path $dataDirectory 'sample_exports/manifest.json') | ConvertFrom-Json
$original = @($manifest | Where-Object { $_.documentId -eq $document.documentId })[0]
if (-not $original -or (Get-FileHash -Algorithm SHA256 -LiteralPath $original.samplePath).Hash.ToLowerInvariant() -ne $digest) {
    throw 'Downloaded checksum differs from the generated original'
}
& $pythonExecutable -c "import sys; from pypdf import PdfReader; r=PdfReader(sys.argv[1],strict=True); assert r.pages; t=' '.join(p.extract_text() for p in r.pages); assert 'SEC-103' in t and 'SEC-104' in t; print('PASS: downloaded PDF parses with selectable source-position text; pages:',len(r.pages))" $downloadPath
if ($LASTEXITCODE -ne 0) { throw 'Downloaded PDF parsing failed' }
Write-Output "PASS binary download, size, and SHA-256: $downloadPath"
Write-Output "Document ID: $($document.documentId)"
Write-Output "SHA-256: $digest"
