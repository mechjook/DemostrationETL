# ETL Conciliación Bancaria

Pipeline automatizado de conciliación bancaria que cruza registros del **libro contable** contra la **cartola bancaria**, genera reportes de diferencias y publica un dashboard interactivo de gráficos vía GitHub Pages.

[![ETL Pipeline](https://github.com/mechjook/DemostrationETL/actions/workflows/etl_pipeline.yml/badge.svg)](https://github.com/mechjook/DemostrationETL/actions/workflows/etl_pipeline.yml)

## Dashboard

Disponible en: **[GitHub Pages](https://mechjook.github.io/DemostrationETL/)**

## Arquitectura del Pipeline

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────┐
│  Generación  │───▶│  Validación   │───▶│  Extracción   │───▶│ Normal. │
│  de Datos    │    │  de Archivos  │    │  Automática   │    │         │
└─────────────┘    └──────────────┘    └──────────────┘    └────┬────┘
                                                                │
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────▼────┐
│  Dashboard   │◀──│  Analytics    │◀──│   Reportes    │◀──│  Match  │
│  HTML+Charts │    │  Estadísticas │    │   CSV         │    │ Códigos │
└─────────────┘    └──────────────┘    └──────────────┘    └─────────┘
```

## Etapas

| # | Etapa | Descripción |
|---|-------|-------------|
| 0 | **Generación** | Crea 2 archivos CSV sintéticos con formatos distintos (encoding, delimitador, formato de fechas y montos) |
| 1 | **Validación** | Verifica estructura, formatos y dimensión de cada columna |
| 2 | **Extracción** | Lectura con detección automática de encoding y delimitador |
| 3 | **Normalización** | Estandarización de columnas, fechas, montos y tipos |
| 4 | **Match** | Cruce por código de operación → matched / solo_libro / solo_banco |
| 5 | **Reportes** | CSV con detalle de cruce, diferencias y resumen ejecutivo |
| 6 | **Analytics** | Estadísticas descriptivas, distribuciones, tasas de conciliación |
| 7 | **Dashboard** | 6 gráficos + página HTML desplegada en GitHub Pages |

## Archivos de Entrada

| Archivo | Formato | Encoding | Delimitador | Registros |
|---------|---------|----------|-------------|-----------|
| `libro_contable.csv` | Fecha DD-MM-YYYY, montos $1.500.000 | latin-1 | `;` | 150 |
| `cartola_bancaria.csv` | Fecha YYYY/MM/DD, montos 1500000,50 | utf-8 | `,` | 140 |

**Diseño del match:** 120 códigos compartidos, 30 solo en libro, 20 solo en banco.

## Ejecución Local

```bash
pip install -r requirements.txt
python main.py
```

## Tests

```bash
pytest tests/ -v
```

## CI/CD

El workflow de GitHub Actions ejecuta:
1. **Tests** — pytest con validación completa
2. **ETL Pipeline** — genera datos, ejecuta pipeline, produce dashboard
3. **Deploy** — publica el dashboard en GitHub Pages (solo en `main`)

## Stack

- Python 3.12
- pandas / numpy
- matplotlib / seaborn
- Jinja2
- pytest
- GitHub Actions + GitHub Pages

## Autor

**José Nicolás Candia** — [@mechjook](https://github.com/mechjook)
