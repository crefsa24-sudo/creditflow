# ============================================================
# backend/kpis.py
# Motores de KPI: agente, gerente, admin + clasificacion de clientes
# Clasificacion por % de cumplimiento:
#   >= 90% -> EXCELENTE CLIENTE
#   >= 80% -> BUEN CLIENTE
#   <  80% -> CLIENTE REGULAR
# ============================================================
from db import fetch_all, fetch_one


def clasificar(cumplimiento):
    if cumplimiento is None:
        return "REGULAR"
    if cumplimiento >= 90:
        return "EXCELENTE"
    if cumplimiento >= 80:
        return "BUEN"
    return "REGULAR"


def comportamiento(cumplimiento):
    if cumplimiento >= 90:
        return "Pago puntual y consistente"
    if cumplimiento >= 80:
        return "Pago con ligeros atrasos"
    return "Pago irregular / requiere gestion de cobranza"


# ------------------------------------------------------------
# BD DE CLIENTES (por zona, agente, fecha ingreso, ciclos, cumplimiento)
# ------------------------------------------------------------
def clientes_db(filtro_zona=None, filtro_agente=None):
    sql = """
    SELECT c.id, u.nombre AS titular, c.titular_telefono, z.nombre AS zona,
           a.nombre AS agente, c.fecha_ingreso,
           c.ciclos_concluidos, c.cumplimiento
    FROM clients c
    JOIN usuarios u ON u.id = c.id_usuario
    LEFT JOIN zonas z ON z.id = u.zona_id
    LEFT JOIN usuarios a ON a.id = c.id_agente
    WHERE 1=1
    """
    params = []
    if filtro_zona:
        sql += " AND z.nombre = ?"; params.append(filtro_zona)
    if filtro_agente:
        sql += " AND a.nombre = ?"; params.append(filtro_agente)
    sql += " ORDER BY c.fecha_ingreso DESC"
    out = []
    for r in fetch_all(sql, params):
        cp = r["cumplimiento"] or 0
        r["clasificacion"] = clasificar(cp)
        r["comportamiento"] = comportamiento(cp)
        out.append(r)
    return out


def recalc_cumplimiento_cliente(id_cliente):
    """% cumplimiento = pagos pagados / pagos programados (vencidos + pagados) del cliente."""
    row = fetch_one("""
        SELECT
          SUM(CASE WHEN p.estado = 'pagado' THEN 1 ELSE 0 END) AS pagados,
          SUM(CASE WHEN p.estado IN ('pagado','pendiente','vencido') THEN 1 ELSE 0 END) AS programados
        FROM pagos p JOIN creditos cr ON cr.id = p.id_credito
        WHERE cr.id_cliente = ?""", (id_cliente,))
    programados = row["programados"] or 0
    cumplimiento = round((row["pagados"] or 0) / programados * 100, 2) if programados else 100.0
    # ciclos concluidos = creditos terminados
    ciclos = fetch_one("SELECT COUNT(*) AS n FROM creditos WHERE id_cliente = ? AND estado = 'concluido'",
                       (id_cliente,))["n"]
    from db import execute
    execute("UPDATE clients SET cumplimiento = ?, ciclos_concluidos = ? WHERE id_usuario = ?",
            (cumplimiento, ciclos, id_cliente))
    return cumplimiento


# ------------------------------------------------------------
# KPI AGENTE: por zonas, # clientes, % cobranza, % cumplimiento,
# clientes nuevos, retencion de clientes
# ------------------------------------------------------------
def kpi_agente(id_agente):
    total_clientes = fetch_one("SELECT COUNT(*) n FROM clients WHERE id_agente = ?", (id_agente,))["n"]
    creditos = fetch_all("SELECT id, monto, saldo FROM creditos WHERE id_agente = ?", (id_agente,))

    # Cobranza: cobrado / (programado no-pagado + cobrado)
    cobrado = 0.0
    programado = 0.0
    for cr in creditos:
        r = fetch_one("""
            SELECT SUM(CASE WHEN estado='pagado' THEN monto ELSE 0 END) AS cob,
                   SUM(CASE WHEN estado IN ('pagado','vencido','pendiente') THEN monto ELSE 0 END) AS prog
            FROM pagos WHERE id_credito = ?""", (cr["id"],))
        cobrado += r["cob"] or 0
        programado += r["prog"] or 0
    pct_cobranza = round(cobrado / programado * 100, 2) if programado else 0.0

    # Cumplimiento medio de sus clientes
    prom = fetch_one("SELECT AVG(cumplimiento) p FROM clients WHERE id_agente = ?", (id_agente,))
    pct_cumplimiento = round(prom["p"] or 0, 2)

    # Clientes nuevos (primer credito en los ultimos 90 dias) y renovados
    nuevos = fetch_one("""
        SELECT COUNT(*) n FROM clients WHERE id_agente = ? AND fecha_ingreso >= datetime('now','localtime','-90 days')
    """, (id_agente,))["n"]

    renovados = fetch_one("""
        SELECT COUNT(*) n FROM (
          SELECT cr.id_cliente FROM creditos cr JOIN clients c ON c.id_usuario = cr.id_cliente
          WHERE c.id_agente = ? GROUP BY cr.id_cliente HAVING COUNT(*) > 1)
    """, (id_agente,))["n"]
    retencion = round(renovados / total_clientes * 100, 2) if total_clientes else 0.0

    # Desglose por zona
    zonas = fetch_all("""
        SELECT z.nombre, COUNT(c.id) AS clientes,
               COALESCE(AVG(c.cumplimiento),0) AS cumplimiento
        FROM clients c
        JOIN usuarios u ON u.id = c.id_usuario
        JOIN zonas z ON z.id = u.zona_id
        WHERE c.id_agente = ? GROUP BY z.nombre""", (id_agente,))

    return {
        "id_agente": id_agente,
        "total_clientes": total_clientes,
        "pct_cobranza": pct_cobranza,
        "pct_cumplimiento": pct_cumplimiento,
        "clientes_nuevos": nuevos,
        "clientes_renovados": renovados,
        "retencion_pct": retencion,
        "por_zona": zonas,
    }


# ------------------------------------------------------------
# KPI GERENTE: por agente y zona, # clientes nuevos y renovados,
# % cobranza, % clientes nuevos, % clientes renovados
# ------------------------------------------------------------
def kpi_gerente(por_zona=None):
    # Por agente
    agentes = fetch_all("SELECT id, nombre FROM usuarios WHERE rol='agente' AND activo=1 ORDER BY nombre")
    filas = []
    for ag in agentes:
        k = kpi_agente(ag["id"])
        filas.append({
            "agente": ag["nombre"],
            "zona": ag.get("zona") or "",
            "clientes": k["total_clientes"],
            "clientes_nuevos": k["clientes_nuevos"],
            "clientes_renovados": k["clientes_renovados"],
            "pct_cobranza": k["pct_cobranza"],
            "pct_clientes_nuevos": round(k["clientes_nuevos"] / k["total_clientes"] * 100, 2) if k["total_clientes"] else 0,
            "pct_clientes_renovados": round(k["clientes_renovados"] / k["total_clientes"] * 100, 2) if k["total_clientes"] else 0,
        })
    # Por zona
    zonas = fetch_all("""
        SELECT z.id, z.nombre,
               COUNT(DISTINCT c.id_usuario) AS clientes,
               SUM(CASE WHEN c.fecha_ingreso >= datetime('now','localtime','-90 days') THEN 1 ELSE 0 END) AS nuevos
        FROM zonas z
        LEFT JOIN usuarios u ON u.zona_id = z.id AND u.rol='cliente'
        LEFT JOIN clients c ON c.id_usuario = u.id
        GROUP BY z.id, z.nombre""")
    return {"por_agente": filas, "por_zona": [dict(z) for z in zonas]}


# ------------------------------------------------------------
# KPI ADMIN (global)
# ------------------------------------------------------------
def kpi_admin():
    g = kpi_gerente()
    creditos = fetch_all("SELECT id FROM creditos")
    cobrado = programado = 0.0
    for cr in creditos:
        r = fetch_one("""SELECT SUM(CASE WHEN estado='pagado' THEN monto ELSE 0 END) cob,
                         SUM(CASE WHEN estado IN ('pagado','vencido','pendiente') THEN monto ELSE 0 END) prog
                         FROM pagos WHERE id_credito=?""", (cr["id"],))
        cobrado += r["cob"] or 0
        programado += r["prog"] or 0
    total_clientes = fetch_one("SELECT COUNT(*) n FROM clients")["n"]
    cartera = fetch_one("SELECT COALESCE(SUM(saldo),0) s FROM creditos WHERE estado='activo'")["s"]
    return {
        "total_clientes": total_clientes,
        "total_agentes": fetch_one("SELECT COUNT(*) n FROM usuarios WHERE rol='agente' AND activo=1")["n"],
        "total_gerentes": fetch_one("SELECT COUNT(*) n FROM usuarios WHERE rol='gerente' AND activo=1")["n"],
        "cartera_activa": cartera,
        "pct_cobranza_global": round(cobrado / programado * 100, 2) if programado else 0,
        "creditos_activos": fetch_one("SELECT COUNT(*) n FROM creditos WHERE estado='activo'")["n"],
        "creditos_concluidos": fetch_one("SELECT COUNT(*) n FROM creditos WHERE estado='concluido'")["n"],
        "por_agente": g["por_agente"],
    }
