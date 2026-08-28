# ============================================================
# backend/db.py
# Capa de datos: SQLite (archivo local creditos.db)
# ============================================================
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "creditos.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS zonas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS usuarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  rol TEXT NOT NULL CHECK(rol IN ('cliente','agente','gerente','admin')),
  telefono TEXT DEFAULT '',
  zona_id INTEGER REFERENCES zonas(id),
  creado_por INTEGER,
  activo INTEGER DEFAULT 1,
  fecha_alta TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS clients (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  id_usuario INTEGER UNIQUE REFERENCES usuarios(id),
  -- Datos del titular
  titular_nombre TEXT, titular_curp TEXT, titular_direccion TEXT, titular_telefono TEXT, titular_fecha_nac TEXT,
  -- Datos del aval
  aval_nombre TEXT, aval_curp TEXT, aval_direccion TEXT, aval_telefono TEXT, aval_parentesco TEXT,
  -- Informacion laboral
  laboral_empresa TEXT, laboral_puesto TEXT, laboral_antiguedad INTEGER, laboral_salario REAL,
  laboral_direccion TEXT, laboral_telefono TEXT,
  -- Informacion economica
  eco_ingresos REAL, eco_egresos REAL, eco_otros_ingresos REAL,
  -- Informacion financiera
  fin_banco TEXT, fin_tarjeta TEXT, fin_ref1 TEXT, fin_ref2 TEXT,
  -- Control interno
  id_agente INTEGER REFERENCES usuarios(id),
  fecha_ingreso TEXT DEFAULT (datetime('now','localtime')),
  ciclos_concluidos INTEGER DEFAULT 0,
  cumplimiento REAL DEFAULT 100.0
);

CREATE TABLE IF NOT EXISTS solicitudes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  id_cliente INTEGER REFERENCES usuarios(id),
  id_agente INTEGER REFERENCES usuarios(id),
  producto TEXT NOT NULL,
  monto REAL NOT NULL,
  plazo INTEGER NOT NULL,
  cuota REAL, total_pagar REAL,
  estado TEXT DEFAULT 'pendiente_agente',
  -- pendiente_agente -> pendiente_gerente -> pendiente_admin -> aprobada -> desembolsada / rechazada
  pdf_path TEXT DEFAULT '',
  fecha TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS aprobaciones (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  id_solicitud INTEGER REFERENCES solicitudes(id),
  nivel TEXT NOT NULL,
  id_usuario INTEGER,
  decision TEXT,
  comentario TEXT,
  fecha TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS creditos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  id_solicitud INTEGER,
  id_cliente INTEGER REFERENCES usuarios(id),
  id_agente INTEGER,
  id_zona INTEGER,
  producto TEXT, monto REAL, plazo INTEGER, cuota REAL, total_pagar REAL,
  saldo REAL, pagos_hechos INTEGER DEFAULT 0,
  estado TEXT DEFAULT 'activo',  -- activo / concluido / moroso
  fecha_desembolso TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS pagos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  id_credito INTEGER REFERENCES creditos(id),
  numero INTEGER,
  monto REAL,
  fecha_programada TEXT,
  fecha_pago TEXT,               -- NULL = aun no cobrado
  estado TEXT DEFAULT 'pendiente', -- pendiente / pagado / vencido
  cobrado_por INTEGER,
  metodo TEXT DEFAULT 'efectivo',  -- TU NEGOCIO: flujo 100% en efectivo
  folio TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS caja (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fecha TEXT DEFAULT (datetime('now','localtime')),
  tipo TEXT CHECK(tipo IN ('ingreso','egreso')),
  monto REAL,
  concepto TEXT,
  referencia TEXT,
  id_usuario INTEGER,
  saldo_parcial REAL
);

CREATE TABLE IF NOT EXISTS arqueos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fecha TEXT DEFAULT (datetime('now','localtime')),
  total_esperado REAL,
  total_contado REAL,
  diferencia REAL,
  nota TEXT,
  id_usuario INTEGER
);

CREATE TABLE IF NOT EXISTS auditoria (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fecha TEXT DEFAULT (datetime('now','localtime')),
  id_usuario INTEGER,
  accion TEXT,
  detalle TEXT
);

CREATE TABLE IF NOT EXISTS sesiones (
  token TEXT PRIMARY KEY,
  id_usuario INTEGER,
  expira TEXT
);
"""


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


# ------------------------------------------------------------
# Helpers genericos
# ------------------------------------------------------------
def fetch_all(sql, params=()):
    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_one(sql, params=()):
    conn = get_conn()
    row = conn.execute(sql, params).fetchone()
    conn.close()
    return dict(row) if row else None


def execute(sql, params=()):
    conn = get_conn()
    cur = conn.execute(sql, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def registrar_auditoria(id_usuario, accion, detalle):
    try:
        execute(
            "INSERT INTO auditoria (id_usuario, accion, detalle) VALUES (?,?,?)",
            (id_usuario, accion, detalle),
        )
    except Exception:
        pass  # la auditoria jamas debe tumbar una operacion
