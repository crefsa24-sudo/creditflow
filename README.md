# 💳 CrediFlow — Sistema de Créditos Personales (4 apps, flujo 100% en efectivo)

Monorepo con **backend Python (FastAPI + SQLite + reportlab)** y **4 aplicaciones web frontend (HTML/JS vanilla)**,
una por rol: **Cliente**, **Agente/Socio**, **Gerente/Supervisor** y **Administrador/Director**.

## Tabla de productos (verificada por cálculo)

| # | Producto | Cuota (por $1,000) | Pagos | Frecuencia | Rango de monto | A $1,000 | Total a pagar | Costo s/capital | TIR/periodo |
|---|----------|-------------------|-------|-----------|----------------|----------|---------------|-----------------|-------------|
| 1 | Clásico 15 | $95 | 15 | Quincenal | $1,000–$15,000 | $1,425 | $1,425.00 | 42.50% | 4.79% |
| 2 | Flexible 23 | $70 | 23 | Quincenal | $1,000–$15,000 | $1,610 | $1,610.00 | 61.00% | 4.40% |
| 3 | Largo Plazo 30 | $45 | 30* | Quincenal | $1,000–$15,000 | $1,350 | $1,350.00 | 35.00% | 2.06% |
| 4 | Diario 21 | $80 | 21 | Diario | $1,000–$5,000 | $1,680 | $1,680.00 | 68.00% | 5.29% |

\* **Supuesto declarado**: el negocio no especificó el plazo del producto 3 ($45/mil); se asumieron **30 pagos
quincenales (~15 meses)**. Se configura en `config/products.py` y todo el sistema (cuotas, totales, PDF, plan) se recalcula solo.

## Clasificación de clientes (por % de cumplimiento)

| Cumplimiento | Clasificación |
|--------------|---------------|
| ≥ 90% | 🟢 EXCELENTE CLIENTE — pago puntual y consistente |
| 80% – 89.99% | 🔵 BUEN CLIENTE — pago con ligeros atrasos |
| < 80% | 🔴 CLIENTE REGULAR — pago irregular / gestión de cobranza |

## Estructura del repositorio

```
creditos_app/
├── config/
│   ├── __init__.py
│   └── products.py          # Tabla oficial de productos + motor de planes/TIR
├── backend/
│   ├── main.py              # API FastAPI (todos los flujos y roles)
│   ├── db.py                # SQLite: esquema + helpers
│   ├── auth.py              # Login + tokens + hashing
│   ├── kpis.py              # KPIs agente/gerente/admin + BD de clientes
│   ├── pdf.py               # Generación del PDF "Solicitud de crédito"
│   ├── seed.py              # Datos semilla de demostración
│   └── creditos.db          # BD local (se crea al ejecutar seed.py)
├── frontend/
│   ├── login.html
│   ├── cliente.html         # App del USUARIO/CLIENTE
│   ├── agente.html          # App del AGENTE/SOCIO
│   ├── gerente.html         # App del GERENTE/SUPERVISOR
│   ├── admin.html           # App del ADMIN/DIRECTOR
│   ├── css/styles.css
│   └── js/ (api.js, common.js, forms.js)
├── requirements.txt
├── run.sh                   # Linux/macOS
├── run.bat                  # Windows
└── README.md
```

## Inicio rápido

```bash
# 1) Instalar dependencias (Python 3.9+)
pip install -r requirements.txt

# 2) Crear BD con datos de demostración
python backend/seed.py

# 3) Iniciar el servidor
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Abrir en el navegador: **http://localhost:8000/static/login.html**

### Cuentas de demostración

| Rol | Correo | Contraseña |
|-----|--------|-----------|
| Administrador/Director | admin@creditflow.app | admin123 |
| Gerente/Supervisor | gerente@creditflow.app | gerente123 |
| Agente/Socio (zona Norte) | agente1@creditflow.app | agente123 |
| Agente/Socio (zona Sur) | agente2@creditflow.app | agente123 |
| Cliente | cliente1@correo.com | cliente123 |
| Cliente | cliente2@correo.com | cliente123 |

## Flujo del crédito (3 niveles + desembolso)

```
Cliente (app) ──formulario──> PDF Solicitud de Crédito
    => Agente/Socio (nivel 1: avalúa y aprueba/rechaza)
    => Gerente/Supervisor (nivel 2)
    => Administrador/Director (nivel 3: aprobación final)
    => DESEMBOLSO (solo director) genera plan de pagos + egreso de caja en EFECTIVO
    => Cobranza del agente en efectivo => KPI agente / gerente / admin
```

## API principal

| Método | Ruta | Rol | Función |
|--------|------|-----|---------|
| POST | /api/login | Todos | Autenticación (token) |
| GET | /api/productos | Autenticado | Catálogo + plan calculado |
| POST | /api/solicitudes | Cliente | Crear solicitud + generar PDF |
| GET | /api/solicitud/{id}/pdf | Autorizados | Descargar PDF |
| POST | /api/solicitudes/{id}/aprobar | Agente/Gerente/Admin | Aprobación por nivel |
| POST | /api/solicitudes/{id}/desembolsar | Admin | Desembolso + plan de pagos |
| GET | /api/solicitudes/pendientes | Agente/Gerente/Admin | Bandejas por nivel |
| POST | /api/pagos/cobrar | Agente | Cobranza en efectivo |
| GET | /api/pagos/pendientes | Agente/Admin | Pagos por cobrar |
| GET | /api/kpi/agente · /kpi/gerente · /kpi/admin | Según rol | KPI por rol |
| GET | /api/db_clientes | Gerente/Admin | BD de clientes + clasificación |
| POST | /api/arqueo | Gerente/Admin | Corte/arqueo de caja |
| GET | /api/auditoria | Admin | Bitácora completa |
| POST | /api/usuarios | Admin | Alta de colaboradores |

## KPI implementados

- **Agente**: clientes por zona, % cobranza, % cumplimiento, clientes nuevos (90 días), renovados y % retención.
- **Gerente**: desempeño por agente y zona, clientes nuevos/renovados, % cobranza, % clientes nuevos, % clientes renovados.
- **Admin**: cartera activa, cobranza global, créditos activos/concluidos y tabla por agente + auditoría.

## Áreas de oportunidad (roadmap sugerido)

Ver la sección "Mejoras y áreas de oportunidad" del documento de entrega.

## Despliegue

**Importante:** GitHub solo aloja el código (el repositorio). GitHub Pages únicamente sirve
sitios estáticos y **no puede ejecutar Python/FastAPI**, así que para que la app funcione de
verdad en internet necesitas subir el código a GitHub y luego conectarlo a un servicio que sí
ejecute Python (Render, Railway, Fly.io, PythonAnywhere, etc.). Abajo están los pasos para
GitHub + Render (ambos con capa gratuita).

### 1) Subir el proyecto a GitHub

```bash
cd creditos_app
git init
git add .
git commit -m "CrediFlow: primera versión lista para desplegar"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/creditflow.git
git push -u origin main
```

`creditos.db`, los PDFs generados y `__pycache__` ya están excluidos por `.gitignore`,
así que no se suben datos de prueba ni archivos temporales.

### 2) Desplegar en Render (recomendado, gratis)

1. Crea una cuenta en https://render.com y conéctala a tu cuenta de GitHub.
2. "New +" → "Blueprint" → selecciona el repositorio `creditflow`. Render detectará el
   archivo `render.yaml` incluido y configurará todo automáticamente (o bien crea un
   "Web Service" manual con *Build Command* `pip install -r requirements.txt` y *Start
   Command* `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`).
3. Espera a que termine el build. Render te dará una URL pública, por ejemplo
   `https://creditflow.onrender.com`.
4. La primera vez que arranca, la app detecta que la base de datos está vacía y **carga
   automáticamente los datos de demostración** (mismas cuentas de la tabla de arriba).
5. Abre la URL pública: te redirige solo a `/static/login.html`.

**Nota sobre persistencia:** en el plan gratuito de Render el disco es efímero, es decir,
si el servicio se reinicia o se vuelve a desplegar, `creditos.db` se recrea desde cero
(y se vuelve a autosemillar). Para un negocio real en producción, el siguiente paso sería
migrar de SQLite a una base de datos administrada (por ejemplo Postgres, que Render también
ofrece gratis) para que la información persista siempre.

### 3) Alternativas a Render

- **Railway** (`railway.app`): detecta el `Procfile` automáticamente.
- **Fly.io**: usa el `Dockerfile` incluido (`fly launch`).
- **Docker en cualquier VPS**: `docker build -t creditflow . && docker run -p 8000:8000 creditflow`.

### 4) Correr en local (sin cambios)

```bash
bash run.sh        # Linux/macOS
run.bat            # Windows
```

Abre **http://localhost:8000** (ya no hace falta escribir `/static/login.html`, la raíz
redirige automáticamente).
