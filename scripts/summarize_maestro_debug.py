"""Summarize saved real UiPath debug envelopes; never synthesize execution evidence."""
import argparse
import json
from pathlib import Path

import httpx

HTTP_NODES = ('CreateDemoRun', 'GetTransferDetails', 'GetDeliveringPositions',
              'GetReceivingPositions', 'RunReconciliation', 'GetCorporateActionReference', 'GetInvestigationReferences')
RESULT_FIELDS = ('transferId', 'demoRunId', 'reconciliationRunId', 'totalPositions',
                 'directlyMatched', 'evidenceExplained', 'unresolvedCount',
                 'workflowOutcome', 'evidenceOutcome', 'extractionResult', 'httpStatus', 'error',
                 'documentEvidenceStatus', 'investigationStatus', 'investigationSummary', 'findings',
                 'unresolvedExceptions', 'recommendedNextActions', 'humanReviewRequired',
                 'missingEvidence', 'validationErrors', 'correctionsApplied', 'transferCompleted')


def read_envelope(path):
    raw = path.read_bytes()
    return json.loads(raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'))


def summarize(path, backend_url=None):
    envelope = read_envelope(path)
    data = envelope.get('Data', {})
    variables = data.get('variables', {})
    result = variables.get('globals', {}).get('result') or {}
    elements = {x['elementId']: x for x in variables.get('elements', [])}
    statuses = {}
    for name in HTTP_NODES:
        if name not in elements:
            statuses[name] = 'NOT_EXECUTED'
            continue
        outputs = elements[name].get('outputs', {})
        response = outputs.get('response') or {}
        error = outputs.get('error') or outputs.get('Error') or {}
        error_status = error.get('status') if isinstance(error, dict) else None
        statuses[name] = response.get('code', response.get('statusCode', response.get('status', error_status)))
    executed = [x['elementId'] for x in data.get('elementExecutions', []) if x.get('status') == 'Completed']
    report = dict(source=path.name, evidenceMode='ACTUAL_UIPATH_DEBUG_EXECUTION',
                cliResult=envelope.get('Result'), finalStatus=data.get('finalStatus'),
                instanceId=data.get('instanceId'), studioWebUrl=data.get('studioWebUrl'),
                result={k: result[k] for k in RESULT_FIELDS if k in result},
                httpStatuses=statuses, completedElements=executed,
                incidentCount=len(data.get('incidents') or []))
    if backend_url and result.get('demoRunId'):
        root = '/api/demo/runs/' + result['demoRunId']
        transfer = elements['GetTransferDetails']['outputs']['response']['body']
        checks = {}
        with httpx.Client(base_url=backend_url, timeout=40, trust_env=False) as client:
            for name, role, account in [('GetDeliveringPositions', 'delivering', 'sourceAccountId'),
                                        ('GetReceivingPositions', 'receiving', 'destinationAccountId')]:
                response = client.get(f"{root}/{role}/accounts/{transfer[account]}/positions", params={'limit': 100, 'offset': 0})
                response.raise_for_status()
                assert response.json() == elements[name]['outputs']['response']['body'], 'Positions changed after reconciliation'
                checks[name] = dict(status=response.status_code, unchanged=True)
            audit = client.get(root + '/audit')
            audit.raise_for_status()
            assert audit.json()['correctionsApplied'] == 0
            checks['audit'] = dict(status=audit.status_code, correctionsApplied=0)
        report['anonymousPostRunChecks'] = checks
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', type=Path, nargs='+')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--verify-backend-url')
    args = parser.parse_args()
    report = json.dumps([summarize(path, args.verify_backend_url) for path in args.files], indent=2)
    if args.output:
        args.output.write_text(report + '\n', encoding='utf-8')
    print(report)


if __name__ == '__main__':
    main()
