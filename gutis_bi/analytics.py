"""
Motor Analítico Integral Gutis BI v2.5 (Fusión de Precisión Modular + Cuadros Ejecutivos TVP & Power BI).
Incluye correcciones de auditoría, compliance ético, filtros limpios y privacidad de datos.
"""

import re
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any

from gutis_bi.catalog import MERCADOS_PRIORITARIOS, PATRON_REGEX_GUTIS
from gutis_bi.data import normalizar_txt, normalizar_serie_rapida, resolver_clave_mercado_gutis

def df_a_markdown_nativo(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "_Sin registros disponibles._"
    cols = [str(c) for c in df.columns]
    filas = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for row in df.itertuples(index=False):
        filas.append("| " + " | ".join(str(val).replace("|", "/") for val in row) + " |")
    return "\n".join(filas)

def formatear_nombre_medico(nombre_raw: Any) -> str:
    if not nombre_raw or pd.isna(nombre_raw):
        return "Especialista"
    partes = [p.capitalize() for p in str(nombre_raw).replace("#", "ñ").strip().split() if len(p) > 1]
    if len(partes) >= 3:
        return f"{partes[2]} {partes[0]}"
    elif len(partes) == 2:
        return f"{partes[1]} {partes[0]}"
    return str(nombre_raw).title()

def limpiar_sku_competencia(sku_raw: Any) -> Tuple[str, str, str]:
    if not sku_raw or pd.isna(sku_raw) or "SIN COMPETIDOR" in str(sku_raw).upper() or "DOMINIO" in str(sku_raw).upper():
        return "la marca tradicional", "presentación convencional", "la competencia de la categoría"
    s = str(sku_raw).strip()
    s_up = s.upper()
    forma_f = "presentación habitual"
    if any(k in s_up for k in ["GOT", "GTS", "DROP"]): forma_f = "Solución Gotas"
    elif any(k in s_up for k in ["JAR", "JBE", "SUSP", "SOL OR", "SYR", "LIQ"]): forma_f = "Jarabe / Suspensión oral"
    elif any(k in s_up for k in ["SPRAY", "NAS", "AER", " INH"]): forma_f = "Spray nasal"
    elif any(k in s_up for k in ["AMP", "INY", "VIAL", "JGA"]): forma_f = "Ampolla inyectable"
    elif any(k in s_up for k in ["SOB", "STICK", "GRAN", "POLV"]): forma_f = "Sobres / Granulado"
    elif any(k in s_up for k in ["CREM", "UNG", "POM", "GEL", "TOP"]): forma_f = "Crema / Ungüento tópico"
    elif any(k in s_up for k in ["TAB", "COMP", "CAP", "GRAG"]): forma_f = "Tabletas / Cápsulas"

    izquierda = s.split("-")[0].strip()
    tokens_izq = izquierda.split()
    marca_limpia = " ".join(tokens_izq[:-1]).title() if (len(tokens_izq) > 1 and len(tokens_izq[-1]) in [2, 3, 4]) else izquierda.title()
    if not marca_limpia:
        marca_limpia = s.split()[0].title()
    return marca_limpia, forma_f, f"{marca_limpia} ({forma_f})"

def diagnosticar_escala_adopcion(
    pxs_gutis_mes: int,
    pxs_tot_mes: int,
    ms_gutis_mes: float,
    pxs_gutis_ytd: int = 0,
    pxs_tot_ytd: int = 0,
    ms_gutis_ytd: float = 0.0
) -> Dict[str, str]:
    ms_eval = ms_gutis_mes if pxs_tot_mes > 0 else ms_gutis_ytd
    pxs_g_eval = pxs_gutis_mes if pxs_tot_mes > 0 else pxs_gutis_ytd
    pxs_t_eval = pxs_tot_mes if pxs_tot_mes > 0 else pxs_tot_ytd
    etiqueta = "Mes" if pxs_tot_mes > 0 else "Histórico YTD"

    if pxs_t_eval <= 0:
        return {
            "nivel": "1. No Consciente",
            "meta": "2. Consciente / 3. Prueba (2-5 Pxs)",
            "modo": "CONQUISTA",
            "accion": "Crear conciencia del perfil de paciente y lograr las primeras recetas de prueba."
        }
    if pxs_g_eval == 0:
        return {
            "nivel": f"2. Consciente (0% MS {etiqueta})",
            "meta": "3. Prueba (2 a 10 Pxs)",
            "modo": "CONQUISTA",
            "accion": f"Iniciar período de prueba en sus próximos 3 a 5 pacientes (prescribe {pxs_t_eval} Pxs en total)."
        }
    
    # NUEVO: Control de Falsos Positivos de Lealtad (Exigir mínimo 6 recetas en la categoría para considerar Lealtad)
    if pxs_t_eval < 6 and ms_eval >= 50.0:
        return {
            "nivel": f"3. Prueba ({ms_eval:.1f}% MS {etiqueta} | {pxs_g_eval} Pxs)",
            "meta": "4. Adopción (Incrementar Base de Pacientes)",
            "modo": "EXPANSION",
            "accion": "Volumen bajo en la categoría. Consolidar el uso clínico antes de considerarlo usuario leal."
        }
        
    if ms_eval < 25.0:
        return {
            "nivel": f"3. Prueba ({ms_eval:.1f}% MS {etiqueta} | {pxs_g_eval} Pxs)",
            "meta": "4. Adopción (25% a 50% MS)",
            "modo": "EXPANSION",
            "accion": "Agradecer recetas iniciales y expandir hacia más del 25% de la categoría."
        }
    if ms_eval < 50.0:
        return {
            "nivel": f"4. Adopción ({ms_eval:.1f}% MS {etiqueta} | {pxs_g_eval} Pxs)",
            "meta": "5. Lealtad (>50% MS)",
            "modo": "EXPANSION",
            "accion": "Reconocer su respaldo activo y migrar sutilmente el segmento que aún comparte."
        }
    return {
        "nivel": f"5. Lealtad ({ms_eval:.1f}% MS {etiqueta} | {pxs_g_eval} Pxs)",
        "meta": "5. Lealtad (Blindaje y Puente)",
        "modo": "LEALTAD",
        "accion": "Agradecer su lealtad como socio estratégico, blindar presentaciones y hacer Puente."
    }

def resumen_global(df_panel: pd.DataFrame, df_productos: pd.DataFrame) -> Dict[str, Any]:
    tot_meds = len(df_panel["Médico"].dropna().unique()) if not df_panel.empty and "Médico" in df_panel.columns else 0
    if df_productos.empty or df_panel.empty:
        return {
            "medicos_panel": tot_meds, "medicos_activos": 0,
            "pxs_mes": 0, "pxs_gutis_mes": 0, "ms_mes": 0.0,
            "pxs_ytd": 0, "pxs_gutis_ytd": 0, "ms_ytd": 0.0
        }
    meds_set = set(df_panel["Médico"].dropna().unique())
    sub = df_productos[df_productos["Médico"].isin(meds_set) & df_productos["Clave_Gutis"].notna()]
    activos = len(sub[sub["Pxs-YTD"] > 0]["Médico"].unique()) if "Pxs-YTD" in sub.columns else 0

    m_tot = int(sub["Pxs-MES"].sum()) if "Pxs-MES" in sub.columns else 0
    m_gut = int(sub[sub["Es_Gutis"]]["Pxs-MES"].sum()) if ("Pxs-MES" in sub.columns and m_tot > 0) else 0
    ms_m = (m_gut / m_tot * 100.0) if m_tot > 0 else 0.0

    y_tot = int(sub["Pxs-YTD"].sum()) if "Pxs-YTD" in sub.columns else 0
    y_gut = int(sub[sub["Es_Gutis"]]["Pxs-YTD"].sum()) if ("Pxs-YTD" in sub.columns and y_tot > 0) else 0
    ms_y = (y_gut / y_tot * 100.0) if y_tot > 0 else 0.0

    return {
        "medicos_panel": tot_meds, "medicos_activos": activos,
        "pxs_mes": m_tot, "pxs_gutis_mes": m_gut, "ms_mes": ms_m,
        "pxs_ytd": y_tot, "pxs_gutis_ytd": y_gut, "ms_ytd": ms_y
    }

def resumen_mercados(df_productos: pd.DataFrame, df_panel: pd.DataFrame, ciudad: Optional[str] = None, incluir_fuera_panel: bool = False) -> pd.DataFrame:
    if df_productos.empty:
        return pd.DataFrame()
    sub = df_productos[df_productos["Clave_Gutis"].notna()].copy()
    if not incluir_fuera_panel and not df_panel.empty and "Médico" in df_panel.columns:
        meds_panel = set(df_panel["Médico"].dropna().unique())
        sub = sub[sub["Médico"].isin(meds_panel)]
    if ciudad and ciudad not in ("TODO MI PANEL", "TODAS"):
        sub = sub[sub["CIUDAD_PANEL"].str.contains(re.escape(ciudad.upper()), na=False)]
    if sub.empty:
        return pd.DataFrame()

    filas = []
    for k_gut, grp in sub.groupby("Clave_Gutis"):
        meta = MERCADOS_PRIORITARIOS.get(k_gut, {})
        tot_m = int(grp["Pxs-MES"].sum()) if "Pxs-MES" in grp.columns else 0
        tot_y = int(grp["Pxs-YTD"].sum()) if "Pxs-YTD" in grp.columns else 0
        if tot_m == 0 and tot_y == 0:
            continue
        grp_g = grp[grp["Es_Gutis"]]
        gut_m = int(grp_g["Pxs-MES"].sum()) if "Pxs-MES" in grp_g.columns else 0
        gut_y = int(grp_g["Pxs-YTD"].sum()) if "Pxs-YTD" in grp_g.columns else 0
        ms_m = round((gut_m / tot_m * 100.0), 2) if tot_m > 0 else 0.0
        ms_y = round((gut_y / tot_y * 100.0), 2) if tot_y > 0 else 0.0
        delta_ms = round(ms_m - ms_y, 2)
        estado_crec = (
            f"GANA PARTICIPACIÓN (+{delta_ms:.1f} pp vs YTD)" if delta_ms >= 2.0
            else (f"CEDE PARTICIPACIÓN ({delta_ms:.1f} pp vs YTD)" if delta_ms <= -2.0
            else f"ESTABLE ({delta_ms:+.1f} pp vs YTD)")
        )

        filas.append({
            "Clave": k_gut,
            "Prioridad": f"P{meta.get('prioridad', 3)}",
            "Marca Gutis": meta.get("producto", k_gut),
            "Clase Terapéutica": meta.get("clase_terapeutica", ""),
            "Mercado Mes": tot_m,
            "Gutis Mes": gut_m,
            "Competencia Mes": tot_m - gut_m,
            "% MS Mes": ms_m,
            "Mercado YTD": tot_y,
            "Gutis YTD": gut_y,
            "Competencia YTD": tot_y - gut_y,
            "% MS YTD": ms_y,
            "Brecha MS Mes vs YTD (pp)": delta_ms,
            "Diagnóstico de Evolución": estado_crec,
            "_p": meta.get("prioridad", 3)
        })

    df_out = pd.DataFrame(filas)
    return df_out.sort_values(by=["_p", "Mercado Mes", "Mercado YTD"], ascending=[True, False, False]).drop(columns=["_p"]) if not df_out.empty else df_out

def calcular_tabla_bi_multifiltro(
    df_auditoria_docs: pd.DataFrame,
    df_auditoria_tot: pd.DataFrame,
    f_zona: str = "Todas",
    f_med: str = "Todas",
    f_esp: str = "Todas",
    f_vis: str = "Todas",
    f_mer: str = "Todas",
    f_mar: str = "Todas",
    f_lab: str = "Todas",
    f_cat: str = "Todas"
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if df_auditoria_docs.empty:
        return pd.DataFrame(), pd.DataFrame()

    sub = df_auditoria_docs
    if f_zona != "Todas": sub = sub[sub["Zona"] == f_zona]
    if f_med != "Todas": sub = sub[sub["Médico"] == f_med]
    if f_esp != "Todas": sub = sub[sub["Especialidad"] == f_esp]
    if f_vis != "Todas" and "VISITADOR" in sub.columns: sub = sub[sub["VISITADOR"] == f_vis]
    if f_mer != "Todas":
        sub = sub[(sub["Clave_Gutis"] == f_mer) | (sub["Mercado_BI"] == f_mer)]
    if f_mar != "Todas": sub = sub[sub["MARCA"] == f_mar]
    if f_lab != "Todas": sub = sub[sub["Laboratorio"] == f_lab]
    if f_cat != "Todas": sub = sub[sub["Categoria_TAM"] == str(f_cat)]

    if sub.empty:
        return pd.DataFrame(), pd.DataFrame()

    sin_filtro_parcial = (f_zona == "Todas" and f_med == "Todas" and f_esp == "Todas" and f_cat == "Todas" and f_mer == "Todas" and f_lab == "Todas" and f_mar == "Todas")
    cols_p = ["% MS - LY", "% MS - Ytd", "% MS - TrasAnt", "% MS - Ant", "% MS - Mes"]
    w_cols = ["W_" + c for c in cols_p]

    if sin_filtro_parcial and not df_auditoria_tot.empty:
        rk_m = df_auditoria_tot[cols_p].copy() * 100.0
        rk_m["Dif %"] = rk_m["% MS - Ytd"] - rk_m["% MS - LY"]
        rk_m = rk_m.reset_index().rename(columns={"index": "MARCA"})
    else:
        grp_m = sub.groupby("MARCA", as_index=False)[w_cols].sum()
        tot_w = grp_m[w_cols].sum(axis=0)
        for c_orig, c_w in zip(cols_p, w_cols):
            grp_m[c_orig] = np.where(tot_w[c_w] > 0, (grp_m[c_w] / tot_w[c_w]) * 100.0, 0.0)
        grp_m["Dif %"] = grp_m["% MS - Ytd"] - grp_m["% MS - LY"]
        rk_m = grp_m[["MARCA"] + cols_p + ["Dif %"]].copy()

    rk_m["Origen"] = np.where(normalizar_serie_rapida(rk_m["MARCA"]).str.contains(PATRON_REGEX_GUTIS, na=False) | rk_m["MARCA"].str.endswith(" GPR"), "GUTIS", "COMPETENCIA")
    rk_m = rk_m.sort_values(by=["% MS - Ytd", "% MS - Mes"], ascending=[False, False]).reset_index(drop=True)
    cols_orden_bi = ["MARCA", "Origen", "% MS - LY", "% MS - Ytd", "Dif %", "% MS - TrasAnt", "% MS - Ant", "% MS - Mes"]
    rk_m = rk_m[cols_orden_bi].round(2)

    grp_d = sub.groupby(["Médico", "Especialidad", "Zona", "Categoria_TAM"], as_index=False)[w_cols].sum()
    tot_wd = grp_d[w_cols].sum(axis=0)
    for c_orig, c_w in zip(cols_p, w_cols):
        grp_d[c_orig] = np.where(tot_wd[c_w] > 0, (grp_d[c_w] / tot_wd[c_w]) * 100.0, 0.0)
    grp_d["Dif %"] = grp_d["% MS - Ytd"] - grp_d["% MS - LY"]
    rk_d = grp_d[["Médico", "Especialidad", "Zona", "Categoria_TAM", "% MS - LY", "% MS - Ytd", "Dif %", "% MS - TrasAnt", "% MS - Ant", "% MS - Mes"]].sort_values(by=["% MS - Ytd", "% MS - Mes"], ascending=[False, False]).reset_index(drop=True).round(2)

    return rk_m, rk_d

def ranking_medicos(
    df_productos: pd.DataFrame,
    df_panel: pd.DataFrame,
    ciudad: Optional[str] = None,
    especialidad: Optional[str] = None,
    mercado: Optional[str] = None,
    modo_panel: str = "PANEL"
) -> pd.DataFrame:
    if df_productos.empty:
        return pd.DataFrame()
    rx_sub = df_productos[df_productos["Clave_Gutis"].notna()].copy()
    if mercado and mercado not in ("Todos los mercados", "TODOS LOS MERCADOS", "TODOS"):
        rx_sub = rx_sub[rx_sub["Clave_Gutis"] == mercado]

    meds_panel_set = set(df_panel["Médico"].dropna().unique()) if not df_panel.empty else set()
    if modo_panel == "PANEL":
        rx_sub = rx_sub[rx_sub["Médico"].isin(meds_panel_set)]
    elif modo_panel == "FUERA_PANEL":
        rx_sub = rx_sub[~rx_sub["Médico"].isin(meds_panel_set)]

    if ciudad and ciudad not in ("TODO MI PANEL", "TODAS"):
        rx_sub = rx_sub[rx_sub["CIUDAD_PANEL"].str.contains(re.escape(ciudad.upper()), na=False)]
    
    # NUEVO: Filtro exacto de especialidad para evitar colisión Medicina General vs Interna
    if especialidad and especialidad not in ("TODAS", "TODAS LAS ESPECIALIDADES"):
        rx_sub = rx_sub[rx_sub["ESP_PANEL"].astype(str).str.upper() == especialidad.upper()]

    if rx_sub.empty:
        return pd.DataFrame()

    c_m, c_y = "Pxs-MES", "Pxs-YTD"
    rx_sub = rx_sub[(rx_sub[c_m] > 0) | (rx_sub[c_y] > 0)].copy()
    if rx_sub.empty:
        return pd.DataFrame()

    filas = []
    for nom_doc, grp in rx_sub.groupby("Médico", sort=False):
        p_m = int(grp[c_m].sum())
        p_y = int(grp[c_y].sum())
        if p_m <= 0 and p_y <= 0:
            continue
        grp_g = grp[grp["Es_Gutis"]]
        g_m = int(grp_g[c_m].sum())
        g_y = int(grp_g[c_y].sum())
        ms_m = round((g_m / p_m * 100.0), 1) if p_m > 0 else 0.0
        ms_y = round((g_y / p_y * 100.0), 1) if p_y > 0 else 0.0
        scale = diagnosticar_escala_adopcion(g_m, p_m, ms_m, g_y, p_y, ms_y)

        grp_ord = grp.sort_values(by=[c_m, c_y], ascending=False)
        grp_riv = grp_ord[~grp_ord["Es_Gutis"]]
        riv_str = f"{grp_riv.iloc[0]['NOMBRE_PRODUCTO']} ({int(grp_riv.iloc[0][c_m])} Mes / {int(grp_riv.iloc[0][c_y])} YTD)" if not grp_riv.empty else "Dominio 100% Gutis"
        top_marcas = [f"{r['NOMBRE_PRODUCTO']} [{int(r[c_m])}M/{int(r[c_y])}Y]" for _, r in grp_ord.head(3).iterrows()]

        pf = grp.iloc[0]
        filas.append({
            "Médico": nom_doc,
            "Estatus Panel": "EN PANEL" if nom_doc in meds_panel_set else "FUERA DE PANEL",
            "Especialidad": str(pf.get("ESP_PANEL", "ESPECIALISTA")),
            "Cat": str(pf.get("CAT_PANEL", "S/C")),
            "Ciudad": str(pf.get("CIUDAD_PANEL", "NICARAGUA")),
            "Pxs Mes": p_m,
            "Gutis Mes": g_m,
            "Comp Mes": p_m - g_m,
            "% MS Mes": ms_m,
            "Pxs YTD": p_y,
            "Gutis YTD": g_y,
            "Comp YTD": p_y - g_y,
            "% MS YTD": ms_y,
            "Escala TVP": scale["nivel"].split("(")[0].strip(),
            "Rival Principal en la Clase": riv_str,
            "Desglose Marcas [Mes/YTD]": " | ".join(top_marcas)
        })
    df_res = pd.DataFrame(filas)
    return df_res.sort_values(by=["Pxs Mes", "Pxs YTD", "Comp Mes"], ascending=[False, False, False]).reset_index(drop=True) if not df_res.empty else df_res

def perfil_medico(df_panel: pd.DataFrame, df_productos: pd.DataFrame, medico: str) -> Dict[str, Any]:
    res = {"Médico": medico, "CIUDAD": "NICARAGUA", "Especialidad": "ESPECIALISTA", "CATEGORIA": "FUERA DE PANEL"}
    if not df_panel.empty and "Médico" in df_panel.columns:
        row = df_panel[df_panel["Médico"] == medico]
        if not row.empty:
            res["CIUDAD"] = str(row.iloc[0].get("CIUDAD", "NICARAGUA")).strip().upper()
            res["Especialidad"] = str(row.iloc[0].get("Especialidad", "ESPECIALISTA")).strip().upper()
            res["CATEGORIA"] = str(row.iloc[0].get("CATEGORIA", "S/C")).strip()

    if not df_productos.empty and "Médico" in df_productos.columns:
        sub = df_productos[(df_productos["Médico"] == medico) & df_productos["Clave_Gutis"].notna()]
        pm = int(sub["Pxs-MES"].sum()) if "Pxs-MES" in sub.columns else 0
        py = int(sub["Pxs-YTD"].sum()) if "Pxs-YTD" in sub.columns else 0
        gm = int(sub[sub["Es_Gutis"]]["Pxs-MES"].sum()) if ("Pxs-MES" in sub.columns and pm > 0) else 0
        gy = int(sub[sub["Es_Gutis"]]["Pxs-YTD"].sum()) if ("Pxs-YTD" in sub.columns and py > 0) else 0
        res["Pxs Mes"] = pm
        res["Gutis Mes"] = gm
        res["Comp Mes"] = pm - gm
        res["% MS Mes"] = round((gm / pm * 100.0), 1) if pm > 0 else 0.0
        res["Pxs YTD"] = py
        res["Gutis YTD"] = gy
        res["Comp YTD"] = py - gy
        res["% MS YTD"] = round((gy / py * 100.0), 1) if py > 0 else 0.0
    return res

def productos_medico(df_productos: pd.DataFrame, medico: str, criterio_mercado: Optional[str] = None) -> pd.DataFrame:
    if df_productos.empty or "Médico" not in df_productos.columns:
        return pd.DataFrame()
    sub = df_productos[(df_productos["Médico"] == medico) & df_productos["Clave_Gutis"].notna()].copy()
    if criterio_mercado and criterio_mercado not in ("TODOS", "TODOS LOS MERCADOS", "Todos los mercados"):
        sub = sub[sub["Clave_Gutis"] == criterio_mercado].copy()
    if sub.empty:
        return pd.DataFrame()
    sub = sub[(sub["Pxs-MES"] > 0) | (sub["Pxs-YTD"] > 0)].copy()
    if sub.empty:
        return pd.DataFrame()

    sub["Origen"] = np.where(sub["Es_Gutis"], "GUTIS", "COMPETENCIA")
    sub["Clase Terapéutica"] = sub["Clave_Gutis"].map({k: v["clase_terapeutica"] for k, v in MERCADOS_PRIORITARIOS.items()}).fillna("")
    sub["Mercado"] = sub["Clave_Gutis"].map({k: v["producto"] for k, v in MERCADOS_PRIORITARIOS.items()}).fillna("")

    tot_m = sub.groupby("Clave_Gutis")["Pxs-MES"].transform("sum")
    sub["% MS Mes (Categoría)"] = np.where(tot_m > 0, (sub["Pxs-MES"] / tot_m * 100.0).round(1), 0.0)
    tot_y = sub.groupby("Clave_Gutis")["Pxs-YTD"].transform("sum")
    sub["% MS YTD (Categoría)"] = np.where(tot_y > 0, (sub["Pxs-YTD"] / tot_y * 100.0).round(1), 0.0)

    sub["Pxs-MES"] = sub["Pxs-MES"].astype(int)
    sub["Pxs-YTD"] = sub["Pxs-YTD"].astype(int)

    cols = ["MERCADO", "Mercado", "Clase Terapéutica", "NOMBRE_PRODUCTO", "Origen", "Pxs-MES", "% MS Mes (Categoría)", "Pxs-YTD", "% MS YTD (Categoría)"]
    cols_exist = [c for c in cols if c in sub.columns]
    return sub[cols_exist].rename(columns={
        "MERCADO": "Mercado Close-Up",
        "NOMBRE_PRODUCTO": "Marca Prescrita",
        "Pxs-MES": "Pxs Mes",
        "Pxs-YTD": "Pxs YTD"
    }).sort_values(by=["Mercado", "Pxs Mes", "Pxs YTD"], ascending=[True, False, False])

def obtener_matriz_clases_terapeuticas_medico(df_clases: pd.DataFrame, df_productos: pd.DataFrame, medico: str) -> pd.DataFrame:
    if not df_clases.empty and "Médico" in df_clases.columns:
        sub_c = df_clases[df_clases["Médico"] == medico].copy()
        if not sub_c.empty:
            col_ct = next((c for c in sub_c.columns if any(k in normalizar_txt(c) for k in ["CLASE", "TERAPEUTICA", "ATC", "MERCADO"])), None)
            if col_ct:
                sub_c = sub_c[~sub_c[col_ct].astype(str).str.upper().isin(["TOTAL", "NAN", "NONE", ""])].copy()
                cols_num = [c for c in sub_c.columns if any(k in c.upper() for k in ["PXS", "MS", "LY", "YTD", "TRIM", "MES"])]
                for cn in cols_num:
                    sub_c[cn] = pd.to_numeric(sub_c[cn], errors="coerce").fillna(0)
                col_ord = next((c for c in cols_num if "YTD" in c.upper() and "PXS" in c.upper()), cols_num[0] if cols_num else None)
                if col_ord: sub_c = sub_c.sort_values(by=col_ord, ascending=False)
                return sub_c[[col_ct] + cols_num].reset_index(drop=True)
    return productos_medico(df_productos, medico)

def radar_laboratorios(
    df_laboratorios: pd.DataFrame,
    df_panel: pd.DataFrame,
    ciudad: Optional[str] = None,
    especialidad: Optional[str] = None,
    medico: Optional[str] = None
) -> pd.DataFrame:
    if df_laboratorios.empty or "FABRICANTE" not in df_laboratorios.columns:
        return pd.DataFrame()
    sub = df_laboratorios[~df_laboratorios["FABRICANTE"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])].copy()
    if medico:
        sub = sub[sub["Médico"] == medico]
    else:
        if not df_panel.empty:
            p_sub = df_panel.copy()
            if ciudad and ciudad not in ("TODO MI PANEL", "TODAS"):
                p_sub = p_sub[p_sub["CIUDAD"].str.contains(re.escape(ciudad.upper()), na=False)]
            # NUEVO: Filtro exacto para evitar colisión Medicina General vs Interna
            if especialidad and especialidad not in ("TODAS", "TODAS LAS ESPECIALIDADES"):
                p_sub = p_sub[p_sub["Especialidad"].astype(str).str.upper() == especialidad.upper()]
            sub = sub[sub["Médico"].isin(set(p_sub["Médico"].dropna().unique()))]

    if sub.empty:
        return pd.DataFrame()

    rk = sub.groupby("FABRICANTE").agg({"Pxs-MES": "sum", "Pxs-YTD": "sum", "Médico": "nunique"}).reset_index()
    tot_m = rk["Pxs-MES"].sum()
    tot_y = rk["Pxs-YTD"].sum()
    rk["Pxs Mes"] = rk["Pxs-MES"].astype(int)
    rk["% MS Mes"] = np.where(tot_m > 0, (rk["Pxs-MES"] / tot_m * 100.0).round(2), 0.0)
    rk["Pxs YTD"] = rk["Pxs-YTD"].astype(int)
    rk["% MS YTD"] = np.where(tot_y > 0, (rk["Pxs-YTD"] / tot_y * 100.0).round(2), 0.0)
    rk["Brecha MS (Mes vs YTD)"] = (rk["% MS Mes"] - rk["% MS YTD"]).round(2)
    # NUEVO: Solo agregar [GUTIS] si no lo tiene, para evitar duplicaciones en app.py
    rk["Laboratorio"] = np.where(
        (rk["FABRICANTE"].astype(str).str.upper().str.contains("GUTIS", na=False)) & (~rk["FABRICANTE"].astype(str).str.upper().str.startswith("[GUTIS]")), 
        "[GUTIS] " + rk["FABRICANTE"].astype(str), 
        rk["FABRICANTE"].astype(str)
    )
    rk = rk.sort_values(by=["Pxs Mes", "Pxs YTD"], ascending=[False, False]).reset_index(drop=True)
    return rk[["Laboratorio", "Médico", "Pxs Mes", "% MS Mes", "Pxs YTD", "% MS YTD", "Brecha MS (Mes vs YTD)"]].rename(columns={"Médico": "Prescriptores"})

def matriz_penetracion(df_panel_sub: pd.DataFrame, df_laboratorios: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if df_panel_sub.empty or df_laboratorios.empty:
        return pd.DataFrame(), pd.DataFrame()
    df_l = df_laboratorios[~df_laboratorios["FABRICANTE"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])].copy()

    filas_rend, filas_top = [], []
    for esp, grp in df_panel_sub.groupby("Especialidad"):
        meds = set(grp["Médico"].dropna().unique())
        n_panel = len(meds)
        if n_panel == 0:
            continue
        sub_l = df_l[df_l["Médico"].isin(meds) & (df_l["Pxs-YTD"] > 0)]
        n_cap = len(sub_l["Médico"].unique())
        rec_gutis, top1, top3 = 0, 0, 0
        if not sub_l.empty:
            grp_mf = sub_l.groupby(["Médico", "FABRICANTE"], as_index=False)["Pxs-YTD"].sum().sort_values(by=["Médico", "Pxs-YTD"], ascending=[True, False])
            grp_mf["Rank"] = grp_mf.groupby("Médico").cumcount() + 1
            fg = grp_mf[grp_mf["FABRICANTE"].astype(str).str.upper().str.contains("GUTIS", na=False) & (grp_mf["Pxs-YTD"] > 0)]
            rec_gutis = len(fg["Médico"].unique())
            top1 = int((fg["Rank"] == 1).sum())
            top3 = int((fg["Rank"] <= 3).sum())

        pen = (rec_gutis / n_cap * 100.0) if n_cap > 0 else 0.0
        ms_y, ms_m = 0.0, 0.0
        top5 = ["-"] * 5
        if not sub_l.empty:
            rk = sub_l.groupby("FABRICANTE").agg({"Pxs-YTD": "sum", "Pxs-MES": "sum"}).reset_index().sort_values(by="Pxs-YTD", ascending=False).reset_index(drop=True)
            ty = rk["Pxs-YTD"].sum()
            tm = rk["Pxs-MES"].sum()
            fg_e = rk[rk["FABRICANTE"].astype(str).str.upper().str.contains("GUTIS", na=False)]
            if not fg_e.empty:
                ms_y = float(fg_e.iloc[0]["Pxs-YTD"] / ty * 100.0) if ty > 0 else 0.0
                ms_m = float(fg_e.iloc[0]["Pxs-MES"] / tm * 100.0) if tm > 0 else 0.0
            top5 = [
                f"{'[GUTIS] ' if 'GUTIS' in str(rk.iloc[i]['FABRICANTE']).upper() else ''}{str(rk.iloc[i]['FABRICANTE']).strip()} ({(rk.iloc[i]['Pxs-MES']/tm*100 if tm>0 else 0):.1f}% M | {(rk.iloc[i]['Pxs-YTD']/ty*100 if ty>0 else 0):.1f}% Y)"
                if i < len(rk) else "-" for i in range(5)
            ]

        filas_rend.append({
            "ESPECIALIDAD": esp, "PANEL": n_panel, "CAPTADOS": n_cap, "RECETAN GUTIS": rec_gutis,
            "PENETRACIÓN": round(pen, 2), "TOP 1": top1, "TOP 3": top3,
            "% MS MES": round(ms_m, 2), "% MS YTD": round(ms_y, 2)
        })
        filas_top.append({
            "ESPECIALIDAD": esp,
            "#1": top5[0], "#2": top5[1], "#3": top5[2], "#4": top5[3], "#5": top5[4],
            "_orden": n_panel
        })

    df_rend = pd.DataFrame(filas_rend).sort_values(by="PANEL", ascending=False) if filas_rend else pd.DataFrame()
    df_comp = pd.DataFrame(filas_top).sort_values(by="_orden", ascending=False).drop(columns=["_orden"]) if filas_top else pd.DataFrame()
    return df_rend, df_comp

def auditoria_marcas(
    df_auditoria: pd.DataFrame,
    df_auditoria_tot: pd.DataFrame,
    zona: str = "Todas",
    medico: str = "Todos",
    especialidad: str = "Todas",
    mercado: str = "Todos"
) -> pd.DataFrame:
    rk_m, _ = calcular_tabla_bi_multifiltro(
        df_auditoria, df_auditoria_tot,
        f_zona=zona,
        f_med="Todas" if medico == "Todos" else medico,
        f_esp=especialidad,
        f_vis="Todas",
        f_mer="Todas" if mercado == "Todos" else mercado,
        f_mar="Todas",
        f_lab="Todas",
        f_cat="Todas"
    )
    return rk_m

def resumen_ventas_ciudad(df_ventas: pd.DataFrame, ciudad: str) -> Dict[str, Any]:
    if df_ventas.empty or "DESCRIPCION_RUTA" not in df_ventas.columns:
        return {"total": 0.0, "pdvs": 0, "top_farmacias": "principales farmacias de la zona"}
    vz = df_ventas[df_ventas["DESCRIPCION_RUTA"].str.contains(re.escape(ciudad.upper()), na=False)].copy()
    if vz.empty:
        return {"total": 0.0, "pdvs": 0, "top_farmacias": "principales farmacias de la zona"}
    vz = vz[~vz["NOMBRE_CLIENTE_1"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
    tot = float(vz["Monto Real"].sum())
    rk_f = vz.groupby("NOMBRE_CLIENTE_1")["Monto Real"].sum().reset_index().sort_values(by="Monto Real", ascending=False)
    top_f = ", ".join(rk_f["NOMBRE_CLIENTE_1"].head(3).tolist()) if not rk_f.empty else "principales farmacias de la zona"
    return {"total": tot, "pdvs": len(rk_f), "top_farmacias": top_f}

def ventas_por_trimestre(df_ventas: pd.DataFrame, ciudad: Optional[str] = None, producto: Optional[str] = None) -> pd.DataFrame:
    if df_ventas.empty:
        return pd.DataFrame()
    sub = df_ventas[~df_ventas["NOMBRE_CLIENTE_1"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])].copy()
    if ciudad and ciudad not in ("TODO MI PANEL", "TODAS"):
        sub = sub[sub["DESCRIPCION_RUTA"].str.contains(re.escape(ciudad.upper()), na=False)]
    if producto:
        sub = sub[sub["PRODUCTO_VENTA"] == producto.upper()]
    if sub.empty or "Trimestre" not in sub.columns:
        return pd.DataFrame()

    piv = pd.pivot_table(sub, values="Monto Real", index=["NOMBRE_CLIENTE_1", "PRODUCTO_VENTA"], columns=["Trimestre"], aggfunc="sum", fill_value=0.0).reset_index()
    for q in ["Q1", "Q2", "Q3"]:
        if q not in piv.columns: piv[q] = 0.0
        piv[q] = piv[q].round(2)
    piv["Total Acumulado"] = (piv["Q1"] + piv["Q2"] + piv["Q3"]).round(2)
    return piv.sort_values(by="Total Acumulado", ascending=False)

def construir_guion_tvp_dinamico(
    medico_raw: str,
    especialidad: str,
    ciudad: str,
    m_primario: Dict[str, Any],
    prod2: str,
    benef2: str,
    rival2_raw: str,
    prod3: str,
    tipo_cita_sel: str,
    nec_detras_sel: str,
    top_farmacias_str: str,
    num_variante: int = 0,
    notas_rapport: str = ""
) -> str:
    nom_corto = formatear_nombre_medico(medico_raw)
    es_ped = "PEDIAT" in especialidad.upper()
    meta1 = m_primario["meta_info"]
    prod1 = m_primario["prod_gutis"]
    modo_tac = m_primario["modo_tactico"]
    rival_marca, rival_forma, rival_completo = limpiar_sku_competencia(m_primario["rival_principal"])
    rival2_marca, _, _ = limpiar_sku_competencia(rival2_raw)
    paciente_meta = meta1.get("paciente_meta_ped", meta1["paciente_meta"]) if es_ped else meta1["paciente_meta"]
    farmacia_top1 = top_farmacias_str.split(",")[0].strip()

    if "Imagen" in nec_detras_sel:
        enfoque_ndn_titulo = "Prestigio Clínico y Satisfacción del Paciente (NdN: Imagen)"
        argumento_ndn = meta1.get("arg_imagen", meta1["beneficio"])
        pregunta_ndn = f"¿qué impacto tiene en la confianza de la familia cuando el paciente evoluciona sin efectos secundarios ni rechazo a la {rival_forma.lower()}?"
    elif "Finanzas" in nec_detras_sel:
        enfoque_ndn_titulo = "Rendimiento Terapéutico y Economía del Paciente (NdN: Finanzas)"
        argumento_ndn = meta1.get("arg_finanzas", meta1["beneficio"])
        pregunta_ndn = f"¿cuánto influye en el apego al tratamiento completo el hecho de que el paciente no tenga que suspender o gastar doble en farmacia?"
    else:
        enfoque_ndn_titulo = "Eficacia Clínica y Adherencia Terapéutica (NdN: Desempeño)"
        argumento_ndn = meta1["beneficio"]
        pregunta_ndn = f"¿qué aspecto considera prioritario optimizar en rapidez de acción y tolerabilidad frente a {rival_marca} en {rival_forma.lower()}?"

    # NUEVO: No incluir el texto de rapport personal si va a pasarse a la IA
    rap_txt = f" Tenía presente además lo conversado en visitas anteriores." if notas_rapport else ""
    
    # NUEVO: Control exacto de minúsculas
    tc_lower = tipo_cita_sel.lower()
    if "pasillo" in tc_lower:
        intro_contexto = f"Doctor(a) {nom_corto}, sé que va en movimiento hacia consulta; le tomo literalmente 45 segundos.{rap_txt}"
    elif "improvisto" in tc_lower:
        intro_contexto = f"Doctor(a) {nom_corto}, agradezco mucho que me reciba este minuto entre pacientes.{rap_txt}"
    else:
        intro_contexto = f"Doctor(a) {nom_corto}, qué gusto saludarlo(a) en esta visita programada.{rap_txt}"

    v_idx = num_variante % 3
    if modo_tac == "LEALTAD":
        if v_idx == 0:
            return f"""#### Guion Táctico TVP — Socio en Lealtad ({enfoque_ndn_titulo})
1. **Apertura de Reconocimiento y Valoración ({tipo_cita_sel}):**
   > «{intro_contexto} Hoy mi prioridad es agradecerle su respaldo contundente a **{prod1}** ({m_primario['gutis_mes']} recetas en el mes y {m_primario['gutis_ytd']} en el acumulado anual); usted lidera el estándar de cuidado en {ciudad} para **{paciente_meta.lower()}**.»
2. **Sondeo de Blindaje y Validación Clínica:**
   > «En esta amplia experiencia que ya tiene prescribiendo **{prod1}**, {pregunta_ndn} Le confirmo que en **{top_farmacias_str}** ya blindamos el inventario completo de todas nuestras presentaciones para que ninguna receta suya sufra cambios en mostrador.»
3. **El Puente de Autoridad hacia la 2da Posición (`{prod2}`):**
   > «Precisamente porque usted ya comprueba a diario la nobleza galénica de Gutis con **{prod1}** (*{meta1['caracteristica']}*), quiero apoyarme en esa misma confianza para sus pacientes donde requiere **{benef2}** (donde aún se observan prescripciones hacia **{rival2_marca}**).»
4. **Cierre Bilateral en el Producto Puente y Recordación (`{prod3}`):**
   > «¿Me permite que esta semana extendamos esa misma alianza iniciando con **{prod2}** en sus próximos 3 a 5 pacientes de este perfil, contando además con **{prod3}** totalmente disponible en **{farmacia_top1}**?»"""
        elif v_idx == 1:
            return f"""#### Variante Táctica II (Enfoque Consultivo de Blindaje + Extensión de Línea)
1. **Apertura Ejecutiva de Socio Estratégico:**
   > «{intro_contexto} Viendo el comportamiento de *{m_primario['clase_terapeutica']}* en {ciudad}, **{prod1}** representa el **{m_primario['ms_mes']:.0f}%** de su elección actual. Gracias por esa confianza en nuestra tecnología.»
2. **Pregunta de Retención Activa:**
   > «Para asegurar que el 100% de sus pacientes reciban exactamente el esquema que usted indica, ¿hay alguna presentación específica de **{prod1}** que desee que reforcemos hoy mismo en **{farmacia_top1}**?»
3. **Apoyo Cruzado y Salto al Puente (`{prod2}`):**
   > «Con **{prod1}** usted {argumento_ndn}. Esa misma exigencia farmacéutica la tiene disponible en **{prod2}**, diseñado para que en su consulta de **{especialidad}** logre **{benef2}**.»
4. **Acuerdo de Expansión Cruzada:**
   > «Doctor(a) {nom_corto}, mantengamos a **{prod1}** como su referencia indiscutible y démosle la oportunidad a **{prod2}** en los próximos 4 pacientes donde antes consideraba **{rival2_marca}**. ¿Trato hecho?»"""
        else:
            return f"""#### Variante Táctica III (Abordaje Rápido y Respaldo en Farmacias Aliadas)
1. **Apertura Directa:**
   > «{intro_contexto} Vengo con dos objetivos muy concretos: agradecerle que **{prod1}** sea su marca número uno en la categoría y actualizarle nuestra cobertura en **{top_farmacias_str}**.»
2. **Validación de Necesidad detrás de la Necesidad ({nec_detras_sel.split('(')[0].strip()}):**
   > «Sabemos que para usted lo primordial es que el tratamiento **{argumento_ndn}**. ¿Cómo han respondido sus pacientes más recientes con nuestro esquema?»
3. **Conexión Inmediata P1 -> P2 -> P3:**
   > «Así como **{prod1}** le responde sin fallas, hoy tenemos stock garantizado de **{prod2}** y **{prod3}** en **{farmacia_top1}** para respaldar sus esquemas integrales en **{especialidad}**.»
4. **Cierre de Compromiso Dual:**
   > «Cuente con mi gestión personal en las farmacias de {ciudad} para cuidar cada receta suya de **{prod1}**, y acompáñeme esta semana evaluando **{prod2}** en sus próximos casos. ¿Le parece bien?»"""
    elif modo_tac == "EXPANSION":
        if v_idx == 0:
            return f"""#### Guion Táctico TVP — Expansión de Cuota ({enfoque_ndn_titulo})
1. **Apertura de Seguimiento Clínico ({tipo_cita_sel}):**
   > «{intro_contexto} Quiero agradecerle los pacientes que ya está tratando con **{prod1}** ({m_primario['gutis_mes']} en el mes / {m_primario['gutis_ytd']} en el año) y proponerle revisar cómo consolidar la adherencia en **{paciente_meta.lower()}**. ¿Le parece bien?»
2. **Sondeo de Valor Mutuo (Aislar el Segmento que Comparte con `{rival_marca}`):**
   > «Al **comparar** la evolución de sus pacientes tratados con **{prod1}** frente a los casos donde aún indica **{rival_completo}** ({m_primario['comp_mes']} recetas en el mes), ¿en qué perfil específico siente que todavía alterna con esa opción y {pregunta_ndn}»
3. **Apoyo Galénico Diferencial y Love Brand:**
   > «Comprendo su criterio, Doctor(a) {nom_corto}. Justamente para cubrir también a ese subgrupo de **{meta1['nicho_flanqueo']}**, **{prod1}** cuenta con **{meta1['caracteristica']}**, con lo cual **{argumento_ndn}**. *{meta1['love_brand']}*»
4. **Cierre de Migración y Puente hacia `{prod2}`:**
   > «Ya que conoce de primera mano la respuesta de **{prod1}**, ¿migramos esta semana a esos próximos 4 a 6 pacientes que antes alternaba con **{rival_marca}**, con disponibilidad garantizada en **{top_farmacias_str}**? Y como puente clínico, recuerde que cuenta también con **{prod2}** y **{prod3}**.»"""
        else:
            return f"""#### Variante Táctica II (Cierre de Brecha Competitiva frente a {rival_marca})
1. **Apertura Focalizada en Resultados:**
   > «{intro_contexto} Revisando la evolución de sus pacientes en **{especialidad}**, vemos una excelente respuesta en los casos donde ya prescribe **{prod1}**.»
2. **Pregunta de Descubrimiento de Brecha:**
   > «Noté que en *{m_primario['clase_terapeutica']}* todavía hay un grupo de pacientes donde se utiliza **{rival_marca}** en {rival_forma.lower()}. Al **evaluar** ambos esquemas, ¿qué factor le daría total seguridad para unificar toda su categoría en **{prod1}**?»
3. **Demostración de Superioridad Galénica:**
   > «Frente a las presentaciones convencionales, **{prod1}** le asegura **{meta1['caracteristica']}**, lo que significa que **{argumento_ndn}**.»
4. **Cierre de Unificación + Puente a `{prod2}`:**
   > «Unifiquemos sus próximos 5 casos de esta semana bajo **{prod1}** apoyándonos en **{farmacia_top1}**, e incorporemos **{prod2}** donde requiera **{benef2}**. ¿Arrancamos hoy?»"""
    else:
        if v_idx == 0:
            return f"""#### Guion Táctico TVP — Conquista y Flanqueo ({enfoque_ndn_titulo})
1. **Apertura Centrada en el Paciente ({tipo_cita_sel} — Sin mencionar marca):**
   > «{intro_contexto} Quería proponerle analizar brevemente cómo optimizar la rapidez de respuesta y eliminar el abandono terapéutico en **{paciente_meta.lower()}**. ¿Le parece bien revisarlo?»
2. **Sondeo del Embudo frente a `{rival_marca}` (Unidad 4 TVP):**
   > «Actualmente en estos cuadros donde suele prescribirse **{rival_completo}** ({m_primario['comp_mes']} Pxs Mes / {m_primario['comp_ytd']} YTD), al **evaluar** la evolución en las primeras 48 horas, {pregunta_ndn}»
3. **Apoyo Galénico y Storytelling de Marca (Unidad 5 TVP):**
   > «Coincido plenamente con su prioridad, Doctor(a) {nom_corto}. Por ello en Gutis desarrollamos **{prod1}**, que aporta **{meta1['caracteristica']}**, logrando que **{argumento_ndn}**. *{meta1['love_brand']}* ¿No es este el estándar clínico que busca para sus pacientes?»
4. **Cierre de Prueba Inicial y Puente hacia `{prod2}` (Unidad 6 TVP):**
   > «Cuando reciba esta semana a sus próximos 3 a 5 pacientes con este cuadro (especialmente en **{meta1['nicho_flanqueo']}**), ¿iniciamos el período de prueba con **{prod1}** mientras yo le garantizo el stock en **{top_farmacias_str}**? Y conectando con su consulta de **{especialidad}**, cuente también con **{prod2}** y **{prod3}**.»"""
        else:
            return f"""#### Variante Táctica II (Técnica de Flanqueo por Nicho Clínico sin Fricción — Unidad 7 TVP)
1. **Apertura de Desarme Psicológico:**
   > «{intro_contexto} Conozco su experiencia manejando *{m_primario['clase_terapeutica']}* y mi intención hoy no es pedirle que cambie de golpe el esquema general que utiliza con **{rival_marca}**.»
2. **Pregunta de Grieta Clínica (Nicho Específico):**
   > «Solo quiero consultarle por un subgrupo puntual: cuando le llega ese paciente de **{meta1['nicho_flanqueo']}**, ¿cómo asegura que el paciente no rechace ni abandone la {rival_forma.lower()}?»
3. **Presentación de Solución Focalizada (`{prod1}`):**
   > «Para ese nicho exacto de pacientes, **{prod1}** ofrece **{meta1['caracteristica']}**, con lo cual **{argumento_ndn}**.»
4. **Cierre de Rescate (2 a 3 Pacientes) + Puente (`{prod2}`):**
   > «Ponga a prueba a **{prod1}** únicamente en sus próximos **3 pacientes de ese perfil específico**, con abastecimiento listo en **{farmacia_top1}**, y evalúe a la par la respuesta de **{prod2}**. ¿Lo ponemos a prueba esta semana?»"""


def generar_consultoria_cognitiva_chira_medico(
    bundle: Any,
    nombre_med: str,
    pregunta_usr: str
) -> str:
    t_norm = normalizar_txt(pregunta_usr)
    nom_natural = formatear_nombre_medico(nombre_med)
    df_panel = bundle.panel
    df_productos = bundle.productos
    df_ventas = bundle.ventas

    fila_p = df_panel[df_panel["Médico"] == nombre_med] if not df_panel.empty else pd.DataFrame()
    esp_m = str(fila_p.iloc[0].get("Especialidad", "ESPECIALISTA")).upper() if not fila_p.empty else "ESPECIALISTA"
    ciu_m = str(fila_p.iloc[0].get("CIUDAD", "NICARAGUA")).upper() if not fila_p.empty else "NICARAGUA"
    cat_m = str(fila_p.iloc[0].get("CATEGORIA", "S/C")) if not fila_p.empty else "FUERA DE PANEL"
    es_ped_m = "PEDIAT" in esp_m

    rx_m = df_productos[(df_productos["Médico"] == nombre_med) & (df_productos["Clave_Gutis"].notna())].copy() if not df_productos.empty else pd.DataFrame()
    if es_ped_m and not rx_m.empty:
        claves_ped = {k for k, v in MERCADOS_PRIORITARIOS.items() if v.get("apto_pediatria", True)}
        rx_m = rx_m[rx_m["Clave_Gutis"].isin(claves_ped)].copy()

    tot_mes = int(rx_m["Pxs-MES"].sum()) if not rx_m.empty else 0
    tot_ytd = int(rx_m["Pxs-YTD"].sum()) if not rx_m.empty else 0
    gut_mes = int(rx_m[rx_m["Es_Gutis"]]["Pxs-MES"].sum()) if tot_mes > 0 else 0
    gut_ytd = int(rx_m[rx_m["Es_Gutis"]]["Pxs-YTD"].sum()) if tot_ytd > 0 else 0
    comp_mes, comp_ytd = tot_mes - gut_mes, tot_ytd - gut_ytd
    ms_global_m = (gut_mes / tot_mes * 100.0) if tot_mes > 0 else ((gut_ytd / tot_ytd * 100.0) if tot_ytd > 0 else 0.0)

    mercados_doc = []
    if not rx_m.empty:
        for k_g, grp in rx_m.groupby("Clave_Gutis"):
            meta = MERCADOS_PRIORITARIOS.get(k_g, {})
            pm = int(grp["Pxs-MES"].sum())
            py = int(grp["Pxs-YTD"].sum())
            if pm <= 0 and py <= 0:
                continue
            gm = int(grp[grp["Es_Gutis"]]["Pxs-MES"].sum())
            gy = int(grp[grp["Es_Gutis"]]["Pxs-YTD"].sum())
            cm, cy = pm - gm, py - gy
            msm = (gm / pm * 100.0) if pm > 0 else 0.0
            msy = (gy / py * 100.0) if py > 0 else 0.0
            grp_ord = grp.sort_values(by=["Pxs-MES", "Pxs-YTD"], ascending=False)
            grp_riv = grp_ord[~grp_ord["Es_Gutis"]]
            riv_sku = str(grp_riv.iloc[0]["NOMBRE_PRODUCTO"]) if not grp_riv.empty else "Sin competidor activo"
            riv_m = int(grp_riv.iloc[0]["Pxs-MES"]) if not grp_riv.empty else 0
            riv_y = int(grp_riv.iloc[0]["Pxs-YTD"]) if not grp_riv.empty else 0
            scale_info = diagnosticar_escala_adopcion(gm, pm, msm, gy, py, msy)
            mercados_doc.append({
                "clave": k_g, "prod_gutis": meta.get("producto", k_g), "clase": meta.get("clase_terapeutica", ""),
                "prio": meta.get("prioridad", 3), "pm": pm, "py": py, "gm": gm, "gy": gy, "cm": cm, "cy": cy,
                "msm": msm, "msy": msy, "riv_sku": riv_sku, "riv_m": riv_m, "riv_y": riv_y,
                "escala": scale_info["nivel"], "modo": scale_info["modo"], "meta": meta
            })
        mercados_doc.sort(key=lambda x: (-x["pm"], -x["py"], x["prio"]))

    df_labs_m = radar_laboratorios(bundle.laboratorios, bundle.panel, medico=nombre_med)
    labs_resumen = " | ".join([
        f"**#{i+1} {r['Laboratorio']}** ({r['Pxs Mes']} Mes [{r['% MS Mes']:.1f}%] / {r['Pxs YTD']} YTD [{r['% MS YTD']:.1f}%])"
        for i, (_, r) in enumerate(df_labs_m.head(5).iterrows())
    ]) if not df_labs_m.empty else "Sin desglose de fabricantes."

    sell_info = resumen_ventas_ciudad(df_ventas, ciu_m)
    farmacias_z = sell_info["top_farmacias"]

    if mercados_doc:
        m1 = mercados_doc[0]
        cands_p = [m for m in mercados_doc if m["prod_gutis"] != m1["prod_gutis"] and (m["cm"] > 0 or m["cy"] > 0)]
        m2 = cands_p[0] if cands_p else (mercados_doc[1] if len(mercados_doc) > 1 else None)
    else:
        k_fb = "MR TALERDIN" if es_ped_m else "MR GASTROALIVIO"
        meta_fb = MERCADOS_PRIORITARIOS[k_fb]
        m1 = {
            "clave": k_fb, "prod_gutis": meta_fb["producto"], "clase": meta_fb["clase_terapeutica"],
            "prio": 1, "pm": 0, "py": 0, "gm": 0, "gy": 0, "cm": 0, "cy": 0, "msm": 0.0, "msy": 0.0,
            "riv_sku": "Competencia", "riv_m": 0, "riv_y": 0, "escala": "2. Consciente", "modo": "CONQUISTA", "meta": meta_fb
        }
        m2 = None

    prod1, meta1 = m1["prod_gutis"], m1["meta"]
    riv1_marca, riv1_forma, riv1_comp = limpiar_sku_competencia(m1["riv_sku"])
    prod2 = m2["prod_gutis"] if m2 else ("Biotos Inmune / Clembroxil Compuesto" if es_ped_m else "Conflexil Plus Shot / Dalivio")

    lineas_mercados = "\n".join([
        f"* **{m['prod_gutis']}** (*{m['clase']}* — `{m['escala']}`): Mes `{m['pm']} Pxs` (Gutis: `{m['gm']}` [{m['msm']:.1f}%] vs. Rival `{m['riv_sku']}`: `{m['riv_m']}`) | YTD: `{m['py']} Pxs` (Gutis: `{m['gy']}` [{m['msy']:.1f}%] vs. Comp: `{m['cy']}`)."
        for m in mercados_doc[:6]
    ]) if mercados_doc else "* _Sin prescripciones registradas en el corte actual._"

    es_dilucion = any(k in t_norm for k in ["COMPART", "DILUY", "DIVID", "CON NOSOTROS", "FUGA", "POR QUE RECETA OTROS", "QUE PASA"])
    es_comprado = any(k in t_norm for k in ["COMPRAD", "AMARRAD", "CASAD", "FIDELIZAD", "NO SUELTA"]) and not es_dilucion
    # CORREGIDO: Se reescribe la gestión de ROI/Patrocinios para cumplir con Códigos de Ética IFPMA
    es_pedido_roi = any(k in t_norm for k in ["PIDE", "PEDIR", "PIDIO", "A CAMBIO", "CONGRESO", "INSCRIPCION", "APOYO", "PATROCINIO"])

    if es_dilucion:
        bloque_tactico = f"""#### Diagnóstico de Dilución de Receta y Abordaje TVP:
1. **Lectura del Comportamiento Prescriptivo:** El/La Dr(a). {nom_natural} genera `{tot_mes} Pxs Mes` (`{tot_ytd} YTD`), entregando a Gutis `{gut_mes} Pxs Mes` (**{ms_global_m:.1f}% MS**) mientras `{comp_mes} Pxs Mes` (`{comp_ytd} YTD`) se desvían hacia marcas competidoras.
2. **Apertura de Reconocimiento (Sin reclamar):**
   > «Doctor(a) {nom_natural}, gracias por su respaldo constante a nuestro portafolio en {ciu_m}; gracias a su confianza decenas de pacientes reciben esquemas de alta pureza.»
3. **Sondeo Sutil para Aislar el Nicho Compartido:**
   > «Dando seguimiento a la respuesta que ha tenido con **{prod1}**, noté que en un grupo de pacientes aún alterna el esquema con **{riv1_comp}**. Al **comparar** ambos perfiles en su consulta de **{esp_m}**, ¿en qué cuadro específico siente que prefiere usar la otra opción?»
4. **Cierre de Consolidación hacia Lealtad:**
   > «Conociendo de primera mano que **{prod1}** aporta **{meta1['caracteristica'].lower()}**, consolidemos también ese grupo de pacientes bajo un solo estándar de calidad con inventario garantizado en **{farmacias_z}**.»"""
    elif es_comprado:
        bloque_tactico = f"""#### Estrategia de Flanqueo por Nicho Clínico (Médico Fidelizado con Competencia):
1. **Desarme Psicológico (Unidad 7 TVP):**
   > «Doctor(a) {nom_natural}, conozco su experiencia con su esquema habitual de **{riv1_marca}** y mi intención hoy no es pedirle que cambie lo que ya utiliza en su paciente general.»
2. **Pregunta de Grieta Clínica:**
   > «Solo quiero consultarle por un subgrupo específico: cuando recibe a **{meta1['nicho_flanqueo']}**, ¿cómo asegura que el paciente no rechace ni abandone la {riv1_forma.lower()}?»
3. **Cierre de Rescate (2 a 3 Pacientes) + Puente (`{prod2}`):**
   > «Para esos casos puntuales apóyese en **{prod1}** (*{meta1['caracteristica'].lower()}*) en sus próximos **3 pacientes de rescate**, y cuente también con **{prod2}** respaldado en **{farmacias_z}**.»"""
    elif es_pedido_roi:
        bloque_tactico = f"""#### Gestión Ética de Apoyo y Educación Médica Continua (Compliance):
1. **Auditoría de Prescripción Actual:** Volumen total: `{tot_mes} Pxs Mes` | Cuota Gutis: `{gut_mes} Pxs ({ms_global_m:.1f}%)`.
2. **Guion de Valor Científico (Cero Condicionamiento de Recetas):**
   > «Doctor(a) {nom_natural}, su práctica en {ciu_m} es fundamental para nosotros. Nuestro compromiso con la educación médica continua es apoyarlo en su actualización científica, respetando siempre su criterio clínico y sin condicionamientos. Aprovecho para actualizarle sobre **{prod1}** y garantizarle que sus pacientes encontrarán el tratamiento completo en **{farmacias_z}** cuando usted decida prescribirlo.»"""
    else:
        bloque_tactico = construir_guion_tvp_dinamico(
            nombre_med, esp_m, ciu_m,
            {
                "prod_gutis": prod1, "clase_terapeutica": m1["clase"], "modo_tactico": m1["modo"],
                "gutis_mes": m1["gm"], "gutis_ytd": m1["gy"], "comp_mes": m1["cm"], "comp_ytd": m1["cy"],
                "ms_mes": m1["msm"], "rival_principal": m1["riv_sku"], "meta_info": meta1
            },
            prod2, m2["meta"]["beneficio"] if m2 else "eficacia comprobada",
            m2["riv_sku"] if m2 else "la competencia", "Ventilar / Mometzona" if es_ped_m else "Valerpan / Renovart Platinum",
            "Visita con cita previa", "Desempeño (Eficacia y adherencia clínica)", farmacias_z, 0,
            notas_rapport="" # Se omite rapport personal en el prompt IA
        )

    return f"""### Expediente Estratégico y Plan TVP: Dr(a). {nombre_med}
**Especialidad:** `{esp_m}` | **Categoría:** `{cat_m}` | **Ciudad:** `{ciu_m}` | **Volumen Auditado:** `{tot_mes} Pxs Mes` (`{tot_ytd} YTD`) — **Gutis:** `{gut_mes} Mes / {gut_ytd} YTD ({ms_global_m:.1f}% MS)` | **Competencia:** `{comp_mes} Mes / {comp_ytd} YTD`

#### 1. Radiografía por Clase Terapéutica (Vademécum Nicaragua 2026):
{lineas_mercados}

#### 2. Ranking de Laboratorios en su Recetario (Mes vs. YTD):
- {labs_resumen}
- **Farmacias Aliadas en {ciu_m}:** {farmacias_z}

{bloque_tactico}
"""

def generar_analisis_mercado_chira_rico(df_rk_q: pd.DataFrame, mer_q: Optional[str], ciu_q: Optional[str], nota_expansion: str = "") -> str:
    z_lbl = ciu_q or "TODO MI PANEL"
    if mer_q and mer_q in MERCADOS_PRIORITARIOS:
        meta_m = MERCADOS_PRIORITARIOS[mer_q]
        m_lbl = f"{meta_m['producto']} — {meta_m['clase_terapeutica']}"
        marca_foco = meta_m["producto"]
    else:
        m_lbl = mer_q or "Portafolio Oficial Gutis Nicaragua"
        marca_foco = "Portafolio Gutis"

    tot_m_zona = int(df_rk_q["Pxs Mes"].sum())
    gut_m_zona = int(df_rk_q["Gutis Mes"].sum())
    comp_m_zona = int(df_rk_q["Comp Mes"].sum())
    ms_m_zona = (gut_m_zona / tot_m_zona * 100.0) if tot_m_zona > 0 else 0.0

    tot_y_zona = int(df_rk_q["Pxs YTD"].sum())
    gut_y_zona = int(df_rk_q["Gutis YTD"].sum())
    comp_y_zona = int(df_rk_q["Comp YTD"].sum())
    ms_y_zona = (gut_y_zona / tot_y_zona * 100.0) if tot_y_zona > 0 else 0.0

    meds_leales_mes = df_rk_q[df_rk_q["% MS Mes"] >= 50.0]
    if not meds_leales_mes.empty:
        txt_leales = ", ".join([
            f"**Dr(a). {formatear_nombre_medico(r['Médico'])}** ({r['Gutis Mes']} Mes / {r['Gutis YTD']} YTD — {r['% MS Mes']:.0f}% MS Mes)"
            for _, r in meds_leales_mes.head(3).iterrows()
        ])
    else:
        meds_leales_ytd = df_rk_q[df_rk_q["% MS YTD"] >= 50.0]
        if not meds_leales_ytd.empty:
            txt_leales = ", ".join([
                f"**Dr(a). {formatear_nombre_medico(r['Médico'])}** ({r['Gutis YTD']} YTD — {r['% MS YTD']:.0f}% MS YTD [Consistencia Anual])"
                for _, r in meds_leales_ytd.head(3).iterrows()
            ])
        else:
            txt_leales = "Sin médicos en escalón de Lealtad (>=50% MS) en este corte; prioridad total en Conquista y Expansión."

    meds_conquista = df_rk_q.sort_values(by=["Comp Mes", "Comp YTD"], ascending=[False, False])
    txt_conquista = "\n".join([
        f"  - **Dr(a). {formatear_nombre_medico(r['Médico'])}** ({r['Especialidad']} | Cat {r['Cat']}): Entrega **{r['Comp Mes']} Pxs Mes** (`{r['Comp YTD']} YTD`) a la competencia -> Rival #1: `{r['Rival Principal en la Clase']}`."
        for _, r in meds_conquista.head(4).iterrows() if (r["Comp Mes"] > 0 or r["Comp YTD"] > 0)
    ]) or "  - _Todo el volumen auditado ya pertenece a Gutis._"

    cols_v = ["Médico", "Estatus Panel", "Especialidad", "Cat", "Ciudad", "Pxs Mes", "Gutis Mes", "Comp Mes", "% MS Mes", "Pxs YTD", "% MS YTD", "Escala TVP", "Desglose Marcas [Mes/YTD]"]
    cols_v_exist = [c for c in cols_v if c in df_rk_q.columns]
    df_vista_q = df_rk_q.head(12)[cols_v_exist]
    md_rk = df_a_markdown_nativo(df_vista_q)

    return f"""### Auditoría Estratégica de Mercado | {m_lbl} — Territorio: {z_lbl}
{nota_expansion}**Volumen Categoría Mes:** `{tot_m_zona} Pxs` (Gutis: `{gut_m_zona}` [**{ms_m_zona:.1f}% MS**] | Competencia: `{comp_m_zona} Pxs`)  
**Volumen Categoría YTD:** `{tot_y_zona} Pxs` (Gutis: `{gut_y_zona}` [**{ms_y_zona:.1f}% MS**] | Competencia: `{comp_y_zona} Pxs`)

{md_rk}

#### Plan de Acción Táctico en {z_lbl} para {marca_foco}:
1. **Socios Leales a Blindar y Apalancar con Puente (>50% MS):** {txt_leales}
2. **Objetivos Prioritarios de Conquista y Migración:**
{txt_conquista}
3. **Directriz de Ejecución en Campo:** En los médicos de **Lealtad**, agradece su respaldo sin vender de cero y construye el puente hacia una segunda línea. En los médicos de **Conquista/Expansión**, aplica flanqueo directo sobre la presentación del rival principal asegurando disponibilidad previa en las farmacias líderes de {z_lbl}.
"""
