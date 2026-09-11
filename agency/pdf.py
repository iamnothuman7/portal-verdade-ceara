from html import escape
from io import BytesIO
from pathlib import Path
import re

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle


BRAND_RED = colors.HexColor("#B60000")
INK = colors.HexColor("#171717")
MUTED = colors.HexColor("#62626A")
LIGHT = colors.HexColor("#F3F3F4")


def _safe(value):
    return escape(str(value or "-"))


def _currency(value):
    formatted = f"{value:,.2f}"
    return "R$ " + formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def _page_brand(canvas, document):
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#080808"))
    canvas.rect(0, height - 28 * mm, width, 28 * mm, fill=1, stroke=0)
    logo_path = Path(settings.BASE_DIR) / "static" / "images" / "logo-portal-verdade-ceara.png"
    organization = document.organization
    if organization.logo and Path(organization.logo.path).exists():
        logo_path = Path(organization.logo.path)
    if logo_path.exists():
        canvas.drawImage(
            str(logo_path),
            16 * mm,
            height - 27 * mm,
            width=62 * mm,
            height=25 * mm,
            preserveAspectRatio=True,
            anchor="w",
            mask="auto",
        )
    canvas.setStrokeColor(colors.HexColor(organization.accent_color))
    canvas.setLineWidth(2)
    canvas.line(0, height - 28 * mm, width, height - 28 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    label = getattr(document, "footer_label", "Documento eletrônico")
    footer = f"{organization.pdf_footer or organization.name} | {label} | Página {document.page}"
    while canvas.stringWidth(footer, "Helvetica", 8) > width - 24 * mm and len(footer) > 45:
        footer = footer[:len(footer) // 2 - 2] + "…" + footer[len(footer) // 2 + 3:]
    canvas.drawCentredString(width / 2, 10 * mm, footer)
    company_line = " · ".join(v for v in (organization.tax_id, organization.email, organization.phone) if v)
    canvas.setFont("Helvetica", 7)
    if company_line:
        canvas.drawCentredString(width / 2, 6 * mm, company_line[:135])
    canvas.restoreState()


def _portal_document(output, *, title, author="Portal Verdade Ceará", right_margin=18 * mm, left_margin=18 * mm):
    from .models import OrganizationSettings
    organization = OrganizationSettings.current()
    document = BaseDocTemplate(
        output,
        pagesize=A4,
        rightMargin=right_margin,
        leftMargin=left_margin,
        topMargin=36 * mm,
        bottomMargin=18 * mm,
        title=title,
        author=organization.name,
    )
    document.organization = organization
    frame = Frame(
        document.leftMargin,
        document.bottomMargin,
        document.width,
        document.height,
        id="portal-content",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    document.addPageTemplates(PageTemplate(id="portal-letterhead", frames=(frame,), onPage=_page_brand))
    return document


def build_contract_pdf(contract):
    output = BytesIO()
    document = _portal_document(output, title=f"{contract.title} - {contract.client.trade_name}")
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "PortalTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=25,
        textColor=INK,
        alignment=TA_CENTER,
        spaceAfter=14,
    )
    eyebrow = ParagraphStyle(
        "PortalEyebrow",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=BRAND_RED,
        alignment=TA_CENTER,
        spaceAfter=7,
    )
    heading = ParagraphStyle(
        "PortalHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=INK,
        spaceBefore=12,
        spaceAfter=8,
    )
    body = ParagraphStyle(
        "PortalBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=INK,
        alignment=TA_JUSTIFY,
        spaceAfter=7,
    )
    small = ParagraphStyle("PortalSmall", parent=body, fontSize=8, leading=11, textColor=MUTED)

    story = [
        Paragraph("CONTRATO DE PRESTAÇÃO DE SERVIÇOS", eyebrow),
        Paragraph(_safe(contract.title), title),
    ]

    metadata = [
        [Paragraph("CONTRATANTE", small), Paragraph("VIGÊNCIA", small), Paragraph("VALOR MENSAL", small)],
        [
            Paragraph(f"<b>{_safe(contract.client.legal_name or contract.client.trade_name)}</b><br/>{_safe(contract.client.tax_id or 'Documento não informado')}", body),
            Paragraph(f"<b>{contract.start_date:%d/%m/%Y}</b><br/>até {contract.end_date:%d/%m/%Y}", body),
            Paragraph(f"<b>{_safe(_currency(contract.monthly_value))}</b><br/>vencimento dia {contract.billing_day}", body),
        ],
    ]
    meta_table = Table(metadata, colWidths=[76 * mm, 48 * mm, 48 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D8D8DC")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E2E5")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([meta_table, Spacer(1, 6 * mm), Paragraph("PACOTE MENSAL CONTRATADO", heading)])

    quota_rows = [["Material", "Quantidade mensal", "Detalhes"]]
    for quota in contract.quotas.all():
        quota_rows.append([quota.get_kind_display(), str(quota.quantity), quota.notes or "-"])
    if len(quota_rows) == 1:
        quota_rows.append(["Pacote personalizado", "Conforme demanda", "Descrito nos termos"])
    quota_table = Table(quota_rows, colWidths=[65 * mm, 48 * mm, 59 * mm], repeatRows=1)
    quota_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111113")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D8D8DC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([quota_table, Spacer(1, 5 * mm), Paragraph("TERMOS E CONDIÇÕES", heading)])
    term_lines = [line.strip() for line in contract.terms.splitlines() if line.strip()]
    index = 0
    while index < len(term_lines):
        line = term_lines[index]
        is_heading = bool(re.match(r"^\d+\.\s", line)) or (line.isupper() and len(line) < 100)
        if is_heading and index + 1 < len(term_lines):
            clause_heading = ParagraphStyle("PortalClause", parent=body, fontName="Helvetica-Bold", spaceBefore=7, spaceAfter=5)
            story.append(KeepTogether([Paragraph(_safe(line), clause_heading), Paragraph(_safe(term_lines[index + 1]), body)]))
            index += 2
        else:
            story.append(Paragraph(_safe(line), body))
            index += 1

    if contract.signed_at:
        signed_at = timezone.localtime(contract.signed_at)
        proof = [
            Paragraph("COMPROVANTE DE ASSINATURA ELETRÔNICA", heading),
            Paragraph(
                f"Assinado por <b>{_safe(contract.signer_name)}</b>, documento {_safe(contract.signer_tax_id)}, "
                f"em {signed_at:%d/%m/%Y às %H:%M}.<br/>"
                f"Identificador criptográfico: {_safe(contract.signature_hash)}",
                small,
            ),
        ]
    else:
        proof = [
            Spacer(1, 8 * mm),
            Paragraph("ASSINATURAS", heading),
            Spacer(1, 8 * mm),
            Table(
                [["__________________________________", "__________________________________"], [Paragraph(_safe(document.organization.legal_name or document.organization.name), small), Paragraph(_safe(contract.client.legal_name or contract.client.trade_name), small)]],
                colWidths=[86 * mm, 86 * mm],
                style=TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9)]),
            ),
        ]
    story.append(KeepTogether(proof))
    document.build(story)
    return output.getvalue()


def build_financial_report_pdf(context):
    output = BytesIO()
    month = context["month"]
    document = _portal_document(
        output,
        title=f"Relatório financeiro - {month:%m/%Y}",
        right_margin=16 * mm,
        left_margin=16 * mm,
    )
    document.footer_label = "Relatório financeiro confidencial"
    styles = getSampleStyleSheet()
    title = ParagraphStyle("ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22, leading=25, textColor=INK, spaceAfter=4)
    subtitle = ParagraphStyle("ReportSubtitle", parent=styles["Normal"], fontSize=9, leading=13, textColor=MUTED, spaceAfter=16)
    label = ParagraphStyle("ReportLabel", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=MUTED)
    value = ParagraphStyle("ReportValue", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=INK)
    small = ParagraphStyle("ReportSmall", parent=styles["Normal"], fontSize=7.5, leading=10, textColor=INK)

    story = [
        Paragraph("RELATÓRIO FINANCEIRO", title),
        Paragraph(f"Competência {month:%m/%Y} | Gerado em {timezone.localtime():%d/%m/%Y às %H:%M}", subtitle),
    ]
    metrics = [
        [Paragraph("ENTRADAS PREVISTAS", label), Paragraph("SAÍDAS PREVISTAS", label), Paragraph("SALDO PREVISTO", label)],
        [Paragraph(_currency(context["projected_income"]), value), Paragraph(_currency(context["projected_expense"]), value), Paragraph(_currency(context["projected_balance"]), value)],
        [Paragraph("ENTRADAS REALIZADAS", label), Paragraph("SAÍDAS REALIZADAS", label), Paragraph("SALDO REALIZADO", label)],
        [Paragraph(_currency(context["realized_income"]), value), Paragraph(_currency(context["realized_expense"]), value), Paragraph(_currency(context["realized_balance"]), value)],
    ]
    metric_table = Table(metrics, colWidths=[59 * mm, 59 * mm, 59 * mm])
    metric_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#FFF0F0")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D8D8DC")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E2E5")),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([metric_table, Spacer(1, 7 * mm), Paragraph("LANÇAMENTOS DA COMPETÊNCIA", ParagraphStyle("ReportHeading", parent=title, fontSize=12, leading=15, spaceAfter=8))])

    rows = [["Vencimento", "Descrição / cliente", "Tipo", "Situação", "Valor"]]
    for entry in context["entries"]:
        description = _safe(entry.description)
        client = _safe(entry.client or "Sem cliente vinculado")
        rows.append(
            [
                entry.due_date.strftime("%d/%m/%Y"),
                Paragraph(f"<b>{description}</b><br/><font color='#62626A'>{client}</font>", small),
                entry.get_kind_display(),
                entry.get_status_display(),
                _currency(entry.amount),
            ]
        )
    if len(rows) == 1:
        rows.append(["-", "Nenhum lançamento para os filtros selecionados.", "-", "-", "R$ 0,00"])
    entries_table = Table(rows, colWidths=[27 * mm, 68 * mm, 24 * mm, 31 * mm, 27 * mm], repeatRows=1)
    entries_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111113")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8D8DC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend(
        [
            entries_table,
            Spacer(1, 6 * mm),
            Paragraph(
                f"Pendentes a receber: <b>{_currency(context['pending_income'])}</b> | "
                f"Pendentes a pagar: <b>{_currency(context['pending_expense'])}</b> | "
                f"Vencidos: <b>{context['overdue_count']}</b> lançamento(s), total de <b>{_currency(context['overdue_total'])}</b>.",
                small,
            ),
        ]
    )
    document.build(story)
    return output.getvalue()
