"""
Etapa 4 — REPORT
Generación de reportes CSV con resumen de conciliación.
"""

import os
import pandas as pd


def generate_reports(
    results: dict[str, pd.DataFrame],
    df_libro: pd.DataFrame,
    df_cartola: pd.DataFrame,
    output_dir: str,
) -> dict[str, str]:
    """Genera reportes CSV de la conciliación."""
    print("\n" + "=" * 60)
    print("ETAPA 4: GENERACIÓN DE REPORTES")
    print("=" * 60)

    os.makedirs(output_dir, exist_ok=True)
    paths = {}

    # 1. Reporte de registros cruzados
    matched = results["matched"]
    matched_path = os.path.join(output_dir, "reporte_matched.csv")
    matched.to_csv(matched_path, index=False, encoding="utf-8")
    paths["matched"] = matched_path
    print(f"  reporte_matched.csv        : {len(matched)} registros")

    # 2. Reporte de solo libro
    solo_libro = results["solo_libro"]
    solo_libro_path = os.path.join(output_dir, "reporte_solo_libro.csv")
    solo_libro.to_csv(solo_libro_path, index=False, encoding="utf-8")
    paths["solo_libro"] = solo_libro_path
    print(f"  reporte_solo_libro.csv     : {len(solo_libro)} registros")

    # 3. Reporte de solo banco
    solo_banco = results["solo_banco"]
    solo_banco_path = os.path.join(output_dir, "reporte_solo_banco.csv")
    solo_banco.to_csv(solo_banco_path, index=False, encoding="utf-8")
    paths["solo_banco"] = solo_banco_path
    print(f"  reporte_solo_banco.csv     : {len(solo_banco)} registros")

    # 4. Reporte resumen ejecutivo
    total_libro = df_libro["monto"].sum()
    total_banco = df_cartola["monto"].sum()
    total_matched_libro = matched["monto_libro"].sum() if len(matched) > 0 else 0
    total_matched_banco = matched["monto_banco"].sum() if len(matched) > 0 else 0
    total_solo_libro = solo_libro["monto"].sum()
    total_solo_banco = solo_banco["monto"].sum()
    diferencia_global = total_libro - total_banco

    resumen = pd.DataFrame([
        {"Concepto": "Total Libro Contable", "Monto": total_libro, "Registros": len(df_libro)},
        {"Concepto": "Total Cartola Bancaria", "Monto": total_banco, "Registros": len(df_cartola)},
        {"Concepto": "Diferencia Global", "Monto": diferencia_global, "Registros": "-"},
        {"Concepto": "---", "Monto": "---", "Registros": "---"},
        {"Concepto": "Total Matched (Libro)", "Monto": total_matched_libro, "Registros": len(matched)},
        {"Concepto": "Total Matched (Banco)", "Monto": total_matched_banco, "Registros": len(matched)},
        {"Concepto": "Diferencia en Matched", "Monto": total_matched_libro - total_matched_banco, "Registros": "-"},
        {"Concepto": "---", "Monto": "---", "Registros": "---"},
        {"Concepto": "Total Solo Libro", "Monto": total_solo_libro, "Registros": len(solo_libro)},
        {"Concepto": "Total Solo Banco", "Monto": total_solo_banco, "Registros": len(solo_banco)},
    ])

    resumen_path = os.path.join(output_dir, "resumen_conciliacion.csv")
    resumen.to_csv(resumen_path, index=False, encoding="utf-8")
    paths["resumen"] = resumen_path
    print(f"  resumen_conciliacion.csv   : resumen ejecutivo generado")

    # 5. Reporte de diferencias en montos (solo matched con diferencia)
    if len(matched) > 0:
        con_diferencia = matched[~matched["match_exacto"]].copy()
        con_diferencia = con_diferencia.sort_values("diferencia_abs", ascending=False)
        diff_path = os.path.join(output_dir, "reporte_diferencias.csv")
        con_diferencia.to_csv(diff_path, index=False, encoding="utf-8")
        paths["diferencias"] = diff_path
        print(f"  reporte_diferencias.csv    : {len(con_diferencia)} registros con diferencia de monto")

    return paths
