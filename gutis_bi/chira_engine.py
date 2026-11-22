"""
Motor Cognitivo y Analítico Avanzado CHIRA v3.0 para Gutis BI.
Conecta Close-Up (Rx y Auditoría) con Sell-Out Mensual 6 Meses (Real vs. Cuota)
y traduce preguntas coloquiales a 8 motores tácticos sin alucinaciones numéricas.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from gutis_bi.ai_service import (
    clasificar_intencion_coloquial,
    generar_respuesta_objecion_tactica,
)
from gutis_bi.analytics import (
    df_a_markdown_nativo,
    formatear_nombre_medico,
    generar_analisis_mercado_chira_rico,
    generar_consultoria_cognitiva_chira_medico,
    ranking_medicos,
    resumen_mercados,
    resumen_ventas_ciudad,
)
from gutis_bi.catalog import MERCADOS_PRIORITARIOS
from gutis_bi.data import normalizar_txt, resolver_clave_mercado_gutis

# Mapeo bidireccional entre VM4 de datos 2026.xlsx y claves de MERCADOS_PRIORITARIOS
ALIAS_VENTA_A_TOKENS = {
    "BIOTOS": ["BIOTOS"],
    "TALERDIN": ["TALERDIN"],
    "MOMETZONA": ["MOMETZONA"],
    "CLEMBROXIL": ["CLEMBROXIL"],
    "VENTILAR": ["VENTILAR"],
    "MUPIRAL": ["MUPIRAL"],
    "BICORPAN": ["BICORPAN"],
    "GASTROALIVIO": ["GASTROALIVIO"],
    "DALIVIUM": ["DALIVIO", "DALIVIUM"],
}


def canonizar_departamento(texto: Any) -> str:
    t = normalizar_txt(texto)
    if not t:
        return "OTROS"
    for depto in [
        "MANAGUA", "MASAYA", "GRANADA", "CARAZO", "RIVAS",
        "BOACO", "CHONTALES", "NUEVA GUINEA", "JINOTEGA",
        "MATAGALPA", "LEON", "CHINANDEGA", "ESTELI", "RAAN",
    ]:
        if depto in t:
            return depto
    if "WALMART" in t or "CSU" in t:
        return "CADENA WALMART"
    if "FARMACOSTO" in t:
        return "FARMACOSTO"
    return t


def _match_producto_venta(df_v: pd.DataFrame, clave_mercado: Optional[str]) -> pd.DataFrame:
    if df_v.empty or not clave_mercado or "PRODUCTO_VENTA" not in df_v.columns:
        return df_v
    meta = MERCADOS_PRIORITARIOS.get(clave_mercado, {})
    objetivo = normalizar_txt(f"{clave_mercado} {meta.get('producto', '')}")
    pv_norm = df_v["PRODUCTO_VENTA"].apply(normalizar_txt)

    # Buscar coincidencia por raíz del producto
    tokens_match = []
    for vm4_key, aliases in ALIAS_VENTA_A_TOKENS.items():
        if vm4_key in objetivo or any(a in objetivo for a in aliases):
            tokens_match.append(vm4_key)
    if tokens_match:
        return df_v[pv_norm.isin(tokens_match)].copy()

    raiz = normalizar_txt(meta.get("producto", clave_mercado)).split()[0]
    return df_v[pv_norm.str.contains(re.escape(raiz[:6]), na=False)].copy()


def _clave_desde_vm4(vm4_str: str) -> Optional[str]:
    v_norm = normalizar_txt(vm4_str)
    if not v_norm:
        return None
    if v_norm == "DALIVIUM":
        return resolver_clave_mercado_gutis("DALIVIO", "DALIVIO")
    return resolver_clave_mercado_gutis(v_norm, v_norm)


def _orden_meses_ventas(df_v: pd.DataFrame) -> List[str]:
    if df_v.empty or "Mes_Label" not in df_v.columns:
        return []
    if "Mes_Orden" in df_v.columns:
        return (
            df_v[["Mes_Orden", "Mes_Label"]]
            .drop_duplicates()
            .sort_values("Mes_Orden")["Mes_Label"]
            .tolist()
        )
    return df_v["Mes_Label"].dropna().unique().tolist()


# ============================================================================
# 1. TABLA MENSUAL DE 6 MESES + REAL VS CUOTA (Para Módulo 4 Evolución y CHIRA)
# ============================================================================
def ventas_mensuales_resumen(
    df_ventas: pd.DataFrame,
    ciudad: Optional[str] = None,
    producto: Optional[str] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Construye la tabla pivote mensual (May 26 -> Oct 26) por Sucursal y Producto,
    con Real Semestre, Cuota Semestre, % Cumplimiento, Brecha ($) y tendencia.
    """
    kpis = {
        "meses": [],
        "totales_mes": {},
        "cuotas_mes": {},
        "total_real": 0.0,
        "total_cuota": 0.0,
        "pct_cumpl": 0.0,
        "brecha_total": 0.0,
        "es_mensual": False,
    }
    if df_ventas.empty or "Monto Real" not in df_ventas.columns:
        return pd.DataFrame(), kpis

    sub = df_ventas.copy()
    sub["DEPTO_CANON"] = sub["DESCRIPCION_RUTA"].apply(canonizar_departamento)
    if ciudad and ciudad not in ("TODO MI PANEL", "TODAS"):
        ciu_canon = canonizar_departamento(ciudad)
        sub = sub[
            (sub["DEPTO_CANON"] == ciu_canon)
            | (sub["DESCRIPCION_RUTA"].str.contains(re.escape(normalizar_txt(ciudad)), na=False))
        ]
    if producto and producto not in ("TODOS", "Todos"):
        p_norm = normalizar_txt(producto)
        sub = sub[sub["PRODUCTO_VENTA"].apply(normalizar_txt).str.contains(re.escape(p_norm[:6]), na=False)]

    if sub.empty:
        return pd.DataFrame(), kpis

    meses = _orden_meses_ventas(sub)
    kpis["meses"] = meses
    kpis["es_mensual"] = len(meses) >= 2 and not all(m in ("Q1", "Q2", "Q3", "Q4") for m in meses)

    tiene_cuota = "Monto Cuota" in sub.columns
    for m in meses:
        sm = sub[sub["Mes_Label"] == m]
        kpis["totales_mes"][m] = round(float(sm["Monto Real"].sum()), 2)
        kpis["cuotas_mes"][m] = round(float(sm["Monto Cuota"].sum()), 2) if tiene_cuota else 0.0

    kpis["total_real"] = round(float(sub["Monto Real"].sum()), 2)
    kpis["total_cuota"] = round(float(sub["Monto Cuota"].sum()), 2) if tiene_cuota else 0.0
    kpis["pct_cumpl"] = round((kpis["total_real"] / kpis["total_cuota"] * 100.0), 1) if kpis["total_cuota"] > 0 else 0.0
    kpis["brecha_total"] = round(kpis["total_real"] - kpis["total_cuota"], 2)

    piv = pd.pivot_table(
        sub,
        values="Monto Real",
        index=["DEPTO_CANON", "NOMBRE_CLIENTE_1", "PRODUCTO_VENTA"],
        columns=["Mes_Label"],
        aggfunc="sum",
        fill_value=0.0,
    ).reset_index()

    for m in meses:
        if m not in piv.columns:
            piv[m] = 0.0
        piv[m] = piv[m].round(2)

    piv["Real Semestre ($)"] = piv[meses].sum(axis=1).round(2)

    if tiene_cuota:
        cuota_grp = (
            sub.groupby(["DEPTO_CANON", "NOMBRE_CLIENTE_1", "PRODUCTO_VENTA"], as_index=False)["Monto Cuota"]
            .sum()
            .rename(columns={"Monto Cuota": "Cuota Semestre ($)"})
        )
        piv = piv.merge(cuota_grp, on=["DEPTO_CANON", "NOMBRE_CLIENTE_1", "PRODUCTO_VENTA"], how="left")
        piv["Cuota Semestre ($)"] = piv["Cuota Semestre ($)"].fillna(0.0).round(2)
        piv["% Cumpl."] = np.where(
            piv["Cuota Semestre ($)"] > 0,
            (piv["Real Semestre ($)"] / piv["Cuota Semestre ($)"] * 100.0).round(1),
            0.0,
        )
        piv["Brecha ($)"] = (piv["Real Semestre ($)"] - piv["Cuota Semestre ($)"]).round(2)

    if len(meses) >= 2:
        ult, prev = meses[-1], meses[-2]
        piv["Var. Últ. Mes ($)"] = (piv[ult] - piv[prev]).round(2)

    piv = piv.rename(
        columns={
            "DEPTO_CANON": "Departamento",
            "NOMBRE_CLIENTE_1": "Sucursal / Farmacia",
            "PRODUCTO_VENTA": "Producto",
        }
    )
    orden_cols = ["Departamento", "Sucursal / Farmacia", "Producto"] + meses + ["Real Semestre ($)"]
    for extra in ["Cuota Semestre ($)", "% Cumpl.", "Brecha ($)", "Var. Últ. Mes ($)"]:
        if extra in piv.columns:
            orden_cols.append(extra)

    piv = piv[orden_cols].sort_values(by="Real Semestre ($)", ascending=False).reset_index(drop=True)
    return piv, kpis


# ============================================================================
# 2. MOTOR: MÉDICOS CON TENDENCIA DE CAÍDA EN RECETAS (CAIDA_RX)
# ============================================================================
def analizar_caida_rx_medicos(
    bundle: Any,
    clave_mercado: Optional[str] = None,
    ciudad: Optional[str] = None,
    solo_panel: bool = True,
) -> str:
    df_prod = bundle.productos
    df_panel = bundle.panel
    df_aud = bundle.auditoria

    if df_prod.empty:
        return "No hay datos de Close-Up cargados para analizar caídas prescriptivas."

    sub = df_prod[df_prod["Clave_Gutis"].notna()].copy()
    if solo_panel and not df_panel.empty:
        sub = sub[sub["Médico"].isin(set(df_panel["Médico"].dropna().unique()))]
    if clave_mercado:
        sub = sub[sub["Clave_Gutis"] == clave_mercado]
    if ciudad:
        c_norm = canonizar_departamento(ciudad)
        sub = sub[sub["CIUDAD_PANEL"].apply(canonizar_departamento) == c_norm]

    if sub.empty:
        return "No se encontraron registros prescriptivos con esos filtros para evaluar tendencia de caída."

    # Extraer delta de Auditoría (% MS Mes vs % MS Ant) por médico
    delta_aud_map: Dict[str, Tuple[float, float, float]] = {}
    if not df_aud.empty and "% MS - Mes" in df_aud.columns and "% MS - Ant" in df_aud.columns:
        aud_sub = df_aud.copy()
        if clave_mercado:
            aud_sub = aud_sub[aud_sub["Clave_Gutis"] == clave_mercado]
        # Quedarnos solo con marcas Gutis en Auditoría
        aud_g = aud_sub[aud_sub["MARCA"].str.endswith(" GPR") | aud_sub["MARCA"].str.contains("GUTIS|TALERDIN|BIOTOS|MOMETZONA|CLEMBROXIL|VENTILAR|MUPIRAL|BICORPAN|GASTROALIVIO|DALIVIO", na=False)]
        if not aud_g.empty:
            grp_a = aud_g.groupby("Médico")[["% MS - TrasAnt", "% MS - Ant", "% MS - Mes"]].sum() * 100.0
            for m_doc, r in grp_a.iterrows():
                delta_aud_map[m_doc] = (round(float(r["% MS - TrasAnt"]), 1), round(float(r["% MS - Ant"]), 1), round(float(r["% MS - Mes"]), 1))

    filas = []
    for doc, grp in sub.groupby("Médico"):
        pm = int(grp["Pxs-MES"].sum())
        py = int(grp["Pxs-YTD"].sum())
        gm = int(grp[grp["Es_Gutis"]]["Pxs-MES"].sum())
        gy = int(grp[grp["Es_Gutis"]]["Pxs-YTD"].sum())
        if gy <= 0 and py <= 0:
            continue

        ms_m = round((gm / pm * 100.0), 1) if pm > 0 else 0.0
        ms_y = round((gy / py * 100.0), 1) if py > 0 else 0.0
        # Ritmo mensual esperado YTD (corte septiembre = 9 meses)
        ritmo_g = round(gy / 9.0, 1)
        caida_pxs = round(gm - ritmo_g, 1)
        delta_ms_ytd = round(ms_m - ms_y, 1)

        tr_ms, ant_ms, mes_aud_ms = delta_aud_map.get(doc, (np.nan, np.nan, np.nan))
        caida_aud = (mes_aud_ms - ant_ms) if not np.isnan(ant_ms) else 0.0

        # Criterio real de enfriamiento / caída
        esta_cayendo = (
            (gy >= 3 and gm == 0)
            or (caida_pxs <= -1.0 and gm < ritmo_g)
            or (delta_ms_ytd <= -8.0 and pm >= 2)
            or (caida_aud <= -5.0)
        )
        if not esta_cayendo:
            continue

        grp_riv = grp[~grp["Es_Gutis"]].sort_values(by=["Pxs-MES", "Pxs-YTD"], ascending=False)
        riv_top = f"{grp_riv.iloc[0]['NOMBRE_PRODUCTO']} ({int(grp_riv.iloc[0]['Pxs-MES'])}M)" if not grp_riv.empty else "Sin rival claro"

        pf = grp.iloc[0]
        severidad = abs(min(caida_pxs, 0.0)) * 3.0 + abs(min(delta_ms_ytd, 0.0)) * 0.4 + (10.0 if gm == 0 and gy >= 5 else 0.0)
        alerta = "APAGÓN TOTAL (0 Mes)" if (gm == 0 and gy >= 4) else ("CAÍDA FUERTE" if delta_ms_ytd <= -15 or caida_pxs <= -3 else "ENFRIAMIENTO")

        filas.append({
            "Médico": doc,
            "Ciudad": str(pf.get("CIUDAD_PANEL", "N/D")),
            "Cat": str(pf.get("CAT_PANEL", "S/C")),
            "Gutis Mes": gm,
            "Prom. Mes YTD": ritmo_g,
            "Gutis YTD": gy,
            "% MS Mes": ms_m,
            "% MS YTD": ms_y,
            "Delta MS (pp)": delta_ms_ytd,
            "Alerta": alerta,
            "Rival Absorbiendo": riv_top,
            "_sev": severidad,
        })

    etiqueta_prod = MERCADOS_PRIORITARIOS[clave_mercado]["producto"] if clave_mercado in MERCADOS_PRIORITARIOS else "Portafolio Gutis"
    etiqueta_ciu = ciudad.upper() if ciudad else "TODO TU PANEL"

    if not filas:
        return f"### Radar de Caída Prescriptiva — {etiqueta_prod} ({etiqueta_ciu})\nNo se detectaron médicos con caída significativa en **{etiqueta_prod}** en este corte. Tu base prescriptiva se mantiene estable o en crecimiento."

    df_caida = pd.DataFrame(filas).sort_values(by="_sev", ascending=False).drop(columns=["_sev"]).reset_index(drop=True)
    top3 = df_caida.head(3)
    foco_txt = "\n".join([
        f"- **Dr(a). {formatear_nombre_medico(r['Médico'])}** ({r['Ciudad']}, Cat {r['Cat']}): Bajó a `{r['Gutis Mes']} Pxs` este mes frente a su promedio YTD de `{r['Prom. Mes YTD']} Pxs/mes` (`{r['Gutis YTD']} YTD` | `{r['% MS Mes']}%` vs `{r['% MS YTD']}% MS YTD`). Rival activo: `{r['Rival Absorbiendo']}`."
        for _, r in top3.iterrows()
    ])

    return f"""### Alerta de Caída y Enfriamiento Prescriptivo — {etiqueta_prod} ({etiqueta_ciu})
Se detectaron **{len(df_caida)} médicos** con señal de caída o apagón reciente en **{etiqueta_prod}** (comparando Mes actual contra su promedio mensual YTD y cuota histórica).

{df_a_markdown_nativo(df_caida.head(12))}

#### Prioridad Inmediata de Rescate en Ruta:
{foco_txt}

#### Acción Táctica Recomendada:
1. **En los casos de «APAGÓN TOTAL (0 Mes)»:** No repitas el discurso introductorio; abre validando si hubo problema de **abastecimiento en farmacia cercana** o cambio por precio en mostrador.
2. **En los casos de «CAÍDA FUERTE»:** Indaga qué ocurrió con la marca rival que está absorbiendo esas recetas y usa flanqueo directo sobre tolerabilidad/adherencia.
"""


# ============================================================================
# 3. MOTOR: SUBIDA DE CUOTA (Close-Up % MS + Sell-Out % Cumplimiento)
# ============================================================================
def analizar_subida_cuota(
    bundle: Any,
    ciudad: Optional[str] = None,
    solo_panel: bool = True,
) -> str:
    df_mer = resumen_mercados(bundle.productos, bundle.panel, ciudad=ciudad, incluir_fuera_panel=not solo_panel)
    df_v = bundle.ventas

    ciu_lbl = ciudad.upper() if ciudad else "TODO TU TERRITORIO"
    bloques = [f"### Auditoría de Subida de Cuota (Prescripción Close-Up + Venta Mensual) — {ciu_lbl}"]

    if not df_mer.empty:
        suben_rx = df_mer[df_mer["Brecha MS Mes vs YTD (pp)"] > 0].sort_values(by="Brecha MS Mes vs YTD (pp)", ascending=False)
        bajan_rx = df_mer[df_mer["Brecha MS Mes vs YTD (pp)"] < 0].sort_values(by="Brecha MS Mes vs YTD (pp)", ascending=True)

        cols_rx = ["Marca Gutis", "Gutis Mes", "Mercado Mes", "% MS Mes", "% MS YTD", "Brecha MS Mes vs YTD (pp)", "Diagnóstico de Evolución"]
        bloques.append("#### 1. Productos que Subieron Cuota Prescriptiva (Close-Up % MS Mes vs. YTD)")
        if not suben_rx.empty:
            bloques.append(df_a_markdown_nativo(suben_rx[cols_rx]))
        else:
            bloques.append("_Ninguna marca registró ganancia neta de % MS este mes frente a su promedio YTD._")

        if not bajan_rx.empty:
            bloques.append("\n**Atención (Marcas que cedieron cuota este mes):** " + ", ".join([
                f"**{r['Marca Gutis']}** (`{r['Brecha MS Mes vs YTD (pp)']:+.1f} pp`)" for _, r in bajan_rx.head(4).iterrows()
            ]))

    # Parte 2: Cumplimiento de Cuota en Ventas Mensuales (datos 2026.xlsx)
    if not df_v.empty and "Monto Cuota" in df_v.columns:
        v_sub = df_v.copy()
        v_sub["DEPTO_CANON"] = v_sub["DESCRIPCION_RUTA"].apply(canonizar_departamento)
        if ciudad:
            v_sub = v_sub[v_sub["DEPTO_CANON"] == canonizar_departamento(ciudad)]

        meses = _orden_meses_ventas(v_sub)
        if len(meses) >= 2 and not v_sub.empty:
            ult, prev = meses[-1], meses[-2]
            g_ult = v_sub[v_sub["Mes_Label"] == ult].groupby("PRODUCTO_VENTA")[["Monto Real", "Monto Cuota"]].sum()
            g_prev = v_sub[v_sub["Mes_Label"] == prev].groupby("PRODUCTO_VENTA")[["Monto Real", "Monto Cuota"]].sum()
            g_sem = v_sub.groupby("PRODUCTO_VENTA")[["Monto Real", "Monto Cuota"]].sum()

            comp = pd.DataFrame(index=g_sem.index)
            comp[f"Real {prev} ($)"] = g_prev["Monto Real"].reindex(comp.index).fillna(0.0).round(2)
            comp[f"Real {ult} ($)"] = g_ult["Monto Real"].reindex(comp.index).fillna(0.0).round(2)
            comp[f"% Cuota {prev}"] = np.where(g_prev["Monto Cuota"].reindex(comp.index).fillna(0.0) > 0, (comp[f"Real {prev} ($)"] / g_prev["Monto Cuota"].reindex(comp.index) * 100.0).round(1), 0.0)
            comp[f"% Cuota {ult}"] = np.where(g_ult["Monto Cuota"].reindex(comp.index).fillna(0.0) > 0, (comp[f"Real {ult} ($)"] / g_ult["Monto Cuota"].reindex(comp.index) * 100.0).round(1), 0.0)
            comp["Delta Cuota (pp)"] = (comp[f"% Cuota {ult}"] - comp[f"% Cuota {prev}"]).round(1)
            comp["% Cuota Semestre"] = np.where(g_sem["Monto Cuota"] > 0, (g_sem["Monto Real"] / g_sem["Monto Cuota"] * 100.0).round(1), 0.0)
            comp = comp.reset_index().rename(columns={"PRODUCTO_VENTA": "Producto Venta"}).sort_values(by="Delta Cuota (pp)", ascending=False)

            bloques.append(f"\n#### 2. Evolución de Cumplimiento de Cuota en Ventas ({prev} vs. {ult})")
            bloques.append(df_a_markdown_nativo(comp))

    return "\n".join(bloques)


# ============================================================================
# 4. MOTOR: PRODUCTOS CON MAYOR POTENCIAL PARA SUBIR MÁS AÚN (POTENCIAL_EXPANSION)
# ============================================================================
def analizar_potencial_expansion(
    bundle: Any,
    ciudad: Optional[str] = None,
    solo_panel: bool = True,
) -> str:
    df_prod = bundle.productos
    df_panel = bundle.panel
    df_v = bundle.ventas

    if df_prod.empty:
        return "No hay datos de prescripción disponibles para calcular potencial de expansión."

    sub = df_prod[df_prod["Clave_Gutis"].notna()].copy()
    if solo_panel and not df_panel.empty:
        sub = sub[sub["Médico"].isin(set(df_panel["Médico"].dropna().unique()))]
    if ciudad:
        sub = sub[sub["CIUDAD_PANEL"].apply(canonizar_departamento) == canonizar_departamento(ciudad)]

    if sub.empty:
        return "No hay registros suficientes para calcular potencial en este territorio."

    # Brecha disponible en dólares en datos 2026.xlsx (último mes)
    brecha_venta_map: Dict[str, float] = {}
    if not df_v.empty and "Monto Cuota" in df_v.columns:
        v_s = df_v.copy()
        v_s["DEPTO_CANON"] = v_s["DESCRIPCION_RUTA"].apply(canonizar_departamento)
        if ciudad:
            v_s = v_s[v_s["DEPTO_CANON"] == canonizar_departamento(ciudad)]
        meses = _orden_meses_ventas(v_s)
        if meses:
            v_ult = v_s[v_s["Mes_Label"] == meses[-1]]
            for prod_v, grp_v in v_ult.groupby("PRODUCTO_VENTA"):
                k_m = _clave_desde_vm4(str(prod_v))
                if k_m:
                    brecha = max(0.0, float(grp_v["Monto Cuota"].sum() - grp_v["Monto Real"].sum()))
                    brecha_venta_map[k_m] = round(brecha, 2)

    filas = []
    for k_gut, grp in sub.groupby("Clave_Gutis"):
        meta = MERCADOS_PRIORITARIOS.get(k_gut, {})
        tot_m = int(grp["Pxs-MES"].sum())
        gut_m = int(grp[grp["Es_Gutis"]]["Pxs-MES"].sum())
        comp_m = tot_m - gut_m
        ms_m = round((gut_m / tot_m * 100.0), 1) if tot_m > 0 else 0.0

        # Contar médicos "listos para escalar" (ya recetan Gutis >0 pero comp aún > Gutis)
        meds_escalables = 0
        meds_conquista_alta = 0
        for _, g_doc in grp.groupby("Médico"):
            dm = int(g_doc["Pxs-MES"].sum())
            dg = int(g_doc[g_doc["Es_Gutis"]]["Pxs-MES"].sum())
            dc = dm - dg
            if dg > 0 and dc > dg:
                meds_escalables += 1
            elif dg == 0 and dc >= 5:
                meds_conquista_alta += 1

        brecha_usd = brecha_venta_map.get(k_gut, 0.0)
        # Score de oportunidad: premia alto volumen rival + médicos ya tibios (escalables) + techo libre (<55% MS)
        techo_factor = max(0.15, (100.0 - ms_m) / 100.0)
        score = round((comp_m * 0.7 + meds_escalables * 12.0 + meds_conquista_alta * 8.0) * techo_factor + (brecha_usd / 500.0), 1)

        filas.append({
            "Producto": meta.get("producto", k_gut),
            "% MS Mes": ms_m,
            "Vol. Rival Mes (Pxs)": comp_m,
            "Médicos Listos p/ Escalar": meds_escalables,
            "Médicos Alta Conquista (0% MS)": meds_conquista_alta,
            "Brecha Cuota Últ. Mes ($)": brecha_usd,
            "Índice Oportunidad": score,
        })

    df_pot = pd.DataFrame(filas).sort_values(by="Índice Oportunidad", ascending=False).reset_index(drop=True)
    top3 = df_pot.head(3)
    resumen_top = "\n".join([
        f"1. **{r['Producto']}** (`{r['% MS Mes']}% MS` actual): Tiene **{r['Vol. Rival Mes (Pxs)']} recetas/mes** en manos de la competencia, **{r['Médicos Listos p/ Escalar']} médicos** que ya lo prueban pero aún comparten mayoría con rivales y **${r['Brecha Cuota Últ. Mes ($)']:,.0f}** disponibles para cerrar cuota."
        for _, r in top3.iterrows()
    ])

    ciu_lbl = ciudad.upper() if ciudad else "TODO TU PANEL"
    return f"""### Radar de Potencial de Expansión («Dónde hay más margen para subir») — {ciu_lbl}
Ranking calculado combinando **volumen libre en manos de la competencia**, **médicos ya tibios (Escalón 3–4 listos para subir)** y **brecha disponible contra tu cuota mensual en dólares**.

{df_a_markdown_nativo(df_pot)}

#### Top 3 Palancas de Crecimiento Rápido:
{resumen_top}
"""


# ============================================================================
# 5. MOTOR: SUCURSALES A ABORDAR Y CON QUÉ PRODUCTOS (SUCURSALES_ABORDAJE)
# ============================================================================
def analizar_sucursales_abordaje(
    bundle: Any,
    ciudad: Optional[str] = None,
    clave_mercado: Optional[str] = None,
) -> str:
    df_v = bundle.ventas
    df_prod = bundle.productos

    if df_v.empty:
        return "No se encontró el archivo de ventas mensuales (`datos 2026.xlsx`) para priorizar sucursales."

    sub = df_v.copy()
    sub["DEPTO_CANON"] = sub["DESCRIPCION_RUTA"].apply(canonizar_departamento)
    if ciudad:
        ciu_canon = canonizar_departamento(ciudad)
        sub = sub[
            (sub["DEPTO_CANON"] == ciu_canon)
            | (sub["DESCRIPCION_RUTA"].str.contains(re.escape(normalizar_txt(ciudad)), na=False))
        ]
    if clave_mercado:
        sub = _match_producto_venta(sub, clave_mercado)

    if sub.empty:
        return "No hay datos de sucursales en ventas para ese filtro."

    meses = _orden_meses_ventas(sub)
    ult_mes = meses[-1] if meses else "Últ. Mes"
    tiene_cuota = "Monto Cuota" in sub.columns

    # Demanda médica Close-Up por departamento y producto (para recomendar qué códigos empujar)
    demanda_rx_depto: Dict[Tuple[str, str], int] = {}
    if not df_prod.empty:
        p_g = df_prod[df_prod["Es_Gutis"] & df_prod["Clave_Gutis"].notna()].copy()
        p_g["DEPTO_CANON"] = p_g["CIUDAD_PANEL"].apply(canonizar_departamento)
        for (dep, k_m), g_rx in p_g.groupby(["DEPTO_CANON", "Clave_Gutis"]):
            # Mapear clave a nombre corto VM4
            meta_n = normalizar_txt(MERCADOS_PRIORITARIOS.get(k_m, {}).get("producto", k_m)).split()[0]
            if meta_n == "DALIVIO":
                meta_n = "DALIVIUM"
            demanda_rx_depto[(dep, meta_n)] = int(g_rx["Pxs-MES"].sum())

    # Evaluar cada sucursal en el último mes vs su promedio semestral y su cuota
    sub_ult = sub[sub["Mes_Label"] == ult_mes] if meses else sub
    filas_pdv = []

    for (depto, pdv), grp_sem in sub.groupby(["DEPTO_CANON", "NOMBRE_CLIENTE_1"]):
        real_sem = float(grp_sem["Monto Real"].sum())
        cuota_sem = float(grp_sem["Monto Cuota"].sum()) if tiene_cuota else 0.0
        n_meses = max(1, grp_sem["Mes_Label"].nunique())
        prom_mes = real_sem / n_meses

        grp_u = sub_ult[(sub_ult["DEPTO_CANON"] == depto) & (sub_ult["NOMBRE_CLIENTE_1"] == pdv)]
        real_ult = float(grp_u["Monto Real"].sum())
        cuota_ult = float(grp_u["Monto Cuota"].sum()) if tiene_cuota else 0.0
        brecha_ult = cuota_ult - real_ult if tiene_cuota else max(0.0, prom_mes - real_ult)
        pct_ult = round((real_ult / cuota_ult * 100.0), 1) if cuota_ult > 0 else 0.0

        # Solo priorizar PDVs con relevancia económica (cuota o promedio > $250) y déficit real
        if cuota_ult < 250 and prom_mes < 250:
            continue
        if brecha_ult <= 50:
            continue

        # Detectar los 2-3 productos con mayor brecha negativa en esa sucursal específica
        if not grp_u.empty and tiene_cuota:
            gp = grp_u.groupby("PRODUCTO_VENTA")[["Monto Real", "Monto Cuota"]].sum()
            gp["Brecha"] = gp["Monto Cuota"] - gp["Monto Real"]
            gp["Pct"] = np.where(gp["Monto Cuota"] > 0, (gp["Monto Real"] / gp["Monto Cuota"] * 100.0).round(0), 0.0)
            gp["Rx_Zona"] = [demanda_rx_depto.get((depto, normalizar_txt(p)), 0) for p in gp.index]
            gp_foco = gp[gp["Brecha"] > 20].sort_values(by=["Brecha", "Rx_Zona"], ascending=[False, False]).head(3)
            prods_rec = " | ".join([
                f"{p} (-${r['Brecha']:,.0f}, {int(r['Pct'])}% cuota" + (f", {int(r['Rx_Zona'])} Rx zona)" if r["Rx_Zona"] > 0 else ")")
                for p, r in gp_foco.iterrows()
            ]) or "Revisar mix completo"
        else:
            prods_rec = "Surtido general del portafolio"

        estado_pdv = "CAÍDA + BAJA CUOTA" if (real_ult < prom_mes * 0.8 and pct_ult < 70) else ("BRECHA DE CUOTA" if pct_ult < 75 else "RECUPERAR RITMO")

        filas_pdv.append({
            "Departamento": depto,
            "Sucursal / Farmacia": pdv,
            f"Real {ult_mes} ($)": round(real_ult, 2),
            f"Cuota {ult_mes} ($)": round(cuota_ult, 2),
            "% Cuota": pct_ult,
            "Déficit ($)": round(brecha_ult, 2),
            "Prom. Semestral ($)": round(prom_mes, 2),
            "Diagnóstico": estado_pdv,
            "Productos a Abordar (Brecha + Demanda Rx)": prods_rec,
        })

    ciu_lbl = ciudad.upper() if ciudad else "TODO TU TERRITORIO"
    if not filas_pdv:
        return f"### Plan de Abordaje de Sucursales ({ult_mes}) — {ciu_lbl}\nTodas las sucursales relevantes se encuentran en línea o por encima de su cuota en este filtro."

    df_pdv = pd.DataFrame(filas_pdv).sort_values(by="Déficit ($)", ascending=False).reset_index(drop=True)
    deficit_top10 = df_pdv.head(10)["Déficit ($)"].sum()

    return f"""### Plan Prioritario de Abordaje a Sucursales ({ult_mes}) — {ciu_lbl}
Estas son las farmacias con mayor dinero pendiente por recuperar frente a su cuota de **{ult_mes}** (**${deficit_top10:,.2f}** concentrados solo en el Top 10), junto con los **códigos exactos** que debes empujar en mostrador según brecha de cuota y demanda prescriptiva de la zona.

{df_a_markdown_nativo(df_pdv.head(12))}

#### Guion Rápido de Abordaje en Mostrador:
1. **Llega con el dato de receta médica local:** En las sucursales marcadas con `Rx zona`, muestra al encargado/regente qué productos están recetando activamente los médicos de su misma ciudad para justificar reposición inmediata y evitar fuga de clientes.
2. **Prioriza códigos en 0% a 30% de cuota:** Son quiebres de inventario o sustituciones activas donde recuperar una sola compra levanta rápido el cumplimiento del mes.
"""


# ============================================================================
# 6. MOTOR: CRUCE DEPARTAMENTAL RX (Close-Up) VS. VENTA MENSUAL (CRUCE_RX_VENTA)
# ============================================================================
def analizar_cruce_rx_vs_venta(
    bundle: Any,
    clave_mercado: Optional[str] = None,
    ciudad: Optional[str] = None,
) -> str:
    df_prod = bundle.productos
    df_v = bundle.ventas

    if df_prod.empty or df_v.empty:
        return "Se requieren tanto Close-Up (`PRODUCTOS`) como las ventas mensuales (`datos 2026.xlsx`) para ejecutar el cruce por departamento."

    # 1. Close-Up por departamento
    p_sub = df_prod[df_prod["Clave_Gutis"].notna()].copy()
    if clave_mercado:
        p_sub = p_sub[p_sub["Clave_Gutis"] == clave_mercado]
    p_sub["DEPTO"] = p_sub["CIUDAD_PANEL"].apply(canonizar_departamento)
    p_sub = p_sub[p_sub["DEPTO"] != "FUERA DE PANEL"]

    rx_dep = {}
    for dep, grp in p_sub.groupby("DEPTO"):
        pm = int(grp["Pxs-MES"].sum())
        py = int(grp["Pxs-YTD"].sum())
        gm = int(grp[grp["Es_Gutis"]]["Pxs-MES"].sum())
        gy = int(grp[grp["Es_Gutis"]]["Pxs-YTD"].sum())
        ms_m = round((gm / pm * 100.0), 1) if pm > 0 else 0.0
        ms_y = round((gy / py * 100.0), 1) if py > 0 else 0.0
        rx_dep[dep] = {
            "gm": gm,
            "ritmo_g": round(gy / 9.0, 1),
            "ms_m": ms_m,
            "ms_y": ms_y,
            "delta_ms": round(ms_m - ms_y, 1),
        }

    # 2. Ventas mensuales por departamento (Último mes vs Mes anterior y vs Cuota)
    v_sub = _match_producto_venta(df_v.copy(), clave_mercado)
    v_sub["DEPTO"] = v_sub["DESCRIPCION_RUTA"].apply(canonizar_departamento)
    meses = _orden_meses_ventas(v_sub)
    if len(meses) < 2:
        return "No hay al menos 2 meses en ventas para comparar variación mensual contra recetas."

    ult, prev = meses[-1], meses[-2]
    tiene_cuota = "Monto Cuota" in v_sub.columns

    deptos_todos = sorted(set(rx_dep.keys()) | set(v_sub["DEPTO"].unique()))
    if ciudad:
        c_can = canonizar_departamento(ciudad)
        deptos_todos = [d for d in deptos_todos if d == c_can]

    filas = []
    for dep in deptos_todos:
        r_info = rx_dep.get(dep, {"gm": 0, "ritmo_g": 0.0, "ms_m": 0.0, "ms_y": 0.0, "delta_ms": 0.0})
        v_d = v_sub[v_sub["DEPTO"] == dep]
        v_ult = float(v_d[v_d["Mes_Label"] == ult]["Monto Real"].sum())
        v_prev = float(v_d[v_d["Mes_Label"] == prev]["Monto Real"].sum())
        c_ult = float(v_d[v_d["Mes_Label"] == ult]["Monto Cuota"].sum()) if tiene_cuota else 0.0
        if r_info["gm"] == 0 and v_ult == 0 and v_prev == 0:
            continue

        var_v_pct = round(((v_ult - v_prev) / v_prev * 100.0), 1) if v_prev > 0 else (100.0 if v_ult > 0 else 0.0)
        pct_cuota = round((v_ult / c_ult * 100.0), 1) if c_ult > 0 else 0.0

        # Diagnóstico cruzado de alta gerencia
        rx_sube = r_info["delta_ms"] >= 2.0 or (r_info["gm"] > r_info["ritmo_g"] * 1.08)
        rx_baja = r_info["delta_ms"] <= -2.0 or (r_info["ritmo_g"] > 0 and r_info["gm"] < r_info["ritmo_g"] * 0.85)
        v_sube = var_v_pct >= 5.0
        v_baja = var_v_pct <= -5.0

        if rx_sube and v_baja:
            diag = "ALERTA FUGA MOSTRADOR / STOCK (Sube Rx, cae Venta)"
        elif rx_sube and v_sube:
            diag = "CRECIMIENTO SANO (Sube Rx + Sube Venta)"
        elif rx_baja and v_baja:
            diag = "CONTRACCIÓN DUAL (Cae Rx + Cae Venta)"
        elif rx_baja and v_sube:
            diag = "EMPUJE EN FARMACIA / REVISAR MÉDICOS (Cae Rx, sube Venta)"
        else:
            diag = "ESTABLE / EN SEGUIMIENTO"

        filas.append({
            "Departamento": dep,
            "Gutis Rx Mes": r_info["gm"],
            "% MS Mes": r_info["ms_m"],
            "Delta MS (pp)": r_info["delta_ms"],
            f"Venta {prev} ($)": round(v_prev, 2),
            f"Venta {ult} ($)": round(v_ult, 2),
            "Var. Venta (%)": var_v_pct,
            f"% Cuota {ult}": pct_cuota,
            "Diagnóstico Cruzado Rx vs. Venta": diag,
        })

    prod_lbl = MERCADOS_PRIORITARIOS[clave_mercado]["producto"] if clave_mercado in MERCADOS_PRIORITARIOS else "Portafolio Completo Gutis"
    if not filas:
        return f"No se encontraron departamentos comparables entre Close-Up y ventas para **{prod_lbl}**."

    df_cruce = pd.DataFrame(filas).sort_values(by=f"Venta {ult} ($)", ascending=False).reset_index(drop=True)
    alertas_fuga = df_cruce[df_cruce["Diagnóstico Cruzado Rx vs. Venta"].str.contains("FUGA")]
    alertas_dual = df_cruce[df_cruce["Diagnóstico Cruzado Rx vs. Venta"].str.contains("CONTRACCIÓN")]

    conclusiones = []
    if not alertas_fuga.empty:
        deps_f = ", ".join(alertas_fuga["Departamento"].tolist())
        conclusiones.append(f"- **Posible Fuga en Mostrador o Quiebre de Stock ({deps_f}):** Tus médicos están aumentando la receta, pero la venta en farmacia bajó de **{prev}** a **{ult}**. Urge auditar inventario y sustitución en mostrador.")
    if not alertas_dual.empty:
        deps_c = ", ".join(alertas_dual["Departamento"].tolist())
        conclusiones.append(f"- **Contracción Dual ({deps_c}):** Cayeron tanto la cuota prescriptiva como la venta facturada; requiere refuerzo simultáneo en consultorio y punto de venta.")
    if not conclusiones:
        conclusiones.append(f"- **Alineación Territorio-Venta:** Revisa en la tabla los departamentos con `% Cuota {ult}` debajo de 75% para focalizar cierre de mes.")

    return f"""### Cruce Estratégico por Departamento: Recetas Close-Up vs. Venta Mensual ({prev} → {ult}) — {prod_lbl}

{df_a_markdown_nativo(df_cruce)}

#### Lectura Ejecutiva para Toma de Decisiones:
""" + "\n".join(conclusiones)


# ============================================================================
# 7. ORQUESTADOR MAESTRO COLOQUIAL DE CHIRA
# ============================================================================
def enrutar_consulta_chira(
    bundle: Any,
    consulta_final: str,
    medico_sel: str,
    especialidad_sel: str,
    ciudad_sel: str,
    alcance_sb: str,
    lista_ciudades: List[str],
    lista_medicos_busqueda: List[str],
) -> Tuple[str, str]:
    """
    Orquesta cualquier pregunta coloquial o técnica en CHIRA, eligiendo
    automáticamente el motor analítico correcto y devolviendo (markdown_verificado, etiqueta_motor).
    """
    q_norm = normalizar_txt(consulta_final)
    solo_panel = alcance_sb.startswith("SOLO")

    # 1. Detección rápida de médico mencionado por nombre o apellido
    medico_detectado = None
    tokens_q = [w for w in re.split(r"[^A-Z0-9]+", q_norm) if len(w) >= 4 and w not in {"DOCTOR", "DOCTORA", "MEDICO", "BIOTOS", "TALERDIN", "MOMETZONA", "VENTILAR", "MASAYA", "GRANADA", "CARAZO", "MANAGUA", "CHONTALES", "RIVAS", "BOACO", "PRECIO", "CUOTA", "VENTA", "CAIDA"}]
    for m_cand in lista_medicos_busqueda:
        m_n = normalizar_txt(m_cand)
        if m_n in q_norm:
            medico_detectado = m_cand
            break
    if not medico_detectado and tokens_q:
        for m_cand in lista_medicos_busqueda:
            partes_m = set(normalizar_txt(m_cand).split())
            coinc = [t for t in tokens_q if t in partes_m]
            if len(coinc) >= 2:
                medico_detectado = m_cand
                break

    # 2. Clasificador coloquial (Gemini + respaldo local)
    claves_validas = list(MERCADOS_PRIORITARIOS.keys())
    cls = clasificar_intencion_coloquial(
        consulta=consulta_final,
        ciudades_validas=lista_ciudades,
        claves_mercado_validas=claves_validas,
        medicos_validos=[],
    )
    intencion = cls.get("intencion", "AUDITORIA_MERCADO")

    # Resolver ciudad (desde clasificador o texto directo)
    ciu_detectada = cls.get("ciudad") or next(
        (c for c in lista_ciudades if normalizar_txt(c) in q_norm),
        None,
    )
    if ciu_detectada and normalizar_txt(ciu_detectada) in ("", "TODAS", "TODO MI PANEL"):
        ciu_detectada = None

    # Resolver clave de mercado (prioriza mención explícita en texto)
    mer_detectado = resolver_clave_mercado_gutis(consulta_final, consulta_final) or (
        cls.get("clave_mercado") if cls.get("clave_mercado") in MERCADOS_PRIORITARIOS else None
    )

    # 3. Enrutamiento a los 8 motores tácticos
    if intencion == "OBJECION":
        mer_obj = mer_detectado or "MR BIOTOS"
        meta_obj = MERCADOS_PRIORITARIOS.get(mer_obj, next(iter(MERCADOS_PRIORITARIOS.values())))
        doc_ctx = medico_detectado or medico_sel
        ciu_ctx = ciu_detectada or ciudad_sel
        sell_ctx = resumen_ventas_ciudad(bundle.ventas, ciu_ctx)
        resp = generar_respuesta_objecion_tactica(
            consulta=consulta_final,
            clave_mercado=mer_obj,
            meta_prod=meta_obj,
            medico_foco=doc_ctx,
            especialidad=especialidad_sel,
            ciudad=ciu_ctx,
            farmacias_str=sell_ctx["top_farmacias"],
        )
        return resp, "Manejo de Objeciones & Playbook TVP"

    if medico_detectado and intencion in ("EXPEDIENTE_MEDICO", "AUDITORIA_MERCADO"):
        return generar_consultoria_cognitiva_chira_medico(bundle, medico_detectado, consulta_final), "Expediente 360 & Guion TVP"

    if intencion == "CAIDA_RX":
        return analizar_caida_rx_medicos(bundle, clave_mercado=mer_detectado, ciudad=ciu_detectada, solo_panel=solo_panel), "Radar de Caída Prescriptiva"

    if intencion == "SUBIDA_CUOTA":
        return analizar_subida_cuota(bundle, ciudad=ciu_detectada, solo_panel=solo_panel), "Auditoría de Subida de Cuota"

    if intencion == "POTENCIAL_EXPANSION":
        return analizar_potencial_expansion(bundle, ciudad=ciu_detectada, solo_panel=solo_panel), "Radar de Potencial de Expansión"

    if intencion == "SUCURSALES_ABORDAJE":
        return analizar_sucursales_abordaje(bundle, ciudad=ciu_detectada, clave_mercado=mer_detectado), "Plan de Abordaje a Sucursales (Sell-Out)"

    if intencion == "CRUCE_RX_VENTA":
        return analizar_cruce_rx_vs_venta(bundle, clave_mercado=mer_detectado, ciudad=ciu_detectada), "Cruce Departamental Rx vs. Venta Mensual"

    if intencion == "EXPEDIENTE_MEDICO":
        return generar_consultoria_cognitiva_chira_medico(bundle, medico_detectado or medico_sel, consulta_final), "Expediente 360 & Guion TVP"

    # Default: Auditoría de mercado territorial
    df_rk_chira = ranking_medicos(
        bundle.productos,
        bundle.panel,
        ciudad=ciu_detectada,
        mercado=mer_detectado,
        modo_panel="PANEL" if solo_panel else "TODOS",
    )
    if not df_rk_chira.empty:
        return generar_analisis_mercado_chira_rico(df_rk_chira, mer_detectado, ciu_detectada), "Auditoría de Mercado Close-Up"

    return generar_consultoria_cognitiva_chira_medico(bundle, medico_sel, consulta_final), "Expediente 360 & Guion TVP"
