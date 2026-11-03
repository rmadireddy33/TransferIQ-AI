"""Anonymous Render API checks; never claims UiPath runtime execution."""
import json
from scripts.verify_public_demo import verify

if __name__ == '__main__':
    report = verify('https://transferiq-api.onrender.com')
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['status'] == 'PASSED' else 2)
