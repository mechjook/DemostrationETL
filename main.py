"""
ETL Conciliación Bancaria — Pipeline Principal
================================================
Demostración de capacidades de automatización de procesos contables.

Etapas:
  1. Generación de datos sintéticos
  2. Validación de archivos de entrada
  3. Extracción (detección automática de encoding/delimitador)
  4. Normalización (estandarización de formatos)
  5. Match por código de operación
  6. Generación de reportes
  7. Análisis estadístico
  8. Generación de gráficos y dashboard HTML

Autor: José Nicolás Candia (@mechjook)
"""

import os
import sys
import time

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

LIBRO_PATH = os.path.join(DATA_DIR, "libro_contable.csv")
CARTOLA_PATH = os.path.join(DATA_DIR, "cartola_bancaria.csv")


def main():
    start = time.time()

    print("╔══════════════════════════════════════════════════════════╗")
    print("║     ETL CONCILIACIÓN BANCARIA — PIPELINE AUTOMÁTICO     ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # --- Etapa 0: Generación de datos ---
    from src.generate_data import generate_all
    print("\n" + "=" * 60)
    print("ETAPA 0: GENERACIÓN DE DATOS SINTÉTICOS")
    print("=" * 60)
    libro_path, cartola_path = generate_all()
    print(f"  Libro contable : {libro_path}")
    print(f"  Cartola bancaria: {cartola_path}")

    # --- Etapa 1: Validación ---
    from validators.file_validator import validate_all
    result_libro, result_cartola = validate_all(libro_path, cartola_path)

    if not result_libro.is_valid or not result_cartola.is_valid:
        print("\n⚠ ARCHIVOS DE ENTRADA INVÁLIDOS — PIPELINE DETENIDO")
        sys.exit(1)

    # --- Etapa 2: Extracción ---
    from src.extract import extract_all
    df_libro, df_cartola = extract_all(libro_path, cartola_path)

    # --- Etapa 3: Normalización ---
    from src.normalize import normalize_all
    libro_norm, cartola_norm = normalize_all(df_libro, df_cartola)

    # --- Etapa 4: Match ---
    from src.match import match_records
    results = match_records(libro_norm, cartola_norm)

    # --- Etapa 5: Reportes ---
    from src.report import generate_reports
    report_paths = generate_reports(results, libro_norm, cartola_norm, OUTPUT_DIR)

    # --- Etapa 6: Analytics ---
    from src.analytics import run_analytics
    stats = run_analytics(results, libro_norm, cartola_norm)

    # --- Etapa 7: Charts & Dashboard ---
    from src.charts import generate_charts
    dashboard_path = generate_charts(results, libro_norm, cartola_norm, stats, OUTPUT_DIR)

    # --- Resumen final ---
    elapsed = time.time() - start
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETADO")
    print("=" * 60)
    print(f"  Tiempo total     : {elapsed:.2f}s")
    print(f"  Dashboard        : {dashboard_path}")
    print(f"  Reportes en      : {OUTPUT_DIR}/")
    print(f"  Gráficos en      : {OUTPUT_DIR}/charts/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
