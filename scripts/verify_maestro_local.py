"""Actual local HTTP checks through emitted Flow JS/edges, NOT a Maestro cloud run."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess

import httpx

from backend.core.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    settings = Settings.from_environment()
    key = settings.api_key.get_secret_value() if settings.api_key else ''
    if not key:
        raise SystemExit('API_KEY must match the running backend; no key was printed.')
    report = {'evidenceMode': 'LOCAL_HTTP_AND_EMITTED_GRAPH_NOT_UIPATH_RUNTIME',
              'timestampUtc': datetime.now(timezone.utc).isoformat(), 'cases': []}

    def run(tid, base_url=args.base_url, authorized=True, configured=True):
        env = dict(os.environ, API_KEY=key if authorized else '')
        result = subprocess.run(['node', str(ROOT / 'scripts/maestro-local-runner.mjs')],
            input=json.dumps(dict(transferId=tid, baseUrl=base_url, localTransport=configured)),
            capture_output=True, text=True, timeout=90, env=env, cwd=ROOT)
        if result.returncode:
            raise RuntimeError('Local graph harness failed; no response or credentials logged')
        return json.loads(result.stdout)

    before = {}
    with httpx.Client(base_url=args.base_url, timeout=15) as client:
        for n in range(1001, 1006):
            tid = f'TRF-{n}'
            transfer = client.get(f'/api/transfers/{tid}').raise_for_status().json()
            paths = [f'/api/transfers/{tid}',
                     f"/api/delivering/accounts/{transfer['sourceAccountId']}/positions?limit=100",
                     f"/api/receiving/accounts/{transfer['destinationAccountId']}/positions?transferId={tid}&limit=100"]
            for path in paths:
                before[path] = client.get(path).raise_for_status().json()
        expected = [(7, 0, 0, 0), (5, 1, 1, 0), (0, 1, 0, 0), (7, 0, 0, 1), (0, 0, 1, 0)]
        for n, counts in zip(range(1001, 1006), expected):
            tid = f'TRF-{n}'
            execution = run(tid)
            result = execution['result']
            actual = tuple(result[k] for k in ('directlyMatched', 'evidenceExplained', 'unresolvedCount', 'costBasisIssues'))
            assert actual == counts, (tid, actual)
            assert result['workflowOutcome'] == ('INVESTIGATION_REQUIRED' if counts[2] else 'CLEAN')
            report['cases'].append(dict(case=tid, status='PASSED', outcome=result['workflowOutcome'], counts=actual,
                reconciliationRunId=result['reconciliationRunId'], trace=execution['trace']))
        for name, execution, error in [
            ('invalid ID', run('TRF-NOT-FOUND'), 'HTTP_REQUEST_FAILED'),
            ('invalid input', run('../bad'), 'INVALID_TRANSFER_INPUT'),
            ('unauthorized', run('TRF-1001', authorized=False), 'HTTP_REQUEST_FAILED'),
            ('unconfigured', run('TRF-1001', configured=False), 'CONFIGURATION_REQUIRED'),
        ]:
            assert execution['result']['workflowOutcome'] == 'FAILED'
            assert execution['result']['error']['code'] == error
            if name == 'invalid ID': assert execution['result']['httpStatus'] == 404
            if name == 'unauthorized':
                assert execution['result']['httpStatus'] == 401
                assert len([c for c in execution['calls'] if c['nodeId'] == 'RunReconciliation']) == 1
            report['cases'].append(dict(case=name, status='PASSED', outcome='FAILED', trace=execution['trace']))
        # A bound, non-listening local socket gives a real refused connection on an OS-assigned port.
        with socket.socket() as unavailable:
            unavailable.bind(('127.0.0.1', 0))
            execution = run('TRF-1001', base_url=f'http://127.0.0.1:{unavailable.getsockname()[1]}')
            assert execution['result']['workflowOutcome'] == 'FAILED'
            assert len(execution['calls']) == 2
            report['cases'].append(dict(case='backend unavailable', status='PASSED', outcome='FAILED', trace=execution['trace']))
        for path, original in before.items():
            assert client.get(path).raise_for_status().json() == original, 'Financial or transfer record changed'
        report['preservedTransferAndPositionResponses'] = len(before)
    report['maestroRuntime'] = 'BLOCKED: no externally reachable HTTPS backend or bound HTTP connection'
    output = settings.data_dir / 'verification' / 'maestro-step5-local.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    for case in report['cases']:
        print(f"{case['case']}: {case['status']} ({case['outcome']})")
    print(f'Preserved {len(before)} transfer/source/staging responses. Report: {output}')
    print(report['maestroRuntime'])


if __name__ == '__main__':
    main()
