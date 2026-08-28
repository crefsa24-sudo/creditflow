# ============================================================
# config/products.py
# TABLA OFICIAL DE PRODUCTOS DE CREDITO (parametros del negocio)
# Todas las cuotas se expresan "por cada $1,000 de monto solicitado"
# ============================================================

PRODUCTOS = {
    "P1": {
        "nombre": "Credito Clasico 15",
        "cuota_por_mil": 95.0,   # $95 por cada $1,000
        "pagos": 15,             # 15 pagos quincenales
        "frecuencia": "quincenal",
        "monto_min": 1000,
        "monto_max": 15000,
    },
    "P2": {
        "nombre": "Credito Flexible 23",
        "cuota_por_mil": 70.0,   # $70 por cada $1,000
        "pagos": 23,             # 23 pagos quincenales
        "frecuencia": "quincenal",
        "monto_min": 1000,
        "monto_max": 15000,
    },
    "P3": {
        "nombre": "Credito Largo Plazo 30",
        "cuota_por_mil": 45.0,   # $45 por cada $1,000
        "pagos": 30,             # 30 pagos quincenales (~15 meses)
        "frecuencia": "quincenal",
        "monto_min": 1000,
        "monto_max": 15000,
        # NOTA IMPORTANTE (suposicion declarada):
        # El negocio NO especifico el plazo de este producto.
        # Se asume 30 pagos quincenales (~15 meses) como default.
        # Es 100% configurable: cambia "pagos" aqui y todo el sistema
        # (cuotas, totales, TIR, plan de pagos y PDF) se recalcula solo.
    },
    "DIARIO": {
        "nombre": "Credito Diario 21",
        "cuota_por_mil": 80.0,   # $80 por cada $1,000
        "pagos": 21,             # 21 pagos diarios
        "frecuencia": "diario",
        "monto_min": 1000,
        "monto_max": 5000,       # cap especial: maximo $5,000
    },
}


def validar_producto(producto):
    if producto not in PRODUCTOS:
        raise ValueError(f"Producto desconocido: {producto}. Validos: {list(PRODUCTOS)}")
    return PRODUCTOS[producto]


def plan_de_pagos(monto, producto):
    """Calcula cuota, total a pagar, costo y TIR por periodo para un monto dado."""
    p = validar_producto(producto)
    if not (p["monto_min"] <= monto <= p["monto_max"]):
        raise ValueError(f"Monto {monto} fuera de rango [{p['monto_min']}, {p['monto_max']}] para {producto}")

    cuota = round((monto / 1000.0) * p["cuota_por_mil"], 2)   # cuota proporcional al monto
    total = round(cuota * p["pagos"], 2)                      # total a pagar
    costo = round(total - monto, 2)                           # costo financiero en $
    pct_costo = round(costo / monto * 100.0, 2)               # costo sobre capital (%)
    tir = tir_por_periodo(monto, cuota, p["pagos"])           # TIR por periodo (quincenal o diario)

    return {
        "producto": producto,
        "nombre": p["nombre"],
        "monto": monto,
        "cuota_por_mil": p["cuota_por_mil"],
        "pagos": p["pagos"],
        "frecuencia": p["frecuencia"],
        "cuota": cuota,
        "total_pagar": total,
        "costo": costo,
        "pct_costo": pct_costo,
        "tir_por_periodo_pct": round(tir * 100.0, 4),
    }


def tir_por_periodo(principal, cuota, n_pagos, tol=1e-9, max_iter=200):
    """TIR por periodo via biseccion sobre VPN = -principal + cuota * (1-(1+i)^-n)/i = 0"""
    lo, hi = 0.0, 10.0
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        if mid == 0:
            vpn = -principal + cuota * n_pagos
        else:
            vpn = -principal + cuota * ((1 - (1 + mid) ** -n_pagos) / mid)
        if abs(vpn) < tol:
            break
        if vpn > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def listado_productos():
    """Vista publica para la API: un ejemplo de plan por producto."""
    out = []
    for prod in PRODUCTOS:
        base = plan_de_pagos(1000.0, prod)
        base["monto_min"] = PRODUCTOS[prod]["monto_min"]
        base["monto_max"] = PRODUCTOS[prod]["monto_max"]
        out.append(base)
    return out


if __name__ == "__main__":
    print("=" * 78)
    print("TABLA DE PRODUCTOS — CALCULO VERIFICADO (por cada $1,000)")
    print("=" * 78)
    for prod in PRODUCTOS:
        p = plan_de_pagos(1000.0, prod)
        print(f"\n[{prod}] {p['nombre']}  |  {p['pagos']} pagos {p['frecuencia']}es"
              f"  |  rango ${PRODUCTOS[prod]['monto_min']:,} - ${PRODUCTOS[prod]['monto_max']:,}")
        print(f"   Cuota por cada $1,000 : ${p['cuota']:,.2f}")
        print(f"   Total a pagar          : ${p['total_pagar']:,.2f}  (costo ${p['costo']:,.2f} = {p['pct_costo']:.2f}% sobre capital)")
        print(f"   TIR por periodo        : {p['tir_por_periodo_pct']:.4f}%  |  ejemplo monto $15,000 -> cuota ${p['cuota']*15:,.2f}, total ${p['total_pagar']*15:,.2f}")
