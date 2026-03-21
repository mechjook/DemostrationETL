"""
Etapa 3 — MATCH
Cruce de registros entre libro contable y cartola bancaria por código de operación.
Genera tres conjuntos: matched, solo_libro, solo_banco.
"""

import pandas as pd


def match_records(
    df_libro: pd.DataFrame,
    df_cartola: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """
    Realiza el cruce entre libro contable y cartola bancaria.

    Retorna un diccionario con:
      - matched    : registros que cruzan por código
      - solo_libro : registros solo en libro (sin contraparte bancaria)
      - solo_banco : registros solo en banco (sin contraparte contable)
    """
    print("\n" + "=" * 60)
    print("ETAPA 3: MATCH POR CÓDIGO DE OPERACIÓN")
    print("=" * 60)

    codigos_libro = set(df_libro["codigo"].unique())
    codigos_banco = set(df_cartola["codigo"].unique())

    codigos_match = codigos_libro & codigos_banco
    codigos_solo_libro = codigos_libro - codigos_banco
    codigos_solo_banco = codigos_banco - codigos_libro

    # Matched: merge completo con sufijos para diferenciar origen
    matched = pd.merge(
        df_libro[df_libro["codigo"].isin(codigos_match)],
        df_cartola[df_cartola["codigo"].isin(codigos_match)],
        on="codigo",
        suffixes=("_libro", "_banco"),
        how="inner",
    )

    # Calcular diferencia de montos
    matched["diferencia_monto"] = matched["monto_libro"] - matched["monto_banco"]
    matched["diferencia_abs"] = matched["diferencia_monto"].abs()
    matched["match_exacto"] = matched["diferencia_abs"] < 0.01

    # No cruzados
    solo_libro = df_libro[df_libro["codigo"].isin(codigos_solo_libro)].copy()
    solo_banco = df_cartola[df_cartola["codigo"].isin(codigos_solo_banco)].copy()

    print(f"  Códigos en libro  : {len(codigos_libro)}")
    print(f"  Códigos en banco  : {len(codigos_banco)}")
    print(f"  Match encontrados : {len(codigos_match)} códigos → {len(matched)} registros cruzados")
    print(f"  Solo en libro     : {len(codigos_solo_libro)} códigos → {len(solo_libro)} registros")
    print(f"  Solo en banco     : {len(codigos_solo_banco)} códigos → {len(solo_banco)} registros")

    match_exacto_count = matched["match_exacto"].sum()
    match_con_diff = len(matched) - match_exacto_count
    print(f"  Match exacto monto: {match_exacto_count} | Con diferencia: {match_con_diff}")

    return {
        "matched": matched,
        "solo_libro": solo_libro,
        "solo_banco": solo_banco,
    }
