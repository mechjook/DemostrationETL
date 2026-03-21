"""
Etapa 6 — CHARTS
Generación de gráficos para el dashboard de conciliación.
Exporta como imágenes PNG y genera una página HTML consolidada.
"""

import os
import base64
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import pandas as pd
import numpy as np
from jinja2 import Template


sns.set_theme(style="whitegrid", palette="muted")
COLORS = {"libro": "#2563EB", "banco": "#10B981", "diff": "#F59E0B", "alert": "#EF4444"}


def _fig_to_base64(fig) -> str:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _save_fig(fig, path: str):
    fig.savefig(path, dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def chart_conciliacion_resumen(results: dict[str, pd.DataFrame]) -> tuple:
    """Gráfico de torta: proporción match / no-match."""
    matched_count = len(results["matched"]["codigo"].unique()) if len(results["matched"]) > 0 else 0
    solo_libro_count = len(results["solo_libro"])
    solo_banco_count = len(results["solo_banco"])

    fig, ax = plt.subplots(figsize=(7, 5))
    sizes = [matched_count, solo_libro_count, solo_banco_count]
    labels = [f"Conciliados\n({matched_count})", f"Solo Libro\n({solo_libro_count})", f"Solo Banco\n({solo_banco_count})"]
    colors = [COLORS["libro"], COLORS["diff"], COLORS["alert"]]
    ax.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%", startangle=90,
           textprops={"fontsize": 11, "fontweight": "bold"})
    ax.set_title("Resultado de Conciliación Bancaria", fontsize=14, fontweight="bold", pad=20)
    return fig, "conciliacion_resumen"


def chart_montos_comparativo(df_libro: pd.DataFrame, df_cartola: pd.DataFrame) -> tuple:
    """Gráfico de barras mensual comparando montos libro vs banco."""
    fig, ax = plt.subplots(figsize=(12, 5))

    for label, df, color in [("Libro Contable", df_libro, COLORS["libro"]), ("Cartola Bancaria", df_cartola, COLORS["banco"])]:
        df_temp = df.copy()
        df_temp["mes"] = df_temp["fecha"].dt.month
        monthly = df_temp.groupby("mes")["monto"].sum()
        months = range(1, 13)
        values = [monthly.get(m, 0) for m in months]
        offset = -0.2 if "Libro" in label else 0.2
        ax.bar([m + offset for m in months], values, width=0.4, label=label, color=color, alpha=0.85)

    ax.set_xlabel("Mes", fontsize=11)
    ax.set_ylabel("Monto Total ($)", fontsize=11)
    ax.set_title("Comparativo Mensual: Libro Contable vs Cartola Bancaria", fontsize=13, fontweight="bold")
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"])
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.legend(fontsize=10)
    return fig, "montos_comparativo"


def chart_distribucion_montos(df_libro: pd.DataFrame, df_cartola: pd.DataFrame) -> tuple:
    """Histograma superpuesto de distribución de montos."""
    fig, ax = plt.subplots(figsize=(10, 5))

    ax.hist(df_libro["monto"].dropna() / 1_000_000, bins=30, alpha=0.6, label="Libro Contable",
            color=COLORS["libro"], edgecolor="white")
    ax.hist(df_cartola["monto"].dropna() / 1_000_000, bins=30, alpha=0.6, label="Cartola Bancaria",
            color=COLORS["banco"], edgecolor="white")

    ax.set_xlabel("Monto (millones $)", fontsize=11)
    ax.set_ylabel("Frecuencia", fontsize=11)
    ax.set_title("Distribución de Montos por Origen", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10)
    return fig, "distribucion_montos"


def chart_diferencias(results: dict[str, pd.DataFrame]) -> tuple:
    """Boxplot y scatter de diferencias en registros cruzados."""
    matched = results["matched"]
    if len(matched) == 0:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "Sin registros cruzados", ha="center", va="center", fontsize=14)
        return fig, "diferencias"

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Boxplot de diferencias
    diffs = matched["diferencia_monto"] / 1_000_000
    ax1.boxplot(diffs.dropna(), vert=True, patch_artist=True,
                boxprops=dict(facecolor=COLORS["diff"], alpha=0.7))
    ax1.set_ylabel("Diferencia (millones $)", fontsize=11)
    ax1.set_title("Distribución de Diferencias", fontsize=12, fontweight="bold")
    ax1.set_xticklabels(["Libro - Banco"])

    # Scatter monto libro vs monto banco
    ax2.scatter(matched["monto_libro"] / 1_000_000, matched["monto_banco"] / 1_000_000,
                alpha=0.5, c=COLORS["libro"], s=20)
    max_val = max(matched["monto_libro"].max(), matched["monto_banco"].max()) / 1_000_000
    ax2.plot([0, max_val], [0, max_val], "r--", alpha=0.5, label="Línea 1:1")
    ax2.set_xlabel("Monto Libro (millones $)", fontsize=11)
    ax2.set_ylabel("Monto Banco (millones $)", fontsize=11)
    ax2.set_title("Libro vs Banco (registros cruzados)", fontsize=12, fontweight="bold")
    ax2.legend()

    fig.tight_layout()
    return fig, "diferencias"


def chart_tipo_movimiento(df_libro: pd.DataFrame, df_cartola: pd.DataFrame) -> tuple:
    """Gráfico de barras horizontales por tipo de movimiento."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    for ax, df, title, color in [
        (ax1, df_libro, "Libro Contable", COLORS["libro"]),
        (ax2, df_cartola, "Cartola Bancaria", COLORS["banco"]),
    ]:
        grouped = df.groupby("tipo")["monto"].agg(["count", "sum"]).sort_values("sum", ascending=True)
        ax.barh(grouped.index, grouped["sum"] / 1_000_000, color=color, alpha=0.85)
        ax.set_xlabel("Monto Total (millones $)", fontsize=10)
        ax.set_title(f"{title} por Tipo", fontsize=12, fontweight="bold")

        for i, (_, row) in enumerate(grouped.iterrows()):
            ax.text(row["sum"] / 1_000_000, i, f" {int(row['count'])} reg", va="center", fontsize=9)

    fig.tight_layout()
    return fig, "tipo_movimiento"


def chart_top_diferencias(results: dict[str, pd.DataFrame]) -> tuple:
    """Top 15 mayores diferencias absolutas."""
    matched = results["matched"]
    if len(matched) == 0:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "Sin registros cruzados", ha="center", va="center", fontsize=14)
        return fig, "top_diferencias"

    top = matched.nlargest(15, "diferencia_abs").copy()
    top = top.sort_values("diferencia_abs", ascending=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = [COLORS["alert"] if d > 0 else COLORS["banco"] for d in top["diferencia_monto"]]
    ax.barh(top["codigo"], top["diferencia_monto"] / 1_000_000, color=colors, alpha=0.85)
    ax.set_xlabel("Diferencia Libro - Banco (millones $)", fontsize=11)
    ax.set_title("Top 15 Mayores Diferencias en Conciliación", fontsize=13, fontweight="bold")
    ax.axvline(x=0, color="gray", linewidth=0.8)
    fig.tight_layout()
    return fig, "top_diferencias"


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard Conciliación Bancaria - ETL</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0F172A; color: #E2E8F0; }
        .header {
            background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
            padding: 2rem;
            border-bottom: 2px solid #2563EB;
        }
        .header h1 { font-size: 1.8rem; color: #fff; }
        .header p { color: #94A3B8; margin-top: 0.3rem; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            padding: 1.5rem 2rem;
        }
        .stat-card {
            background: #1E293B;
            border-radius: 12px;
            padding: 1.2rem;
            border: 1px solid #334155;
        }
        .stat-card .label { font-size: 0.8rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em; }
        .stat-card .value { font-size: 1.6rem; font-weight: 700; margin-top: 0.3rem; }
        .stat-card .value.blue { color: #60A5FA; }
        .stat-card .value.green { color: #34D399; }
        .stat-card .value.yellow { color: #FBBF24; }
        .stat-card .value.red { color: #F87171; }
        .charts-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 1.5rem;
            padding: 1.5rem 2rem;
            max-width: 1400px;
            margin: 0 auto;
        }
        .chart-card {
            background: #1E293B;
            border-radius: 12px;
            padding: 1.5rem;
            border: 1px solid #334155;
        }
        .chart-card img { width: 100%; height: auto; border-radius: 8px; }
        .footer {
            text-align: center;
            padding: 2rem;
            color: #64748B;
            font-size: 0.85rem;
            border-top: 1px solid #1E293B;
        }
        .footer a { color: #60A5FA; text-decoration: none; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Dashboard Conciliaci&oacute;n Bancaria</h1>
        <p>ETL Pipeline &mdash; An&aacute;lisis autom&aacute;tico generado el {{ generated_at }}</p>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="label">Tasa de Conciliaci&oacute;n</div>
            <div class="value green">{{ tasa_conciliacion }}%</div>
        </div>
        <div class="stat-card">
            <div class="label">Registros Libro</div>
            <div class="value blue">{{ total_libro }}</div>
        </div>
        <div class="stat-card">
            <div class="label">Registros Banco</div>
            <div class="value blue">{{ total_banco }}</div>
        </div>
        <div class="stat-card">
            <div class="label">Registros Cruzados</div>
            <div class="value green">{{ total_matched }}</div>
        </div>
        <div class="stat-card">
            <div class="label">Solo en Libro</div>
            <div class="value yellow">{{ solo_libro }}</div>
        </div>
        <div class="stat-card">
            <div class="label">Solo en Banco</div>
            <div class="value red">{{ solo_banco }}</div>
        </div>
    </div>

    <div class="charts-grid">
        {% for chart in charts %}
        <div class="chart-card">
            <img src="data:image/png;base64,{{ chart.base64 }}" alt="{{ chart.name }}">
        </div>
        {% endfor %}
    </div>

    <div class="footer">
        <p>Generado autom&aacute;ticamente por <strong>ETL Conciliaci&oacute;n Bancaria</strong> |
        <a href="https://github.com/mechjook">mechjook</a> | Pipeline CI/CD con GitHub Actions</p>
    </div>
</body>
</html>"""


def generate_charts(
    results: dict[str, pd.DataFrame],
    df_libro: pd.DataFrame,
    df_cartola: pd.DataFrame,
    stats: dict,
    output_dir: str,
) -> str:
    """Genera todos los gráficos y el dashboard HTML."""
    print("\n" + "=" * 60)
    print("ETAPA 6: GENERACIÓN DE GRÁFICOS Y DASHBOARD")
    print("=" * 60)

    os.makedirs(output_dir, exist_ok=True)
    charts_dir = os.path.join(output_dir, "charts")
    os.makedirs(charts_dir, exist_ok=True)

    chart_functions = [
        chart_conciliacion_resumen,
        chart_montos_comparativo,
        chart_distribucion_montos,
        chart_diferencias,
        chart_tipo_movimiento,
        chart_top_diferencias,
    ]

    charts_data = []
    for func in chart_functions:
        if "results" in func.__code__.co_varnames[:func.__code__.co_argcount]:
            fig, name = func(results)
        else:
            fig, name = func(df_libro, df_cartola)

        png_path = os.path.join(charts_dir, f"{name}.png")
        _save_fig(fig, png_path)

        # Re-read for base64 embedding
        with open(png_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        charts_data.append({"name": name, "base64": b64})
        print(f"  {name}.png generado")

    # Generate HTML dashboard
    from datetime import datetime
    template = Template(HTML_TEMPLATE)
    matched_count = len(results["matched"]["codigo"].unique()) if len(results["matched"]) > 0 else 0

    html = template.render(
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        tasa_conciliacion=stats.get("tasa_conciliacion", 0),
        total_libro=len(df_libro),
        total_banco=len(df_cartola),
        total_matched=matched_count,
        solo_libro=len(results["solo_libro"]),
        solo_banco=len(results["solo_banco"]),
        charts=charts_data,
    )

    html_path = os.path.join(output_dir, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Dashboard HTML generado: {html_path}")

    return html_path
