"""Actual anonymous HTTP + emitted graph checks. This is NOT a UiPath runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import httpx

ROOT = Path(__file__).resolve().parents[1]


def verify(base_url):
    report = {'evidenceMode': 'REAL_HTTP_LOCAL_GRAPH_NOT_UIPATH_RUNTIME',
              'baseUrl': base_url, 'authenticationHeadersSent': False, 'cases': []}
    with httpx.Client(base_url=base_url, timeout=40, follow_redirects=False, trust_env=False) as client:
        health = client.get('/health')
        report['healthStatus'] = health.status_code
        health.raise_for_status()
        spec = client.get('/openapi.json').raise_for_status().json()
        if '/api/demo/runs' not in spec['paths']:
            return dict(report, status='BLOCKED', reason='Deployed backend lacks /api/demo/runs; redeploy this revision first')
        for tid, expected in [('TRF-1001', (7, 0, 0)), ('TRF-1002', (5, 1, 1)), ('TRF-NOT-FOUND', None)]:
            execution = subprocess.run(['node', str(ROOT / 'scripts/maestro-local-runner.mjs')],
                input=json.dumps(dict(transferId=tid, baseUrl=base_url, localTransport=True)),
                capture_output=True, text=True, check=True, timeout=180, cwd=ROOT)
            graph = json.loads(execution.stdout)
            result = graph['result']
            case = dict(transferId=tid, outcome=result['workflowOutcome'],
                        localDecisionBranch=graph['trace'][-1], httpCalls=graph['calls'])
            if expected is None:
                assert result['workflowOutcome'] == 'FAILED' and result['httpStatus'] == 422
            else:
                assert tuple(result[k] for k in ('directlyMatched', 'evidenceExplained', 'unresolvedCount')) == expected
                assert result['workflowOutcome'] == ('CLEAN' if not expected[2] else 'INVESTIGATION_REQUIRED')
                root = '/api/demo/runs/' + result['demoRunId']
                case['counts'] = expected
                case['runId'] = result['demoRunId']
                case['reconciliationRunId'] = result['reconciliationRunId']
                case['readStatuses'] = {}
                for suffix in ('/transfer', '/reconciliation', '/exceptions', '/documents', '/audit'):
                    response = client.get(root + suffix)
                    assert response.status_code == 200, (suffix, response.status_code)
                    case['readStatuses'][suffix] = response.status_code
                docs = client.get(root + '/documents').json()['items']
                pdf = client.get(root + '/documents/' + docs[0]['documentId'] + '/download')
                assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF-')
                assert hashlib.sha256(pdf.content).hexdigest() == docs[0]['checksumSha256']
                case['pdfStatus'] = pdf.status_code
                retry = client.post(root + '/reconcile', json={})
                assert retry.status_code == 200 and retry.json()['reconciliationRunId'] == result['reconciliationRunId']
                case['retryStatus'] = retry.status_code
            report['cases'].append(case)
        for method, path in [('GET', '/api/transfers/TRF-1001'),
                             ('POST', '/api/transfers/TRF-1001/reconcile'),
                             ('POST', '/api/transfers/TRF-1001/documents')]:
            assert client.request(method, path).status_code in (401, 503)
    return dict(report, status='PASSED', maestroRuntime='NOT_EXECUTED')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    report = verify(args.base_url)
    print(json.dumps(report, indent=2))
    if report['status'] != 'PASSED':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
