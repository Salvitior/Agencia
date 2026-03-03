"""
Generador de billetes electrónicos (e-ticket) y facturas mejoradas en PDF.

- E-ticket con código de barras, datos de vuelo, pasajeros, equipaje
- Factura con datos fiscales completos, IVA, desglose de servicios
- Tarjeta de embarque (boarding pass) básica
"""

import os
import json
import logging
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    HRFlowable, Image, KeepTogether, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

logger = logging.getLogger(__name__)

# Datos de la agencia (configurables por env)
AGENCIA = {
    'nombre': os.getenv('AGENCIA_NOMBRE', 'Viatges Carcaixent S.L.'),
    'cif': os.getenv('AGENCIA_CIF', 'B12345678'),
    'direccion': os.getenv('AGENCIA_DIRECCION', 'Calle Mayor 1, 46740 Carcaixent, Valencia'),
    'telefono': os.getenv('AGENCIA_TELEFONO', '+34 962 43 00 00'),
    'email': os.getenv('AGENCIA_EMAIL', 'info@viatgescarcaixent.com'),
    'web': os.getenv('APP_URL', 'https://viatgescarcaixent.com'),
    'licencia': os.getenv('AGENCIA_LICENCIA', 'CV-XXX'),
    'iban': os.getenv('AGENCIA_IBAN', 'ES00 0000 0000 0000 0000 0000'),
}


def _estilos():
    """Crea estilos personalizados para los PDFs"""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'TituloAgencia', parent=styles['Heading1'],
        fontSize=22, textColor=colors.hexColor("#1e293b"),
        spaceAfter=5, fontName='Helvetica-Bold',
    ))
    styles.add(ParagraphStyle(
        'Subtitulo', parent=styles['Normal'],
        fontSize=10, textColor=colors.hexColor("#64748b"),
    ))
    styles.add(ParagraphStyle(
        'SeccionLabel', parent=styles['Normal'],
        fontSize=9, fontName='Helvetica-Bold',
        textColor=colors.hexColor("#6366f1"), spaceBefore=15, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        'ValorGrande', parent=styles['Normal'],
        fontSize=18, fontName='Helvetica-Bold',
        textColor=colors.hexColor("#1e293b"),
    ))
    styles.add(ParagraphStyle(
        'Derecha', parent=styles['Normal'],
        alignment=TA_RIGHT,
    ))
    styles.add(ParagraphStyle(
        'Centro', parent=styles['Normal'],
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'Pie', parent=styles['Normal'],
        fontSize=7, textColor=colors.hexColor("#94a3b8"),
        alignment=TA_CENTER,
    ))
    return styles


# ==============================
# E-TICKET (BILLETE ELECTRÓNICO)
# ==============================

def generar_eticket_pdf(reserva_data):
    """
    Genera un billete electrónico PDF profesional.
    
    Args:
        reserva_data: dict con:
            - codigo_reserva, booking_reference
            - pasajeros: [{given_name, family_name, tipo_pasajero, documento}]
            - datos_vuelo: {origen, destino, fecha_ida, hora_salida, hora_llegada,
                           aerolinea, numero_vuelo, clase, escalas, duracion}
            - vuelo_vuelta: (opcional) mismos campos
            - precio_total, moneda
            - ticket_numbers: [str]
            - extras: [{tipo, descripcion}]
    """
    folder = "etickets"
    os.makedirs(folder, exist_ok=True)

    codigo = reserva_data.get('codigo_reserva', 'UNKNOWN')
    ruta_pdf = f"{folder}/eticket_{codigo}.pdf"

    doc = SimpleDocTemplate(
        ruta_pdf, pagesize=A4,
        rightMargin=25*mm, leftMargin=25*mm,
        topMargin=20*mm, bottomMargin=20*mm,
    )
    styles = _estilos()
    elements = []

    # --- CABECERA ---
    elements.append(Paragraph(
        f"<b>{AGENCIA['nombre']}</b>",
        styles['TituloAgencia']
    ))
    elements.append(Paragraph(
        f"Licencia {AGENCIA['licencia']} | {AGENCIA['telefono']} | {AGENCIA['web']}",
        styles['Subtitulo']
    ))
    elements.append(HRFlowable(
        width="100%", thickness=2,
        color=colors.hexColor("#6366f1"),
        spaceBefore=8, spaceAfter=15,
    ))

    # --- TIPO DE DOCUMENTO ---
    elements.append(Paragraph("BILLETE ELECTRÓNICO / E-TICKET", ParagraphStyle(
        'eticket_title', parent=styles['Normal'],
        fontSize=14, fontName='Helvetica-Bold',
        textColor=colors.hexColor("#6366f1"),
        alignment=TA_CENTER, spaceBefore=5, spaceAfter=15,
    )))

    # --- LOCALIZADORES ---
    booking_ref = reserva_data.get('booking_reference', 'Pendiente')
    header_data = [[
        Paragraph(f"<b>Código Reserva:</b><br/><font size=16 color='#6366f1'>{codigo}</font>", styles['Normal']),
        Paragraph(f"<b>Localizador Aerolínea:</b><br/><font size=16 color='#10b981'>{booking_ref}</font>", styles['Normal']),
        Paragraph(f"<b>Fecha Emisión:</b><br/>{datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']),
    ]]
    t = Table(header_data, colWidths=[170, 170, 170])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.hexColor("#f8fafc")),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 1, colors.hexColor("#e2e8f0")),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 15))

    # --- DATOS DE VUELO IDA ---
    datos_vuelo = reserva_data.get('datos_vuelo', {})
    elements.append(Paragraph("✈ VUELO DE IDA", styles['SeccionLabel']))

    vuelo_data = [[
        Paragraph("<b>Origen</b>", styles['Centro']),
        Paragraph("", styles['Centro']),
        Paragraph("<b>Destino</b>", styles['Centro']),
    ], [
        Paragraph(f"<font size=16><b>{datos_vuelo.get('origen', 'N/A')}</b></font>", styles['Centro']),
        Paragraph("→", ParagraphStyle('arrow', parent=styles['Normal'], fontSize=20, alignment=TA_CENTER)),
        Paragraph(f"<font size=16><b>{datos_vuelo.get('destino', 'N/A')}</b></font>", styles['Centro']),
    ], [
        Paragraph(f"{datos_vuelo.get('hora_salida', '')}", styles['Centro']),
        Paragraph(f"{datos_vuelo.get('fecha_ida', '')}", styles['Centro']),
        Paragraph(f"{datos_vuelo.get('hora_llegada', '')}", styles['Centro']),
    ]]

    tv = Table(vuelo_data, colWidths=[170, 170, 170])
    tv.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 1, colors.hexColor("#e2e8f0")),
        ('BACKGROUND', (0, 0), (-1, 0), colors.hexColor("#eef2ff")),
    ]))
    elements.append(tv)

    # Detalles del vuelo
    detalles = [[
        f"Aerolínea: {datos_vuelo.get('aerolinea', 'N/A')}",
        f"Vuelo: {datos_vuelo.get('numero_vuelo', 'N/A')}",
        f"Clase: {datos_vuelo.get('clase', 'Economy')}",
        f"Duración: {datos_vuelo.get('duracion', 'N/A')}",
    ]]
    td = Table(detalles, colWidths=[127, 127, 127, 127])
    td.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.hexColor("#475569")),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (0, 0), (-1, -1), colors.hexColor("#f1f5f9")),
    ]))
    elements.append(td)

    # --- VUELO DE VUELTA (si es ida y vuelta) ---
    vuelta = reserva_data.get('vuelo_vuelta')
    if vuelta:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("✈ VUELO DE VUELTA", styles['SeccionLabel']))

        vuelta_data = [[
            Paragraph(f"<font size=16><b>{vuelta.get('origen', 'N/A')}</b></font>", styles['Centro']),
            Paragraph("→", ParagraphStyle('arrow2', parent=styles['Normal'], fontSize=20, alignment=TA_CENTER)),
            Paragraph(f"<font size=16><b>{vuelta.get('destino', 'N/A')}</b></font>", styles['Centro']),
        ], [
            Paragraph(f"{vuelta.get('hora_salida', '')}", styles['Centro']),
            Paragraph(f"{vuelta.get('fecha', '')}", styles['Centro']),
            Paragraph(f"{vuelta.get('hora_llegada', '')}", styles['Centro']),
        ]]

        tvv = Table(vuelta_data, colWidths=[170, 170, 170])
        tvv.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('BOX', (0, 0), (-1, -1), 1, colors.hexColor("#e2e8f0")),
        ]))
        elements.append(tvv)

    # --- PASAJEROS ---
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("👥 PASAJEROS", styles['SeccionLabel']))

    pasajeros = reserva_data.get('pasajeros', [])
    ticket_numbers = reserva_data.get('ticket_numbers', [])
    
    pax_header = [["Nº", "Nombre Completo", "Tipo", "Documento", "Nº Ticket"]]
    for i, pax in enumerate(pasajeros):
        nombre = f"{pax.get('given_name', '')} {pax.get('family_name', '')}"
        tipo = pax.get('type', pax.get('tipo_pasajero', 'Adulto'))
        doc_num = pax.get('identity_document_number', pax.get('documento', '***'))
        ticket = ticket_numbers[i] if i < len(ticket_numbers) else 'Pendiente'
        pax_header.append([str(i + 1), nombre, tipo.capitalize(), doc_num, ticket])

    tp = Table(pax_header, colWidths=[30, 160, 60, 100, 160])
    tp.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (-1, 0), colors.hexColor("#6366f1")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.hexColor("#e2e8f0")),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.hexColor("#f8fafc")]),
    ]))
    elements.append(tp)

    # --- EXTRAS / SERVICIOS ---
    extras = reserva_data.get('extras', [])
    if extras:
        elements.append(Spacer(1, 15))
        elements.append(Paragraph("🧳 SERVICIOS INCLUIDOS", styles['SeccionLabel']))
        
        extras_rows = [["Servicio", "Detalle", "Precio"]]
        for extra in extras:
            extras_rows.append([
                extra.get('tipo', ''),
                extra.get('descripcion', ''),
                f"{extra.get('precio', 0)}€",
            ])
        
        te = Table(extras_rows, colWidths=[150, 250, 110])
        te.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, 0), colors.hexColor("#f1f5f9")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.hexColor("#e2e8f0")),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
        ]))
        elements.append(te)

    # --- PRECIO TOTAL ---
    elements.append(Spacer(1, 20))
    moneda = reserva_data.get('moneda', 'EUR')
    precio = reserva_data.get('precio_total', 0)
    total_data = [["", "PRECIO TOTAL:", f"{precio} {moneda}"]]
    tt = Table(total_data, colWidths=[300, 120, 90])
    tt.setStyle(TableStyle([
        ('FONTNAME', (1, 0), (2, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (2, 0), (2, 0), 16),
        ('ALIGN', (1, 0), (2, 0), 'RIGHT'),
        ('TEXTCOLOR', (2, 0), (2, 0), colors.hexColor("#6366f1")),
        ('LINEABOVE', (1, 0), (2, 0), 2, colors.hexColor("#6366f1")),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(tt)

    # --- INFORMACIÓN IMPORTANTE ---
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("📋 INFORMACIÓN IMPORTANTE", styles['SeccionLabel']))
    info_items = [
        "• Preséntese en el aeropuerto con al menos 2 horas de antelación (3h vuelos internacionales).",
        "• Realice el check-in online 24-48h antes del vuelo para evitar cargos adicionales.",
        "• Lleve documento de identidad/pasaporte válido y en vigor.",
        "• Consulte las restricciones de equipaje de su aerolínea.",
        "• Este billete electrónico es su confirmación de reserva. Guárdelo.",
        f"• Para consultas: {AGENCIA['telefono']} o {AGENCIA['email']}",
    ]
    for item in info_items:
        elements.append(Paragraph(item, ParagraphStyle(
            'info_item', parent=styles['Normal'],
            fontSize=8, textColor=colors.hexColor("#475569"),
            spaceBefore=2,
        )))

    # --- PIE DE PÁGINA ---
    elements.append(Spacer(1, 25))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.hexColor("#e2e8f0")))
    elements.append(Paragraph(
        f"{AGENCIA['nombre']} | CIF: {AGENCIA['cif']} | {AGENCIA['direccion']}",
        styles['Pie']
    ))
    elements.append(Paragraph(
        "Documento generado electrónicamente. No requiere firma.",
        styles['Pie']
    ))

    doc.build(elements)
    logger.info(f"📄 E-ticket generado: {ruta_pdf}")
    return ruta_pdf


# ==============================
# FACTURA MEJORADA CON DATOS FISCALES
# ==============================

def generar_factura_completa(datos):
    """
    Genera una factura PDF completa con:
    - Datos fiscales del emisor y receptor
    - Número secuencial de factura
    - Desglose de servicios con IVA
    - Base imponible, IVA, total
    - IBAN para transferencia
    - Información legal (LSSI)
    
    Args:
        datos: {
            numero_factura, fecha, fecha_vencimiento,
            cliente: {nombre, cif, direccion, email},
            conceptos: [{descripcion, cantidad, precio_unitario, iva_pct}],
            reserva: {codigo, tipo_viaje, origen, destino},
            pagada, metodo_pago,
        }
    """
    folder = "facturas"
    os.makedirs(folder, exist_ok=True)

    num_factura = datos.get('numero_factura', f"FAC-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    ruta_pdf = f"{folder}/factura_{num_factura}.pdf"

    doc = SimpleDocTemplate(
        ruta_pdf, pagesize=A4,
        rightMargin=25*mm, leftMargin=25*mm,
        topMargin=20*mm, bottomMargin=25*mm,
    )
    styles = _estilos()
    elements = []

    # --- CABECERA ---
    header = [[
        Paragraph(f"<b>{AGENCIA['nombre']}</b><br/>"
                  f"<font size=8>CIF: {AGENCIA['cif']}<br/>"
                  f"{AGENCIA['direccion']}<br/>"
                  f"Tel: {AGENCIA['telefono']}<br/>"
                  f"{AGENCIA['email']}</font>",
                  styles['Normal']),
        Paragraph(f"<b><font size=18 color='#6366f1'>FACTURA</font></b><br/><br/>"
                  f"<b>Nº:</b> {num_factura}<br/>"
                  f"<b>Fecha:</b> {datos.get('fecha', datetime.now().strftime('%d/%m/%Y'))}<br/>"
                  f"<b>Vencimiento:</b> {datos.get('fecha_vencimiento', 'Pagada')}",
                  styles['Derecha']),
    ]]
    t_header = Table(header, colWidths=[270, 240])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t_header)
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.hexColor("#6366f1"), spaceBefore=10, spaceAfter=15))

    # --- DATOS DEL CLIENTE ---
    cliente = datos.get('cliente', {})
    elements.append(Paragraph("DATOS DEL CLIENTE", styles['SeccionLabel']))

    cliente_info = [[
        Paragraph(f"<b>{cliente.get('nombre', 'N/A')}</b><br/>"
                  f"CIF/DNI: {cliente.get('cif', 'N/A')}<br/>"
                  f"Dirección: {cliente.get('direccion', 'N/A')}<br/>"
                  f"Email: {cliente.get('email', 'N/A')}",
                  styles['Normal']),
    ]]
    tc = Table(cliente_info, colWidths=[510])
    tc.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.hexColor("#f8fafc")),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.hexColor("#e2e8f0")),
    ]))
    elements.append(tc)
    elements.append(Spacer(1, 15))

    # --- REFERENCIA DE RESERVA ---
    reserva = datos.get('reserva', {})
    if reserva:
        elements.append(Paragraph("REFERENCIA", styles['SeccionLabel']))
        ref_data = [[
            f"Reserva: {reserva.get('codigo', 'N/A')}",
            f"Tipo: {reserva.get('tipo_viaje', 'Vuelo')}",
            f"Ruta: {reserva.get('origen', '')} → {reserva.get('destino', '')}",
        ]]
        tr = Table(ref_data, colWidths=[170, 120, 220])
        tr.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, -1), colors.hexColor("#eef2ff")),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.hexColor("#c7d2fe")),
        ]))
        elements.append(tr)
        elements.append(Spacer(1, 15))

    # --- CONCEPTOS / LÍNEAS DE FACTURA ---
    elements.append(Paragraph("DESGLOSE DE SERVICIOS", styles['SeccionLabel']))

    conceptos = datos.get('conceptos', [])
    concepto_header = [["Descripción", "Cant.", "P. Unitario", "IVA %", "Subtotal"]]
    
    base_imponible = 0
    total_iva = 0
    
    for concepto in conceptos:
        cantidad = concepto.get('cantidad', 1)
        precio_unit = concepto.get('precio_unitario', 0)
        iva_pct = concepto.get('iva_pct', 0)  # Viajes = 0% IVA (régimen especial)
        subtotal = cantidad * precio_unit
        iva_cantidad = subtotal * (iva_pct / 100)
        
        base_imponible += subtotal
        total_iva += iva_cantidad
        
        concepto_header.append([
            Paragraph(concepto.get('descripcion', ''), ParagraphStyle('desc', parent=styles['Normal'], fontSize=8)),
            str(cantidad),
            f"{precio_unit:.2f} €",
            f"{iva_pct}%",
            f"{subtotal:.2f} €",
        ])
    
    total = base_imponible + total_iva

    tcon = Table(concepto_header, colWidths=[220, 40, 80, 50, 120])
    tcon.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (-1, 0), colors.hexColor("#6366f1")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.hexColor("#e2e8f0")),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.hexColor("#f8fafc")]),
    ]))
    elements.append(tcon)

    # --- TOTALES ---
    elements.append(Spacer(1, 10))
    totales_data = [
        ["", "Base Imponible:", f"{base_imponible:.2f} €"],
        ["", f"IVA:", f"{total_iva:.2f} €"],
        ["", "TOTAL:", f"{total:.2f} €"],
    ]
    
    # Nota sobre régimen especial de agencias de viajes
    if all(c.get('iva_pct', 0) == 0 for c in conceptos):
        totales_data.insert(0, ["", Paragraph(
            "<i><font size=7>Operación sujeta al Régimen Especial de Agencias de Viaje (Art. 141-147 Ley 37/1992 del IVA)</font></i>",
            styles['Derecha']
        ), ""])
    
    tt = Table(totales_data, colWidths=[250, 140, 120])
    tt.setStyle(TableStyle([
        ('FONTNAME', (1, -1), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (2, -1), (2, -1), 14),
        ('ALIGN', (1, 0), (2, -1), 'RIGHT'),
        ('TEXTCOLOR', (2, -1), (2, -1), colors.hexColor("#6366f1")),
        ('LINEABOVE', (1, -1), (2, -1), 2, colors.hexColor("#6366f1")),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(tt)

    # --- PASAJEROS ---
    pasajeros = datos.get('pasajeros', [])
    if pasajeros:
        elements.append(Spacer(1, 15))
        elements.append(Paragraph("PASAJEROS", styles['SeccionLabel']))
        
        pax_rows = [["Nombre Completo", "Documento"]]
        for p in pasajeros:
            pax_rows.append([
                p.get('nombre', 'N/A'),
                p.get('dni', '***'),
            ])
        
        tpax = Table(pax_rows, colWidths=[300, 210])
        tpax.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, 0), colors.hexColor("#f1f5f9")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.hexColor("#e2e8f0")),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(tpax)

    # --- FORMA DE PAGO ---
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("FORMA DE PAGO", styles['SeccionLabel']))
    
    metodo = datos.get('metodo_pago', 'Tarjeta de crédito')
    estado_pago = "✅ PAGADA" if datos.get('pagada', False) else "⏳ PENDIENTE"
    
    pago_data = [[
        f"Método: {metodo}",
        f"Estado: {estado_pago}",
        f"IBAN: {AGENCIA['iban']}",
    ]]
    tpago = Table(pago_data, colWidths=[170, 130, 210])
    tpago.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (-1, -1), colors.hexColor("#f0fdf4") if datos.get('pagada') else colors.hexColor("#fef3c7")),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.hexColor("#e2e8f0")),
    ]))
    elements.append(tpago)

    # --- PIE LEGAL ---
    elements.append(Spacer(1, 30))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.hexColor("#e2e8f0")))
    
    legal_texts = [
        f"{AGENCIA['nombre']} | CIF: {AGENCIA['cif']} | Licencia: {AGENCIA['licencia']}",
        f"{AGENCIA['direccion']}",
        "Inscrita en el Registro Mercantil de Valencia. Seguro de responsabilidad civil obligatorio.",
        "Factura válida como justificante fiscal. Conservar durante 4 años.",
        "En cumplimiento de la LSSI-CE y el RGPD. Política de privacidad disponible en nuestra web.",
    ]
    for text in legal_texts:
        elements.append(Paragraph(text, styles['Pie']))

    doc.build(elements)
    logger.info(f"📄 Factura generada: {ruta_pdf}")
    return ruta_pdf


# ==============================
# TARJETA DE EMBARQUE (BOARDING PASS)
# ==============================

def generar_boarding_pass_pdf(datos):
    """
    Genera una tarjeta de embarque básica.
    Esta se genera cuando la aerolínea proporciona los datos de check-in.
    
    Args:
        datos: {
            pasajero: {nombre, apellidos},
            vuelo: {numero, origen, destino, fecha, hora_embarque, puerta, asiento, terminal},
            booking_reference, secuencia_embarque,
        }
    """
    folder = "boarding_passes"
    os.makedirs(folder, exist_ok=True)

    pasajero = datos.get('pasajero', {})
    vuelo = datos.get('vuelo', {})
    nombre = f"{pasajero.get('apellidos', '').upper()}/{pasajero.get('nombre', '').upper()}"
    
    ruta_pdf = f"{folder}/boarding_{vuelo.get('numero', 'XX')}_" \
               f"{pasajero.get('apellidos', 'pax').upper()}.pdf"

    doc = SimpleDocTemplate(
        ruta_pdf, pagesize=landscape(A4),
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=10*mm, bottomMargin=10*mm,
    )
    styles = _estilos()
    elements = []

    # Tarjeta principal
    bp_data = [
        # Fila 1: Header
        [
            Paragraph(f"<b><font color='white' size=12>TARJETA DE EMBARQUE</font></b>", styles['Normal']),
            "",
            Paragraph(f"<b><font color='white'>BOARDING PASS</font></b>", styles['Derecha']),
        ],
        # Fila 2: Datos principales
        [
            Paragraph(f"<b>Pasajero / Passenger:</b><br/><font size=14><b>{nombre}</b></font>", styles['Normal']),
            Paragraph(f"<b>Vuelo / Flight:</b><br/><font size=14><b>{vuelo.get('numero', 'N/A')}</b></font>", styles['Centro']),
            Paragraph(f"<b>Fecha / Date:</b><br/><font size=14><b>{vuelo.get('fecha', 'N/A')}</b></font>", styles['Centro']),
        ],
        # Fila 3: Ruta
        [
            Paragraph(f"<b>De / From:</b><br/><font size=18><b>{vuelo.get('origen', 'XXX')}</b></font>", styles['Normal']),
            Paragraph("✈", ParagraphStyle('plane', parent=styles['Normal'], fontSize=30, alignment=TA_CENTER)),
            Paragraph(f"<b>A / To:</b><br/><font size=18><b>{vuelo.get('destino', 'XXX')}</b></font>", styles['Normal']),
        ],
        # Fila 4: Detalles
        [
            Paragraph(f"<b>Puerta / Gate:</b><br/><font size=14>{vuelo.get('puerta', 'TBC')}</font>", styles['Normal']),
            Paragraph(f"<b>Asiento / Seat:</b><br/><font size=14><b>{vuelo.get('asiento', 'N/A')}</b></font>", styles['Centro']),
            Paragraph(f"<b>Embarque / Boarding:</b><br/><font size=14>{vuelo.get('hora_embarque', 'N/A')}</font>", styles['Centro']),
        ],
        # Fila 5: Info adicional
        [
            Paragraph(f"Terminal: {vuelo.get('terminal', 'N/A')}", styles['Normal']),
            Paragraph(f"Seq: {datos.get('secuencia_embarque', 'N/A')}", styles['Centro']),
            Paragraph(f"Ref: {datos.get('booking_reference', 'N/A')}", styles['Derecha']),
        ],
    ]

    tbp = Table(bp_data, colWidths=[280, 170, 280])
    tbp.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.hexColor("#6366f1")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        # Body
        ('PADDING', (0, 0), (-1, -1), 12),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 2, colors.hexColor("#6366f1")),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.hexColor("#e2e8f0")),
        # Última fila
        ('BACKGROUND', (0, -1), (-1, -1), colors.hexColor("#f1f5f9")),
        ('FONTSIZE', (0, -1), (-1, -1), 8),
    ]))
    elements.append(tbp)

    # Aviso
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(
        "⚠ Esta tarjeta de embarque es informativa. Consulte con la aerolínea para la versión oficial. "
        f"Generada por {AGENCIA['nombre']}.",
        ParagraphStyle('aviso', parent=styles['Normal'], fontSize=7,
                       textColor=colors.hexColor("#94a3b8"), alignment=TA_CENTER),
    ))

    doc.build(elements)
    logger.info(f"📄 Boarding pass generado: {ruta_pdf}")
    return ruta_pdf


# ==============================
# NUMERACIÓN SECUENCIAL DE FACTURAS
# ==============================

class FacturaSequencer:
    """
    Gestión de números secuenciales de factura.
    Formato: F-YYYY-NNNNN (ej: F-2026-00001)
    """

    @staticmethod
    def siguiente_numero():
        """Obtiene el siguiente número de factura secuencial"""
        from database import Factura, get_db_session
        
        session = get_db_session()
        try:
            year = datetime.now().year
            prefix = f"F-{year}-"
            
            # Buscar la última factura del año
            ultima = session.query(Factura).filter(
                Factura.numero_factura.like(f"{prefix}%")
            ).order_by(Factura.numero_factura.desc()).first()
            
            if ultima:
                try:
                    ultimo_num = int(ultima.numero_factura.split('-')[-1])
                except (ValueError, IndexError):
                    ultimo_num = 0
            else:
                ultimo_num = 0
            
            nuevo_num = ultimo_num + 1
            return f"{prefix}{nuevo_num:05d}"
        finally:
            session.close()

    @staticmethod
    def crear_factura_desde_reserva(reserva, cliente_datos=None):
        """
        Crea una factura automática a partir de una reserva confirmada.
        
        Args:
            reserva: ReservaVuelo object
            cliente_datos: dict con datos fiscales del cliente (opcional)
        """
        from database import Factura, get_db_session
        import json

        num_factura = FacturaSequencer.siguiente_numero()
        
        # Datos del vuelo
        datos_vuelo = {}
        try:
            datos_vuelo = json.loads(reserva.datos_vuelo) if isinstance(reserva.datos_vuelo, str) else (reserva.datos_vuelo or {})
        except (json.JSONDecodeError, TypeError):
            pass

        # Pasajeros
        pasajeros = []
        try:
            pax_data = json.loads(reserva.pasajeros) if isinstance(reserva.pasajeros, str) else (reserva.pasajeros or [])
            for p in pax_data:
                pasajeros.append({
                    'nombre': f"{p.get('given_name', '')} {p.get('family_name', '')}",
                    'dni': p.get('identity_document_number', '***'),
                })
        except (json.JSONDecodeError, TypeError):
            pass

        # Conceptos de la factura
        conceptos = [{
            'descripcion': f"Vuelo {datos_vuelo.get('origen', '')} → {datos_vuelo.get('destino', '')} "
                          f"({reserva.codigo_reserva})",
            'cantidad': 1,
            'precio_unitario': float(reserva.precio_vuelos or reserva.precio_total or 0),
            'iva_pct': 0,  # Régimen especial de agencias de viajes
        }]

        # Extras
        if reserva.precio_extras and reserva.precio_extras > 0:
            conceptos.append({
                'descripcion': 'Servicios adicionales (equipaje, seguros, extras)',
                'cantidad': 1,
                'precio_unitario': float(reserva.precio_extras),
                'iva_pct': 0,
            })

        # Cliente
        cliente = cliente_datos or {
            'nombre': reserva.nombre_cliente or 'N/A',
            'cif': '',
            'direccion': '',
            'email': reserva.email_cliente or '',
        }

        # Generar PDF
        datos_factura = {
            'numero_factura': num_factura,
            'fecha': datetime.now().strftime('%d/%m/%Y'),
            'fecha_vencimiento': 'Pagada' if reserva.estado in ('PAGADO', 'CONFIRMADO', 'EMITIDO') else '30 días',
            'cliente': cliente,
            'conceptos': conceptos,
            'pasajeros': pasajeros,
            'reserva': {
                'codigo': reserva.codigo_reserva,
                'tipo_viaje': 'Ida y vuelta' if reserva.es_viaje_redondo else 'Solo ida',
                'origen': datos_vuelo.get('origen', ''),
                'destino': datos_vuelo.get('destino', ''),
            },
            'pagada': reserva.estado in ('PAGADO', 'CONFIRMADO', 'EMITIDO'),
            'metodo_pago': 'Tarjeta de crédito',
        }

        ruta_pdf = generar_factura_completa(datos_factura)

        # Guardar en DB
        session = get_db_session()
        try:
            factura = Factura(
                numero_factura=num_factura,
                email_cliente=reserva.email_cliente,
                monto=float(reserva.precio_total or 0),
                url_archivo_pdf=ruta_pdf,
                pagada=reserva.estado in ('PAGADO', 'CONFIRMADO', 'EMITIDO'),
                fecha_emision=datetime.utcnow(),
                stripe_payment_intent=reserva.stripe_payment_intent_id,
            )

            # Si hay expediente, vincularlo
            if hasattr(reserva, 'expediente_id') and reserva.expediente_id:
                factura.id_expediente = reserva.expediente_id

            session.add(factura)
            session.commit()
            factura_id = factura.id_factura
            session.close()

            return {
                'success': True,
                'numero_factura': num_factura,
                'ruta_pdf': ruta_pdf,
                'factura_id': factura_id,
            }
        except Exception as e:
            session.rollback()
            session.close()
            logger.error(f"Error guardando factura en DB: {e}")
            return {
                'success': True,
                'numero_factura': num_factura,
                'ruta_pdf': ruta_pdf,
                'factura_id': None,
                'warning': f'PDF generado pero no guardado en DB: {e}',
            }
