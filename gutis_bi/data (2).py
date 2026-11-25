"""
Cargador de Datos Robusto y Normalización Close-Up + Sell-Out Mensual para Gutis BI.
- Pondera Auditoría Close-Up por (VISITADOR, MARCA) sin mezclar otros visitadores.
- Detecta automáticamente el Excel mensual inspeccionando sus hojas reales (datos 2026.xlsx).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from gutis_bi.catalog import MERCADOS_PRIORITARIOS, PATRON_REGEX_GUTIS

TABLA_SIN_ACENTOS = str.maketrans("ÁÉÍÓÚÜÀÈÌÒÙÂÊÎÔÛáéíóúüàèìòùâêîôû", "AEIOUUAEIOUAEIOUaeiouuaeiouaeiou")

ORDEN_MESES_ES = {
    "ENERO": (1, "Ene"),
    "FEBRERO": (2, "Feb"),
    "MARZO": (3, "Mar"),
    "ABRIL": (4, "Abr"),
    "MAYO": (5, "May"),
    "JUNIO": (6, "Jun"),
    "JULIO": (7, "Jul"),
    "AGOSTO": (8, "Ago"),
    "SEPTIEMBRE": (9, "Sep"),
    "SETIEMBRE": (9, "Sep"),
    "OCTUBRE": (10, "Oct"),
    "NOVIEMBRE": (11, "Nov"),
    "DICIEMBRE": (12, "Dic"),
}


def normalizar_txt(texto: Any) -> str:
    if pd.isna(texto) or texto is None:
        return ""
    return str(texto).strip().upper().translate(TABLA_SIN_ACENTOS)


def normalizar_serie_rapida(serie: pd.Series) -> pd.Series:
    return serie.fillna("").astype(str).str.strip().str.upper().str.translate(TABLA_SIN_ACENTOS)


def _limpiar_numero_serie(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(
        serie.astype(str).str.replace("$", "", regex=False).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    ).fillna(0.0)


def _parsear_hoja_mensual(nombre_hoja: str) -> Optional[Tuple[int, str, str]]:
    h_norm = normalizar_txt(nombre_hoja)
    anio_match = re.search(r"(20\d{2})", h_norm)
    anio = int(anio_match.group(1)) if anio_match else 2026
    for mes_nom, (mes_num, mes_abrev) in ORDEN_MESES_ES.items():
        if mes_nom in h_norm:
            clave_ord = anio * 100 + mes_num
            etiqueta = f"{mes_abrev} {str(anio)[-2:]}"
            q_eq = "Q1" if mes_num <= 3 else ("Q2" if mes_num <= 6 else ("Q3" if mes_num <= 9 else "Q4"))
            return clave_ord, etiqueta, q_eq
    return None


def _buscar_excel_mensual_por_hojas(data_dir: Path) -> Optional[Tuple[Path, List[Tuple[str, int, str, str]]]]:
    if not data_dir.exists():
        return None
    mejor: Optional[Tuple[int, Path, List[Tuple[str, int, str, str]]]] = None
    for p_cand in sorted(data_dir.iterdir()):
        if p_cand.suffix.lower() not in (".xlsx", ".xls") or p_cand.name.startswith("~$"):
            continue
        try:
            xl_test = pd.ExcelFile(p_cand)
            hojas_validas: List[Tuple[str, int, str, str]] = []
            for s_name in xl_test.sheet_names:
                info = _parsear_hoja_mensual(s_name)
                if info is not None:
                    hojas_validas.append((s_name, info[0], info[1], info[2]))
            if len(hojas_validas) >= 2:
                if mejor is None or len(hojas_validas) > mejor[0]:
                    mejor = (len(hojas_validas), p_cand, hojas_validas)
        except Exception:
            continue
    if mejor is not None:
        return mejor[1], sorted(mejor[2], key=lambda x: x[1])
    return None


def resolver_clave_mercado_gutis(texto_mercado_o_clase: str, nombre_prod: str = "") -> Optional[str]:
    t_norm = normalizar_txt(f"{texto_mercado_o_clase} {nombre_prod}")
    if not t_norm or t_norm in ("TOTAL", "NAN", "NONE"):
        return None
    if any(ex in t_norm for ex in ["VALVIREX", "PRIMABELA", "BELEZA", "GESIMAX", "FLUKIT", "ZITRO"]):
        return None
    for m_key, m_info in MERCADOS_PRIORITARIOS.items():
        if any(normalizar_txt(term) in t_norm for term in m_info["terminos_busqueda"]):
            return m_key
    return None


def encontrar_archivo_en_dir(
    data_dir: Path,
    palabras_obligatorias: List[str],
    palabras_preferidas: Optional[List[str]] = None,
) -> Optional[Path]:
    if not data_dir.exists():
        return None
    archivos = [p for p in data_dir.iterdir() if p.suffix.lower() in [".xlsx", ".xls"] and not p.name.startswith("~$")]
    candidatos = []
    for p in archivos:
        p_norm = normalizar_txt(p.name)
        if all(normalizar_txt(k) in p_norm for k in palabras_obligatorias):
            score = sum(10 for pref in (palabras_preferidas or []) if normalizar_txt(pref) in p_norm)
            candidatos.append((score, p))
    if candidatos:
        candidatos.sort(key=lambda x: (-x[0], x[1].name))
        return candidatos[0][1]
    return None


@dataclass
class DataBundle:
    panel: pd.DataFrame = field(default_factory=pd.DataFrame)
    productos: pd.DataFrame = field(default_factory=pd.DataFrame)
    laboratorios: pd.DataFrame = field(default_factory=pd.DataFrame)
    clases: pd.DataFrame = field(default_factory=pd.DataFrame)
    auditoria: pd.DataFrame = field(default_factory=pd.DataFrame)
    auditoria_totales: pd.DataFrame = field(default_factory=pd.DataFrame)
    ventas: pd.DataFrame = field(default_factory=pd.DataFrame)
    archivos: Dict[str, str] = field(default_factory=dict)
    avisos: List[str] = field(default_factory=list)


@st.cache_data(show_spinner=False)
def load_data(data_dir_str: str, _schema_ver: str = "v5_visitador_mensual") -> DataBundle:
    data_dir = Path(data_dir_str)
    bundle = DataBundle()

    # 1. Panel
    f_panel = encontrar_archivo_en_dir(data_dir, ["PANEL"])
    if f_panel:
        bundle.panel = pd.read_excel(f_panel)
        bundle.panel.columns = bundle.panel.columns.astype(str).str.strip()
        bundle.archivos["Panel"] = f_panel.name
        if "Médico" in bundle.panel.columns:
            bundle.panel["Médico"] = bundle.panel["Médico"].astype(str).str.strip().str.upper()
        for col in ["CIUDAD", "Especialidad"]:
            if col in bundle.panel.columns:
                bundle.panel[col] = bundle.panel[col].astype(str).str.strip().str.upper()
    else:
        bundle.avisos.append("No se encontró el archivo de PANEL.")

    mapa_ciu, mapa_esp, mapa_cat = {}, {}, {}
    if not bundle.panel.empty and "Médico" in bundle.panel.columns:
        p_unico = bundle.panel.drop_duplicates(subset=["Médico"]).set_index("Médico")
        mapa_ciu = p_unico["CIUDAD"].to_dict() if "CIUDAD" in p_unico.columns else {}
        mapa_esp = p_unico["Especialidad"].to_dict() if "Especialidad" in p_unico.columns else {}
        mapa_cat = p_unico["CATEGORIA"].astype(str).to_dict() if "CATEGORIA" in p_unico.columns else {}

    # 2. Clases Terapéuticas (Mapeo)
    f_clases = encontrar_archivo_en_dir(data_dir, ["CLASES", "TERAPEUTICAS"])
    mapa_ct = {}
    if f_clases:
        bundle.clases = pd.read_excel(f_clases)
        bundle.clases.columns = bundle.clases.columns.astype(str).str.strip()
        bundle.archivos["Clases"] = f_clases.name
        col_prod_ct = next((c for c in bundle.clases.columns if "PRODUCTO" in normalizar_txt(c) or "MARCA" in normalizar_txt(c)), None)
        col_clase_ct = next((c for c in bundle.clases.columns if any(k in normalizar_txt(c) for k in ["CLASE", "TERAPEUTICA", "ATC", "MERCADO"])), None)
        if col_prod_ct and col_clase_ct:
            df_ct_clean = bundle.clases.dropna(subset=[col_prod_ct, col_clase_ct]).copy()
            df_ct_clean["_KEY"] = df_ct_clean[col_prod_ct].astype(str).str.strip().str.upper()
            df_ct_clean = df_ct_clean.drop_duplicates(subset=["_KEY"])
            mapa_ct = df_ct_clean.set_index("_KEY")[col_clase_ct].to_dict()

    # 3. Productos Close-Up
    f_rx = encontrar_archivo_en_dir(data_dir, ["PRODUCTOS"])
    mapa_marca_a_mercado = {}
    if f_rx:
        bundle.productos = pd.read_excel(f_rx)
        bundle.productos.columns = bundle.productos.columns.astype(str).str.strip()
        bundle.archivos["Productos"] = f_rx.name
        if "Médico" in bundle.productos.columns:
            bundle.productos["Médico"] = bundle.productos["Médico"].astype(str).str.strip().str.upper()
        if "NOMBRE_PRODUCTO" in bundle.productos.columns:
            bundle.productos = bundle.productos.dropna(subset=["NOMBRE_PRODUCTO"]).copy()
            bundle.productos["NOMBRE_PRODUCTO"] = bundle.productos["NOMBRE_PRODUCTO"].astype(str).str.strip()
            bundle.productos = bundle.productos[~bundle.productos["NOMBRE_PRODUCTO"].str.upper().isin(["TOTAL", "NAN", "NONE", ""])].copy()

        for c in ["Pxs-MES", "Pxs-YTD", "Pxs-TRIM", "Pxs-LY"]:
            if c in bundle.productos.columns:
                bundle.productos[c] = pd.to_numeric(bundle.productos[c], errors="coerce").fillna(0)

        bundle.productos["CLASE_TERAPEUTICA_ARCHIVO"] = bundle.productos["NOMBRE_PRODUCTO"].str.upper().map(mapa_ct).fillna("")

        col_fab = next((c for c in bundle.productos.columns if "FABRICANTE" in c.upper() or "LAB" in c.upper()), None)
        prod_norm_s = normalizar_serie_rapida(bundle.productos["NOMBRE_PRODUCTO"])
        es_gutis_mask = prod_norm_s.str.contains(PATRON_REGEX_GUTIS, na=False)
        if col_fab:
            es_gutis_mask = es_gutis_mask | normalizar_serie_rapida(bundle.productos[col_fab]).str.contains("GUTIS", na=False)
        bundle.productos["Es_Gutis"] = es_gutis_mask.fillna(False).astype(bool)

        bundle.productos["_clave_combo"] = (
            bundle.productos.get("MERCADO", "").fillna("").astype(str)
            + " || "
            + bundle.productos["CLASE_TERAPEUTICA_ARCHIVO"]
            + " || "
            + bundle.productos["NOMBRE_PRODUCTO"]
        )
        mapa_combo = {}
        for combo in bundle.productos["_clave_combo"].unique():
            partes = combo.split(" || ")
            m_txt = f"{partes[0]} {partes[1]}" if len(partes) > 1 else partes[0]
            p_txt = partes[2] if len(partes) > 2 else ""
            k_m = resolver_clave_mercado_gutis(m_txt, "") or resolver_clave_mercado_gutis(m_txt, p_txt)
            mapa_combo[combo] = k_m
        bundle.productos["Clave_Gutis"] = bundle.productos["_clave_combo"].map(mapa_combo)
        bundle.productos = bundle.productos.drop(columns=["_clave_combo"])

        bundle.productos["CIUDAD_PANEL"] = bundle.productos["Médico"].map(mapa_ciu).fillna("FUERA DE PANEL")
        bundle.productos["ESP_PANEL"] = bundle.productos["Médico"].map(mapa_esp).fillna("ESPECIALISTA")
        bundle.productos["CAT_PANEL"] = bundle.productos["Médico"].map(mapa_cat).fillna("S/C")

        temp_marcas = bundle.productos[["NOMBRE_PRODUCTO", "MERCADO", "Clave_Gutis"]].copy()
        temp_marcas["_marca_base"] = temp_marcas["NOMBRE_PRODUCTO"].str.split("-").str[0].str.strip().str.upper()
        for row in temp_marcas[["_marca_base", "MERCADO", "Clave_Gutis"]].drop_duplicates(subset=["_marca_base"]).to_dict("records"):
            mapa_marca_a_mercado[row["_marca_base"]] = (row["MERCADO"], row["Clave_Gutis"])

    # 4. Laboratorios
    f_labs = encontrar_archivo_en_dir(data_dir, ["LABORATORIOS"])
    if f_labs:
        bundle.laboratorios = pd.read_excel(f_labs)
        bundle.laboratorios.columns = bundle.laboratorios.columns.astype(str).str.strip()
        bundle.archivos["Laboratorios"] = f_labs.name
        if "Médico" in bundle.laboratorios.columns:
            bundle.laboratorios["Médico"] = bundle.laboratorios["Médico"].astype(str).str.strip().str.upper()
        for c in ["Pxs-MES", "Pxs-YTD", "Pxs-TRIM", "Pxs-LY"]:
            if c in bundle.laboratorios.columns:
                bundle.laboratorios[c] = pd.to_numeric(bundle.laboratorios[c], errors="coerce").fillna(0)

    # 5. Auditoría Close-Up (dedup por VISITADOR + MARCA)
    f_aud = encontrar_archivo_en_dir(data_dir, ["CLASES", "AUDITORIA"]) or encontrar_archivo_en_dir(data_dir, ["AUDITORIA"])
    if f_aud:
        df_aud_raw = pd.read_excel(f_aud)
        df_aud_raw.columns = df_aud_raw.columns.astype(str).str.strip()
        bundle.archivos["Auditoría"] = f_aud.name
        if "MARCA" in df_aud_raw.columns and "MEDICO_ESPECIALIDAD" in df_aud_raw.columns:
            cols_ms = ["% MS - LY", "% MS - Ytd", "Dif %", "% MS - TrasAnt", "% MS - Ant", "% MS - Mes"]
            for c in cols_ms:
                if c in df_aud_raw.columns:
                    df_aud_raw[c] = pd.to_numeric(df_aud_raw[c], errors="coerce").fillna(0.0)

            df_aud_raw["MARCA"] = df_aud_raw["MARCA"].astype(str).str.strip().str.upper()
            _cols_dedup = ["VISITADOR", "MARCA"] if "VISITADOR" in df_aud_raw.columns else ["MARCA"]
            bundle.auditoria_totales = (
                df_aud_raw[df_aud_raw["MEDICO_ESPECIALIDAD"].astype(str).str.strip().str.upper() == "TOTAL"]
                .drop_duplicates(subset=_cols_dedup)
                .set_index("MARCA")
            )

            mask_docs = (
                ~df_aud_raw["MARCA"].isin(["TOTAL", "NAN", "NONE", ""])
                & ~df_aud_raw["MEDICO_ESPECIALIDAD"].astype(str).str.strip().str.upper().isin(["TOTAL", "NAN", "NONE", ""])
                & df_aud_raw["MEDICO_ESPECIALIDAD"].notna()
            )
            df_docs = df_aud_raw[mask_docs].copy()
            partes = df_docs["MEDICO_ESPECIALIDAD"].astype(str).str.rsplit(" - ", n=1, expand=True)
            df_docs["Médico"] = partes[0].str.strip().str.upper()
            df_docs["Especialidad"] = partes[1].str.strip().str.upper() if partes.shape[1] > 1 else "ESPECIALISTA"
            df_docs["Laboratorio"] = df_docs["MARCA"].str.split().str[-1]
            df_docs["Zona"] = df_docs["Médico"].map(mapa_ciu).fillna("FUERA DE PANEL")
            df_docs["Categoria_TAM"] = df_docs["Médico"].map(mapa_cat).fillna("FUERA DE PANEL")

            map_m_mer, map_m_clave = {}, {}
            for m_u in df_docs["MARCA"].unique():
                if m_u in mapa_marca_a_mercado:
                    mer_str, k_g = mapa_marca_a_mercado[m_u]
                else:
                    k_g = resolver_clave_mercado_gutis(m_u, m_u)
                    mer_str = k_g if k_g else "OTROS MERCADOS"
                map_m_mer[m_u] = mer_str if mer_str not in ["", "NAN", None] else (k_g or "OTROS MERCADOS")
                map_m_clave[m_u] = k_g
            df_docs["Mercado_BI"] = df_docs["MARCA"].map(map_m_mer)
            df_docs["Clave_Gutis"] = df_docs["MARCA"].map(map_m_clave)

            for c_bi in ["% MS - LY", "% MS - Ytd", "% MS - TrasAnt", "% MS - Ant", "% MS - Mes"]:
                if c_bi in df_docs.columns and c_bi in bundle.auditoria_totales.columns:
                    if "VISITADOR" in bundle.auditoria_totales.columns and "VISITADOR" in df_docs.columns:
                        _tot_key = bundle.auditoria_totales.reset_index().set_index(["VISITADOR", "MARCA"])[c_bi]
                        _idx = pd.MultiIndex.from_frame(df_docs[["VISITADOR", "MARCA"]])
                        p_marca_serie = pd.Series(_tot_key.reindex(_idx).to_numpy(), index=df_docs.index).fillna(0.0)
                    else:
                        p_marca_serie = df_docs["MARCA"].map(bundle.auditoria_totales[c_bi]).fillna(0.0)
                    df_docs["W_" + c_bi] = p_marca_serie * df_docs[c_bi]

            bundle.auditoria = df_docs

    # 6. Ventas / Sell-Out: Detecta por HOJAS REALES el archivo mensual (datos 2026.xlsx)
    dfs_v = []
    hallazgo_mensual = _buscar_excel_mensual_por_hojas(data_dir)
    if hallazgo_mensual is not None:
        f_ventas_mensual, hojas_info = hallazgo_mensual
        try:
            for sheet_m, clave_ord, etiq_mes, q_eq in hojas_info:
                d_m = pd.read_excel(f_ventas_mensual, sheet_name=sheet_m)
                d_m["Mes_Orden"] = clave_ord
                d_m["Mes_Label"] = etiq_mes
                d_m["Trimestre"] = q_eq
                dfs_v.append(d_m)
            if dfs_v:
                bundle.archivos["Ventas Mensual"] = f"{f_ventas_mensual.name} ({len(hojas_info)} meses)"
        except Exception as e:
            bundle.avisos.append(f"Aviso al leer ventas mensuales: {e}")

    if not dfs_v:
        for q_kw, q_lbl in [("PRIMER", "Q1"), ("SEGUNDO", "Q2"), ("TERCER", "Q3")]:
            f_v = encontrar_archivo_en_dir(data_dir, ["VENTA", q_kw]) or encontrar_archivo_en_dir(data_dir, ["VENTAS", q_kw])
            if f_v:
                try:
                    xl = pd.ExcelFile(f_v)
                    sheet_target = "Export" if "Export" in xl.sheet_names else xl.sheet_names[0]
                    d_temp = pd.read_excel(f_v, sheet_name=sheet_target)
                    d_temp["Trimestre"] = q_lbl
                    d_temp["Mes_Orden"] = {"Q1": 202603, "Q2": 202606, "Q3": 202609}[q_lbl]
                    d_temp["Mes_Label"] = q_lbl
                    dfs_v.append(d_temp)
                    bundle.archivos[f"Ventas {q_lbl}"] = f_v.name
                except Exception:
                    pass

    if dfs_v:
        df_v_all = pd.concat(dfs_v, ignore_index=True)
        df_v_all.columns = df_v_all.columns.astype(str).str.strip()

        for col_filt in ["DESCRIPCION_RUTA", "NOMBRE_CLIENTE_1", "VM4"]:
            if col_filt in df_v_all.columns:
                df_v_all = df_v_all[df_v_all[col_filt].notna()].copy()
                s_up = df_v_all[col_filt].astype(str).str.strip().str.upper()
                df_v_all = df_v_all[~s_up.isin(["TOTAL", "NAN", "NONE", ""])].copy()

        for col_num in ["Und Real", "Monto Real", "Und Cuota", "Monto Cuota", "% Real", "Und Negat", "Monto Negat"]:
            if col_num in df_v_all.columns:
                df_v_all[col_num] = _limpiar_numero_serie(df_v_all[col_num])

        if "% Real" in df_v_all.columns:
            df_v_all["% Cumplimiento"] = np.where(
                df_v_all["% Real"].abs() <= 2.5,
                (df_v_all["% Real"] * 100.0).round(1),
                df_v_all["% Real"].round(1),
            )
        elif "Monto Cuota" in df_v_all.columns and "Monto Real" in df_v_all.columns:
            df_v_all["% Cumplimiento"] = np.where(
                df_v_all["Monto Cuota"] > 0,
                (df_v_all["Monto Real"] / df_v_all["Monto Cuota"] * 100.0).round(1),
                0.0,
            )

        if "DESCRIPCION_RUTA" in df_v_all.columns:
            df_v_all["DESCRIPCION_RUTA"] = df_v_all["DESCRIPCION_RUTA"].astype(str).str.strip().str.upper()
        if "NOMBRE_CLIENTE_1" in df_v_all.columns:
            df_v_all["NOMBRE_CLIENTE_1"] = df_v_all["NOMBRE_CLIENTE_1"].astype(str).str.strip().str.upper()

        col_p_v = "VM4" if "VM4" in df_v_all.columns else next((c for c in df_v_all.columns if "PRODUCTO" in c.upper()), None)
        if col_p_v:
            df_v_all["PRODUCTO_VENTA"] = df_v_all[col_p_v].astype(str).str.strip().str.upper()

        bundle.ventas = df_v_all

    return bundle


def clear_data_cache():
    st.cache_data.clear()
