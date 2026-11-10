"""Generate reviewed public fixtures OFFLINE using a fresh temporary SQLite DB.

Never reads .env or a development/production database; never uploads or deploys.
"""
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.seed import seed_demo
from backend.database.session import create_database_engine, session_factory
from backend.services.reconciliation import collect_inputs
from backend.services.reconciliation_rules import evaluate
from backend.models.entities import Transfer
from backend.schemas.judging import DemoCatalog, DemoTransfer, DemoPosition, DemoException

TITLES = ['Matching positions', 'Split timing and unexplained quantity mismatch',
          'Verified identifier change', 'Missing cost-basis evidence', 'Unsupported quantity correction']

# Display-only synthetic metadata. These values deliberately do not come from
# the private database and contain no live account, client, or firm identifiers.
PORTAL_METADATA = {
    'TRF-1001': ('Avery DemoVale', 'FICTIONAL-SRC-001', 'FICTIONAL-DST-001', '2026-01-15T12:00:00Z'),
    'TRF-1002': ('Morgan DemoReed', 'FICTIONAL-SRC-1002', 'FICTIONAL-DST-1002', '2026-08-15T12:00:00Z'),
    'TRF-1003': ('Morgan DemoReed', 'FICTIONAL-SRC-1003', 'FICTIONAL-DST-1003', '2026-08-15T12:00:00Z'),
    'TRF-1004': ('Morgan DemoReed', 'FICTIONAL-SRC-1004', 'FICTIONAL-DST-1004', '2026-08-15T12:00:00Z'),
    'TRF-1005': ('Morgan DemoReed', 'FICTIONAL-SRC-1005', 'FICTIONAL-DST-1005', '2026-08-15T12:00:00Z'),
}


def build_catalog(directory):
    engine = create_database_engine(Settings(data_dir=directory))
    try:
        initialize_database(engine)
        factory = session_factory(engine)
        seed_demo(factory, include_scenarios=True)
        items = []
        with factory() as session:
            for number, title in zip(range(1001, 1006), TITLES):
                tid = f'TRF-{number}'
                inputs = collect_inputs(session, session.get(Transfer, tid))
                result = evaluate(inputs)
                positions = [DemoPosition(**{k: None if p.get(k) is None else str(p[k])
                    for k in DemoPosition.model_fields}) for p in result['position_results']]
                exceptions = [DemoException(**{k: e.get(k) for k in DemoException.model_fields})
                              for e in result['exceptions']]
                client_name, source_reference, destination_reference, last_updated = PORTAL_METADATA[tid]
                items.append(DemoTransfer(transfer_id=tid, title=title,
                    client_name=client_name, delivering_firm_name='Summit Wealth',
                    receiving_firm_name='Northstar Securities',
                    source_account_reference=source_reference,
                    destination_account_reference=destination_reference,
                    last_updated=last_updated, rule_version=inputs['rule_version'],
                    total_positions=result['total_positions'], directly_matched=result['directly_matched'],
                    evidence_explained=result['evidence_explained'], unresolved_count=result['unresolved_count'],
                    cost_basis_issues=result['cost_basis_issues'],
                    expected_workflow_outcome='INVESTIGATION_REQUIRED' if result['unresolved_count'] else 'CLEAN',
                    requires_cost_basis_review=bool(result['cost_basis_issues']), positions=positions, exceptions=exceptions))
        return DemoCatalog(items=items)
    finally:
        engine.dispose()


def main():
    with TemporaryDirectory(prefix='transferiq-public-fixtures-') as directory:
        payload = build_catalog(Path(directory))
    output = Path(__file__).resolve().parents[1] / 'backend/resources/judging_samples.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(payload.model_dump_json(by_alias=True, indent=2) + '\n', encoding='utf-8')
    print('Generated five precomputed fictional samples from an isolated database; no live executions.')


if __name__ == '__main__':
    main()
