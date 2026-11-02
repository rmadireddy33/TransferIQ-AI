"""Deterministic selectable-text PDFs from a snapshot of authoritative mock records."""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, select

from backend.api.dependencies import fail
from backend.models.documents import DocumentType
from backend.models.entities import BrokerageAccount, BrokerageFirm, Client, PositionSnapshot, ReceivingTransferStagingPosition, Security, Transfer
from backend.models.reconciliation import CorporateAction, CostBasisRecord, SecurityIdentifierMapping
from backend.services.reconciliation import snapshot
from backend.services.reconciliation_rules import decimal_text
from backend.services.transfers import require_record

TEMPLATE_VERSION = "pdf-1"


def document_data(session, transfer_id, document_type, action_id=None):
    transfer = require_record(session, Transfer, transfer_id)
    client = require_record(session, Client, transfer.client_id)
    source_account = require_record(session, BrokerageAccount, transfer.source_account_id)
    destination_account = require_record(session, BrokerageAccount, transfer.destination_account_id)
    source_firm = require_record(session, BrokerageFirm, transfer.delivering_firm_id)
    receiving_firm = require_record(session, BrokerageFirm, transfer.receiving_firm_id)
    latest = session.scalar(select(func.max(PositionSnapshot.snapshot_date)).where(PositionSnapshot.account_id == source_account.account_id))
    positions = session.scalars(select(PositionSnapshot).where(PositionSnapshot.account_id == source_account.account_id,
        PositionSnapshot.snapshot_date == latest).order_by(PositionSnapshot.security_id, PositionSnapshot.position_id)).all()
    targets = session.scalars(select(ReceivingTransferStagingPosition).where(ReceivingTransferStagingPosition.transfer_id == transfer_id)
                              .order_by(ReceivingTransferStagingPosition.security_id)).all()
    ids = {row.security_id for row in positions + targets}
    securities = {s.security_id: snapshot(s) for s in session.scalars(select(Security).where(Security.security_id.in_(ids)))}
    data = dict(template_version=TEMPLATE_VERSION, transfer=snapshot(transfer), client=snapshot(client),
        source_account=snapshot(source_account), destination_account=snapshot(destination_account),
        delivering_firm=snapshot(source_firm), receiving_firm=snapshot(receiving_firm),
        statement_date=latest.isoformat() if latest else None, positions=[snapshot(row) for row in positions],
        securities=securities, targets=[snapshot(row) for row in targets])
    if document_type == DocumentType.ACCOUNT_STATEMENT:
        if not positions:
            fail(422, "source_snapshot_missing", "An account statement requires a stored source snapshot")
        data["mappings"] = [snapshot(m) for m in session.scalars(select(SecurityIdentifierMapping).where(
            SecurityIdentifierMapping.canonical_security_id.in_(ids)).order_by(SecurityIdentifierMapping.mapping_id))]
    if document_type == DocumentType.CORPORATE_ACTION_NOTICE:
        action = require_record(session, CorporateAction, action_id)
        if action.security_id not in ids:
            fail(422, "irrelevant_reference", "Corporate action is not relevant to the transfer's securities")
        data["action"] = snapshot(action)
    if document_type == DocumentType.COST_BASIS_STATEMENT:
        lots = session.scalars(select(CostBasisRecord).where(CostBasisRecord.transfer_id == transfer_id)
                               .order_by(CostBasisRecord.security_id, CostBasisRecord.cost_basis_id)).all()
        data["lots"] = [snapshot(lot) for lot in lots]
        data["missing_basis"] = sorted(ids - {lot.security_id for lot in lots})
    return data


def render_pdf(data, document_type, layout=1):
    if layout not in {1, 2, 3}:
        raise ValueError("Supported PDF layouts are 1, 2, and 3")
    buffer = BytesIO()
    palette = {1: ("#18354C", "#EEF3F7"), 2: ("#006D77", "#EAF6F4"), 3: ("#303742", "#F2F2F2")}
    ink, tint = map(colors.HexColor, palette[layout])
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleLocal", fontName="Helvetica-Bold", fontSize=21, leading=25, textColor=ink, spaceAfter=12))
    styles.add(ParagraphStyle(name="SectionLocal", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=ink, spaceBefore=14, spaceAfter=7))
    styles.add(ParagraphStyle(name="BodyLocal", fontName="Helvetica", fontSize=9, leading=13, spaceAfter=6))
    styles.add(ParagraphStyle(name="CellLocal", fontName="Helvetica", fontSize=8, leading=11))
    styles.add(ParagraphStyle(name="HeadLocal", fontName="Helvetica-Bold", fontSize=8, leading=11, textColor=colors.white))
    styles.add(ParagraphStyle(name="NumberLocal", parent=styles["CellLocal"], alignment=TA_RIGHT))
    width = letter[0] - 88
    story = []

    def text(value):
        return "Unavailable" if value is None or value == "" else str(value)

    def paragraph(value, style="BodyLocal"):
        return Paragraph(escape(text(value)), styles[style])

    def section(title):
        story.append(paragraph(title, "SectionLocal"))

    def fields(items):
        rows = [[paragraph(label, "CellLocal"), paragraph(value, "CellLocal")] for label, value in items]
        table = Table(rows, colWidths=[140 if layout != 2 else 170, width - (140 if layout != 2 else 170)], hAlign="LEFT")
        table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (0, -1), tint),
            ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, -1), (-1, -1), 0.5, ink)]))
        story.append(table)

    def grid(headers, rows, widths, number_cols=()):
        cells = [[paragraph(h, "HeadLocal") for h in headers]]
        cells.extend([[paragraph(value, "NumberLocal" if i in number_cols else "CellLocal") for i, value in enumerate(row)] for row in rows])
        table = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
        commands = [("BACKGROUND", (0, 0), (-1, 0), ink), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]
        if layout == 1:
            commands.append(("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CED8DF")))
        elif layout == 2:
            commands.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [tint, colors.white]))
        else:
            commands.append(("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#BBBBBB")))
        table.setStyle(TableStyle(commands))
        story.append(table)

    tid = data["transfer"]["transfer_id"]
    titles = {DocumentType.TRANSFER_REQUEST: "Brokerage Transfer Request",
              DocumentType.ACCOUNT_STATEMENT: ["Delivering Account Statement", "Portfolio Statement", "Custody Holdings Report"][layout-1],
              DocumentType.CORPORATE_ACTION_NOTICE: ["Corporate Action Notice", "Security Reference Bulletin", "Corporate Event Advisory"][layout-1],
              DocumentType.COST_BASIS_STATEMENT: "Cost Basis Statement"}
    story.append(paragraph(titles[document_type], "TitleLocal"))
    story.append(paragraph("SAMPLE / FICTIONAL - Demonstration records only. Not valid for trading, transfer, tax filing, or client authorization."))
    name = f"{data['client']['first_name']} {data['client']['last_name']}"
    if document_type == DocumentType.TRANSFER_REQUEST:
        section("Transfer instructions")
        fields([("Transfer ID", tid), ("Client name", name), ("Delivering firm", data["delivering_firm"]["firm_name"]),
            ("Receiving firm", data["receiving_firm"]["firm_name"]), ("Source account", data["source_account"]["account_number"]),
            ("Destination account", data["destination_account"]["account_number"]), ("Transfer type", data["transfer"]["transfer_type"]),
            ("Request date", data["transfer"]["created_at"][:10])])
        section("Fictional client authorization")
        story.append(paragraph("Sample authorization placeholder only. No real client signature or authorization is asserted. This form records a fictional transfer request and does not instruct any institution to move securities."))
    elif document_type == DocumentType.ACCOUNT_STATEMENT:
        section("Account overview" if layout == 2 else "Statement particulars")
        fields([("Transfer ID", tid), ("Client name", name), ("Brokerage firm", data["delivering_firm"]["firm_name"]),
                ("Account number", data["source_account"]["account_number"]), ("Statement date", data["statement_date"])])
        section("Holdings - original delivering snapshot")
        headers = ["Security ID", "Symbol", "Security name", "Security type", "Quantity"]
        rows = []
        for position in data["positions"]:
            security = data["securities"][position["security_id"]]
            rows.append([security["security_id"], security["symbol"], security["security_name"],
                         security["security_type"], decimal_text(position["quantity"])])
        grid(headers, rows, [64, 80, 167, 98, 115], number_cols=(4,))
        section("Statement notes")
        story.append(paragraph("Quantities reflect the stored source snapshot on the statement date. Later corporate actions are not applied to this statement. Receiving staging records are not settled custody holdings."))
        if data.get("mappings"):
            section("Identifier reference appendix - independent reference data")
            for mapping in data["mappings"]:
                fields([("Mapping reference", mapping["mapping_id"]), ("Canonical security", mapping["canonical_security_id"]),
                    ("Old identifier", mapping["old_identifier"]), ("New identifier", mapping["new_identifier"]),
                    ("Effective date", mapping["effective_date"]), ("Verified reference", "Yes" if mapping["verified"] else "No"),
                    ("Evidence reference", mapping["evidence_reference"])])
    elif document_type == DocumentType.CORPORATE_ACTION_NOTICE:
        action = data["action"]
        security = data["securities"][action["security_id"]]
        kind = "STOCK_SPLIT" if action["action_type"] == "SPLIT" else action["action_type"]
        if layout == 2:
            section(f"{action['numerator']}-for-{action['denominator']} | {kind}")
        elif layout == 3:
            section(f"Effective {action['effective_date']} - {security['security_name']}")
        fields([("Corporate action ID", action["corporate_action_id"]), ("Security ID", action["security_id"]),
            ("Security name", security["security_name"]), ("Action type", kind),
            ("Reference action code", action["action_type"]), ("Split ratio", f"{action['numerator']}-for-{action['denominator']}"),
            ("Numerator", action["numerator"]), ("Denominator", action["denominator"]),
            ("Effective date", action["effective_date"]), ("Notice date", action["created_at"][:10]),
            ("Verified reference", "Yes" if action["verified"] else "No"), ("Evidence reference", action["evidence_reference"])])
        section("Reference-data provenance")
        story.append(paragraph(f"Issued by the fictional security reference-data repository; associated with {tid} because the security is relevant to that transfer. It does not originate from the client's transfer request. Notice date reflects the reference record creation date."))
        story.append(paragraph("This sample notice describes stored reference evidence only. It does not modify positions, establish settlement, or authorize a correction."))
    elif document_type == DocumentType.COST_BASIS_STATEMENT:
        fields([("Transfer ID", tid), ("Client name", name), ("Receiving account", data["destination_account"]["account_number"])])
        section("Recorded tax lots - no inferred acquisition costs")
        rows = [[lot["security_id"], lot["acquisition_date"], decimal_text(lot["quantity"]),
                 decimal_text(lot["cost_basis_amount"]), lot["cost_basis_id"]] for lot in data["lots"]]
        rows.extend([[sid, None, None, None, "No authoritative lot record"] for sid in data["missing_basis"]])
        grid(["Security ID", "Acquisition date", "Acquired quantity", "Cost basis amount", "Lot reference"],
             rows, [67, 80, 93, 90, 194], number_cols=(2, 3))
        section("Completeness and evidence")
        story.append(paragraph("Unavailable means no authoritative value is stored; it is not zero. Currency is unavailable because the current cost-basis model does not record a currency. No tax lots, prices, or amounts have been invented or split for this document."))
        for lot in data["lots"]:
            story.append(paragraph(f"{lot['cost_basis_id']} | status: {lot['status']} | evidence: {text(lot['evidence_reference'])}"))
        if data["missing_basis"]:
            story.append(paragraph("Missing cost-basis records: " + ", ".join(data["missing_basis"]) + ". This is an investigation item independent of quantity reconciliation."))
    else:
        raise ValueError("Unsupported document type")

    def page_frame(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(ink)
        canvas.rect(44, 750, width, 3 if layout != 2 else 7, fill=1, stroke=0)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(44, 764, "TransferIQ AI  |  Fictional brokerage operations")
        canvas.setFont("Helvetica", 8)
        canvas.drawString(44, 29, f"SAMPLE / FICTIONAL  |  {tid}")
        canvas.drawRightString(568, 29, f"Page {doc.page}  |  Layout {layout}")
        canvas.restoreState()

    def deterministic_canvas(*args, **kwargs):
        return Canvas(*args, **{**kwargs, "invariant": 1, "pageCompression": 1})

    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=44, rightMargin=44,
                            topMargin=58, bottomMargin=48, title=titles[document_type],
                            author="TransferIQ AI - Fictional Sample Repository")
    doc.build(story, onFirstPage=page_frame, onLaterPages=page_frame, canvasmaker=deterministic_canvas)
    return buffer.getvalue()
