"""Optional developer-only PDFium rendering; outputs live under DATA_DIR."""
import json
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw

from backend.core.config import Settings
from backend.database.session import create_database_engine, session_factory
from backend.models.documents import DocumentType
from backend.services.pdf_generation import document_data, render_pdf


def main():
    settings = Settings.from_environment()
    manifest = json.loads((settings.data_dir / 'sample_exports/manifest.json').read_text(encoding='utf-8'))
    output = settings.data_dir / 'verification/pdf-qa'
    output.mkdir(parents=True, exist_ok=True)
    engine = create_database_engine(settings)
    try:
        with session_factory(engine)() as session:
            data = document_data(session, "TRF-1002", DocumentType.ACCOUNT_STATEMENT)
        # QA-only page-break stress sample, never registered as financial evidence.
        data["positions"] *= 15
        stress = output / "layout-stress-only.pdf"
        stress.write_bytes(render_pdf(data, DocumentType.ACCOUNT_STATEMENT))
    finally:
        engine.dispose()
    paths = [Path(row["samplePath"]) for row in manifest] + [stress]
    thumbnails = []
    for index, path in enumerate(paths):
        with pdfium.PdfDocument(path) as document:
            for page_number in range(len(document)):
                page = document[page_number]
                bitmap = page.render(scale=1.5)
                image = bitmap.to_pil().copy()
                page_path = output / f"document-{index+1:02}-page-{page_number+1:02}.png"
                image.save(page_path)
                image.thumbnail((367, 475))
                card = Image.new("RGB", (387, 505), "#dce2e5")
                card.paste(image, ((387-image.width)//2, 24))
                ImageDraw.Draw(card).text((8, 5), f"Doc {index+1:02} / page {page_number+1} / {path.parent.name}", fill="black")
                thumbnails.append(card)
                bitmap.close()
                page.close()
    for start in range(0, len(thumbnails), 12):
        group = thumbnails[start:start+12]
        sheet = Image.new("RGB", (387*4, 505*((len(group)+3)//4)), "white")
        for index, thumbnail in enumerate(group):
            sheet.paste(thumbnail, ((index % 4)*387, (index//4)*505))
        target = output / f"contact-{start//12+1}.png"
        sheet.save(target)
        print(target)
    print(f"Rendered {len(paths)} PDFs / {len(thumbnails)} pages for visual review.")


if __name__ == "__main__":
    main()
