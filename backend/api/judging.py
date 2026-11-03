"""Public judging reads a packaged fixture only, never a live database or PDF."""
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from backend.schemas.judging import DemoCatalog, DemoTransfer

router = APIRouter(prefix='/api/demo', tags=['Public fictional samples'])
SAMPLE_FILE = Path(__file__).resolve().parents[1] / 'resources/judging_samples.json'


@lru_cache(maxsize=1)
def catalog():
    result = DemoCatalog.model_validate_json(SAMPLE_FILE.read_text(encoding='utf-8'))
    if {x.transfer_id for x in result.items} != {f'TRF-{n}' for n in range(1001, 1006)}:
        raise ValueError('Invalid public fixture catalog')
    return result


def public_response(request, response):
    if not request.app.state.settings.public_demo_enabled:
        raise HTTPException(404, detail={'code': 'not_found', 'message': 'Public demo is disabled'})
    response.headers['Cache-Control'] = 'public, max-age=60'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-TransferIQ-Evidence'] = 'precomputed-synthetic-sample'


@router.get('/transfers', response_model=DemoCatalog)
def samples(request: Request, response: Response):
    public_response(request, response)
    return catalog()


@router.get('/transfers/{transferId}', response_model=DemoTransfer)
def sample(transferId: str, request: Request, response: Response):
    public_response(request, response)
    for item in catalog().items:
        if item.transfer_id == transferId:
            return item
    raise HTTPException(404, detail={'code': 'not_found', 'message': 'Unknown fictional sample'})
