"""
Generador de datos sintéticos para el ETL de Conciliación Bancaria.

Produce dos archivos CSV con formatos intencionalmente distintos
para demostrar las capacidades de normalización del pipeline.

- libro_contable.csv : Registros del libro mayor contable
- cartola_bancaria.csv : Movimientos del extracto bancario
"""

import csv
import os
import random
from datetime import datetime, timedelta

SEED = 42
random.seed(SEED)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def _random_date(start: datetime, end: datetime) -> datetime:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def generate_libro_contable(path: str, n_records: int = 150) -> str:
    """Genera el libro contable con formato típico de ERP chileno."""
    cuentas = {
        "1101001": "Caja",
        "1102001": "Banco Estado CTA CTE",
        "1102002": "Banco Chile CTA CTE",
        "2101001": "Proveedores Nacionales",
        "2101002": "Proveedores Internacionales",
        "4101001": "Ventas Nacionales",
        "4101002": "Ventas Exportación",
        "5101001": "Costo de Ventas",
        "6101001": "Remuneraciones",
        "6102001": "Arriendos",
        "6103001": "Servicios Básicos",
        "6104001": "Honorarios",
    }

    descripciones_cargo = [
        "Pago proveedor factura",
        "Pago remuneraciones mes",
        "Pago arriendo oficina",
        "Pago servicios básicos",
        "Pago honorarios consultoría",
        "Compra insumos oficina",
        "Pago impuestos mensuales",
        "Transferencia entre cuentas",
    ]

    descripciones_abono = [
        "Depósito cliente",
        "Cobro factura venta",
        "Transferencia recibida",
        "Abono nota de crédito",
        "Ingreso por servicios",
        "Cobro exportación",
    ]

    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 12, 31)

    # Generar códigos de operación — algunos compartidos con cartola, otros no
    codigos_compartidos = [f"OP-{i:05d}" for i in range(1, 121)]
    codigos_solo_libro = [f"OP-{i:05d}" for i in range(121, 151)]
    codigos = codigos_compartidos + codigos_solo_libro

    rows = []
    for i, codigo in enumerate(codigos):
        fecha = _random_date(start_date, end_date)
        tipo = random.choice(["CARGO", "ABONO"])
        cuenta_code = random.choice(list(cuentas.keys()))

        if tipo == "CARGO":
            desc = random.choice(descripciones_cargo)
            monto = round(random.uniform(50000, 15000000), 0)
        else:
            desc = random.choice(descripciones_abono)
            monto = round(random.uniform(100000, 25000000), 0)

        # Formato intencional: fecha DD-MM-YYYY, montos con punto de miles
        fecha_str = fecha.strftime("%d-%m-%Y")
        monto_str = f"${monto:,.0f}".replace(",", ".")

        rows.append({
            "Fecha_Registro": fecha_str,
            "Codigo_Operacion": codigo,
            "Cuenta_Contable": cuenta_code,
            "Nombre_Cuenta": cuentas[cuenta_code],
            "Descripcion": desc,
            "Tipo_Movimiento": tipo,
            "Monto": monto_str,
            "Centro_Costo": random.choice(["CC-100", "CC-200", "CC-300", "CC-400"]),
        })

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="latin-1") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    return path


def generate_cartola_bancaria(path: str, n_records: int = 140) -> str:
    """Genera la cartola bancaria con formato típico de banco chileno."""
    codigos_compartidos = [f"OP-{i:05d}" for i in range(1, 121)]
    codigos_solo_banco = [f"OP-{i:05d}" for i in range(151, 171)]
    codigos = codigos_compartidos + codigos_solo_banco

    tipos_txn = {
        "CARGO": ["PAG", "TRF", "COM", "IMP", "GIR"],
        "ABONO": ["DEP", "TRF", "ABN", "INT"],
    }

    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 12, 31)

    rows = []
    for codigo in codigos:
        fecha = _random_date(start_date, end_date)
        tipo = random.choice(["CARGO", "ABONO"])
        subtipo = random.choice(tipos_txn[tipo])

        if tipo == "CARGO":
            monto = round(random.uniform(50000, 15000000), 2)
        else:
            monto = round(random.uniform(100000, 25000000), 2)

        # Formato banco: fecha YYYY/MM/DD, montos con decimales y coma
        fecha_str = fecha.strftime("%Y/%m/%d")
        monto_str = f"{monto:.2f}".replace(".", ",")

        sucursal = random.choice(["SUC-01", "SUC-02", "SUC-03", "DIGITAL"])

        rows.append({
            "FECHA_TXN": fecha_str,
            "COD_REF": codigo,
            "TIPO_TXN": subtipo,
            "CLASIFICACION": tipo,
            "DETALLE": f"{subtipo} - Operación {codigo}",
            "MONTO_$": monto_str,
            "SUCURSAL": sucursal,
            "N_DOCUMENTO": f"DOC-{random.randint(100000, 999999)}",
        })

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter=",")
        writer.writeheader()
        writer.writerows(rows)

    return path


def generate_all():
    """Genera ambos archivos de entrada."""
    libro_path = os.path.join(DATA_DIR, "libro_contable.csv")
    cartola_path = os.path.join(DATA_DIR, "cartola_bancaria.csv")

    generate_libro_contable(libro_path)
    generate_cartola_bancaria(cartola_path)

    return libro_path, cartola_path


if __name__ == "__main__":
    libro, cartola = generate_all()
    print(f"Generados:\n  - {libro}\n  - {cartola}")
