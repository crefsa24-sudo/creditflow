# ============================================================
# backend/auth.py
# Autenticacion simple por sesion (token) + hash PBKDF2
# ============================================================
import hashlib
import secrets
from db import get_conn, fetch_one


def hash_password(pw):
    salt = secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${h}"


def verify_password(pw, stored):
    try:
        salt, h = stored.split("$")
    except ValueError:
        return False
    return h == hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000).hex()


def crear_token(id_usuario):
    token = secrets.token_hex(24)
    conn = get_conn()
    conn.execute(
        "INSERT INTO sesiones (token, id_usuario, expira) VALUES (?,?, datetime('now','localtime','+7 days'))",
        (token, id_usuario),
    )
    conn.commit()
    conn.close()
    return token


def usuario_por_token(token):
    if not token:
        return None
    return fetch_one(
        """SELECT u.*, z.nombre AS zona
           FROM sesiones s
           JOIN usuarios u ON u.id = s.id_usuario
           LEFT JOIN zonas z ON z.id = u.zona_id
           WHERE s.token = ? AND s.expira > datetime('now','localtime')""",
        (token,),
    )


def login(email, password):
    u = fetch_one("SELECT * FROM usuarios WHERE email = ? AND activo = 1", (email.strip().lower(),))
    if not u or not verify_password(password, u["password_hash"]):
        return None
    return {"token": crear_token(u["id"]), "usuario": {
        "id": u["id"], "nombre": u["nombre"], "email": u["email"],
        "rol": u["rol"], "zona": u.get("zona") or "",
    }}
