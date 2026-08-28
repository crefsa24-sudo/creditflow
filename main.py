# ============================================================
# backend/main.py
# API del sistema de creditos personales (4 roles)
# Flujo: solicitud (usuario) -> pdf -> agente -> gerente -> admin
#        -> aprobada -> DESEMBOLSO (solo admin) -> plan de pagos
#        -> cobranza en EFECTIVO -> KPI agente/gerente/admin
# ============================================================
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional

from db import init_db, fetch_all, fetch_one, execute, registrar_auditoria, DB_PATH
from auth import login, usuario_por_token, hash_password
from config.products import PRODUCTOS, validar_producto, plan_de_pagos, listado_productos
from kpis import kpi_agente, kpi_gerente, kpi_admin, clientes_db, recalc_cumplimiento_cliente
from pdf import generar_pdf_solicitud

app = FastAPI(title="CrediFlow API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "frontend")), name="static")

# Garantiza que las tablas existan al importar (incluso sin ejecutar seed.py)
init_db()

# Si la base de datos esta vacia (primer arranque en un servidor nuevo,
# por ejemplo tras desplegar en Render/Railway), se carga automaticamente
# la informacion semilla de demostracion para que la app sea usable de inmediato.
try:
    if not fetch_one("SELECT id FROM usuarios LIMIT 1"):
        from seed import seed_if_needed
        seed_if_needed()
except Exception as _e:
    print(f"aviso: no se pudo autosemillar la base de datos -> {_e}")

# Redirige la raiz del sitio a la pantalla de acceso, ya que el proyecto
# no tiene un index.html propio: todo el frontend se sirve desde /static.
@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse(url="/static/login.html")

ROLES = ("cliente", "agente", "gerente", "admin")

# ---------------- Schemas ----------------
class ReqLogin(BaseModel):
    email: str
    password: str

class ReqUsuario(BaseModel):
    nombre: str
    email: str
    password: str
    rol: str
    telefono: str = ""
    zona: str = ""
    creado_por: int = 0

class ReqSolicitud(BaseModel):
    id_cliente: int
    producto: str
    monto: float
    titular: dict
    aval: dict
    laboral: dict
    economica: dict
    financiera: dict

class ReqPago(BaseModel):
    id_pago: int
    monto: float

# ---------------- Dependencia: auth ----------------
def quien(autorizacion):
    token = (autorizacion or "").replace("Bearer ", "")
    u = usuario_por_token(token)
    if not u:
        raise HTTPException(401, "Sesion invalida o expirada")
    return u

def solo_roles(u, roles):
    if u["rol"] not in roles:
        raise HTTPException(403, f"Acceso restringido. Rol requerido: {', '.join(roles)}")

# ---------------- Endpoints: auth ----------------
@app.post("/api/login")
def api_login(r: ReqLogin):
    res = login(r.email, r.password)
    if not res:
        raise HTTPException(401, "Credenciales incorrectas")
    registrar_auditoria(res["usuario"]["id"], "login", "Inicio de sesion")
    return res

# ---------------- Endpoints: catalogos ----------------
@app.get("/api/productos")
def api_productos(authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    return listado_productos()

@app.get("/api/zonas")
def api_zonas(authorization: Optional[str] = Header(None)):
    quien(authorization)
    return fetch_all("SELECT * FROM zonas ORDER BY nombre")

# ---------------- Endpoints: administracion de usuarios (solo admin) ----------------
@app.post("/api/usuarios")
def api_crear_usuario(r: ReqUsuario, authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    solo_roles(u, ["admin"])
    if r.rol not in ROLES:
        raise HTTPException(400, "Rol invalido")
    if r.rol in ("admin",) and u.get("rol") != "admin":
        raise HTTPException(403, "Solo el director puede crear administradores")
    # gerentes crean agentes/supervisores; la creacion de colaboradores la hace SIEMPRE el admin
    zona_id = None
    if r.zona:
        row = fetch_one("SELECT id FROM zonas WHERE nombre = ?", (r.zona,))
        zona_id = row["id"] if row else execute("INSERT INTO zonas (nombre) VALUES (?)", (r.zona,))
    nuevo = execute(
        "INSERT INTO usuarios (nombre,email,password_hash,rol,telefono,zona_id,creado_por) VALUES (?,?,?,?,?,?,?)",
        (r.nombre, r.email.strip().lower(), hash_password(r.password), r.rol, r.telefono, zona_id, u["id"]),
    )
    registrar_auditoria(u["id"], "alta_usuario", f"Alta de {r.rol}: {r.nombre} ({r.email})")
    return {"id": nuevo, "mensaje": f"{r.rol} dado de alta correctamente"}

@app.get("/api/usuarios")
def api_listar_usuarios(authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    solo_roles(u, ["admin", "gerente"])
    filas = fetch_all("""
        SELECT ur.id, ur.nombre, ur.email, ur.rol, ur.telefono, ur.activo, ur.fecha_alta,
               z.nombre AS zona
        FROM usuarios ur LEFT JOIN zonas z ON z.id = ur.zona_id
        WHERE ur.rol IN ('agente','gerente','cliente')
        ORDER BY ur.rol, ur.nombre""")
    # el admin (director) siempre ve la lista completa de colaboradores
    if u["rol"] == "admin":
        filas = fetch_all("""
            SELECT ur.id, ur.nombre, ur.email, ur.rol, ur.telefono, ur.activo, ur.fecha_alta,
                   z.nombre AS zona
            FROM usuarios ur LEFT JOIN zonas z ON z.id = ur.zona_id
            ORDER BY ur.rol, ur.nombre""")
    return filas

# ---------------- Endpoints: clientes / solicitud (app del USUARIO) ----------------
@app.post("/api/solicitudes")
def api_crear_solicitud(r: ReqSolicitud, authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    solo_roles(u, ["cliente"])
    if r.id_cliente != u["id"]:
        raise HTTPException(403, "Solo puedes solicitar para tu propia cuenta")
    plan = plan_de_pagos(r.monto, r.producto)

    # Guardar/actualizar ficha del cliente (titular = datos de la solicitud)
    fila = fetch_one("SELECT id FROM clients WHERE id_usuario = ?", (u["id"],))
    data = (r.titular.get("nombre",""), r.titular.get("curp",""), r.titular.get("direccion",""),
            r.titular.get("telefono",""), r.titular.get("fecha_nac",""),
            r.aval.get("nombre",""), r.aval.get("curp",""), r.aval.get("direccion",""),
            r.aval.get("telefono",""), r.aval.get("parentesco",""),
            r.laboral.get("empresa",""), r.laboral.get("puesto",""), int(r.laboral.get("antiguedad",0) or 0),
            float(r.laboral.get("salario",0) or 0), r.laboral.get("direccion",""), r.laboral.get("telefono",""),
            float(r.economica.get("ingresos",0) or 0), float(r.economica.get("egresos",0) or 0),
            float(r.economica.get("otros",0) or 0),
            r.financiera.get("banco",""), r.financiera.get("tarjeta",""),
            r.financiera.get("ref1",""), r.financiera.get("ref2",""))
    if fila:
        execute("""UPDATE clients SET titular_nombre=?,titular_curp=?,titular_direccion=?,titular_telefono=?,
                   titular_fecha_nac=?, aval_nombre=?,aval_curp=?,aval_direccion=?,aval_telefono=?,aval_parentesco=?,
                   laboral_empresa=?,laboral_puesto=?,laboral_antiguedad=?,laboral_salario=?,laboral_direccion=?,
                   laboral_telefono=?, eco_ingresos=?,eco_egresos=?,eco_otros_ingresos=?,
                   fin_banco=?,fin_tarjeta=?,fin_ref1=?,fin_ref2=? WHERE id_usuario=?""", data + (u["id"],))
    else:
        execute("""INSERT INTO clients (id_usuario,titular_nombre,titular_curp,titular_direccion,titular_telefono,
                   titular_fecha_nac,aval_nombre,aval_curp,aval_direccion,aval_telefono,aval_parentesco,
                   laboral_empresa,laboral_puesto,laboral_antiguedad,laboral_salario,laboral_direccion,laboral_telefono,
                   eco_ingresos,eco_egresos,eco_otros_ingresos,fin_banco,fin_tarjeta,fin_ref1,fin_ref2,id_agente)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                 data + (u["id"], u.get("zona_id")))

    sid = execute("""INSERT INTO solicitudes (id_cliente,producto,monto,plazo,cuota,total_pagar)
                     VALUES (?,?,?,?,?,?)""",
                  (u["id"], r.producto, r.monto, plan["pagos"], plan["cuota"], plan["total_pagar"]))

    solicitud = fetch_one("SELECT * FROM solicitudes WHERE id = ?", (sid,))
    cliente = fetch_one("SELECT * FROM clients WHERE id_usuario = ?", (u["id"],))
    agente = fetch_one("""
        SELECT u.nombre, z.nombre AS zona FROM usuarios u
        LEFT JOIN zonas z ON z.id = u.zona_id
        WHERE u.id = (SELECT id_agente FROM clients WHERE id_usuario = ?)""", (u["id"],))
    try:
        pdf_path = generar_pdf_solicitud(solicitud, cliente, agente, plan)
        execute("UPDATE solicitudes SET pdf_path = ? WHERE id = ?", (os.path.basename(pdf_path), sid))
    except Exception as e:
        registrar_auditoria(u["id"], "error_pdf", f"Fallo PDF de la solicitud {sid}: {e}")

    registrar_auditoria(u["id"], "solicitud", f"Solicitud {sid} creada: {r.producto} ${r.monto:,.2f}")
    return {"id": sid, "estado": "pendiente_agente", "plan": plan, "mensaje": "Solicitud enviada al agente"}

@app.get("/api/mis_solicitudes")
def api_mis_solicitudes(authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    return fetch_all("SELECT * FROM solicitudes WHERE id_cliente = ? ORDER BY id DESC", (u["id"],))

@app.get("/api/mis_creditos")
def api_mis_creditos(authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    return fetch_all("""
        SELECT cr.*, (SELECT COUNT(*) FROM pagos p WHERE p.id_credito=cr.id AND p.estado='pagado') pagos_pagados
        FROM creditos cr WHERE cr.id_cliente = ? ORDER BY cr.id DESC""", (u["id"],))

@app.get("/api/mis_pagos/{id_credito}")
def api_mis_pagos(id_credito: int, authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    return fetch_all("SELECT * FROM pagos WHERE id_credito = ? ORDER BY numero", (id_credito,))

@app.get("/api/solicitud/{sid}/pdf")
def api_pdf_solicitud(sid: int, authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    s = fetch_one("SELECT * FROM solicitudes WHERE id = ?", (sid,))
    if not s:
        raise HTTPException(404, "Solicitud no encontrada")
    if not (u["rol"] in ("admin","gerente","agente") or u["id"] == s["id_cliente"]):
        raise HTTPException(403, "Sin permiso")
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdfs", s["pdf_path"]) if s["pdf_path"] else ""
    if not path or not os.path.exists(path):
        raise HTTPException(404, "PDF aun no generado (la solicitud se envio antes de activarse el PDF)")
    from fastapi.responses import FileResponse
    return FileResponse(path, media_type="application/pdf",
                        filename=os.path.basename(path))

# ---------------- Endpoints: aprobaciones (agente -> gerente -> admin) ----------------
@app.post("/api/solicitudes/{sid}/aprobar")
def api_aprobar(sid: int, decision: str, comentario: str = "", authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    s = fetch_one("SELECT * FROM solicitudes WHERE id = ?", (sid,))
    if not s:
        raise HTTPException(404, "Solicitud no encontrada")
    if decision not in ("aprobar", "rechazar"):
        raise HTTPException(400, "decision debe ser aprobar|rechazar")

    flujo = {"pendiente_agente": ("agente", "pendiente_gerente"),
             "pendiente_gerente": ("gerente", "pendiente_admin"),
             "pendiente_admin": ("admin", "aprobada")}
    if s["estado"] not in flujo:
        raise HTTPException(400, f"Ya no se puede accionar esta solicitud (estado: {s['estado']})")
    rol_requerido, sgte = flujo[s["estado"]]
    solo_roles(u, [rol_requerido])

    nuevo_estado = sgte if decision == "aprobar" else "rechazada"
    execute("UPDATE solicitudes SET estado = ? WHERE id = ?", (nuevo_estado, sid))
    execute("INSERT INTO aprobaciones (id_solicitud,nivel,id_usuario,decision,comentario) VALUES (?,?,?,?,?)",
            (sid, s["estado"], u["id"], decision, comentario))
    registrar_auditoria(u["id"], "aprobacion",
                        f"Solicitud {sid} {decision} por {u['rol']} -> estado {nuevo_estado}")
    return {"estado": nuevo_estado}

@app.get("/api/solicitudes/pendientes")
def api_pendientes(authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    if u["rol"] == "agente":
        filas = fetch_all("SELECT s.*, cl.titular_nombre FROM solicitudes s "
                          "JOIN clients cl ON cl.id_usuario = s.id_cliente "
                          "WHERE s.estado = 'pendiente_agente' ORDER BY s.id DESC")
    elif u["rol"] == "gerente":
        filas = fetch_all("SELECT s.*, cl.titular_nombre FROM solicitudes s "
                          "JOIN clients cl ON cl.id_usuario = s.id_cliente "
                          "WHERE s.estado = 'pendiente_gerente' ORDER BY s.id DESC")
    else:
        filas = fetch_all("SELECT s.*, cl.titular_nombre FROM solicitudes s "
                          "JOIN clients cl ON cl.id_usuario = s.id_cliente "
                          "WHERE s.estado IN ('pendiente_admin','aprobada') ORDER BY s.id DESC")
    return filas

# ---------------- DESEMBOLSO: SOLO ADMIN (genera plan de pagos) ----------------
@app.post("/api/solicitudes/{sid}/desembolsar")
def api_desembolsar(sid: int, authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    solo_roles(u, ["admin"])
    s = fetch_one("SELECT * FROM solicitudes WHERE id = ?", (sid,))
    if not s:
        raise HTTPException(404, "Solicitud no encontrada")
    if s["estado"] != "aprobada":
        raise HTTPException(400, "Solo se desembolsa una solicitud aprobada por los 3 niveles")
    plan = plan_de_pagos(s["monto"], s["producto"])
    cli = fetch_one("SELECT * FROM clients WHERE id_usuario = ?", (s["id_cliente"],))

    cid = execute("""INSERT INTO creditos (id_solicitud,id_cliente,id_agente,id_zona,producto,monto,plazo,
                     cuota,total_pagar,saldo)
                     VALUES (?,?,?,?,?,?,?,?,?,?)""",
                  (sid, s["id_cliente"], cli["id_agente"], cli["id_agente"] and
                   fetch_one("SELECT zona_id FROM usuarios WHERE id = ?", (cli["id_agente"],))["zona_id"],
                   s["producto"], s["monto"], plan["pagos"], plan["cuota"], plan["total_pagar"], s["monto"]))

    fecha_base = datetime.now()
    for i in range(1, plan["pagos"] + 1):
        delta = i if plan["frecuencia"] == "diario" else i * 14
        fprog = (fecha_base + timedelta(days=delta)).strftime("%Y-%m-%d")
        execute("INSERT INTO pagos (id_credito,numero,monto,fecha_programada) VALUES (?,?,?,?)",
                (cid, i, plan["cuota"], fprog))

    execute("UPDATE solicitudes SET estado = 'desembolsada' WHERE id = ?", (sid,))
    execute("INSERT INTO caja (tipo,monto,concepto,referencia,id_usuario) VALUES ('egreso',?,?,?,?)",
            (s["monto"], f"DESEMBOLSO de credito SOL-{sid:05d}", f"credito_{cid}", u["id"]))
    registrar_auditoria(u["id"], "desembolso",
                        f"Credito {cid} desembolsado por ${s['monto']:,.2f} en EFECTIVO (producto {s['producto']})")
    return {"credito_id": cid, "mensaje": f"Credito {cid} desembolsado en efectivo. {plan['pagos']} pagos de ${plan['cuota']:,.2f}."}

# ---------------- Cobranza en efectivo ----------------
@app.post("/api/pagos/cobrar")
def api_cobrar(r: ReqPago, authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    solo_roles(u, ["agente"])
    p = fetch_one("SELECT p.*, cr.id_cliente, cr.monto FROM pagos p JOIN creditos cr ON cr.id = p.id_credito WHERE p.id = ?",
                  (r.id_pago,))
    if not p:
        raise HTTPException(404, "Pago no encontrado")
    if p["estado"] == "pagado":
        raise HTTPException(400, "Este pago ya fue cobrado")
    if abs(p["monto"] - r.monto) > 0.01:
        raise HTTPException(400, f"El monto a cobrar debe ser ${p['monto']:,.2f} (flujo 100% efectivo)")

    execute("UPDATE pagos SET estado='pagado', fecha_pago=datetime('now','localtime'), cobrado_por=? WHERE id=?",
            (u["id"], r.id_pago))
    execute("""UPDATE creditos SET pagos_hechos = pagos_hechos + 1,
               saldo = ROUND(saldo - ?, 2) WHERE id = ?""", (r.monto, p["id_credito"]))
    cr = fetch_one("SELECT * FROM creditos WHERE id = ?", (p["id_credito"],))
    if cr["saldo"] <= 0:
        execute("UPDATE creditos SET estado = 'concluido' WHERE id = ?", (p["id_credito"],))
    execute("INSERT INTO caja (tipo,monto,concepto,referencia,id_usuario) VALUES ('ingreso',?,?,?,?)",
            (r.monto, f"COBRANZA credito {p['id_credito']} pago #{p['numero']}", f"pago_{r.id_pago}", u["id"]))
    recalc_cumplimiento_cliente(p["id_cliente"])
    return {"mensaje": f"Pago #{p['numero']} por ${r.monto:,.2f} cobrado en efectivo"}

@app.get("/api/pagos/pendientes")
def api_pagos_pendientes(authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    solo_roles(u, ["agente", "admin"])
    return fetch_all("""
        SELECT p.id, p.numero, p.monto, p.fecha_programada, p.estado, cr.id AS credito, cr.producto,
               cl.titular_nombre, z.nombre AS zona, ua.nombre AS agente
        FROM pagos p
        JOIN creditos cr ON cr.id = p.id_credito
        JOIN clients cl ON cl.id_usuario = cr.id_cliente
        LEFT JOIN zonas z ON z.id = cr.id_zona
        LEFT JOIN usuarios ua ON ua.id = cr.id_agente
        WHERE p.estado IN ('pendiente','vencido')
        ORDER BY p.fecha_programada""")

# ---------------- Caja / arqueo ----------------
@app.get("/api/caja")
def api_caja(authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    solo_roles(u, ["admin", "agente"])
    return fetch_all("SELECT * FROM caja ORDER BY id DESC LIMIT 200")

@app.post("/api/arqueo")
def api_arqueo(total_contado: float, nota: str = "", authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    solo_roles(u, ["admin", "gerente"])
    entradas = fetch_one("SELECT COALESCE(SUM(monto),0) s FROM caja WHERE tipo='ingreso'")["s"]
    salidas = fetch_one("SELECT COALESCE(SUM(monto),0) s FROM caja WHERE tipo='egreso'")["s"]
    esperado = round(entradas - salidas, 2)
    execute("INSERT INTO arqueos (total_esperado,total_contado,diferencia,nota,id_usuario) VALUES (?,?,?,?,?)",
            (esperado, total_contado, round(total_contado - esperado, 2), nota, u["id"]))
    registrar_auditoria(u["id"], "arqueo", f"Esperado ${esperado:,.2f} vs contado ${total_contado:,.2f}")
    return {"esperado": esperado, "contado": total_contado, "diferencia": round(total_contado - esperado, 2)}

# ---------------- KPIs y base de datos de clientes ----------------
@app.get("/api/db_clientes")
def api_db_clientes(filtro_zona: str = "", filtro_agente: str = "", authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    solo_roles(u, ["admin", "gerente"])
    if u["rol"] == "gerente" and not filtro_zona:
        pass
    return clientes_db(filtro_zona or None, filtro_agente or None)

@app.get("/api/kpi/agente")
def api_kpi_agente(authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    return kpi_agente(u["id"])

@app.get("/api/kpi/gerente")
def api_kpi_gerente(authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    if u["rol"] == "admin":
        return kpi_gerente()
    solo_roles(u, ["gerente"])
    return kpi_gerente()

@app.get("/api/kpi/admin")
def api_kpi_admin(authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    solo_roles(u, ["admin"])
    return kpi_admin()

# ---------------- Auditoria ----------------
@app.get("/api/auditoria")
def api_auditoria(authorization: Optional[str] = Header(None)):
    u = quien(authorization)
    solo_roles(u, ["admin"])
    return fetch_all("SELECT au.*, us.nombre FROM auditoria au LEFT JOIN usuarios us ON us.id = au.id_usuario "
                     "ORDER BY au.id DESC LIMIT 200")

if __name__ == "__main__":
    init_db()
    import uvicorn
    print(f"BD en: {DB_PATH}")
    # Render/Railway/Heroku exponen el puerto asignado en la variable PORT.
    # En local, si no existe esa variable, se usa el 8000 de siempre.
    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=puerto)
