# ============================================================
# backend/seed.py
# Datos semilla de DEMOSTRACION (si creditos.db existe, se recrea):
#  - 2 zonas, 2 agentes, 1 gerente, 1 admin, 2 clientes
#  - 2 solicitudes en espera (para probar el flujo de 3 niveles)
#  - 1 credito desembolsado con 11 de 15 pagos liquidados (73.33%)
# Uso: python seed.py
# ============================================================
import os
import sys
import datetime
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import init_db, execute, fetch_one, DB_PATH
from auth import hash_password
from config.products import plan_de_pagos


def seed_if_needed():
    """Carga los datos semilla SOLO si la base de datos esta vacia.
    Pensado para llamarse automaticamente al arrancar el servidor
    (por ejemplo en un despliegue nuevo en Render/Railway), sin riesgo
    de borrar datos reales ya capturados por el negocio."""
    init_db()
    if fetch_one("SELECT id FROM usuarios LIMIT 1"):
        return False
    _cargar_datos_semilla()
    return True


def _cargar_datos_semilla():
    # --- Zonas y usuarios ---
    zN = execute("INSERT INTO zonas (nombre) VALUES (?)", ("Norte",))
    zS = execute("INSERT INTO zonas (nombre) VALUES (?)", ("Sur",))

    admin = execute("INSERT INTO usuarios (nombre,email,password_hash,rol) VALUES (?,?,?,?)",
                    ("Director General", "admin@creditflow.app", hash_password("admin123"), "admin"))
    gerente = execute("INSERT INTO usuarios (nombre,email,password_hash,rol) VALUES (?,?,?,?)",
                      ("Gerente Regional", "gerente@creditflow.app", hash_password("gerente123"), "gerente"))
    ag1 = execute("INSERT INTO usuarios (nombre,email,password_hash,rol,zona_id) VALUES (?,?,?,?,?)",
                  ("Agente Carlos", "agente1@creditflow.app", hash_password("agente123"), "agente", zN))
    ag2 = execute("INSERT INTO usuarios (nombre,email,password_hash,rol,zona_id) VALUES (?,?,?,?,?)",
                  ("Agente Maria", "agente2@creditflow.app", hash_password("agente123"), "agente", zS))
    cli1 = execute("INSERT INTO usuarios (nombre,email,password_hash,rol,zona_id) VALUES (?,?,?,?,?)",
                   ("Juan Perez", "cliente1@correo.com", hash_password("cliente123"), "cliente", zN))
    cli2 = execute("INSERT INTO usuarios (nombre,email,password_hash,rol,zona_id) VALUES (?,?,?,?,?)",
                   ("Ana Lopez", "cliente2@correo.com", hash_password("cliente123"), "cliente", zS))

    # --- Fichas de clientes (25 columnas) ---
    execute("""INSERT INTO clients (id_usuario,titular_nombre,titular_curp,titular_direccion,titular_telefono,titular_fecha_nac,
               aval_nombre,aval_curp,aval_direccion,aval_telefono,aval_parentesco,
               laboral_empresa,laboral_puesto,laboral_antiguedad,laboral_salario,laboral_direccion,laboral_telefono,
               eco_ingresos,eco_egresos,eco_otros_ingresos,fin_banco,fin_tarjeta,fin_ref1,fin_ref2,id_agente)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cli1, "Juan Perez Martinez", "PEMJ900101HDFRRN04", "Calle 5 de Mayo 123, Monterrey", "8112345678", "1990-01-01",
             "Luis Perez", "PELU650505HDFRRS02", "Av. Juarez 45, Monterrey", "8118765432", "Hermano",
             "Maquilas del Norte", "Operador", 3, 8500.0, "Calle Industria 7", "8122223344",
             9500.0, 6200.0, 0.0, "BBVA 0123", "TDC Banorte 4567", "Ref 1: Mario Diaz", "Ref 2: Rosa Torres", ag1))
    execute("""INSERT INTO clients (id_usuario,titular_nombre,titular_curp,titular_direccion,titular_telefono,titular_fecha_nac,
               aval_nombre,aval_curp,aval_direccion,aval_telefono,aval_parentesco,
               laboral_empresa,laboral_puesto,laboral_antiguedad,laboral_salario,laboral_direccion,laboral_telefono,
               eco_ingresos,eco_egresos,eco_otros_ingresos,fin_banco,fin_tarjeta,fin_ref1,fin_ref2,id_agente)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cli2, "Ana Lopez Garcia", "LOGA950620MMCPRN05", "Calle 16 de Septiembre 888, Merida", "9991234567", "1995-06-20",
             "Rosa Garcia", "GACR700410MYNRRS03", "Calle 60 #200, Merida", "9997654321", "Madre",
             "Servicios Turisticos Sur", "Coordinadora", 2, 11000.0, "Av. Colon 300", "9991112233",
             12500.0, 7800.0, 1500.0, "Santander 7788", "TDC HSBC 9900", "Ref 1: Pedro Gil", "Ref 2: Sofia Ruiz", ag2))

    # --- 2 solicitudes en espera para probar el flujo ---
    p1 = plan_de_pagos(1000.0, "P1")
    execute("INSERT INTO solicitudes (id_cliente,id_agente,producto,monto,plazo,cuota,total_pagar,estado) VALUES (?,?,?,?,?,?,?,'pendiente_agente')",
            (cli1, ag1, "P1", 1000.0, p1["pagos"], p1["cuota"], p1["total_pagar"]))
    p2 = plan_de_pagos(3000.0, "P2")
    execute("INSERT INTO solicitudes (id_cliente,id_agente,producto,monto,plazo,cuota,total_pagar,estado) VALUES (?,?,?,?,?,?,?,'pendiente_gerente')",
            (cli2, ag2, "P2", 3000.0, p2["pagos"], p2["cuota"], p2["total_pagar"]))

    # --- PDFs de las solicitudes en espera (demo) ---
    try:
        from pdf import generar_pdf_solicitud
        for sid in (1, 2):
            s0 = fetch_one("SELECT * FROM solicitudes WHERE id=?", (sid,))
            c0 = fetch_one("SELECT * FROM clients WHERE id_usuario=?", (s0["id_cliente"],))
            a0 = fetch_one("""SELECT u.nombre, z.nombre AS zona FROM usuarios u
                              LEFT JOIN zonas z ON z.id=u.zona_id WHERE u.id=?""", (s0["id_agente"],))
            pl0 = plan_de_pagos(s0["monto"], s0["producto"])
            path0 = generar_pdf_solicitud(s0, c0, a0, pl0)
            execute("UPDATE solicitudes SET pdf_path=? WHERE id=?", (os.path.basename(path0), sid))
    except Exception as e:
        print("aviso: PDFs semilla no generados ->", e)

    # --- 1 credito desembolsado (P1 $1,000, 15 pagos) con 11 pagos cobrados ---
    plan = plan_de_pagos(1000.0, "P1")
    cid = execute("""INSERT INTO creditos (id_solicitud,id_cliente,id_agente,id_zona,producto,monto,plazo,cuota,total_pagar,saldo,estado)
                     VALUES (NULL,?,?,?,'P1',?,?,?,?,?,'activo')""",
                  (cli1, ag1, zN, 1000.0, plan["pagos"], plan["cuota"], plan["total_pagar"], round(plan["total_pagar"] - 11 * plan["cuota"], 2)))  # deuda restante real: saldo=total a pagar - cobrado
    fecha_base = datetime.datetime.now() - timedelta(days=180)
    for i in range(1, plan["pagos"] + 1):
        fprog = (fecha_base + timedelta(days=i * 14)).strftime("%Y-%m-%d")
        if i <= 11:
            execute("""INSERT INTO pagos (id_credito,numero,monto,fecha_programada,fecha_pago,estado,cobrado_por,metodo)
                       VALUES (?,?,?,?,?,'pagado',?,'efectivo')""",
                    (cid, i, plan["cuota"], fprog, fprog, ag1))
            execute("INSERT INTO caja (tipo,monto,concepto,referencia,id_usuario) VALUES ('ingreso',?,?,?,?)",
                    (plan["cuota"], f"COBRANZA credito {cid} pago #{i}", f"pago_seed_{i}", ag1))
        else:
            execute("INSERT INTO pagos (id_credito,numero,monto,fecha_programada,estado) VALUES (?,?,?,?,'pendiente')",
                    (cid, i, plan["cuota"], fprog))
    execute("UPDATE creditos SET pagos_hechos = 11 WHERE id = ?", (cid,))
    execute("UPDATE clients SET cumplimiento = 73.33, ciclos_concluidos = 0 WHERE id_usuario = ?", (cli1,))
    execute("UPDATE clients SET cumplimiento = 100.0, ciclos_concluidos = 2 WHERE id_usuario = ?", (cli2,))
    execute("INSERT INTO caja (tipo,monto,concepto,referencia,id_usuario) VALUES ('egreso',?,?,?,?)",
            (1000.0, "DESEMBOLSO de credito de prueba", f"credito_{cid}", admin))

    # --- Arqueo inicial conciliado ---
    entradas = fetch_one("SELECT SUM(monto) s FROM caja WHERE tipo='ingreso'")["s"]
    salidas = fetch_one("SELECT SUM(monto) s FROM caja WHERE tipo='egreso'")["s"]
    execute("INSERT INTO arqueos (total_esperado,total_contado,diferencia,nota,id_usuario) VALUES (?,?,0,'Arqueo inicial semilla',?)",
            (round(entradas - salidas, 2), round(entradas - salidas, 2), admin))
    execute("INSERT INTO auditoria (id_usuario,accion,detalle) VALUES (?, 'seed', 'Carga de datos semilla')", (admin,))

    print("=" * 62)
    print("BD SEMILLA CREADA (backend/creditos.db)")
    print("=" * 62)
    print("Zonas      : Norte, Sur")
    print("Usuarios   : director (admin@creditflow.app / admin123)")
    print("             gerente (gerente@creditflow.app / gerente123)")
    print("             agente  (agente1@creditflow.app / agente123) - Zona Norte")
    print("             agente  (agente2@creditflow.app / agente123) - Zona Sur")
    print("             cliente (cliente1@correo.com / cliente123)")
    print("             cliente (cliente2@correo.com / cliente123)")
    print("Solicitudes: SOL-1 pendiente agente ($1,000 P1), SOL-2 pendiente gerente ($3,000 P2)")
    print("Credito    : #1 activo, 11/15 pagos cobrados -> cumplimiento 73.33% (REGULAR)")
    print("Caja       : 11 ingresos + 1 egreso, arqueo conciliado")


if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
    _cargar_datos_semilla()
