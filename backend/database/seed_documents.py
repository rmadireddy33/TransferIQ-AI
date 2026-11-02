"""Generate reproducible fixtures separately from the private runtime repository."""
import argparse
import json
from pathlib import Path

from sqlalchemy import select
from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.session import create_database_engine, session_factory
from backend.models.documents import DocumentSource as S, DocumentType as T, TransferDocument
from backend.services.document_storage import checksum, save_document, read_document
from backend.services.pdf_generation import document_data, render_pdf


def document_recipes():
    recipes = []
    for number in range(1001, 1006):
        tid = f"TRF-{number}"
        recipes.extend([(tid, T.TRANSFER_REQUEST, S.TRANSFER_OPERATIONS, 1, False, None),
                        (tid, T.ACCOUNT_STATEMENT, S.DELIVERING_FIRM, 1, False, None)])
    recipes += [("TRF-1002", T.CORPORATE_ACTION_NOTICE, S.REFERENCE_DATA, 1, False, "CA-2026-081"),
                ("TRF-1004", T.COST_BASIS_STATEMENT, S.DELIVERING_FIRM, 1, False, None)]
    for layout in (2, 3):
        recipes += [("TRF-1002", T.ACCOUNT_STATEMENT, S.DELIVERING_FIRM, layout, True, None),
                    ("TRF-1002", T.CORPORATE_ACTION_NOTICE, S.REFERENCE_DATA, layout, True, "CA-2026-081")]
    return recipes


def seed_missing_documents(factory, settings):
    """Startup-only seed: existing sample identities/versions are authoritative.

    No re-render when a recipe already exists, even after source data or PDF
    library versions change. Missing/corrupt registered bytes need repair, not a
    new document ID silently replacing a reference. Pending recovery runs first.
    """
    inserted = 0
    for tid, kind, source, layout, evaluation, action_id in document_recipes():
        key = f"{tid}:{kind.value}:{action_id or 'none'}:layout{layout}"
        with factory() as session:
            existing = session.scalar(select(TransferDocument).where(TransferDocument.sample_key == key)
                .order_by(TransferDocument.version.desc()).limit(1))
            if existing:
                read_document(settings, existing)
                continue
            data = document_data(session, tid, kind, action_id)
        pdf = render_pdf(data, kind, layout)
        _, created = save_document(factory, settings, tid, pdf, f'{kind.value.lower()}-layout{layout}.pdf',
            kind, source, sample_key=key, evaluation_only=evaluation)
        inserted += int(created)
    return inserted


def seed_documents(factory, settings, output_dir=None):
    # Explicit developer export may create a new version; automatic startup never does.
    output_dir = Path(output_dir or settings.data_dir / 'sample_exports').resolve()
    recipes = document_recipes()
    # Capture a consistent DB view, then release the transaction before filesystem work.
    with factory() as session:
        inputs = [(recipe, document_data(session, recipe[0], recipe[1], recipe[5])) for recipe in recipes]
    manifest, inserted = [], 0
    for (tid, kind, source, layout, evaluation, action_id), data in inputs:
        pdf = render_pdf(data, kind, layout)
        digest = checksum(pdf)
        name = f"{kind.value.lower()}-layout{layout}-{digest[:12]}.pdf"
        sample = output_dir / ("evaluation" if evaluation else "primary") / tid / name
        sample.parent.mkdir(parents=True, exist_ok=True)
        if sample.exists():
            if checksum(sample.read_bytes()) != digest:
                raise RuntimeError("A generated sample path contains different bytes; refusing to overwrite it")
        else:
            with sample.open("xb") as handle:
                handle.write(pdf)
        document, created = save_document(factory, settings, tid, pdf, name, kind, source,
            sample_key=f"{tid}:{kind.value}:{action_id or 'none'}:layout{layout}", evaluation_only=evaluation)
        inserted += int(created)
        manifest.append(dict(transferId=tid, documentId=document.document_id, documentType=kind.value,
            documentSource=source.value, layout=layout, evaluationOnly=evaluation, checksumSha256=digest,
            samplePath=str(sample), storagePath=str(settings.data_dir / document.storage_path),
            inputFingerprint=checksum(json.dumps(data, sort_keys=True).encode())))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return inserted, manifest


def main():
    parser = argparse.ArgumentParser(description="Generate and register fictional PDFs from existing seeded data")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    settings = Settings.from_environment()
    engine = create_database_engine(settings)
    try:
        initialize_database(engine)
        count, manifest = seed_documents(session_factory(engine), settings, args.output_dir)
        print(f"Fictional PDFs ready: {len(manifest)}; new document records: {count}")
        for row in manifest:
            print(row["samplePath"])
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
