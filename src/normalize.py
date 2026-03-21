"""
Etapa 2 — NORMALIZE
Estandarización de formatos: columnas, fechas, montos y tipos.
"""

import re
import pandas as pd
import numpy as np


def _clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Estandariza nombres de columnas a snake_case."""
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(r"[^a-z0-9_]", "_", regex=True)
        .str.replace(r"_+", "_", regex=True)
        .str.strip("_")
    )
    return df


def _parse_monto_libro(valor: str) -> float:
    """Parsea montos del libro contable: '$1.500.000' → 1500000.0"""
    if pd.isna(valor) or str(valor).strip() == "":
        return np.nan
    cleaned = re.sub(r"[$ ]", "", str(valor))
    cleaned = cleaned.replace(".", "")
    cleaned = cleaned.replace(",", ".")
    return float(cleaned)


def _parse_monto_cartola(valor: str) -> float:
    """Parsea montos de la cartola: '1500000,50' → 1500000.50"""
    if pd.isna(valor) or str(valor).strip() == "":
        return np.nan
    cleaned = re.sub(r"[$ ]", "", str(valor))
    cleaned = cleaned.replace(".", "")
    cleaned = cleaned.replace(",", ".")
    return float(cleaned)


def _parse_fecha_libro(fecha: str) -> pd.Timestamp:
    """Parsea fechas del libro: 'DD-MM-YYYY' → datetime"""
    try:
        return pd.to_datetime(fecha, format="%d-%m-%Y")
    except (ValueError, TypeError):
        return pd.NaT


def _parse_fecha_cartola(fecha: str) -> pd.Timestamp:
    """Parsea fechas de la cartola: 'YYYY/MM/DD' → datetime"""
    try:
        return pd.to_datetime(fecha, format="%Y/%m/%d")
    except (ValueError, TypeError):
        return pd.NaT


def normalize_libro(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza el libro contable a formato estándar."""
    df = _clean_column_names(df.copy())

    column_map = {
        "fecha_registro": "fecha",
        "codigo_operacion": "codigo",
        "cuenta_contable": "cuenta",
        "nombre_cuenta": "nombre_cuenta",
        "descripcion": "descripcion",
        "tipo_movimiento": "tipo",
        "monto": "monto",
        "centro_costo": "centro_costo",
    }
    df = df.rename(columns=column_map)

    df["fecha"] = df["fecha"].apply(_parse_fecha_libro)
    df["monto"] = df["monto"].apply(_parse_monto_libro)
    df["codigo"] = df["codigo"].str.strip().str.upper()
    df["tipo"] = df["tipo"].str.strip().str.upper()
    df["origen"] = "LIBRO"

    return df


def normalize_cartola(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza la cartola bancaria a formato estándar."""
    df = _clean_column_names(df.copy())

    column_map = {
        "fecha_txn": "fecha",
        "cod_ref": "codigo",
        "tipo_txn": "subtipo_txn",
        "clasificacion": "tipo",
        "detalle": "descripcion",
        "monto__": "monto",
        "sucursal": "sucursal",
        "n_documento": "num_documento",
    }
    df = df.rename(columns=column_map)

    df["fecha"] = df["fecha"].apply(_parse_fecha_cartola)
    df["monto"] = df["monto"].apply(_parse_monto_cartola)
    df["codigo"] = df["codigo"].str.strip().str.upper()
    df["tipo"] = df["tipo"].str.strip().str.upper()
    df["origen"] = "BANCO"

    return df


def normalize_all(df_libro: pd.DataFrame, df_cartola: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ejecuta la normalización completa."""
    print("\n" + "=" * 60)
    print("ETAPA 2: NORMALIZACIÓN")
    print("=" * 60)

    libro_norm = normalize_libro(df_libro)
    nulos_libro = libro_norm["monto"].isna().sum()
    print(f"  Libro contable : {len(libro_norm)} registros normalizados | {nulos_libro} montos nulos")

    cartola_norm = normalize_cartola(df_cartola)
    nulos_cartola = cartola_norm["monto"].isna().sum()
    print(f"  Cartola bancaria: {len(cartola_norm)} registros normalizados | {nulos_cartola} montos nulos")

    return libro_norm, cartola_norm
