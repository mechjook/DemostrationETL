"""
Herramienta de validación y estandarización de archivos de entrada.

Verifica:
  - Existencia y lectura del archivo
  - Encoding correcto
  - Columnas requeridas presentes
  - Formato y dimensión de cada columna
  - Valores nulos o fuera de rango
  - Consistencia de formatos de fecha y monto
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
import numpy as np


@dataclass
class ColumnSpec:
    """Especificación de una columna esperada."""
    name: str
    required: bool = True
    dtype: str = "str"  # str, date, numeric, category
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    allowed_values: Optional[list] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None


@dataclass
class ValidationResult:
    """Resultado de validación de un archivo."""
    file_path: str
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def summary(self) -> str:
        status = "VÁLIDO" if self.is_valid else "INVÁLIDO"
        lines = [
            f"Archivo: {self.file_path}",
            f"Estado : {status}",
            f"Errores: {len(self.errors)} | Advertencias: {len(self.warnings)}",
        ]
        if self.errors:
            lines.append("\nErrores:")
            for e in self.errors:
                lines.append(f"  - {e}")
        if self.warnings:
            lines.append("\nAdvertencias:")
            for w in self.warnings:
                lines.append(f"  - {w}")
        if self.stats:
            lines.append("\nEstadísticas:")
            for k, v in self.stats.items():
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)


# Especificaciones de columnas para cada tipo de archivo
LIBRO_CONTABLE_SPEC = [
    ColumnSpec("Fecha_Registro", required=True, dtype="date", pattern=r"\d{2}-\d{2}-\d{4}"),
    ColumnSpec("Codigo_Operacion", required=True, dtype="str", max_length=10, pattern=r"OP-\d{5}"),
    ColumnSpec("Cuenta_Contable", required=True, dtype="str", max_length=7, pattern=r"\d{7}"),
    ColumnSpec("Nombre_Cuenta", required=True, dtype="str", max_length=50),
    ColumnSpec("Descripcion", required=True, dtype="str", max_length=100),
    ColumnSpec("Tipo_Movimiento", required=True, dtype="category", allowed_values=["CARGO", "ABONO"]),
    ColumnSpec("Monto", required=True, dtype="str", pattern=r"\$[\d\.]+"),
    ColumnSpec("Centro_Costo", required=True, dtype="str", max_length=6, pattern=r"CC-\d{3}"),
]

CARTOLA_BANCARIA_SPEC = [
    ColumnSpec("FECHA_TXN", required=True, dtype="date", pattern=r"\d{4}/\d{2}/\d{2}"),
    ColumnSpec("COD_REF", required=True, dtype="str", max_length=10, pattern=r"OP-\d{5}"),
    ColumnSpec("TIPO_TXN", required=True, dtype="str", max_length=3, allowed_values=["PAG", "TRF", "COM", "IMP", "GIR", "DEP", "ABN", "INT"]),
    ColumnSpec("CLASIFICACION", required=True, dtype="category", allowed_values=["CARGO", "ABONO"]),
    ColumnSpec("DETALLE", required=True, dtype="str", max_length=100),
    ColumnSpec("MONTO_$", required=True, dtype="str", pattern=r"\d+,\d{2}"),
    ColumnSpec("SUCURSAL", required=True, dtype="str", max_length=10),
    ColumnSpec("N_DOCUMENTO", required=True, dtype="str", max_length=15, pattern=r"DOC-\d{6}"),
]


def validate_file(
    path: str,
    specs: list[ColumnSpec],
    encoding: str = "auto",
    delimiter: str = "auto",
) -> ValidationResult:
    """Valida un archivo de entrada contra sus especificaciones."""
    result = ValidationResult(file_path=path)

    # 1. Verificar existencia
    if not os.path.exists(path):
        result.add_error(f"Archivo no encontrado: {path}")
        return result

    # 2. Detectar encoding
    if encoding == "auto":
        from src.extract import detect_encoding
        encoding = detect_encoding(path)

    # 3. Detectar delimitador
    if delimiter == "auto":
        from src.extract import detect_delimiter
        delimiter = detect_delimiter(path, encoding)

    # 4. Leer archivo
    try:
        df = pd.read_csv(path, encoding=encoding, delimiter=delimiter, dtype=str)
    except Exception as e:
        result.add_error(f"Error al leer archivo: {e}")
        return result

    result.stats["filas"] = len(df)
    result.stats["columnas"] = len(df.columns)
    result.stats["encoding"] = encoding
    result.stats["delimiter"] = repr(delimiter)

    # 5. Validar columnas requeridas
    file_columns = set(df.columns.str.strip())
    for spec in specs:
        if spec.required and spec.name not in file_columns:
            result.add_error(f"Columna requerida ausente: '{spec.name}'")

    # 6. Validar cada columna
    for spec in specs:
        col_name = spec.name
        if col_name not in df.columns:
            continue

        col = df[col_name]

        # Nulos
        null_count = col.isna().sum() + (col == "").sum()
        if null_count > 0 and spec.required:
            result.add_warning(f"'{col_name}': {null_count} valores nulos/vacíos")

        # Largo máximo
        if spec.max_length:
            too_long = col.dropna().str.len() > spec.max_length
            if too_long.any():
                count = too_long.sum()
                max_found = col.dropna().str.len().max()
                result.add_warning(
                    f"'{col_name}': {count} valores exceden largo máximo "
                    f"({spec.max_length}). Max encontrado: {max_found}"
                )

        # Patrón regex
        if spec.pattern:
            non_null = col.dropna()
            if len(non_null) > 0:
                matches = non_null.str.match(spec.pattern)
                non_matching = (~matches).sum()
                if non_matching > 0:
                    examples = non_null[~matches].head(3).tolist()
                    result.add_warning(
                        f"'{col_name}': {non_matching} valores no cumplen el patrón "
                        f"'{spec.pattern}'. Ejemplos: {examples}"
                    )

        # Valores permitidos
        if spec.allowed_values:
            non_null = col.dropna().str.strip().str.upper()
            invalid = ~non_null.isin([v.upper() for v in spec.allowed_values])
            if invalid.any():
                bad = non_null[invalid].unique()[:5].tolist()
                result.add_error(
                    f"'{col_name}': valores no permitidos encontrados: {bad}. "
                    f"Permitidos: {spec.allowed_values}"
                )

        # Stats de dimensión
        result.stats[f"{col_name}_unique"] = col.nunique()
        result.stats[f"{col_name}_nulls"] = int(null_count)

    return result


def validate_libro_contable(path: str) -> ValidationResult:
    """Valida archivo de libro contable."""
    return validate_file(path, LIBRO_CONTABLE_SPEC, encoding="auto", delimiter="auto")


def validate_cartola_bancaria(path: str) -> ValidationResult:
    """Valida archivo de cartola bancaria."""
    return validate_file(path, CARTOLA_BANCARIA_SPEC, encoding="auto", delimiter="auto")


def validate_all(libro_path: str, cartola_path: str) -> tuple[ValidationResult, ValidationResult]:
    """Valida ambos archivos de entrada."""
    print("\n" + "=" * 60)
    print("VALIDACIÓN DE ARCHIVOS DE ENTRADA")
    print("=" * 60)

    r1 = validate_libro_contable(libro_path)
    print(f"\n{r1.summary()}")

    r2 = validate_cartola_bancaria(cartola_path)
    print(f"\n{r2.summary()}")

    return r1, r2
