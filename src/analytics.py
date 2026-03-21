"""
Etapa 5 — ANALYTICS
Análisis de datos y estadísticas de la conciliación bancaria.
"""

import pandas as pd
import numpy as np


def run_analytics(
    results: dict[str, pd.DataFrame],
    df_libro: pd.DataFrame,
    df_cartola: pd.DataFrame,
) -> dict:
    """Ejecuta análisis estadístico completo de la conciliación."""
    print("\n" + "=" * 60)
    print("ETAPA 5: ANÁLISIS DE DATOS Y ESTADÍSTICAS")
    print("=" * 60)

    matched = results["matched"]
    solo_libro = results["solo_libro"]
    solo_banco = results["solo_banco"]

    stats = {}

    # --- Tasa de conciliación ---
    total_codigos = len(set(df_libro["codigo"].unique()) | set(df_cartola["codigo"].unique()))
    codigos_matched = len(matched["codigo"].unique()) if len(matched) > 0 else 0
    tasa_conciliacion = (codigos_matched / total_codigos * 100) if total_codigos > 0 else 0

    stats["tasa_conciliacion"] = round(tasa_conciliacion, 2)
    print(f"\n  Tasa de conciliación: {tasa_conciliacion:.1f}%")

    # --- Estadísticas de montos por origen ---
    for nombre, df in [("Libro", df_libro), ("Banco", df_cartola)]:
        montos = df["monto"].dropna()
        stat = {
            "count": len(montos),
            "mean": round(montos.mean(), 2),
            "median": round(montos.median(), 2),
            "std": round(montos.std(), 2),
            "min": round(montos.min(), 2),
            "max": round(montos.max(), 2),
            "q25": round(montos.quantile(0.25), 2),
            "q75": round(montos.quantile(0.75), 2),
            "total": round(montos.sum(), 2),
        }
        stats[f"montos_{nombre.lower()}"] = stat
        print(f"\n  {nombre}:")
        print(f"    Registros : {stat['count']}")
        print(f"    Promedio  : ${stat['mean']:,.0f}")
        print(f"    Mediana   : ${stat['median']:,.0f}")
        print(f"    Desv. Est.: ${stat['std']:,.0f}")
        print(f"    Rango     : ${stat['min']:,.0f} — ${stat['max']:,.0f}")

    # --- Análisis de diferencias ---
    if len(matched) > 0:
        diffs = matched["diferencia_monto"].dropna()
        stats["diferencias"] = {
            "mean": round(diffs.mean(), 2),
            "median": round(diffs.median(), 2),
            "std": round(diffs.std(), 2),
            "max_positiva": round(diffs.max(), 2),
            "max_negativa": round(diffs.min(), 2),
            "match_exacto_pct": round(matched["match_exacto"].mean() * 100, 2),
        }
        print(f"\n  Diferencias en matched:")
        print(f"    Promedio     : ${diffs.mean():,.0f}")
        print(f"    Max positiva : ${diffs.max():,.0f}")
        print(f"    Max negativa : ${diffs.min():,.0f}")
        print(f"    Match exacto : {matched['match_exacto'].mean() * 100:.1f}%")

    # --- Distribución por tipo ---
    print(f"\n  Distribución por tipo:")
    for nombre, df in [("Libro", df_libro), ("Banco", df_cartola)]:
        dist = df.groupby("tipo")["monto"].agg(["count", "sum"]).reset_index()
        stats[f"dist_tipo_{nombre.lower()}"] = dist.to_dict("records")
        for _, row in dist.iterrows():
            print(f"    {nombre} - {row['tipo']}: {int(row['count'])} registros | ${row['sum']:,.0f}")

    # --- Distribución mensual ---
    print(f"\n  Distribución mensual:")
    for nombre, df in [("Libro", df_libro), ("Banco", df_cartola)]:
        df_temp = df.copy()
        df_temp["mes"] = df_temp["fecha"].dt.month
        dist_mes = df_temp.groupby("mes")["monto"].agg(["count", "sum"]).reset_index()
        stats[f"dist_mes_{nombre.lower()}"] = dist_mes.to_dict("records")

    # --- Análisis de partidas pendientes ---
    stats["partidas_pendientes"] = {
        "solo_libro_count": len(solo_libro),
        "solo_libro_monto": round(solo_libro["monto"].sum(), 2),
        "solo_banco_count": len(solo_banco),
        "solo_banco_monto": round(solo_banco["monto"].sum(), 2),
    }
    print(f"\n  Partidas pendientes de conciliar:")
    print(f"    Solo Libro: {len(solo_libro)} registros | ${solo_libro['monto'].sum():,.0f}")
    print(f"    Solo Banco: {len(solo_banco)} registros | ${solo_banco['monto'].sum():,.0f}")

    return stats
