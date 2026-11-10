import re
from pathlib import Path

import pytest


PORTAL_DIST = Path(__file__).resolve().parents[1] / 'frontend' / 'dist'


@pytest.mark.skipif(not (PORTAL_DIST / 'index.html').is_file(), reason='run npm run build in frontend first')
def test_compiled_portal_is_same_origin_and_preserves_api_routes(client):
    root = client.get('/portal')
    nested = client.get('/portal/transfers/TRF-1002/reconciliation')

    assert root.status_code == 200
    assert root.headers['cache-control'] == 'no-cache'
    assert root.headers['x-content-type-options'] == 'nosniff'
    assert '<div id="root"></div>' in root.text
    assert nested.status_code == 200 and nested.text == root.text

    asset = re.search(r'(?:src|href)="(/portal/assets/[^"]+)"', root.text)
    assert asset is not None
    assert client.get(asset.group(1)).status_code == 200

    assert client.get('/api/demo/transfers').status_code == 200
    assert client.get('/health').status_code == 200
    assert client.get('/docs').status_code == 200
    assert '/portal' not in client.get('/openapi.json').json()['paths']
    assert client.post('/portal').status_code == 405
