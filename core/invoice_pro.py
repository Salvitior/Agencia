import os
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT


def _hex_color(value):
    return colors.HexColor(value)


def _safe_text(value, fallback="N/A"):
    text = str(value).strip() if value is not None else ""
    return text or fallback


def _safe_invoice_number(value):
    raw = _safe_text(value, "SIN-NUMERO")
    return re.sub(r"[^A-Za-z0-9_-]", "_", raw)


def generar_factura_pdf(datos):
    if not isinstance(datos, dict):
        raise ValueError("'datos' debe ser un diccionario")

    folder = "facturas"
    os.makedirs(folder, exist_ok=True)

    numero_factura = _safe_invoice_number(datos.get('numero_factura'))
    fecha = _safe_text(datos.get('fecha'))
    cliente = _safe_text(datos.get('cliente'))
    email_cliente = _safe_text(datos.get('email_cliente'))
    viaje = _safe_text(datos.get('viaje'))
    monto = _safe_text(datos.get('monto'), "0.00")

    pasajeros = datos.get('pasajeros') or []
    if not isinstance(pasajeros, list):
        pasajeros = []

    ruta_pdf = os.path.join(folder, f"factura_{numero_factura}.pdf")
    doc = SimpleDocTemplate(ruta_pdf, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()

    estilo_titulo = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, textColor=_hex_color("#1e293b"), spaceAfter=10)
    estilo_subtitulo = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, textColor=colors.grey)
    estilo_label = ParagraphStyle('Label', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', textColor=colors.indigo)

    elements = []

    col1, col2 = [300, 230]
    header_data = [[
        Paragraph("<b>COSMIN</b><font color='#6366f1'>PRO</font>", estilo_titulo),
        Paragraph(f"FACTURA: {numero_factura}<br/>FECHA: {fecha}", ParagraphStyle('Right', parent=styles['Normal'], alignment=TA_RIGHT))
    ]]
    t_header = Table(header_data, colWidths=[col1, col2])
    elements.append(t_header)
    elements.append(Paragraph("Servicios de viaje y gestión integral", estilo_subtitulo))
    elements.append(HRFlowable(width="100%", thickness=1, color=_hex_color("#e2e8f0"), spaceBefore=10, spaceAfter=20))

    info_data = [[
        Paragraph("<b>EMISOR:</b><br/>Cosmin Viajes S.L.<br/>CIF: B12345678<br/>Calle Gran Vía 1, Madrid", styles['Normal']),
        Paragraph(f"<b>CLIENTE:</b><br/>{cliente}<br/>Email: {email_cliente}", styles['Normal'])
    ]]
    t_info = Table(info_data, colWidths=[265, 265])
    elements.append(t_info)
    elements.append(Spacer(1, 30))

    elements.append(Paragraph("DETALLES DEL ITINERARIO", estilo_label))
    elements.append(Spacer(1, 5))
    viaje_data = [
        [Paragraph("<b>Descripción del Servicio</b>", styles['Normal']), Paragraph("<b>Monto</b>", styles['Normal'])],
        [Paragraph(f"{viaje}<br/><font size=8 color='grey'>Vuelo + Estancia Confirmada</font>", styles['Normal']), f"{monto} €"]
    ]
    t_viaje = Table(viaje_data, colWidths=[400, 130])
    t_viaje.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), _hex_color("#f8fafc")),
        ('TEXTCOLOR', (0, 0), (-1, 0), _hex_color("#64748b")),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, _hex_color("#e2e8f0"))
    ]))
    elements.append(t_viaje)
    elements.append(Spacer(1, 25))

    elements.append(Paragraph("PASAJEROS Y DOCUMENTACIÓN", estilo_label))
    elements.append(Spacer(1, 5))
    pax_rows = [["Nombre Completo", "Identificación (DNI/NIE)"]]
    for pasajero in pasajeros:
        nombre = _safe_text((pasajero or {}).get('nombre'))
        dni = _safe_text((pasajero or {}).get('dni'))
        pax_rows.append([nombre, dni])

    if len(pax_rows) == 1:
        pax_rows.append(["Sin datos de pasajeros", "-"])

    t_pax = Table(pax_rows, colWidths=[265, 265])
    t_pax.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), _hex_color("#6366f1")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, _hex_color("#e2e8f0")),
        ('PADDING', (0, 0), (-1, -1), 8)
    ]))
    elements.append(t_pax)

    elements.append(Spacer(1, 40))
    total_data = [["", "TOTAL FACTURADO:", f"{monto} €"]]
    t_total = Table(total_data, colWidths=[300, 130, 100])
    t_total.setStyle(TableStyle([
        ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (2, 0), (2, 0), 14),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('TEXTCOLOR', (2, 0), (2, 0), colors.indigo)
    ]))
    elements.append(t_total)

    doc.build(elements)
    return ruta_pdf