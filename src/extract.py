"""
Etapa 1 — EXTRACT
Lectura de archivos de entrada con detección automática de encoding y delimitador.
"""

import os
import pandas as pd


def detect_encoding(path: str) -> str:
    """Detecta encoding probando los más comunes en Chile."""
    for enc in ["utf-8", "latin-1", "cp1252", "iso-8859-1"]:
        try:
            with open(path, "r", encoding=enc) as f:
                f.read(4096)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "utf-8"


def detect_delimiter(path: str, encoding: str) -> str:
    """Detecta delimitador leyendo la primera línea."""
    with open(path, "r", encoding=encoding) as f:
        first_line = f.readline()
    for delim in [";", ",", "\t", "|"]:
        if delim in first_line:
            return delim
    return ","


def extract_file(path: str) -> pd.DataFrame:
    """Extrae un CSV detectando encoding y delimitador automáticamente."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Archivo no encontrado: {path}")

    encoding = detect_encoding(path)
    delimiter = detect_delimiter(path, encoding)

    df = pd.read_csv(path, encoding=encoding, delimiter=delimiter, dtype=str)
    df.attrs["source_file"] = os.path.basename(path)
    df.attrs["encoding"] = encoding
    df.attrs["delimiter"] = delimiter
    df.attrs["raw_rows"] = len(df)

    return df


def extract_all(libro_path: str, cartola_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Extrae ambos archivos de entrada."""
    print("=" * 60)
    print("ETAPA 1: EXTRACCIÓN")
    print("=" * 60)

    df_libro = extract_file(libro_path)
    print(f"  Libro contable : {len(df_libro)} registros | enc={df_libro.attrs['encoding']} | sep='{df_libro.attrs['delimiter']}'")

    df_cartola = extract_file(cartola_path)
    print(f"  Cartola bancaria: {len(df_cartola)} registros | enc={df_cartola.attrs['encoding']} | sep='{df_cartola.attrs['delimiter']}'")

    return df_libro, df_cartola
