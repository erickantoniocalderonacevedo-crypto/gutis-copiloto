"""
Cargador de Datos Robusto y Normalización Close-Up para Gutis BI.
Corrige desalineación de índices, sanitiza importes y soporta detección automática mensual.
"""

import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
import streamlit as st

from gutis_bi.catalog import MERCADOS_PRIORITARIOS, PATRON_REGEX_GUTIS

TABLA_SIN_ACENTOS = str.maketrans("ÁÉÍÓÚÜÀÈÌÒÙÂÊÎÔÛáéíóúüàèìòùâêîôû", "AEIOUUAEIOUAEIOUaeiouuaeiouaeiou")

def normalizar_txt(texto: Any) -> str:
    if pd.isna(texto) or texto is None:
        return ""
    return str(texto).strip().upper().translate(TABLA_SIN_ACENTOS)

def normalizar_serie_rapida(serie: pd.Series) -> pd.Series:
    return serie.fillna("").astype(str).str.strip().str.upper().str.translate(TABLA_SIN_ACENTOS)

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

def encontrar_archivo_en_dir(data_dir: Path, palabras_obligatorias: List[str], palabras_preferidas: Optional[List[str]] = None) -> Optional[Path]:
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
def load_data(data_dir_str: str) -> DataBundle:
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
            # CORREGIDO: Evita el bug de Length mismatch limpiando índices
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

        # Normalizar columnas numéricas Pxs
        for c in ["Pxs-MES", "Pxs-YTD", "Pxs-TRIM", "Pxs-LY"]:
            if c in bundle.productos.columns:
                bundle.productos[c] = pd.to_numeric(bundle.productos[c], errors="coerce").fillna(0)

        # Asignar Clase del Archivo
        bundle.productos["CLASE_TERAPEUTICA_ARCHIVO"] = bundle.productos["NOMBRE_PRODUCTO"].str.upper().map(mapa_ct).fillna("")

        # Flag Es_Gutis
        col_fab = next((c for c in bundle.productos.columns if "FABRICANTE" in c.upper() or "LAB" in c.upper()), None)
        prod_norm_s = normalizar_serie_rapida(bundle.productos["NOMBRE_PRODUCTO"])
        es_gutis_mask = prod_norm_s.str.contains(PATRON_REGEX_GUTIS, na=False)
        if col_fab:
            es_gutis_mask = es_gutis_mask | normalizar_serie_rapida(bundle.productos[col_fab]).str.contains("GUTIS", na=False)
        bundle.productos["Es_Gutis"] = es_gutis_mask

        # Mapeo Clave Gutis
        bundle.productos["_clave_combo"] = bundle.productos.get("MERCADO", "").fillna("").astype(str) + " || " + bundle.productos["CLASE_TERAPEUTICA_ARCHIVO"] + " || " + bundle.productos["NOMBRE_PRODUCTO"]
        mapa_combo = {}
        for combo in bundle.productos["_clave_combo"].unique():
            partes = combo.split(" || ")
            m_txt = f"{partes[0]} {partes[1]}" if len(partes) > 1 else partes[0]
            p_txt = partes[2] if len(partes) > 2 else ""
            k_m = resolver_clave_mercado_gutis(m_txt, "") or resolver_clave_mercado_gutis(m_txt, p_txt)
            mapa_combo[combo] = k_m
        bundle.productos["Clave_Gutis"] = bundle.productos["_clave_combo"].map(mapa_combo)
        bundle.productos = bundle.productos.drop(columns=["_clave_combo"])

        # Cruce con Panel
        bundle.productos["CIUDAD_PANEL"] = bundle.productos["Médico"].map(mapa_ciu).fillna("FUERA DE PANEL")
        bundle.productos["ESP_PANEL"] = bundle.productos["Médico"].map(mapa_esp).fillna("ESPECIALISTA")
        bundle.productos["CAT_PANEL"] = bundle.productos["Médico"].map(mapa_cat).fillna("S/C")

        # Diccionario rápido Marca -> Mercado (CORREGIDO: sin usar r_m._0 frágil)
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

    # 5. Auditoría Close-Up (Clases y Auditoría.xlsx)
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
            bundle.auditoria_totales = df_aud_raw[df_aud_raw["MEDICO_ESPECIALIDAD"].astype(str).str.strip().str.upper() == "TOTAL"].drop_duplicates(subset=["MARCA"]).set_index("MARCA")

            mask_docs = (
                ~df_aud_raw["MARCA"].isin(["TOTAL", "NAN", "NONE", ""]) &
                ~df_aud_raw["MEDICO_ESPECIALIDAD"].astype(str).str.strip().str.upper().isin(["TOTAL", "NAN", "NONE", ""]) &
                df_aud_raw["MEDICO_ESPECIALIDAD"].notna()
            )
            df_docs = df_aud_raw[mask_docs].copy()
            partes = df_docs["MEDICO_ESPECIALIDAD"].astype(str).str.rsplit(" - ", n=1, expand=True)
            df_docs["Médico"] = partes[0].str.strip().str.upper()
            df_docs["Especialidad"] = partes[1].str.strip().str.upper() if partes.shape[1] > 1 else "ESPECIALISTA"
            df_docs["Laboratorio"] = df_docs["MARCA"].str.split().str[-1]
            df_docs["Zona"] = df_docs["Médico"].map(mapa_ciu).fillna("FUERA DE PANEL")
            df_docs["Categoria_TAM"] = df_docs["Médico"].map(mapa_cat).fillna("FUERA DE PANEL")

            # Mapeo de Mercado y Clave
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

            # Ponderación W exacta
            for c_bi in ["% MS - LY", "% MS - Ytd", "% MS - TrasAnt", "% MS - Ant", "% MS - Mes"]:
                if c_bi in df_docs.columns and c_bi in bundle.auditoria_totales.columns:
                    p_marca_serie = df_docs["MARCA"].map(bundle.auditoria_totales[c_bi]).fillna(0.0)
                    df_docs["W_" + c_bi] = p_marca_serie * df_docs[c_bi]

            bundle.auditoria = df_docs

    # 6. Ventas / Sell-Out (Q1, Q2, Q3)
    dfs_v = []
    for q_kw, q_lbl in [("PRIMER", "Q1"), ("SEGUNDO", "Q2"), ("TERCER", "Q3")]:
        f_v = encontrar_archivo_en_dir(data_dir, ["VENTA", q_kw]) or encontrar_archivo_en_dir(data_dir, ["VENTAS", q_kw])
        if f_v:
            try:
                xl = pd.ExcelFile(f_v)
                sheet_target = "Export" if "Export" in xl.sheet_names else xl.sheet_names[0]
                d_temp = pd.read_excel(f_v, sheet_name=sheet_target)
                d_temp["Trimestre"] = q_lbl
                dfs_v.append(d_temp)
                bundle.archivos[f"Ventas {q_lbl}"] = f_v.name
            except Exception:
                pass

    if dfs_v:
        bundle.ventas = pd.concat(dfs_v, ignore_index=True)
        bundle.ventas.columns = bundle.ventas.columns.astype(str).str.strip()
        # CORREGIDO: Sanitización estricta de Monto Real a numérico
        if "Monto Real" in bundle.ventas.columns:
            bundle.ventas["Monto Real"] = pd.to_numeric(
                bundle.ventas["Monto Real"].astype(str).str.replace("$", "", regex=False).str.replace(",", "", regex=False).str.strip(),
                errors="coerce"
            ).fillna(0.0)
        if "DESCRIPCION_RUTA" in bundle.ventas.columns:
            bundle.ventas["DESCRIPCION_RUTA"] = bundle.ventas["DESCRIPCION_RUTA"].astype(str).str.strip().str.upper()
        col_p_v = "VM4" if "VM4" in bundle.ventas.columns else next((c for c in bundle.ventas.columns if "PRODUCTO" in c.upper()), None)
        if col_p_v:
            bundle.ventas["PRODUCTO_VENTA"] = bundle.ventas[col_p_v].astype(str).str.strip().str.upper()

    return bundle

def clear_data_cache():
    st.cache_data.clear()
