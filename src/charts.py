"""
Etapa 6 — CHARTS
Generación de gráficos estáticos (PNG) y dashboard HTML interactivo.
Usa Chart.js para gráficos interactivos con tooltips, zoom y animaciones.
"""

import os
import json
import base64
from io import BytesIO
from datetime import datetime

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
MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


# ──────────────────────────────────────────────
# Matplotlib PNGs (para artefactos CI)
# ──────────────────────────────────────────────

def _save_fig(fig, path: str):
    fig.savefig(path, dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _generate_static_pngs(results, df_libro, df_cartola, charts_dir):
    """Genera los PNGs estáticos como artefactos."""
    os.makedirs(charts_dir, exist_ok=True)

    matched = results["matched"]
    solo_libro = results["solo_libro"]
    solo_banco = results["solo_banco"]

    # 1. Pie conciliación
    fig, ax = plt.subplots(figsize=(7, 5))
    mc = len(matched["codigo"].unique()) if len(matched) > 0 else 0
    sizes = [mc, len(solo_libro), len(solo_banco)]
    labels = [f"Conciliados\n({mc})", f"Solo Libro\n({len(solo_libro)})", f"Solo Banco\n({len(solo_banco)})"]
    ax.pie(sizes, labels=labels, colors=[COLORS["libro"], COLORS["diff"], COLORS["alert"]],
           autopct="%1.1f%%", startangle=90, textprops={"fontsize": 11, "fontweight": "bold"})
    ax.set_title("Resultado de Conciliación Bancaria", fontsize=14, fontweight="bold", pad=20)
    _save_fig(fig, os.path.join(charts_dir, "conciliacion_resumen.png"))

    # 2. Barras mensual
    fig, ax = plt.subplots(figsize=(12, 5))
    for label, df, color in [("Libro", df_libro, COLORS["libro"]), ("Banco", df_cartola, COLORS["banco"])]:
        tmp = df.copy(); tmp["mes"] = tmp["fecha"].dt.month
        monthly = tmp.groupby("mes")["monto"].sum()
        vals = [monthly.get(m, 0) for m in range(1, 13)]
        off = -0.2 if label == "Libro" else 0.2
        ax.bar([m + off for m in range(1, 13)], vals, width=0.4, label=label, color=color, alpha=0.85)
    ax.set_xticks(range(1, 13)); ax.set_xticklabels(MONTHS)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.legend(); ax.set_title("Comparativo Mensual", fontsize=13, fontweight="bold")
    _save_fig(fig, os.path.join(charts_dir, "montos_comparativo.png"))

    # 3. Histograma
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(df_libro["monto"].dropna() / 1e6, bins=30, alpha=0.6, label="Libro", color=COLORS["libro"])
    ax.hist(df_cartola["monto"].dropna() / 1e6, bins=30, alpha=0.6, label="Banco", color=COLORS["banco"])
    ax.legend(); ax.set_title("Distribución de Montos", fontsize=13, fontweight="bold")
    _save_fig(fig, os.path.join(charts_dir, "distribucion_montos.png"))

    # 4. Diferencias
    if len(matched) > 0:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        diffs = matched["diferencia_monto"] / 1e6
        ax1.boxplot(diffs.dropna(), vert=True, patch_artist=True, boxprops=dict(facecolor=COLORS["diff"], alpha=0.7))
        ax1.set_title("Distribución de Diferencias", fontweight="bold")
        ax2.scatter(matched["monto_libro"] / 1e6, matched["monto_banco"] / 1e6, alpha=0.5, c=COLORS["libro"], s=20)
        mx = max(matched["monto_libro"].max(), matched["monto_banco"].max()) / 1e6
        ax2.plot([0, mx], [0, mx], "r--", alpha=0.5, label="1:1")
        ax2.legend(); ax2.set_title("Libro vs Banco", fontweight="bold")
        fig.tight_layout()
        _save_fig(fig, os.path.join(charts_dir, "diferencias.png"))

    # 5. Tipo movimiento
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    for ax, df, title, color in [(ax1, df_libro, "Libro", COLORS["libro"]), (ax2, df_cartola, "Banco", COLORS["banco"])]:
        g = df.groupby("tipo")["monto"].agg(["count", "sum"]).sort_values("sum", ascending=True)
        ax.barh(g.index, g["sum"] / 1e6, color=color, alpha=0.85)
        ax.set_title(f"{title} por Tipo", fontweight="bold")
    fig.tight_layout()
    _save_fig(fig, os.path.join(charts_dir, "tipo_movimiento.png"))

    # 6. Top diferencias
    if len(matched) > 0:
        top = matched.nlargest(15, "diferencia_abs").sort_values("diferencia_abs", ascending=True)
        fig, ax = plt.subplots(figsize=(10, 6))
        cs = [COLORS["alert"] if d > 0 else COLORS["banco"] for d in top["diferencia_monto"]]
        ax.barh(top["codigo"], top["diferencia_monto"] / 1e6, color=cs, alpha=0.85)
        ax.axvline(x=0, color="gray", linewidth=0.8)
        ax.set_title("Top 15 Diferencias", fontsize=13, fontweight="bold")
        fig.tight_layout()
        _save_fig(fig, os.path.join(charts_dir, "top_diferencias.png"))

    print("  PNGs estáticos generados")


# ──────────────────────────────────────────────
# Datos JSON para Chart.js
# ──────────────────────────────────────────────

def _build_chart_data(results, df_libro, df_cartola, stats):
    """Prepara los datos como diccionarios para inyectar en Chart.js."""
    matched = results["matched"]
    solo_libro = results["solo_libro"]
    solo_banco = results["solo_banco"]

    data = {}

    # Pie conciliación
    mc = len(matched["codigo"].unique()) if len(matched) > 0 else 0
    data["pie"] = {"labels": ["Conciliados", "Solo Libro", "Solo Banco"],
                   "values": [mc, len(solo_libro), len(solo_banco)]}

    # Barras mensual
    libro_monthly = []
    banco_monthly = []
    for m in range(1, 13):
        lm = df_libro[df_libro["fecha"].dt.month == m]["monto"].sum()
        bm = df_cartola[df_cartola["fecha"].dt.month == m]["monto"].sum()
        libro_monthly.append(round(float(lm), 0))
        banco_monthly.append(round(float(bm), 0))
    data["monthly"] = {"labels": MONTHS, "libro": libro_monthly, "banco": banco_monthly}

    # Scatter libro vs banco
    if len(matched) > 0:
        scatter_pts = []
        for _, r in matched.head(120).iterrows():
            scatter_pts.append({"x": round(float(r["monto_libro"]) / 1e6, 2),
                                "y": round(float(r["monto_banco"]) / 1e6, 2),
                                "code": r["codigo"]})
        data["scatter"] = scatter_pts
    else:
        data["scatter"] = []

    # Top diferencias
    if len(matched) > 0:
        top = matched.nlargest(15, "diferencia_abs").sort_values("diferencia_abs", ascending=True)
        data["top_diff"] = {
            "labels": top["codigo"].tolist(),
            "values": [round(float(v) / 1e6, 2) for v in top["diferencia_monto"]],
        }
    else:
        data["top_diff"] = {"labels": [], "values": []}

    # Tipo movimiento
    for key, df in [("tipo_libro", df_libro), ("tipo_banco", df_cartola)]:
        g = df.groupby("tipo")["monto"].agg(["count", "sum"]).reset_index()
        data[key] = {
            "labels": g["tipo"].tolist(),
            "counts": g["count"].astype(int).tolist(),
            "sums": [round(float(s) / 1e6, 2) for s in g["sum"]],
        }

    # Distribución montos (histograma)
    for key, df in [("hist_libro", df_libro), ("hist_banco", df_cartola)]:
        vals = (df["monto"].dropna() / 1e6).tolist()
        counts, edges = np.histogram(vals, bins=20)
        labels = [f"{edges[i]:.1f}-{edges[i+1]:.1f}" for i in range(len(counts))]
        data[key] = {"labels": labels, "values": counts.tolist()}

    # Tabla matched
    table_rows = []
    if len(matched) > 0:
        for _, r in matched.sort_values("diferencia_abs", ascending=False).iterrows():
            table_rows.append({
                "codigo": r["codigo"],
                "monto_libro": round(float(r["monto_libro"]), 0),
                "monto_banco": round(float(r["monto_banco"]), 0),
                "diferencia": round(float(r["diferencia_monto"]), 0),
                "match_exacto": bool(r["match_exacto"]),
            })
    data["table_matched"] = table_rows

    # Tabla solo libro
    table_sl = []
    for _, r in solo_libro.iterrows():
        table_sl.append({
            "codigo": r["codigo"],
            "fecha": str(r["fecha"].date()) if pd.notna(r["fecha"]) else "",
            "descripcion": r.get("descripcion", ""),
            "monto": round(float(r["monto"]), 0),
            "tipo": r["tipo"],
        })
    data["table_solo_libro"] = table_sl

    # Tabla solo banco
    table_sb = []
    for _, r in solo_banco.iterrows():
        table_sb.append({
            "codigo": r["codigo"],
            "fecha": str(r["fecha"].date()) if pd.notna(r["fecha"]) else "",
            "descripcion": r.get("descripcion", ""),
            "monto": round(float(r["monto"]), 0),
            "tipo": r["tipo"],
        })
    data["table_solo_banco"] = table_sb

    # KPIs
    data["kpis"] = {
        "tasa": stats.get("tasa_conciliacion", 0),
        "total_libro": len(df_libro),
        "total_banco": len(df_cartola),
        "matched": mc,
        "solo_libro": len(solo_libro),
        "solo_banco": len(solo_banco),
        "monto_libro": round(float(df_libro["monto"].sum()), 0),
        "monto_banco": round(float(df_cartola["monto"].sum()), 0),
        "monto_diff": round(float(df_libro["monto"].sum() - df_cartola["monto"].sum()), 0),
    }

    return data


# ──────────────────────────────────────────────
# HTML Template interactivo
# ──────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard Conciliaci&oacute;n Bancaria</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
:root {
  --bg-primary: #0F172A; --bg-card: #1E293B; --bg-hover: #334155;
  --border: #334155; --text-primary: #E2E8F0; --text-secondary: #94A3B8;
  --blue: #60A5FA; --green: #34D399; --yellow: #FBBF24; --red: #F87171;
  --blue-bg: rgba(96,165,250,0.15); --green-bg: rgba(52,211,153,0.15);
  --yellow-bg: rgba(251,191,36,0.15); --red-bg: rgba(248,113,113,0.15);
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Segoe UI',system-ui,sans-serif; background:var(--bg-primary); color:var(--text-primary); }

/* NAV */
.nav { position:fixed; top:0; left:0; right:0; z-index:100; background:rgba(15,23,42,0.95);
  backdrop-filter:blur(12px); border-bottom:1px solid var(--border); padding:0 2rem; display:flex;
  align-items:center; height:56px; gap:2rem; }
.nav-brand { font-weight:700; font-size:1.1rem; color:#fff; white-space:nowrap; }
.nav-links { display:flex; gap:0.25rem; overflow-x:auto; }
.nav-links a { color:var(--text-secondary); text-decoration:none; padding:0.5rem 1rem; border-radius:8px;
  font-size:0.85rem; transition:all 0.2s; white-space:nowrap; }
.nav-links a:hover, .nav-links a.active { color:#fff; background:var(--bg-hover); }
.nav-status { margin-left:auto; display:flex; align-items:center; gap:0.5rem; font-size:0.8rem; color:var(--green); }
.nav-status .dot { width:8px; height:8px; border-radius:50%; background:var(--green); animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

.container { max-width:1440px; margin:0 auto; padding:72px 2rem 2rem; }
section { display:none; animation:fadeIn 0.4s ease; }
section.active { display:block; }
@keyframes fadeIn { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }

/* HEADER */
.hero { text-align:center; padding:2.5rem 0 1.5rem; }
.hero h1 { font-size:2rem; background:linear-gradient(135deg,var(--blue),var(--green)); -webkit-background-clip:text;
  -webkit-text-fill-color:transparent; }
.hero p { color:var(--text-secondary); margin-top:0.5rem; }

/* KPI CARDS */
.kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:1rem; margin:1.5rem 0; }
.kpi { background:var(--bg-card); border:1px solid var(--border); border-radius:16px; padding:1.5rem;
  transition:transform 0.2s, box-shadow 0.2s; cursor:default; }
.kpi:hover { transform:translateY(-4px); box-shadow:0 8px 25px rgba(0,0,0,0.3); }
.kpi .label { font-size:0.75rem; color:var(--text-secondary); text-transform:uppercase; letter-spacing:0.08em; }
.kpi .value { font-size:2rem; font-weight:800; margin:0.4rem 0 0.2rem; }
.kpi .sub { font-size:0.8rem; color:var(--text-secondary); }
.kpi.blue { border-left:4px solid var(--blue); }
.kpi.blue .value { color:var(--blue); }
.kpi.green { border-left:4px solid var(--green); }
.kpi.green .value { color:var(--green); }
.kpi.yellow { border-left:4px solid var(--yellow); }
.kpi.yellow .value { color:var(--yellow); }
.kpi.red { border-left:4px solid var(--red); }
.kpi.red .value { color:var(--red); }

/* CHARTS */
.chart-row { display:grid; gap:1.5rem; margin:1.5rem 0; }
.chart-row.cols-2 { grid-template-columns:1fr 1fr; }
.chart-row.cols-1 { grid-template-columns:1fr; }
@media(max-width:900px){ .chart-row.cols-2{grid-template-columns:1fr;} }
.chart-card { background:var(--bg-card); border:1px solid var(--border); border-radius:16px; padding:1.5rem;
  transition:box-shadow 0.2s; }
.chart-card:hover { box-shadow:0 4px 20px rgba(0,0,0,0.2); }
.chart-card h3 { font-size:1rem; margin-bottom:1rem; color:var(--text-primary); }
.chart-card canvas { width:100%!important; }

/* TABLES */
.table-controls { display:flex; gap:1rem; margin-bottom:1rem; flex-wrap:wrap; align-items:center; }
.search-input { background:var(--bg-primary); border:1px solid var(--border); border-radius:8px; padding:0.6rem 1rem;
  color:var(--text-primary); font-size:0.85rem; width:280px; outline:none; transition:border 0.2s; }
.search-input:focus { border-color:var(--blue); }
.search-input::placeholder { color:var(--text-secondary); }
.filter-btn { background:var(--bg-primary); border:1px solid var(--border); border-radius:8px; padding:0.5rem 1rem;
  color:var(--text-secondary); font-size:0.8rem; cursor:pointer; transition:all 0.2s; }
.filter-btn:hover, .filter-btn.active { background:var(--blue); color:#fff; border-color:var(--blue); }
.badge { display:inline-block; padding:0.2rem 0.6rem; border-radius:6px; font-size:0.75rem; font-weight:600; }
.badge-green { background:var(--green-bg); color:var(--green); }
.badge-red { background:var(--red-bg); color:var(--red); }
.badge-yellow { background:var(--yellow-bg); color:var(--yellow); }
.badge-blue { background:var(--blue-bg); color:var(--blue); }

table { width:100%; border-collapse:collapse; font-size:0.85rem; }
thead th { background:var(--bg-primary); color:var(--text-secondary); padding:0.8rem 1rem; text-align:left;
  font-size:0.75rem; text-transform:uppercase; letter-spacing:0.05em; position:sticky; top:0;
  cursor:pointer; user-select:none; border-bottom:2px solid var(--border); }
thead th:hover { color:var(--blue); }
thead th .sort-icon { margin-left:0.3rem; opacity:0.4; }
thead th.sorted .sort-icon { opacity:1; color:var(--blue); }
tbody tr { border-bottom:1px solid var(--border); transition:background 0.15s; }
tbody tr:hover { background:var(--bg-hover); }
tbody td { padding:0.7rem 1rem; }
.table-wrapper { max-height:500px; overflow-y:auto; border-radius:12px; border:1px solid var(--border); }
.table-wrapper::-webkit-scrollbar { width:6px; }
.table-wrapper::-webkit-scrollbar-thumb { background:var(--border); border-radius:3px; }
.table-info { font-size:0.8rem; color:var(--text-secondary); margin-top:0.5rem; }
.table-pagination { display:flex; gap:0.5rem; align-items:center; margin-top:0.8rem; justify-content:center; }
.page-btn { background:var(--bg-card); border:1px solid var(--border); color:var(--text-secondary);
  padding:0.4rem 0.8rem; border-radius:6px; cursor:pointer; font-size:0.8rem; transition:all 0.2s; }
.page-btn:hover, .page-btn.active { background:var(--blue); color:#fff; border-color:var(--blue); }

/* FOOTER */
.footer { text-align:center; padding:3rem 2rem; color:var(--text-secondary); font-size:0.8rem;
  border-top:1px solid var(--border); margin-top:3rem; }
.footer a { color:var(--blue); text-decoration:none; }

/* PROGRESS BAR */
.progress-bar { width:100%; height:8px; background:var(--bg-primary); border-radius:4px; overflow:hidden; margin-top:0.5rem; }
.progress-fill { height:100%; border-radius:4px; transition:width 1.5s ease; }
</style>
</head>
<body>

<nav class="nav">
  <div class="nav-brand">ETL Conciliaci&oacute;n</div>
  <div class="nav-links">
    <a href="#" data-section="resumen" class="active">Resumen</a>
    <a href="#" data-section="graficos">Gr&aacute;ficos</a>
    <a href="#" data-section="analisis">An&aacute;lisis</a>
    <a href="#" data-section="tablas">Tablas</a>
    <a href="#" data-section="pendientes">Pendientes</a>
  </div>
  <div class="nav-status"><span class="dot"></span> Pipeline OK &mdash; {{ generated_at }}</div>
</nav>

<div class="container">

<!-- ===================== RESUMEN ===================== -->
<section id="resumen" class="active">
  <div class="hero">
    <h1>Dashboard Conciliaci&oacute;n Bancaria</h1>
    <p>An&aacute;lisis autom&aacute;tico del cruce entre Libro Contable y Cartola Bancaria</p>
  </div>

  <div class="kpi-grid">
    <div class="kpi green">
      <div class="label">Tasa de Conciliaci&oacute;n</div>
      <div class="value" data-counter="{{ kpis.tasa }}" data-suffix="%">0%</div>
      <div class="progress-bar"><div class="progress-fill" style="width:0%;background:var(--green);" data-width="{{ kpis.tasa }}%"></div></div>
    </div>
    <div class="kpi blue">
      <div class="label">Registros Libro</div>
      <div class="value" data-counter="{{ kpis.total_libro }}">0</div>
      <div class="sub">Monto: $<span data-counter="{{ kpis.monto_libro }}" data-format="money">0</span></div>
    </div>
    <div class="kpi blue">
      <div class="label">Registros Banco</div>
      <div class="value" data-counter="{{ kpis.total_banco }}">0</div>
      <div class="sub">Monto: $<span data-counter="{{ kpis.monto_banco }}" data-format="money">0</span></div>
    </div>
    <div class="kpi green">
      <div class="label">C&oacute;digos Conciliados</div>
      <div class="value" data-counter="{{ kpis.matched }}">0</div>
      <div class="sub">de {{ kpis.total_libro }} + {{ kpis.total_banco }} registros</div>
    </div>
    <div class="kpi yellow">
      <div class="label">Solo en Libro</div>
      <div class="value" data-counter="{{ kpis.solo_libro }}">0</div>
      <div class="sub">Sin contraparte bancaria</div>
    </div>
    <div class="kpi red">
      <div class="label">Solo en Banco</div>
      <div class="value" data-counter="{{ kpis.solo_banco }}">0</div>
      <div class="sub">Sin contraparte contable</div>
    </div>
  </div>

  <div class="chart-row cols-2">
    <div class="chart-card">
      <h3>Resultado de Conciliaci&oacute;n</h3>
      <canvas id="chartPie"></canvas>
    </div>
    <div class="chart-card">
      <h3>Distribuci&oacute;n por Tipo de Movimiento</h3>
      <canvas id="chartTipo"></canvas>
    </div>
  </div>
</section>

<!-- ===================== GRÁFICOS ===================== -->
<section id="graficos">
  <div class="hero"><h1>Gr&aacute;ficos Interactivos</h1><p>Haz hover para ver detalles &mdash; Click en leyendas para filtrar</p></div>

  <div class="chart-row cols-1">
    <div class="chart-card">
      <h3>Comparativo Mensual: Libro vs Banco</h3>
      <canvas id="chartMonthly" height="80"></canvas>
    </div>
  </div>
  <div class="chart-row cols-2">
    <div class="chart-card">
      <h3>Distribuci&oacute;n de Montos — Libro</h3>
      <canvas id="chartHistLibro"></canvas>
    </div>
    <div class="chart-card">
      <h3>Distribuci&oacute;n de Montos — Banco</h3>
      <canvas id="chartHistBanco"></canvas>
    </div>
  </div>
  <div class="chart-row cols-1">
    <div class="chart-card">
      <h3>Libro vs Banco — Registros Cruzados (millones $)</h3>
      <canvas id="chartScatter" height="90"></canvas>
    </div>
  </div>
</section>

<!-- ===================== ANÁLISIS ===================== -->
<section id="analisis">
  <div class="hero"><h1>An&aacute;lisis de Diferencias</h1><p>Top diferencias y dispersi&oacute;n de montos entre origenes</p></div>

  <div class="chart-row cols-1">
    <div class="chart-card">
      <h3>Top 15 Mayores Diferencias (millones $)</h3>
      <canvas id="chartTopDiff" height="100"></canvas>
    </div>
  </div>

  <div class="kpi-grid" style="margin-top:1.5rem;">
    <div class="kpi blue">
      <div class="label">Diferencia Global</div>
      <div class="value">$<span data-counter="{{ kpis.monto_diff }}" data-format="money">0</span></div>
      <div class="sub">Libro &minus; Banco</div>
    </div>
    <div class="kpi green">
      <div class="label">Promedio Libro</div>
      <div class="value" style="font-size:1.4rem;">$<span data-counter="{{ stats_mean_libro }}" data-format="money">0</span></div>
    </div>
    <div class="kpi green">
      <div class="label">Promedio Banco</div>
      <div class="value" style="font-size:1.4rem;">$<span data-counter="{{ stats_mean_banco }}" data-format="money">0</span></div>
    </div>
    <div class="kpi yellow">
      <div class="label">Mediana Libro</div>
      <div class="value" style="font-size:1.4rem;">$<span data-counter="{{ stats_median_libro }}" data-format="money">0</span></div>
    </div>
    <div class="kpi yellow">
      <div class="label">Mediana Banco</div>
      <div class="value" style="font-size:1.4rem;">$<span data-counter="{{ stats_median_banco }}" data-format="money">0</span></div>
    </div>
    <div class="kpi red">
      <div class="label">Desv. Est&aacute;ndar Libro</div>
      <div class="value" style="font-size:1.4rem;">$<span data-counter="{{ stats_std_libro }}" data-format="money">0</span></div>
    </div>
  </div>
</section>

<!-- ===================== TABLAS ===================== -->
<section id="tablas">
  <div class="hero"><h1>Registros Conciliados</h1><p>Busca, filtra y ordena los {{ kpis.matched }} registros cruzados</p></div>

  <div class="table-controls">
    <input type="text" class="search-input" id="searchMatched" placeholder="Buscar por c&oacute;digo...">
    <button class="filter-btn active" data-filter="all" data-table="matched">Todos</button>
    <button class="filter-btn" data-filter="exact" data-table="matched">Match Exacto</button>
    <button class="filter-btn" data-filter="diff" data-table="matched">Con Diferencia</button>
  </div>
  <div class="table-wrapper">
    <table id="tableMatched">
      <thead>
        <tr>
          <th data-sort="codigo">C&oacute;digo <span class="sort-icon">&#x25B2;&#x25BC;</span></th>
          <th data-sort="monto_libro">Monto Libro <span class="sort-icon">&#x25B2;&#x25BC;</span></th>
          <th data-sort="monto_banco">Monto Banco <span class="sort-icon">&#x25B2;&#x25BC;</span></th>
          <th data-sort="diferencia">Diferencia <span class="sort-icon">&#x25B2;&#x25BC;</span></th>
          <th>Estado</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>
  <div class="table-info" id="matchedInfo"></div>
  <div class="table-pagination" id="matchedPagination"></div>
</section>

<!-- ===================== PENDIENTES ===================== -->
<section id="pendientes">
  <div class="hero"><h1>Partidas Pendientes</h1><p>Registros sin contraparte que requieren revisi&oacute;n</p></div>

  <div class="chart-row cols-2">
    <div class="chart-card">
      <h3>Solo en Libro ({{ kpis.solo_libro }} registros)</h3>
      <div class="table-controls">
        <input type="text" class="search-input" id="searchSoloLibro" placeholder="Buscar...">
      </div>
      <div class="table-wrapper" style="max-height:400px;">
        <table id="tableSoloLibro">
          <thead><tr><th>C&oacute;digo</th><th>Fecha</th><th>Tipo</th><th>Monto</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
    <div class="chart-card">
      <h3>Solo en Banco ({{ kpis.solo_banco }} registros)</h3>
      <div class="table-controls">
        <input type="text" class="search-input" id="searchSoloBanco" placeholder="Buscar...">
      </div>
      <div class="table-wrapper" style="max-height:400px;">
        <table id="tableSoloBanco">
          <thead><tr><th>C&oacute;digo</th><th>Fecha</th><th>Tipo</th><th>Monto</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </div>
</section>

</div><!-- /container -->

<div class="footer">
  <p>Generado autom&aacute;ticamente por <strong>ETL Conciliaci&oacute;n Bancaria</strong> |
  <a href="https://github.com/mechjook" target="_blank">@mechjook</a> |
  Pipeline CI/CD con GitHub Actions</p>
</div>

<script>
// ═══════════════════════════════════════
// DATA
// ═══════════════════════════════════════
const DATA = {{ chart_data_json }};

// ═══════════════════════════════════════
// NAV
// ═══════════════════════════════════════
document.querySelectorAll('.nav-links a').forEach(link => {
  link.addEventListener('click', e => {
    e.preventDefault();
    document.querySelectorAll('.nav-links a').forEach(l => l.classList.remove('active'));
    document.querySelectorAll('section').forEach(s => s.classList.remove('active'));
    link.classList.add('active');
    const sec = document.getElementById(link.dataset.section);
    sec.classList.add('active');
    animateCounters(sec);
    animateProgressBars(sec);
  });
});

// ═══════════════════════════════════════
// ANIMATED COUNTERS
// ═══════════════════════════════════════
function animateCounters(container) {
  container.querySelectorAll('[data-counter]').forEach(el => {
    const target = parseFloat(el.dataset.counter);
    const suffix = el.dataset.suffix || '';
    const isMoney = el.dataset.format === 'money';
    const duration = 1200;
    const start = performance.now();
    function tick(now) {
      const p = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - p, 3);
      const val = target * ease;
      if (isMoney) el.textContent = Math.round(val).toLocaleString('es-CL');
      else if (suffix === '%') el.textContent = val.toFixed(1) + '%';
      else el.textContent = Math.round(val).toLocaleString('es-CL');
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  });
}

function animateProgressBars(container) {
  container.querySelectorAll('.progress-fill').forEach(bar => {
    setTimeout(() => { bar.style.width = bar.dataset.width; }, 200);
  });
}

// Initial animation
animateCounters(document.getElementById('resumen'));
animateProgressBars(document.getElementById('resumen'));

// ═══════════════════════════════════════
// FORMAT HELPERS
// ═══════════════════════════════════════
const fmtMoney = v => '$' + Math.round(v).toLocaleString('es-CL');
const fmtM = v => '$' + v.toFixed(1) + 'M';

// ═══════════════════════════════════════
// CHARTS
// ═══════════════════════════════════════
const BLUE = '#60A5FA', GREEN = '#34D399', YELLOW = '#FBBF24', RED = '#F87171';
const BLUE_A = 'rgba(96,165,250,0.7)', GREEN_A = 'rgba(52,211,153,0.7)', YELLOW_A = 'rgba(251,191,36,0.7)', RED_A = 'rgba(248,113,113,0.7)';

Chart.defaults.color = '#94A3B8';
Chart.defaults.borderColor = 'rgba(51,65,85,0.5)';
Chart.defaults.font.family = "'Segoe UI',system-ui,sans-serif";

// Pie
new Chart(document.getElementById('chartPie'), {
  type: 'doughnut',
  data: { labels: DATA.pie.labels, datasets: [{ data: DATA.pie.values, backgroundColor: [BLUE_A, YELLOW_A, RED_A],
    borderColor: [BLUE, YELLOW, RED], borderWidth: 2, hoverOffset: 15 }] },
  options: { responsive:true, plugins: { legend: { position:'bottom', labels:{padding:20,usePointStyle:true} },
    tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.parsed} registros (${(ctx.parsed/DATA.pie.values.reduce((a,b)=>a+b,0)*100).toFixed(1)}%)` } } },
    animation: { animateRotate:true, duration:1500 } }
});

// Tipo movimiento (stacked)
new Chart(document.getElementById('chartTipo'), {
  type: 'bar',
  data: { labels: DATA.tipo_libro.labels,
    datasets: [
      { label:'Libro (millones $)', data:DATA.tipo_libro.sums, backgroundColor:BLUE_A, borderColor:BLUE, borderWidth:1 },
      { label:'Banco (millones $)', data:DATA.tipo_banco.sums, backgroundColor:GREEN_A, borderColor:GREEN, borderWidth:1 }
    ] },
  options: { responsive:true, plugins:{ tooltip:{ callbacks:{ label: ctx => `${ctx.dataset.label}: $${ctx.parsed.y.toFixed(1)}M (${DATA['tipo_'+(ctx.datasetIndex===0?'libro':'banco')].counts[ctx.dataIndex]} reg)` }}},
    scales:{ y:{ beginAtZero:true, ticks:{ callback: v => '$'+v+'M' } } },
    animation:{ duration:1200 } }
});

// Monthly
new Chart(document.getElementById('chartMonthly'), {
  type: 'bar',
  data: { labels: DATA.monthly.labels,
    datasets: [
      { label:'Libro Contable', data:DATA.monthly.libro, backgroundColor:BLUE_A, borderColor:BLUE, borderWidth:1, borderRadius:4 },
      { label:'Cartola Bancaria', data:DATA.monthly.banco, backgroundColor:GREEN_A, borderColor:GREEN, borderWidth:1, borderRadius:4 }
    ] },
  options: { responsive:true, plugins:{ tooltip:{ callbacks:{ label: ctx => `${ctx.dataset.label}: ${fmtMoney(ctx.parsed.y)}` } },
    legend:{position:'top',labels:{usePointStyle:true}} },
    scales:{ y:{ beginAtZero:true, ticks:{ callback: v => '$'+(v/1e6).toFixed(0)+'M' } } },
    animation:{ duration:1500 } }
});

// Histograms
['Libro','Banco'].forEach((name, i) => {
  const key = i===0 ? 'hist_libro' : 'hist_banco';
  const color = i===0 ? BLUE : GREEN;
  const colorA = i===0 ? BLUE_A : GREEN_A;
  new Chart(document.getElementById('chartHist'+name), {
    type:'bar',
    data:{ labels:DATA[key].labels, datasets:[{ label:'Frecuencia', data:DATA[key].values,
      backgroundColor:colorA, borderColor:color, borderWidth:1, borderRadius:2 }] },
    options:{ responsive:true, plugins:{ legend:{display:false},
      tooltip:{ callbacks:{ title:ctx=>`Rango: ${ctx[0].label} M`, label:ctx=>`${ctx.parsed.y} registros` }}},
      scales:{ x:{ ticks:{ maxRotation:45 } }, y:{ beginAtZero:true } }, animation:{duration:1000} }
  });
});

// Scatter
new Chart(document.getElementById('chartScatter'), {
  type:'scatter',
  data:{ datasets:[
    { label:'Registros cruzados', data:DATA.scatter, backgroundColor:BLUE_A, borderColor:BLUE, pointRadius:5, pointHoverRadius:8 },
    { label:'L\\u00ednea 1:1', data:[{x:0,y:0},{x:Math.max(...DATA.scatter.map(p=>p.x)),y:Math.max(...DATA.scatter.map(p=>p.y))}],
      type:'line', borderColor:RED, borderDash:[6,4], pointRadius:0, borderWidth:2 }
  ]},
  options:{ responsive:true, plugins:{ tooltip:{ callbacks:{ label:ctx=> ctx.raw.code ? `${ctx.raw.code}: Libro $${ctx.raw.x}M | Banco $${ctx.raw.y}M` : '' }},
    legend:{position:'top',labels:{usePointStyle:true}} },
    scales:{ x:{title:{display:true,text:'Monto Libro (millones $)'}}, y:{title:{display:true,text:'Monto Banco (millones $)'}} },
    animation:{duration:1500} }
});

// Top diferencias
new Chart(document.getElementById('chartTopDiff'), {
  type:'bar',
  data:{ labels:DATA.top_diff.labels, datasets:[{ label:'Diferencia (millones $)', data:DATA.top_diff.values,
    backgroundColor: DATA.top_diff.values.map(v => v > 0 ? RED_A : GREEN_A),
    borderColor: DATA.top_diff.values.map(v => v > 0 ? RED : GREEN), borderWidth:1, borderRadius:4 }] },
  options:{ indexAxis:'y', responsive:true, plugins:{ tooltip:{ callbacks:{ label:ctx=>`Diferencia: $${ctx.parsed.x.toFixed(2)}M` }},
    legend:{display:false} },
    scales:{ x:{ ticks:{ callback:v=>'$'+v+'M' } } }, animation:{duration:1500} }
});

// ═══════════════════════════════════════
// TABLES
// ═══════════════════════════════════════
const PAGE_SIZE = 20;
let matchedState = { data: DATA.table_matched, filtered: DATA.table_matched, page: 0, sort: {col:'diferencia',asc:false}, filter:'all' };

function renderMatchedTable() {
  const s = matchedState;
  const start = s.page * PAGE_SIZE;
  const pageData = s.filtered.slice(start, start + PAGE_SIZE);
  const tbody = document.querySelector('#tableMatched tbody');
  tbody.innerHTML = pageData.map(r => `<tr>
    <td><strong>${r.codigo}</strong></td>
    <td>${fmtMoney(r.monto_libro)}</td>
    <td>${fmtMoney(r.monto_banco)}</td>
    <td style="color:${Math.abs(r.diferencia)<1?'var(--green)':r.diferencia>0?'var(--yellow)':'var(--red)'}">${fmtMoney(r.diferencia)}</td>
    <td>${r.match_exacto ? '<span class="badge badge-green">Exacto</span>' : '<span class="badge badge-yellow">Diferencia</span>'}</td>
  </tr>`).join('');
  document.getElementById('matchedInfo').textContent = `Mostrando ${start+1}-${Math.min(start+PAGE_SIZE, s.filtered.length)} de ${s.filtered.length} registros`;
  renderPagination('matchedPagination', s.filtered.length, s.page, p => { matchedState.page = p; renderMatchedTable(); });
}

function renderPagination(containerId, total, currentPage, onClick) {
  const pages = Math.ceil(total / PAGE_SIZE);
  const c = document.getElementById(containerId);
  if (pages <= 1) { c.innerHTML = ''; return; }
  let html = '';
  const maxShow = 7;
  let startP = Math.max(0, currentPage - 3);
  let endP = Math.min(pages, startP + maxShow);
  if (endP - startP < maxShow) startP = Math.max(0, endP - maxShow);
  if (startP > 0) html += `<button class="page-btn" data-p="0">1</button><span style="color:var(--text-secondary)">...</span>`;
  for (let i = startP; i < endP; i++)
    html += `<button class="page-btn ${i===currentPage?'active':''}" data-p="${i}">${i+1}</button>`;
  if (endP < pages) html += `<span style="color:var(--text-secondary)">...</span><button class="page-btn" data-p="${pages-1}">${pages}</button>`;
  c.innerHTML = html;
  c.querySelectorAll('.page-btn').forEach(btn => btn.addEventListener('click', () => onClick(parseInt(btn.dataset.p))));
}

// Sort
document.querySelectorAll('#tableMatched th[data-sort]').forEach(th => {
  th.addEventListener('click', () => {
    const col = th.dataset.sort;
    if (matchedState.sort.col === col) matchedState.sort.asc = !matchedState.sort.asc;
    else { matchedState.sort.col = col; matchedState.sort.asc = true; }
    document.querySelectorAll('#tableMatched th').forEach(t => t.classList.remove('sorted'));
    th.classList.add('sorted');
    matchedState.filtered.sort((a,b) => {
      const va = a[col], vb = b[col];
      return matchedState.sort.asc ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1);
    });
    matchedState.page = 0;
    renderMatchedTable();
  });
});

// Search
document.getElementById('searchMatched').addEventListener('input', e => {
  const q = e.target.value.toUpperCase();
  applyMatchedFilters(q, matchedState.filter);
});

// Filter buttons
document.querySelectorAll('[data-table="matched"]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('[data-table="matched"]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    matchedState.filter = btn.dataset.filter;
    const q = document.getElementById('searchMatched').value.toUpperCase();
    applyMatchedFilters(q, matchedState.filter);
  });
});

function applyMatchedFilters(query, filter) {
  let f = matchedState.data;
  if (query) f = f.filter(r => r.codigo.toUpperCase().includes(query));
  if (filter === 'exact') f = f.filter(r => r.match_exacto);
  else if (filter === 'diff') f = f.filter(r => !r.match_exacto);
  matchedState.filtered = f;
  matchedState.page = 0;
  renderMatchedTable();
}

renderMatchedTable();

// Solo libro / banco tables
function renderSimpleTable(tableId, data, searchId) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  function render(filtered) {
    tbody.innerHTML = filtered.map(r => `<tr>
      <td><strong>${r.codigo}</strong></td>
      <td>${r.fecha}</td>
      <td><span class="badge ${r.tipo==='CARGO'?'badge-red':'badge-blue'}">${r.tipo}</span></td>
      <td>${fmtMoney(r.monto)}</td>
    </tr>`).join('');
  }
  render(data);
  if (searchId) {
    document.getElementById(searchId).addEventListener('input', e => {
      const q = e.target.value.toUpperCase();
      render(q ? data.filter(r => r.codigo.toUpperCase().includes(q) || r.descripcion.toUpperCase().includes(q)) : data);
    });
  }
}
renderSimpleTable('tableSoloLibro', DATA.table_solo_libro, 'searchSoloLibro');
renderSimpleTable('tableSoloBanco', DATA.table_solo_banco, 'searchSoloBanco');
</script>
</body>
</html>"""


# ──────────────────────────────────────────────
# Generación principal
# ──────────────────────────────────────────────

def generate_charts(
    results: dict[str, pd.DataFrame],
    df_libro: pd.DataFrame,
    df_cartola: pd.DataFrame,
    stats: dict,
    output_dir: str,
) -> str:
    """Genera PNGs estáticos y dashboard HTML interactivo."""
    print("\n" + "=" * 60)
    print("ETAPA 6: GENERACIÓN DE GRÁFICOS Y DASHBOARD")
    print("=" * 60)

    os.makedirs(output_dir, exist_ok=True)
    charts_dir = os.path.join(output_dir, "charts")

    # PNGs estáticos
    _generate_static_pngs(results, df_libro, df_cartola, charts_dir)

    # Datos para Chart.js
    chart_data = _build_chart_data(results, df_libro, df_cartola, stats)

    # Render HTML
    template = Template(HTML_TEMPLATE)
    kpis = chart_data["kpis"]

    montos_libro = stats.get("montos_libro", {})
    montos_banco = stats.get("montos_banco", {})

    html = template.render(
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        kpis=kpis,
        chart_data_json=json.dumps(chart_data, ensure_ascii=False),
        stats_mean_libro=int(montos_libro.get("mean", 0)),
        stats_mean_banco=int(montos_banco.get("mean", 0)),
        stats_median_libro=int(montos_libro.get("median", 0)),
        stats_median_banco=int(montos_banco.get("median", 0)),
        stats_std_libro=int(montos_libro.get("std", 0)),
    )

    html_path = os.path.join(output_dir, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Dashboard interactivo generado: {html_path}")

    return html_path
