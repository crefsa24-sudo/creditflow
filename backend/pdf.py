# ============================================================
# backend/pdf.py
# Generacion del PDF "SOLICITUD DE CREDITO" (reportlab)
# Incluye: titular, aval, informacion laboral/economica/financiera,
# monto y plazo solicitado + plan de pagos.
# ============================================================
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.join(BASE_DIR, "pdfs")
os.makedirs(PDF_DIR, exist_ok=True)

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Title"], fontSize=16, alignment=1, spaceAfter=4)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11, textColor=colors.HexColor("#1a3c6e"), spaceBefore=10, spaceAfter=4)
NORMAL = styles["Normal"]
SMALL = ParagraphStyle("SMALL", parent=styles["Normal"], fontSize=8.5)


def _tabla_pares(datos):
    rows = [[Paragraph(f"<b>{k}</b>", SMALL), Paragraph(str(v), SMALL)] for k, v in datos]
    t = Table(rows, colWidths=[2.2 * inch, 4.5 * inch])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4d6")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2f8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def generar_pdf_solicitud(solicitud, cliente, agente, plan):
    """solicitud: dict fila; cliente: dict fila; agente: dict o None; plan: dict de config.products"""
    path = os.path.join(PDF_DIR, f"solicitud_{solicitud['id']}.pdf")
    doc = SimpleDocTemplate(path, pagesize=letter,
                            leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    story = []

    story.append(Paragraph("SOLICITUD DE CREDITO PERSONAL", H1))
    story.append(Paragraph(f"<b>Folio:</b> SOL-{solicitud['id']:05d} &nbsp;&nbsp;|&nbsp;&nbsp; "
                           f"<b>Fecha:</b> {solicitud['fecha']} &nbsp;&nbsp;|&nbsp;&nbsp; "
                           f"<b>Zona:</b> {agente['zona'] if agente else '—'}", NORMAL))
    story.append(Paragraph("<i>Documento interno de evaluacion. Flujo de desembolso y cobranza 100% en efectivo.</i>", SMALL))
    story.append(Spacer(1, 6))

    # 1) Datos del titular
    story.append(Paragraph("1. DATOS DEL TITULAR", H2))
    story.append(_tabla_pares([
        ("Nombre completo", cliente.get("titular_nombre") or ""),
        ("CURP", cliente.get("titular_curp") or ""),
        ("Fecha de nacimiento", cliente.get("titular_fecha_nac") or ""),
        ("Domicilio", cliente.get("titular_direccion") or ""),
        ("Telefono", cliente.get("titular_telefono") or ""),
    ]))

    # 2) Datos del aval
    story.append(Paragraph("2. DATOS DEL AVAL", H2))
    story.append(_tabla_pares([
        ("Nombre completo", cliente.get("aval_nombre") or ""),
        ("CURP", cliente.get("aval_curp") or ""),
        ("Parentesco", cliente.get("aval_parentesco") or ""),
        ("Domicilio", cliente.get("aval_direccion") or ""),
        ("Telefono", cliente.get("aval_telefono") or ""),
    ]))

    # 3) Informacion laboral
    story.append(Paragraph("3. INFORMACION LABORAL", H2))
    story.append(_tabla_pares([
        ("Empresa", cliente.get("laboral_empresa") or ""),
        ("Puesto", cliente.get("laboral_puesto") or ""),
        ("Antiguedad (anios)", cliente.get("laboral_antiguedad") or ""),
        ("Salario mensual", f"$ {cliente.get('laboral_salario') or 0:,.2f}"),
        ("Domicilio laboral", cliente.get("laboral_direccion") or ""),
        ("Telefono laboral", cliente.get("laboral_telefono") or ""),
    ]))

    # 4) Informacion economica / financiera
    story.append(Paragraph("4. INFORMACION ECONOMICA Y FINANCIERA", H2))
    story.append(_tabla_pares([
        ("Ingresos mensuales", f"$ {cliente.get('eco_ingresos') or 0:,.2f}"),
        ("Egresos mensuales", f"$ {cliente.get('eco_egresos') or 0:,.2f}"),
        ("Otros ingresos", f"$ {cliente.get('eco_otros_ingresos') or 0:,.2f}"),
        ("Banco / cuenta", cliente.get("fin_banco") or ""),
        ("Tarjeta / linea", cliente.get("fin_tarjeta") or ""),
        ("Referencia 1", cliente.get("fin_ref1") or ""),
        ("Referencia 2", cliente.get("fin_ref2") or ""),
    ]))

    # 5) Monto y plazo solicitado
    story.append(Paragraph(f"5. MONTO Y PLAZO SOLICITADO — {plan['nombre']}", H2))
    story.append(_tabla_pares([
        ("Producto", f"{plan['producto']} — {plan['nombre']} ({plan['frecuencia']})"),
        ("Monto solicitado", f"$ {solicitud['monto']:,.2f}"),
        ("Plazo", f"{plan['pagos']} pagos {plan['frecuencia']}es"),
        ("Cuota por cada $1,000", f"$ {plan['cuota_por_mil']:,.2f}"),
        ("Cuota del credito", f"$ {plan['cuota']:,.2f}"),
        ("Total a pagar", f"$ {plan['total_pagar']:,.2f}"),
        ("Costo financiero", f"$ {plan['costo']:,.2f} ({plan['pct_costo']:.2f}% sobre capital)"),
        ("Agente responsable", agente["nombre"] if agente else "—"),
    ]))

    # 6) Plan de pagos
    story.append(Paragraph("6. PLAN DE PAGOS", H2))
    filas = [["#", "Fecha programada", "Cuota", "Saldo despues"]]
    saldo = solicitud["monto"]
    for i in range(1, plan["pagos"] + 1):
        filas.append([str(i), "", f"$ {plan['cuota']:,.2f}", f"$ {saldo:,.2f}"])
        saldo = max(0, round(saldo - plan["cuota"], 2))
    t = Table(filas, colWidths=[0.6 * inch, 2.2 * inch, 1.4 * inch, 1.6 * inch])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4d6")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c6e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))

    story.append(Paragraph(
        "Declaro bajo protesta de decir verdad que los datos asentados son ciertos y autorizo su verificacion. "
        "Me comprometo a cubrir la totalidad del credito en efectivo en las fechas pactadas.", NORMAL))
    story.append(Spacer(1, 12))
    story.append(Paragraph("_________________________&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                           "_________________________", NORMAL))
    story.append(Paragraph("Firma del titular&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                           "Firma del aval", SMALL))

    doc.build(story)
    return path
