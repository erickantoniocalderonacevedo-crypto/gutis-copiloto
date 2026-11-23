from __future__ import annotations

import hashlib
import html
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from analisis_ventas import render_centro_analisis
from gutis_bi.ai_service import llamar_gemini, obtener_api_key, transcribir_audio_gemini
from gutis_bi.analytics import (
    auditoria_marcas,
    calcular_tabla_bi_multifiltro,
    construir_guion_tvp_dinamico,
    diagnosticar_escala_adopcion,
    formatear_nombre_medico,
    generar_analisis_mercado_chira_rico,
    generar_consultoria_cognitiva_chira_medico,
    limpiar_sku_competencia,
    matriz_penetracion,
    obtener_matriz_clases_terapeuticas_medico,
    perfil_medico,
    productos_medico,
    radar_laboratorios,
    ranking_medicos,
    resumen_global,
    resumen_mercados,
    resumen_ventas_ciudad,
)
from gutis_bi.catalog import MERCADOS_PRIORITARIOS, PATRON_REGEX_GUTIS
from gutis_bi.chira_engine import enrutar_consulta_chira
from gutis_bi.crm import (
    exportar_visitas_csv,
    guardar_perfil_360,
    guardar_visita,
    init_db,
    leer_perfil_360,
    leer_visitas,
    migrar_excels_anteriores,
)
from gutis_bi.data import (
    clear_data_cache,
    load_data,
    normalizar_serie_rapida,
    normalizar_txt,
    resolver_clave_mercado_gutis,
)

# -----------------------------------------------------------------------------
# CONSTANTES DE APLICACIÓN Y CONFIGURACIÓN DE PÁGINA
# -----------------------------------------------------------------------------
APP_VERSION = "v3.3"
VISITADOR_NOMBRE = "Erick Calderón"
VISITADOR_INICIALES = "EC"
ALCANCE_SOLO_PANEL = f"SOLO MI PANEL ({VISITADOR_NOMBRE.upper()})"
ALCANCE_UNIVERSO_TOTAL = "UNIVERSO TOTAL NICARAGUA"

st.set_page_config(
    page_title=f"Gutis BI {APP_VERSION} | Arquitectura TVP & Close-Up",
    page_icon="G",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
custom_data = os.environ.get("GUTIS_DATA_DIR", "")
if custom_data:
    DATA_DIR = Path(custom_data).resolve()
elif (BASE_DIR / "DATOS").exists():
    DATA_DIR = (BASE_DIR / "DATOS").resolve()
elif (BASE_DIR / "data").exists():
    DATA_DIR = (BASE_DIR / "data").resolve()
else:
    DATA_DIR = BASE_DIR.resolve()

DB_PATH = Path(os.environ.get("GUTIS_DB_PATH", str(BASE_DIR / "gutis_bi.db"))).resolve()

# -----------------------------------------------------------------------------
# PARTE 1: SISTEMA DE DISEÑO ENTERPRISE STITCH (CSS MAESTRO, SIDEBAR Y TOPBAR)
# -----------------------------------------------------------------------------


def esc(valor: Any) -> str:
    return html.escape(str(valor if valor is not None else ""))


def render_sb_html(html_str: str) -> None:
    clean_html = "\n".join(line.lstrip() for line in html_str.splitlines() if line.strip())
    st.sidebar.markdown(clean_html, unsafe_allow_html=True)


def render_html(html_str: str) -> None:
    clean_html = "\n".join(line.lstrip() for line in html_str.splitlines() if line.strip())
    st.markdown(clean_html, unsafe_allow_html=True)


render_html("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        .stApp {
            background-color: #f4f6f9;
            font-family: 'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            color: #0f172a;
        }
        .block-container {
            padding-top: 1.2rem !important;
            padding-bottom: 2.5rem !important;
            max-width: 97% !important;
        }

        /* BARRA SUPERIOR BREADCRUMB ESTILO STITCH */
        .stitch-nav-header {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 10px 18px;
            margin-bottom: 14px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
        }
        .stitch-breadcrumbs {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.78rem;
            color: #64748b;
            font-weight: 600;
        }
        .stitch-breadcrumbs b { color: #002b5c; font-weight: 800; }
        .stitch-pill-region {
            background: #eff6ff;
            color: #0284c7;
            border: 1px solid #bae6fd;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.7rem;
            font-weight: 700;
        }
        .stitch-sync-status {
            display: flex;
            align-items: center;
            gap: 14px;
            font-size: 0.75rem;
        }
        .sync-badge {
            background: #ecfdf5;
            color: #059669;
            border: 1px solid #a7f3d0;
            padding: 4px 12px;
            border-radius: 999px;
            font-weight: 700;
            font-size: 0.72rem;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .vm-avatar-top {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-weight: 700;
            color: #1e293b;
        }
        .vm-circle {
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: #002b5c;
            color: #ffffff;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7rem;
            font-weight: 800;
        }

        /* HERO BANNER PRINCIPAL GUTIS */
        .stitch-hero {
            background: linear-gradient(110deg, #001f44 0%, #002b5c 52%, #0f172a 100%);
            color: #ffffff;
            padding: 20px 26px;
            border-radius: 12px;
            margin-bottom: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 8px 20px rgba(0, 43, 92, 0.16);
            border: 1px solid rgba(56, 189, 248, 0.2);
        }
        .hero-left-tag {
            font-size: 0.72rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #38bdf8;
            font-weight: 800;
            margin-bottom: 4px;
        }
        .hero-main-title {
            font-size: 1.45rem;
            font-weight: 800;
            color: #ffffff;
            margin-bottom: 4px;
            letter-spacing: -0.01em;
        }
        .hero-sub-desc {
            font-size: 0.8rem;
            color: #cbd5e1;
            max-width: 680px;
        }
        .hero-glass-box {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.16);
            border-radius: 10px;
            padding: 12px 18px;
            display: flex;
            align-items: center;
            gap: 16px;
        }
        .hero-glass-lbl { font-size: 0.65rem; text-transform: uppercase; color: #94a3b8; font-weight: 700; }
        .hero-glass-val { font-size: 0.86rem; font-weight: 800; color: #ffffff; }
        .hero-ok-pill {
            background: rgba(16, 185, 129, 0.2);
            color: #34d399;
            border: 1px solid rgba(52, 211, 153, 0.4);
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.7rem;
            font-weight: 800;
        }

        /* TARJETAS KPI ESTILO STITCH CON BARRAS DE PROGRESO Y PILLS */
        .kpi-strip {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 14px;
            margin-bottom: 18px;
        }
        .kpi-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 16px 18px;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.03);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .kpi-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 14px rgba(15, 23, 42, 0.06);
        }
        .kpi-top-row {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 8px;
        }
        .kpi-lbl {
            font-size: 0.68rem;
            text-transform: uppercase;
            color: #64748b;
            font-weight: 800;
            letter-spacing: 0.03em;
        }
        .kpi-icon-box {
            background: #eff6ff;
            color: #0284c7;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.68rem;
            font-weight: 800;
        }
        .kpi-num-row {
            display: flex;
            align-items: baseline;
            gap: 8px;
            margin: 4px 0 8px 0;
        }
        .kpi-num {
            font-size: 1.55rem;
            font-weight: 800;
            color: #0f172a;
            letter-spacing: -0.02em;
        }
        .kpi-pill-up {
            background: #dcfce7;
            color: #15803d;
            padding: 2px 8px;
            border-radius: 999px;
            font-size: 0.68rem;
            font-weight: 800;
        }
        .kpi-pill-neutral {
            background: #e0f2fe;
            color: #0369a1;
            padding: 2px 8px;
            border-radius: 999px;
            font-size: 0.68rem;
            font-weight: 800;
        }
        .kpi-pill-warn {
            background: #fef3c7;
            color: #b45309;
            padding: 2px 8px;
            border-radius: 999px;
            font-size: 0.68rem;
            font-weight: 800;
        }
        .kpi-progress-track {
            width: 100%;
            height: 6px;
            background: #f1f5f9;
            border-radius: 999px;
            overflow: hidden;
            margin-bottom: 8px;
        }
        .kpi-progress-fill {
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, #002b5c, #0284c7);
        }
        .kpi-sub {
            font-size: 0.74rem;
            color: #64748b;
            font-weight: 600;
            display: flex;
            justify-content: space-between;
        }

        /* TARJETAS INTERACTIVAS DE LOS 5 MÓDULOS EN EL MENÚ PRINCIPAL */
        .stitch-mod-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 18px 20px;
            margin-bottom: 8px;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.03);
            transition: all 0.18s ease;
        }
        .stitch-mod-card:hover {
            border-color: #93c5fd;
            box-shadow: 0 8px 18px rgba(2, 132, 199, 0.08);
        }
        .mod-card-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .mod-icon-badge {
            width: 36px;
            height: 36px;
            border-radius: 8px;
            background: #eff6ff;
            color: #0284c7;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 0.82rem;
            border: 1px solid #dbeafe;
        }
        .mod-code-tag {
            font-size: 0.66rem;
            font-weight: 800;
            color: #94a3b8;
            letter-spacing: 0.06em;
        }
        .mod-card-title {
            font-size: 0.98rem;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 6px;
        }
        .mod-card-title span {
            color: #0284c7;
            font-size: 0.8rem;
            font-weight: 700;
        }
        .mod-card-desc {
            font-size: 0.78rem;
            color: #64748b;
            line-height: 1.45;
            min-height: 36px;
        }

        /* TARJETA ESPECIALISTA EN BARRA LATERAL */
        .sidebar-doc-card {
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-left: 4px solid #002b5c;
            border-radius: 10px;
            padding: 12px;
            margin-top: 8px;
            box-shadow: 0 2px 5px rgba(15, 23, 42, 0.04);
        }
        .doc-avatar-row {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 8px;
        }
        .doc-initials {
            width: 34px;
            height: 34px;
            border-radius: 50%;
            background: #002b5c;
            color: #ffffff;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 0.78rem;
            font-weight: 800;
            flex-shrink: 0;
        }
        .doc-name-sb {
            font-size: 0.78rem;
            font-weight: 800;
            color: #0f172a;
            line-height: 1.2;
        }
        .doc-esp-sb {
            font-size: 0.68rem;
            color: #64748b;
            font-weight: 600;
        }
        .doc-meta-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid #f1f5f9;
            padding-top: 6px;
            font-size: 0.68rem;
            font-weight: 700;
            color: #475569;
        }
        .doc-cat-pill {
            background: #e0f2fe;
            color: #0369a1;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 800;
        }

        /* BOTONES CORPORATIVOS Y BANNERS DE MÓDULO */
        div.stButton > button {
            border-radius: 8px;
            font-weight: 700;
            border: 1px solid #cbd5e1;
            background-color: #ffffff;
            color: #002b5c;
            padding: 8px 14px;
            transition: all 0.15s ease-in-out;
        }
        div.stButton > button:hover {
            background-color: #002b5c;
            color: #ffffff;
            border-color: #002b5c;
        }
        div.stButton > button[kind="primary"] {
            background: linear-gradient(90deg, #002b5c 0%, #003b7a 100%);
            color: #ffffff;
            border: 1px solid #002b5c;
            box-shadow: 0 2px 6px rgba(0, 43, 92, 0.18);
        }
        div.stButton > button[kind="primary"]:hover {
            background: linear-gradient(90deg, #0284c7 0%, #002b5c 100%);
            border-color: #0284c7;
        }
        .module-banner {
            background: linear-gradient(90deg, #002b5c 0%, #0f172a 100%);
            color: #ffffff;
            padding: 11px 18px;
            border-radius: 8px;
            margin-bottom: 12px;
            border-left: 5px solid #38bdf8;
            font-weight: 800;
            font-size: 0.85rem;
            text-transform: uppercase;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .subnav-label {
            font-size: 0.7rem;
            font-weight: 800;
            text-transform: uppercase;
            color: #475569;
            margin-bottom: 6px;
            letter-spacing: 0.04em;
        }
        .quad-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 16px;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.03);
        }
        .quad-title {
            font-size: 0.74rem;
            font-weight: 800;
            text-transform: uppercase;
            margin-bottom: 10px;
            padding-bottom: 6px;
            border-bottom: 2px solid #f1f5f9;
        }
        .quad-body {
            font-size: 0.83rem;
            color: #1e293b;
            line-height: 1.52;
        }

        /* CHIRA NEURAL ENGINE (MÓDULO 5) */
        .chira-neural-hero {
            background: linear-gradient(115deg, #001a38 0%, #002b5c 50%, #0f172a 100%);
            color: #ffffff;
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 16px;
            border: 1px solid rgba(56, 189, 248, 0.3);
            box-shadow: 0 8px 24px rgba(0, 43, 92, 0.18);
        }
        .chira-neural-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(2, 132, 199, 0.25);
            border: 1px solid #38bdf8;
            color: #7dd3fc;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.68rem;
            font-weight: 800;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        .chira-mem-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: 10px;
            margin-top: 12px;
        }
        .chira-mem-box {
            background: rgba(255, 255, 255, 0.07);
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 8px;
            padding: 10px 12px;
        }
        .chira-mem-lbl { font-size: 0.62rem; text-transform: uppercase; color: #93c5fd; font-weight: 800; }
        .chira-mem-val { font-size: 0.84rem; font-weight: 800; color: #ffffff; margin-top: 2px; }
        .chira-mem-sub { font-size: 0.68rem; color: #cbd5e1; }
        .chira-prompt-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-left: 4px solid #0284c7;
            border-radius: 10px;
            padding: 12px 14px;
            margin-bottom: 8px;
        }
        .chira-prompt-title { font-size: 0.78rem; font-weight: 800; color: #002b5c; margin-bottom: 4px; }
        .chira-prompt-desc { font-size: 0.72rem; color: #64748b; line-height: 1.35; }
    </style>
    """)

# -----------------------------------------------------------------------------
# CARGA DE DATOS E INICIALIZACIÓN DE SQLITE (UNA SOLA VEZ POR SESIÓN)
# -----------------------------------------------------------------------------
if not st.session_state.get("_db_inicializada"):
    init_db(DB_PATH)
    _legacy_history = next(
        (p for p in (BASE_DIR / "HISTORIAL_VISITAS.xlsx", DATA_DIR / "HISTORIAL_VISITAS.xlsx") if p.exists()),
        None,
    )
    _legacy_profile = next(
        (p for p in (BASE_DIR / "PERFIL_360_MEDICOS.xlsx", DATA_DIR / "PERFIL_360_MEDICOS.xlsx") if p.exists()),
        None,
    )
    migrar_excels_anteriores(_legacy_history, _legacy_profile, DB_PATH)
    st.session_state["_db_inicializada"] = True

bundle = load_data(str(DATA_DIR))
df_panel = bundle.panel.copy() if not bundle.panel.empty else pd.DataFrame()
df_productos = bundle.productos.copy() if not bundle.productos.empty else pd.DataFrame()
df_labs = bundle.laboratorios.copy() if not bundle.laboratorios.empty else pd.DataFrame()
df_clases = bundle.clases.copy() if not bundle.clases.empty else pd.DataFrame()
df_auditoria_docs = bundle.auditoria.copy() if not bundle.auditoria.empty else pd.DataFrame()
df_auditoria_tot = bundle.auditoria_totales.copy() if not bundle.auditoria_totales.empty else pd.DataFrame()
df_ventas = bundle.ventas.copy() if not bundle.ventas.empty else pd.DataFrame()

if not df_productos.empty:
    if "Es_Gutis" in df_productos.columns:
        df_productos["Es_Gutis"] = df_productos["Es_Gutis"].fillna(False).astype(bool)
    else:
        df_productos["Es_Gutis"] = False
    for col_def, val_def in [("CIUDAD_PANEL", "FUERA DE PANEL"), ("ESP_PANEL", "ESPECIALISTA"), ("CAT_PANEL", "S/C")]:
        if col_def not in df_productos.columns:
            df_productos[col_def] = val_def

if not df_auditoria_docs.empty:
    for col_a, val_a in [("Zona", "FUERA DE PANEL"), ("Médico", ""), ("MARCA", ""), ("Especialidad", "ESPECIALISTA"), ("Laboratorio", ""), ("Categoria_TAM", "S/C")]:
        if col_a not in df_auditoria_docs.columns:
            df_auditoria_docs[col_a] = val_a

LISTA_CIUDADES_REALES = (
    sorted([c for c in df_panel["CIUDAD"].dropna().unique() if str(c).strip() not in ["", "NAN"]])
    if not df_panel.empty and "CIUDAD" in df_panel.columns
    else []
)
LISTA_ESPECIALIDADES_REALES = (
    sorted([e for e in df_panel["Especialidad"].dropna().unique() if str(e).strip() not in ["", "NAN"]])
    if not df_panel.empty and "Especialidad" in df_panel.columns
    else []
)
LISTA_MERCADOS_GUTIS_KEYS = list(MERCADOS_PRIORITARIOS.keys())

meds_panel_default = (
    sorted(df_panel["Médico"].dropna().unique().tolist())
    if not df_panel.empty and "Médico" in df_panel.columns
    else []
)

for k_st, v_def in [
    ("modulo_activo", "HUB"),
    ("modo_alcance_sidebar", ALCANCE_SOLO_PANEL),
    ("medico_activo_global", meds_panel_default[0] if meds_panel_default else ""),
    ("chira_history", []),
    ("tvp_custom_script", {}),
    ("tvp_variant_counter", 0),
    ("ultimo_audio_hash", None),
    ("sub_previsita", "MAPA"),
    ("sub_previsita_auditoria", "CLASES"),
    ("sub_top_medicos", "BI_EVOLUCION"),
    ("sub_analisis_mercado", "LABS"),
    ("sub_evolucion", "SINCRONIA"),
    ("sub_chira", "COPILOTO"),
    ("mercado_drill_sel", None),
    ("pos_m1_idx", 0),
    ("pos_m2_idx", 1),
    ("pos_m3_idx", 2),
    ("ctx_cita_global", "Visita con cita previa"),
    ("ctx_ndn_global", "Desempeño (Eficacia y adherencia clínica)"),
]:
    if k_st not in st.session_state:
        st.session_state[k_st] = v_def


def ir_a_modulo(nombre_mod: str, medico_destino: str | None = None) -> None:
    st.session_state.modulo_activo = nombre_mod
    if medico_destino:
        st.session_state.medico_activo_global = medico_destino
        st.session_state.pos_m1_idx, st.session_state.pos_m2_idx, st.session_state.pos_m3_idx = 0, 1, 2
        st.session_state.mercado_drill_sel = None


def obtener_iniciales(nombre: str) -> str:
    partes = [p for p in str(nombre).strip().split() if p]
    if len(partes) >= 2:
        return (partes[0][0] + partes[1][0]).upper()
    if len(partes) == 1:
        return partes[0][:2].upper()
    return "MD"


@st.cache_data(show_spinner=False)
def _calcular_bi_cache(
    df_base_bi: pd.DataFrame,
    df_aud_tot: pd.DataFrame,
    f_zona: str,
    f_med: str,
    f_esp: str,
    f_vis: str,
    f_mer: str,
    f_mar: str,
    f_lab: str,
    f_cat: str,
    df_prod: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return calcular_tabla_bi_multifiltro(
        df_base_bi,
        df_aud_tot,
        f_zona=f_zona,
        f_med=f_med,
        f_esp=f_esp,
        f_vis=f_vis,
        f_mer=f_mer,
        f_mar=f_mar,
        f_lab=f_lab,
        f_cat=f_cat,
        df_productos=df_prod,
    )


def calcular_meta_objetivo(comp_mes: int) -> int:
    comp = int(comp_mes or 0)
    if comp <= 0:
        return 0
    return max(1, min(comp, round(comp * 0.3)))


def texto_objetivo_clinico(n: int) -> str:
    if n <= 0:
        return "consolidar la adherencia terapéutica en los pacientes actuales"
    return f"evaluar como opción terapéutica en sus próximos {n} paciente{'s' if n != 1 else ''}"


_RE_NUM_GENERAL = re.compile(r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?")
_RE_CIFRAS_AUDITORIA = re.compile(
    r"(?:\$\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?))"
    r"|(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)\s*(?:%|pxs?\b|rx\b|recetas?\b|pp\b)",
    re.IGNORECASE,
)


def _fmt_num_estable(val: float) -> str:
    s = f"{val:.2f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _normalizar_num(raw: str) -> list[str]:
    s = raw.strip()
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        partes = s.split(",")
        if len(partes[-1]) == 3 and all(len(p) <= 3 for p in partes):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    elif "." in s:
        partes = s.split(".")
        if len(partes) > 2 and all(len(p) == 3 for p in partes[1:]):
            s = s.replace(".", "")
    try:
        val = float(s)
        return [_fmt_num_estable(val), str(int(round(val)))]
    except ValueError:
        return []


def _todos_los_numeros(texto: str) -> set[str]:
    out: set[str] = set()
    for m in _RE_NUM_GENERAL.findall(texto or ""):
        out.update(_normalizar_num(m))
    return out


def _cifras_auditoria(texto: str) -> set[str]:
    out: set[str] = set()
    for g1, g2 in _RE_CIFRAS_AUDITORIA.findall(texto or ""):
        raw = g1 or g2
        if raw:
            nums = _normalizar_num(raw)
            if nums:
                out.add(nums[0])
    return out


def respuesta_ia_conserva_cifras(resp_ia: str, texto_base: str) -> bool:
    base_nums = _todos_los_numeros(texto_base)
    ia_metricas = _cifras_auditoria(resp_ia)
    return ia_metricas.issubset(base_nums)


def csv_para_excel(data: object) -> bytes:
    if isinstance(data, str):
        data = data.encode("utf-8")
    data = bytes(data or b"")
    return data if data.startswith(b"\xef\xbb\xbf") else b"\xef\xbb\xbf" + data


# -----------------------------------------------------------------------------
# BARRA LATERAL ESTILO STITCH (LOGO, NAVEGACIÓN, TARJETA AVATAR MÉDICO)
# -----------------------------------------------------------------------------
render_sb_html(f"""
    <div translate='no' style='display:flex; align-items:center; gap:10px; padding:4px 0 12px 0; border-bottom:1px solid #e2e8f0; margin-bottom:10px;'>
        <div style='width:34px; height:34px; border-radius:8px; background:#002b5c; color:#fff; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:1.05rem;'>G</div>
        <div>
            <div style='font-weight:800; font-size:0.95rem; color:#0f172a;'>GUTIS BI <span style='background:#dcfce7; color:#15803d; font-size:0.65rem; padding:2px 6px; border-radius:4px;'>{esc(APP_VERSION)}</span></div>
            <div style='font-size:0.68rem; color:#64748b; font-weight:600;'>Arquitectura TVP &amp; Close-Up</div>
        </div>
    </div>
    """)

st.sidebar.markdown("<div class='subnav-label'>NAVEGACIÓN DEL PORTAL (5 MÓDULOS)</div>", unsafe_allow_html=True)
opciones_nav = {
    "HUB": "Inicio | Menú Principal",
    "TOP_MEDICOS": "1. Top Médicos (inf.target)",
    "PREVISITA": "2. Previsita TVP (inf.target)",
    "ANALISIS_MERCADO": "3. Análisis Mercado (inf.market)",
    "EVOLUCION": "4. Evolución Rx vs. Sell-Out",
    "CHIRA": "5. CHIRA (Copiloto & CRM)",
}
st.sidebar.radio(
    "Módulo Activo:",
    list(opciones_nav.keys()),
    key="modulo_activo",
    format_func=lambda k: opciones_nav[k],
    label_visibility="collapsed",
)

st.sidebar.divider()
st.sidebar.markdown("<div class='subnav-label'>ESPECIALISTA ACTIVO (PREVISITA)</div>", unsafe_allow_html=True)

alcance_sb = st.sidebar.radio(
    "Universo de Médicos:",
    [ALCANCE_SOLO_PANEL, ALCANCE_UNIVERSO_TOTAL],
    key="modo_alcance_sidebar",
    help="Por defecto muestra exclusivamente los médicos de tu panel asignado.",
)

if alcance_sb == ALCANCE_SOLO_PANEL:
    ciu_sb = st.sidebar.selectbox("Filtrar Ciudad del Panel:", ["TODAS"] + LISTA_CIUDADES_REALES)
    df_pan_sb = df_panel if ciu_sb == "TODAS" else df_panel[df_panel["CIUDAD"] == ciu_sb]
    esp_opciones_sb = sorted(df_pan_sb["Especialidad"].dropna().unique().tolist()) if not df_pan_sb.empty else []
    esp_sb = st.sidebar.selectbox("Filtrar Especialidad:", ["TODAS"] + esp_opciones_sb)
    if esp_sb != "TODAS":
        df_pan_sb = df_pan_sb[df_pan_sb["Especialidad"] == esp_sb]
    lista_meds_sb = sorted(df_pan_sb["Médico"].dropna().unique().tolist()) if not df_pan_sb.empty else []
else:
    ciu_sb = st.sidebar.selectbox("Filtrar Ciudad:", ["TODAS"] + LISTA_CIUDADES_REALES)
    df_prod_sb = df_productos if ciu_sb == "TODAS" else df_productos[df_productos["CIUDAD_PANEL"] == ciu_sb]
    if ciu_sb == "TODAS":
        lista_meds_sb = sorted(set(meds_panel_default) | (set(df_prod_sb["Médico"].dropna().unique().tolist()) if not df_prod_sb.empty else set()))
    else:
        lista_meds_sb = sorted(df_prod_sb["Médico"].dropna().unique().tolist()) if not df_prod_sb.empty else []

if not lista_meds_sb:
    st.sidebar.warning("Sin médicos para esa combinación de ciudad/especialidad.")
    med_elegido_sb = ""
else:
    idx_med_sb = lista_meds_sb.index(st.session_state.medico_activo_global) if st.session_state.medico_activo_global in lista_meds_sb else 0
    med_elegido_sb = st.sidebar.selectbox("Especialista en Foco:", lista_meds_sb, index=idx_med_sb)
    if med_elegido_sb != st.session_state.medico_activo_global:
        st.session_state.medico_activo_global = med_elegido_sb
        st.session_state.pos_m1_idx, st.session_state.pos_m2_idx, st.session_state.pos_m3_idx = 0, 1, 2
        st.session_state.mercado_drill_sel = None
        st.rerun()

medico_sel = med_elegido_sb
dp_global = perfil_medico(df_panel, df_productos, medico_sel) if medico_sel else {}
ciudad = dp_global.get("CIUDAD", "NICARAGUA")
especialidad = dp_global.get("Especialidad", "ESPECIALISTA")
categoria = dp_global.get("CATEGORIA", "S/C")
es_pediatra = "PEDIAT" in str(especialidad).upper()
ini_med = obtener_iniciales(medico_sel)

render_sb_html(f"""
    <div class='sidebar-doc-card' translate='no'>
        <div class='doc-avatar-row'>
            <div class='doc-initials'>{esc(ini_med)}</div>
            <div>
                <div class='doc-name-sb'>{esc(medico_sel[:26]) if medico_sel else 'Sin selección'}</div>
                <div class='doc-esp-sb'>{esc(especialidad)}</div>
            </div>
        </div>
        <div class='doc-meta-row'>
            <span class='doc-cat-pill'>Cat {esc(categoria)}</span>
            <span>{esc(ciudad)}, Nic.</span>
            <span style='color:#0284c7;'>{dp_global.get('Pxs Mes', 0)} Pxs/M</span>
        </div>
    </div>
    """)

st.sidebar.divider()
with st.sidebar.expander("Estado de Bases de Datos y Caché", expanded=False):
    st.caption(f"Carpeta activa: `{DATA_DIR}`")
    for k_f, v_f in bundle.archivos.items():
        st.caption(f"• **{k_f}:** `{v_f}`")
    if st.button("Recargar Excels y Limpiar Caché", width="stretch"):
        clear_data_cache()
        st.rerun()

render_sb_html(f"""
    <div translate='no' style='display:flex; align-items:center; justify-content:space-between; padding-top:8px; font-size:0.72rem; color:#475569; font-weight:700;'>
        <span><span style='color:#10b981;'>●</span> Conexión Local Estable</span>
        <span>{esc(VISITADOR_NOMBRE)} (VM)</span>
    </div>
    """)

# -----------------------------------------------------------------------------
# BARRA SUPERIOR DE MIGAS DE PAN & ESTADO SYNC (TOPBAR STITCH)
# -----------------------------------------------------------------------------
corte_nombre = bundle.archivos.get("Auditoría") or bundle.archivos.get("Productos") or "CLASES_Y_AUDITORIA.XLSX"
nombre_mod_breadcrumb = opciones_nav.get(st.session_state.modulo_activo, "Menú Principal")
render_html(f"""
    <div class='stitch-nav-header' translate='no'>
        <div class='stitch-breadcrumbs'>
            <b>GUTIS BI</b> <span>/</span> <span>Comité Médico Estratégico</span> <span>/</span>
            <b>{esc(nombre_mod_breadcrumb)}</b>
            <span class='stitch-pill-region'>{esc(ciudad) if st.session_state.modulo_activo == 'PREVISITA' else 'Región Pacífico &amp; Centro'}</span>
        </div>
        <div class='stitch-sync-status'>
            <span style='color:#64748b; font-weight:600;'>Auditoría Close-Up: <b>{esc(corte_nombre)}</b></span>
            <span class='sync-badge'>● Sincronización Close-Up</span>
            <div class='vm-avatar-top'>
                <span class='vm-circle'>{esc(VISITADOR_INICIALES)}</span>
                <span>{esc(VISITADOR_NOMBRE)} <small style='display:block; font-size:0.64rem; color:#10b981; font-weight:700;'>Visitador Médico · Activo</small></span>
            </div>
        </div>
    </div>
    """)

kpi_hub = resumen_global(df_panel, df_productos)

# -----------------------------------------------------------------------------
# PARTE 2: FUNCIONES AUXILIARES, MENÚ PRINCIPAL (HUB STITCH) Y MÓDULO 1 (VISOR BI)
# -----------------------------------------------------------------------------


def show_table(df: pd.DataFrame, height: int = 420) -> None:
    if df is None or df.empty:
        st.info("No hay registros para los filtros seleccionados.")
        return
    cfg: dict[str, Any] = {}
    meses_pref = ("Ene ", "Feb ", "Mar ", "Abr ", "May ", "Jun ", "Jul ", "Ago ", "Sep ", "Oct ", "Nov ", "Dic ")
    for col in df.columns:
        if "% MS" in col or "% Cumpl" in col or "% Cuota" in col:
            cfg[col] = st.column_config.ProgressColumn(col, format="%.1f%%", min_value=0, max_value=100)
        elif "($)" in col or col in ("Q1", "Q2", "Q3", "Total Acumulado") or col.startswith(meses_pref):
            cfg[col] = st.column_config.NumberColumn(col, format="$%.2f")
        elif "Dif %" in col or "Brecha" in col or "Delta" in col:
            cfg[col] = st.column_config.NumberColumn(col, format="%+.1f pp")
    if "Sucursal / Farmacia" in df.columns:
        cfg["Sucursal / Farmacia"] = st.column_config.TextColumn("Sucursal / Farmacia", pinned=True, width="medium")
    st.dataframe(df, hide_index=True, width="stretch", height=height, column_config=cfg)


# -----------------------------------------------------------------------------
# MÓDULO HUB (MENÚ PRINCIPAL ESTILO STITCH: HERO, 4 KPIS Y CARDS MOD-01 A MOD-05)
# -----------------------------------------------------------------------------
if st.session_state.modulo_activo == "HUB":
    render_html(f"""
        <div class='stitch-hero' translate='no'>
            <div>
                <div class='hero-left-tag'>GUTIS · INNOVACIÓN Y TECNOLOGÍA PARA LA VIDA</div>
                <div class='hero-main-title'>Análisis Close-Up &amp; Arquitectura TVP</div>
                <div class='hero-sub-desc'>
                    Plataforma integral de efectividad médica comercial, monitoreo de cuota de mercado por clases terapéuticas y preparación ejecutiva previa de visitas.
                </div>
            </div>
            <div class='hero-glass-box'>
                <div>
                    <div class='hero-glass-lbl'>CENTRO DE COMPETENCIAS</div>
                    <div class='hero-glass-val'>Inteligencia de Negocio {esc(APP_VERSION)}</div>
                </div>
                <div class='hero-ok-pill'>Motor Activo</div>
            </div>
        </div>
        """)

    tot_pan = max(kpi_hub["medicos_panel"], 1)
    pct_cob = round((kpi_hub["medicos_activos"] / tot_pan) * 100.0, 1)
    brecha_hub = round(kpi_hub["ms_mes"] - kpi_hub["ms_ytd"], 1)
    signo_b = f"↑ +{brecha_hub:.1f} pp" if brecha_hub >= 0 else f"↓ {brecha_hub:.1f} pp"
    clase_pill_b = "kpi-pill-up" if brecha_hub >= 0 else "kpi-pill-warn"

    if abs(brecha_hub) < 1.0:
        txt_ytd_pill, clase_ytd_pill = "Estable", "kpi-pill-neutral"
    elif brecha_hub > 0:
        txt_ytd_pill, clase_ytd_pill = "Mes sobre YTD", "kpi-pill-up"
    else:
        txt_ytd_pill, clase_ytd_pill = "Mes bajo YTD", "kpi-pill-warn"

    w_mes = min(max(kpi_hub["ms_mes"], 0.0), 100.0)
    w_ytd = min(max(kpi_hub["ms_ytd"], 0.0), 100.0)

    render_html(f"""
        <div class='kpi-strip' translate='no'>
            <div class='kpi-card'>
                <div class='kpi-top-row'>
                    <div class='kpi-lbl'>PANEL MÉDICO REGISTRADO</div>
                    <div class='kpi-icon-box'>RX</div>
                </div>
                <div class='kpi-num-row'>
                    <div class='kpi-num'>{kpi_hub['medicos_panel']}</div>
                    <span class='kpi-pill-up'>{pct_cob:.1f}% Cobertura</span>
                </div>
                <div class='kpi-progress-track'>
                    <div class='kpi-progress-fill' style='width:{min(pct_cob, 100.0):.0f}%;'></div>
                </div>
                <div class='kpi-sub'>
                    <span>Prescriptores Activos Close-Up:</span>
                    <b style='color:#0f172a;'>{kpi_hub['medicos_activos']}</b>
                </div>
            </div>

            <div class='kpi-card'>
                <div class='kpi-top-row'>
                    <div class='kpi-lbl'>CUOTA GUTIS MES (CLASES ACTIVAS)</div>
                    <div class='kpi-icon-box' style='background:#ecfdf5; color:#059669;'>MS</div>
                </div>
                <div class='kpi-num-row'>
                    <div class='kpi-num'>{kpi_hub['ms_mes']:.1f}%</div>
                    <span class='{clase_pill_b}'>{esc(signo_b)}</span>
                </div>
                <div class='kpi-progress-track'>
                    <div class='kpi-progress-fill' style='width:{w_mes:.0f}%; background:linear-gradient(90deg, #059669, #10b981);'></div>
                </div>
                <div class='kpi-sub'>
                    <span>{kpi_hub['pxs_gutis_mes']:,} Gutis / {kpi_hub['pxs_mes']:,} Total Mes</span>
                </div>
            </div>

            <div class='kpi-card'>
                <div class='kpi-top-row'>
                    <div class='kpi-lbl'>CUOTA GUTIS YTD (ACUMULADO)</div>
                    <div class='kpi-icon-box'>YTD</div>
                </div>
                <div class='kpi-num-row'>
                    <div class='kpi-num'>{kpi_hub['ms_ytd']:.1f}%</div>
                    <span class='{clase_ytd_pill}'>{esc(txt_ytd_pill)}</span>
                </div>
                <div class='kpi-progress-track'>
                    <div class='kpi-progress-fill' style='width:{w_ytd:.0f}%;'></div>
                </div>
                <div class='kpi-sub'>
                    <span>{kpi_hub['pxs_gutis_ytd']:,} Gutis / {kpi_hub['pxs_ytd']:,} Total YTD</span>
                </div>
            </div>

            <div class='kpi-card' style='border-left: 4px solid #002b5c;'>
                <div class='kpi-top-row'>
                    <div class='kpi-lbl'>ESPECIALISTA EN PREPARACIÓN</div>
                    <span class='kpi-pill-warn'>En Foco TVP</span>
                </div>
                <div style='font-size:1.02rem; font-weight:800; color:#0f172a; margin:6px 0 4px 0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>
                    {esc(medico_sel) if medico_sel else 'Sin selección'}
                </div>
                <div style='font-size:0.75rem; color:#475569; font-weight:700; margin-bottom:10px;'>
                    {esc(especialidad)} · <b style='color:#002b5c;'>Cat {esc(categoria)}</b> · {esc(ciudad)}
                </div>
                <div class='kpi-sub' style='border-top:1px solid #f1f5f9; padding-top:6px;'>
                    <span>Prioridad:</span>
                    <b style='color:#059669;'>Prescriptor Clave ({dp_global.get('Pxs Mes', 0)} Pxs)</b>
                </div>
            </div>
        </div>
        """)

    render_html("""
        <div translate='no' style='text-align:center; margin: 18px 0 14px 0;'>
            <div style='font-size:1.08rem; font-weight:800; color:#0f172a; letter-spacing:0.02em;'>SELECCIONE EL MÓDULO DE INTELIGENCIA COMERCIAL</div>
            <div style='font-size:0.78rem; color:#64748b; font-weight:500;'>Navegue por las herramientas analíticas para optimizar la previsita, auditoría de médicos y correlación de recetas</div>
        </div>
        """)

    row1_m1, row1_m2 = st.columns(2)
    with row1_m1:
        render_html("""
            <div class='stitch-mod-card' translate='no'>
                <div class='mod-card-top'>
                    <div class='mod-icon-badge'>M1</div>
                    <div class='mod-code-tag'>MOD-01</div>
                </div>
                <div class='mod-card-title'>TOP MÉDICOS <span>(inf.target)</span></div>
                <div class='mod-card-desc'>
                    Visor BI Multifiltro de Clases y Auditoría Close-Up. Ranking de prescriptores, potencial individual y segmentación por categoría.
                </div>
            </div>
            """)
        st.button("Abrir Visor Multifiltro  →", key="btn_hub_m1", width="stretch", type="primary", on_click=ir_a_modulo, args=("TOP_MEDICOS",))

    with row1_m2:
        render_html("""
            <div class='stitch-mod-card' translate='no'>
                <div class='mod-card-top'>
                    <div class='mod-icon-badge' style='background:#f0fdf4; color:#15803d; border-color:#bbf7d0;'>TVP</div>
                    <div class='mod-code-tag'>MOD-02</div>
                </div>
                <div class='mod-card-title'>PREVISITA TVP <span>(inf.target)</span></div>
                <div class='mod-card-desc'>
                    Mapa de Mercado del facultativo, Canvas TVP estructurado de 4 cuadrantes, guion de visita con IA y auditoría médica 360.
                </div>
            </div>
            """)
        st.button("Preparar Guion & Canvas  →", key="btn_hub_m2", width="stretch", type="primary", on_click=ir_a_modulo, args=("PREVISITA",))

    st.write("")
    row2_m3, row2_m4 = st.columns(2)
    with row2_m3:
        render_html("""
            <div class='stitch-mod-card' translate='no'>
                <div class='mod-card-top'>
                    <div class='mod-icon-badge' style='background:#f5f3ff; color:#6d28d9; border-color:#ddd6fe;'>MKT</div>
                    <div class='mod-code-tag'>MOD-03</div>
                </div>
                <div class='mod-card-title'>ANÁLISIS MERCADO <span>(inf.market)</span></div>
                <div class='mod-card-desc'>
                    Penetración y cuota de receta por Especialidad Médica, radar de laboratorios competidores directos y dinamismo de marcas en el territorio.
                </div>
            </div>
            """)
        st.button("Explorar Radar de Mercado  →", key="btn_hub_m3", width="stretch", on_click=ir_a_modulo, args=("ANALISIS_MERCADO",))

    with row2_m4:
        render_html("""
            <div class='stitch-mod-card' translate='no'>
                <div class='mod-card-top'>
                    <div class='mod-icon-badge' style='background:#ecfdf5; color:#047857; border-color:#a7f3d0;'>6M</div>
                    <div class='mod-code-tag'>MOD-04</div>
                </div>
                <div class='mod-card-title'>EVOLUCIÓN <span>(inf.target)</span></div>
                <div class='mod-card-desc'>
                    Centro de Análisis Sell-Out vs. Cuota (May – Oct 2026), radar de apagones, simulador de cierre Pareto y sincronía con recetas Close-Up.
                </div>
            </div>
            """)
        st.button("Abrir Centro de Análisis Sell-Out  →", key="btn_hub_m4", width="stretch", on_click=ir_a_modulo, args=("EVOLUCION",))

    st.write("")
    render_html(f"""
        <div class='chira-neural-hero' translate='no' style='padding:16px 22px; margin-bottom:8px;'>
            <div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;'>
                <div>
                    <span class='chira-neural-badge'>✦ MOD-05 · CHIRA NEURAL ENGINE {esc(APP_VERSION)}</span>
                    <div style='font-size:1.05rem; font-weight:800; color:#ffffff;'>CHIRA — Copiloto Coloquial de Campo, Cuota &amp; Sell-Out Mensual</div>
                    <div style='font-size:0.78rem; color:#cbd5e1;'>Consultoría táctica en lenguaje natural sobre Close-Up, 15 objeciones reales, apagones, Pareto 80/20, abordaje a sucursales y CRM SQLite.</div>
                </div>
                <div class='hero-ok-pill'>12 Motores Activos</div>
            </div>
        </div>
        """)
    st.button("Iniciar Consola Cognitiva CHIRA & Bitácora CRM  →", key="btn_hub_m5", width="stretch", type="primary", on_click=ir_a_modulo, args=("CHIRA",))


# -----------------------------------------------------------------------------
# MÓDULO 1: TOP MÉDICOS & VISOR POWER BI MULTIFILTRO
# -----------------------------------------------------------------------------
elif st.session_state.modulo_activo == "TOP_MEDICOS":
    c_back, c_tit = st.columns([0.85, 3.15])
    with c_back:
        st.button("← Volver al Menú Principal", width="stretch", on_click=ir_a_modulo, args=("HUB",))
    with c_tit:
        render_html("""
            <div class='module-banner' translate='no'>
                <span>MÓDULO 1: TOP MÉDICOS (INF.TARGET) — VISOR POWER BI MULTIFILTRO, PROSPECCIÓN Y CONQUISTA</span>
                <span style='font-size:0.68rem; background:rgba(56,189,248,0.2); color:#7dd3fc; padding:3px 8px; border-radius:4px;'>VISTA INTERACTIVA</span>
            </div>
            """)

    st.markdown("<div class='subnav-label'>SELECCIONE LA VISTA ANALÍTICA (UNA COSA A LA VEZ):</div>", unsafe_allow_html=True)
    btm0, btm1, btm2, btm3 = st.columns(4)
    with btm0:
        if st.button("1. Evolución - Mercado (Visor BI)", width="stretch", type="primary" if st.session_state.sub_top_medicos == "BI_EVOLUCION" else "secondary"):
            st.session_state.sub_top_medicos = "BI_EVOLUCION"
            st.rerun()
    with btm1:
        if st.button("2. Ranking por Volumen de Recetas", width="stretch", type="primary" if st.session_state.sub_top_medicos == "RANKING" else "secondary"):
            st.session_state.sub_top_medicos = "RANKING"
            st.rerun()
    with btm2:
        if st.button("3. Mercados que Crecen (Mes vs. YTD)", width="stretch", type="primary" if st.session_state.sub_top_medicos == "CRECIMIENTO" else "secondary"):
            st.session_state.sub_top_medicos = "CRECIMIENTO"
            st.rerun()
    with btm3:
        if st.button("4. Médicos Fuera de Panel (Prospección)", width="stretch", type="primary" if st.session_state.sub_top_medicos == "FUERA_PANEL" else "secondary"):
            st.session_state.sub_top_medicos = "FUERA_PANEL"
            st.rerun()

    st.write("")

    if st.session_state.sub_top_medicos == "BI_EVOLUCION":
        if not df_auditoria_docs.empty:
            with st.container(border=True):
                c_hdr_f1, c_hdr_f2 = st.columns([3.0, 1.0])
                with c_hdr_f1:
                    st.markdown("<div class='subnav-label'>FILTROS CORPORATIVOS POWER BI (SELECTORES EN CASCADA):</div>", unsafe_allow_html=True)
                with c_hdr_f2:
                    f_solo_panel_bi = st.checkbox(
                        f"Solo Mi Panel ({VISITADOR_NOMBRE.split()[0]})",
                        value=(alcance_sb == ALCANCE_SOLO_PANEL),
                        key=f"bi_chk_panel_{'solo' if alcance_sb == ALCANCE_SOLO_PANEL else 'total'}",
                    )

                df_base_bi = df_auditoria_docs[df_auditoria_docs["Zona"] != "FUERA DE PANEL"].copy() if f_solo_panel_bi else df_auditoria_docs.copy()

                r1_c1, r1_c2, r1_c3, r1_c4 = st.columns([1.0, 1.5, 1.2, 1.0])
                zonas_bi = ["Todas"] + sorted([z for z in df_base_bi["Zona"].dropna().unique() if z not in ["", "NAN"]])
                meds_bi = ["Todas"] + sorted(df_base_bi["Médico"].dropna().unique().tolist())
                esps_bi = ["Todas"] + sorted(df_base_bi["Especialidad"].dropna().unique().tolist())
                viss_bi = ["Todas"] + sorted(df_base_bi["VISITADOR"].dropna().unique().tolist()) if "VISITADOR" in df_base_bi.columns else ["Todas", "CALDERON ERICK"]

                with r1_c1:
                    f_bi_zona = st.selectbox("ZONA:", zonas_bi, key="bi_f_zona")
                with r1_c2:
                    f_bi_med = st.selectbox("MÉDICO:", meds_bi, key="bi_f_med")
                with r1_c3:
                    f_bi_esp = st.selectbox("ESPECIALIDAD:", esps_bi, key="bi_f_esp")
                with r1_c4:
                    f_bi_vis = st.selectbox("VISITADOR:", viss_bi, index=0, key="bi_f_vis")

                df_casc = df_base_bi
                if f_bi_zona != "Todas":
                    df_casc = df_casc[df_casc["Zona"] == f_bi_zona]
                if f_bi_med != "Todas":
                    df_casc = df_casc[df_casc["Médico"] == f_bi_med]
                if f_bi_esp != "Todas":
                    df_casc = df_casc[df_casc["Especialidad"] == f_bi_esp]
                if f_bi_vis != "Todas" and "VISITADOR" in df_casc.columns:
                    df_casc = df_casc[df_casc["VISITADOR"] == f_bi_vis]

                r2_c1, r2_c2, r2_c3, r2_c4 = st.columns([1.4, 1.3, 1.1, 1.0])
                mers_bi_keys = ["Todas"] + LISTA_MERCADOS_GUTIS_KEYS + sorted(
                    [m for m in df_casc["Mercado_BI"].dropna().unique() if m not in LISTA_MERCADOS_GUTIS_KEYS and m not in ["", "OTROS MERCADOS"]]
                )
                with r2_c1:
                    f_bi_mer = st.selectbox(
                        "MERCADO:",
                        mers_bi_keys,
                        format_func=lambda k: "Todas" if k == "Todas" else (f"MR {MERCADOS_PRIORITARIOS[k]['producto']} ({k})" if k in MERCADOS_PRIORITARIOS else k),
                        key="bi_f_mer",
                    )
                if f_bi_mer != "Todas":
                    df_casc = df_casc[(df_casc["Clave_Gutis"] == f_bi_mer) | (df_casc["Mercado_BI"] == f_bi_mer)]

                marcas_bi = ["Todas"] + sorted(df_casc["MARCA"].dropna().unique().tolist())
                labs_bi = ["Todas"] + sorted(df_casc["Laboratorio"].dropna().unique().tolist())
                cats_bi = ["Todas"] + sorted(df_casc["Categoria_TAM"].dropna().astype(str).unique().tolist())

                with r2_c2:
                    f_bi_mar = st.selectbox("MARCA / PRODUCTO:", marcas_bi, key="bi_f_mar")
                with r2_c3:
                    f_bi_lab = st.selectbox("LABORATORIO:", labs_bi, key="bi_f_lab")
                with r2_c4:
                    f_bi_cat = st.selectbox("CATEGORÍA TAM:", cats_bi, key="bi_f_cat")

            df_bi_marcas, df_bi_medicos = _calcular_bi_cache(
                df_base_bi,
                df_auditoria_tot,
                f_zona=f_bi_zona,
                f_med=f_bi_med,
                f_esp=f_bi_esp,
                f_vis=f_bi_vis,
                f_mer=f_bi_mer,
                f_mar=f_bi_mar,
                f_lab=f_bi_lab,
                f_cat=f_bi_cat,
                df_prod=df_productos,
            )

            c_rad_bi, c_hint_bi = st.columns([1.8, 1.2])
            with c_rad_bi:
                modo_vista_bi = st.radio(
                    "NIVEL PRINCIPAL DE LA MATRIZ:",
                    ["1. Universo de Productos / Marcas (Competidores y % MS)", "2. Ranking de Médicos Prescriptores (% de Participación)"],
                    horizontal=True,
                )
            with c_hint_bi:
                st.caption("Selecciona cualquier marca o médico debajo para auditar el desglose hijo (+) y saltar a Previsita TVP.")

            cfg_cols_bi = {
                "% MS - LY": st.column_config.NumberColumn("% MS - LY", format="%.2f%%"),
                "% MS - Ytd": st.column_config.ProgressColumn("% MS - YTD", format="%.2f%%", min_value=0, max_value=100),
                "Dif %": st.column_config.NumberColumn("DIF %", format="%+.2f%%"),
                "% MS - TrasAnt": st.column_config.NumberColumn("% MS - TRASANT", format="%.2f%%"),
                "% MS - Ant": st.column_config.NumberColumn("% MS - ANT", format="%.2f%%"),
                "% MS - Mes": st.column_config.ProgressColumn("% MS - MES", format="%.2f%%", min_value=0, max_value=100),
            }

            if modo_vista_bi.startswith("1."):
                if not df_bi_marcas.empty:
                    df_m_show = df_bi_marcas.copy()
                    if "MARCA" in df_m_show.columns and not any(c.upper() == "ORIGEN" for c in df_m_show.columns):
                        s_norm_m = normalizar_serie_rapida(df_m_show["MARCA"])
                        df_m_show.insert(
                            1,
                            "Origen",
                            np.where(s_norm_m.str.contains(PATRON_REGEX_GUTIS, na=False), "GUTIS", "COMPETENCIA"),
                        )
                    st.dataframe(df_m_show, hide_index=True, width="stretch", height=390, column_config=cfg_cols_bi)

                    with st.container(border=True):
                        c_dh1, c_dh2 = st.columns([1.8, 1.2])
                        lista_m_hijo = df_bi_marcas["MARCA"].dropna().unique().tolist()
                        with c_dh1:
                            st.markdown(
                                "<div style='font-size:0.84rem; font-weight:800; color:#002b5c;'>● Desglose Hijo (+): ¿Qué médicos recetan esta Marca / Producto bajo los filtros actuales?</div>",
                                unsafe_allow_html=True,
                            )
                        with c_dh2:
                            marca_hijo_sel = st.selectbox("Marca en auditoría:", lista_m_hijo, label_visibility="collapsed", key="bi_hijo_marca")

                        _, df_meds_de_marca = _calcular_bi_cache(
                            df_base_bi,
                            df_auditoria_tot,
                            f_zona=f_bi_zona,
                            f_med=f_bi_med,
                            f_esp=f_bi_esp,
                            f_vis=f_bi_vis,
                            f_mer=f_bi_mer,
                            f_mar=marca_hijo_sel,
                            f_lab=f_bi_lab,
                            f_cat=f_bi_cat,
                            df_prod=df_productos,
                        )
                        if not df_meds_de_marca.empty:
                            st.dataframe(df_meds_de_marca, hide_index=True, width="stretch", height=260, column_config=cfg_cols_bi)
                            j_c1, j_c2 = st.columns([2.2, 1.0])
                            with j_c1:
                                doc_hijo_jump = st.selectbox(
                                    "Seleccionar médico de esta marca para ir a Previsita TVP:",
                                    df_meds_de_marca["Médico"].tolist(),
                                    key="bi_hijo_doc_jump",
                                )
                            with j_c2:
                                st.write("")
                                st.button(
                                    "Abrir en Previsita TVP →",
                                    type="primary",
                                    width="stretch",
                                    key="btn_bi_hijo_jump",
                                    on_click=ir_a_modulo,
                                    args=("PREVISITA", doc_hijo_jump),
                                )
                        else:
                            st.info("No hay prescriptores registrados para esta marca bajo los filtros actuales.")
                else:
                    st.info("No hay registros de marcas para los filtros seleccionados.")
            else:
                if not df_bi_medicos.empty:
                    st.dataframe(df_bi_medicos, hide_index=True, width="stretch", height=420, column_config=cfg_cols_bi)
                    doc_sel_bi = st.selectbox("Abrir especialista en Previsita TVP:", df_bi_medicos["Médico"].tolist(), key="bi_doc_jump")
                    st.button(
                        "Ir a Previsita TVP con este médico →",
                        type="primary",
                        on_click=ir_a_modulo,
                        args=("PREVISITA", doc_sel_bi),
                    )
                else:
                    st.info("No hay médicos para los filtros seleccionados.")
        else:
            st.warning("No se encontró el archivo de Close-Up (Clases y Auditoría.xlsx).")

    elif st.session_state.sub_top_medicos in ["RANKING", "FUERA_PANEL", "CRECIMIENTO"]:
        f1, f2, f3 = st.columns(3)
        with f1:
            tm_ciu = st.selectbox("Territorio:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="tm_ciu")
        with f2:
            tm_mer = st.selectbox(
                "Mercado:",
                ["TODOS LOS MERCADOS"] + LISTA_MERCADOS_GUTIS_KEYS,
                format_func=lambda k: "TODOS LOS MERCADOS" if k == "TODOS LOS MERCADOS" else MERCADOS_PRIORITARIOS[k]["producto"],
                key="tm_mer",
            )
        with f3:
            tm_esp = st.selectbox("Especialidad:", ["TODAS"] + LISTA_ESPECIALIDADES_REALES, key="tm_esp")

        if st.session_state.sub_top_medicos in ["RANKING", "FUERA_PANEL"]:
            modo_p = "FUERA_PANEL" if st.session_state.sub_top_medicos == "FUERA_PANEL" else "PANEL"
            df_rk = ranking_medicos(
                df_productos,
                df_panel,
                ciudad=None if tm_ciu == "TODO MI PANEL" else tm_ciu,
                especialidad=None if tm_esp == "TODAS" else tm_esp,
                mercado=None if tm_mer == "TODOS LOS MERCADOS" else tm_mer,
                modo_panel=modo_p,
            )
            if not df_rk.empty:
                c_k1, c_k2, c_k3 = st.columns(3)
                c_k1.metric("Médicos en Lista", f"{len(df_rk):,}")
                c_k2.metric("Recetas Gutis Mes", f"{int(df_rk['Gutis Mes'].sum()):,}")
                c_k3.metric("Recetas Competencia Mes (Oportunidad)", f"{int(df_rk['Comp Mes'].sum()):,}")
                show_table(df_rk, 430)

                with st.container(border=True):
                    drill_doc = st.selectbox("Seleccionar especialista para auditar su recetario completo:", df_rk["Médico"].tolist(), key="rk_drill")
                    show_table(productos_medico(df_productos, drill_doc), 260)
                    st.button(
                        "Preparar Visita en Previsita TVP →",
                        type="primary",
                        on_click=ir_a_modulo,
                        args=("PREVISITA", drill_doc),
                    )
            else:
                st.info("Sin registros en este ranking para los filtros seleccionados.")
        elif st.session_state.sub_top_medicos == "CRECIMIENTO":
            st.markdown(f"##### Dinamismo de Clases Terapéuticas ({tm_ciu})")
            df_crec = resumen_mercados(df_productos, df_panel, None if tm_ciu == "TODO MI PANEL" else tm_ciu, incluir_fuera_panel=False)
            if not df_crec.empty:
                show_table(df_crec, 450)
            else:
                st.info("Sin datos de crecimiento para esta selección.")

# -----------------------------------------------------------------------------
# PARTE 3: MÓDULO 2 — PREVISITA TVP (MAPA 3X3 + DRILL-DOWN, CANVAS, GUION Y 360)
# -----------------------------------------------------------------------------
elif st.session_state.modulo_activo == "PREVISITA":
    c_back, c_tit = st.columns([0.85, 3.15])
    with c_back:
        st.button("← Volver al Menú Principal", width="stretch", on_click=ir_a_modulo, args=("HUB",))
    with c_tit:
        render_html("""
            <div class='module-banner' translate='no'>
                <span>MÓDULO 2: PREVISITA TVP (INF.TARGET) — PREPARACIÓN EJECUTIVA PASO A PASO</span>
                <span style='font-size:0.68rem; background:rgba(56,189,248,0.2); color:#7dd3fc; padding:3px 8px; border-radius:4px;'>MODO TÁCTICO 1:1</span>
            </div>
            """)

    if not medico_sel:
        st.warning("Selecciona un especialista en la barra lateral izquierda para abrir su Previsita TVP.")
        st.stop()

    perfil_360_actual = leer_perfil_360(medico_sel, DB_PATH)
    sell_z = resumen_ventas_ciudad(df_ventas, ciudad)
    farmacias_aliadas_str = sell_z["top_farmacias"]

    claves_disponibles_med = [
        k for k, v in MERCADOS_PRIORITARIOS.items()
        if not (es_pediatra and not v.get("apto_pediatria", True))
    ]
    rx_med_raw = (
        df_productos[
            (df_productos["Médico"] == medico_sel) & (df_productos["Clave_Gutis"].isin(claves_disponibles_med))
        ].copy()
        if not df_productos.empty and "Médico" in df_productos.columns and "Clave_Gutis" in df_productos.columns
        else pd.DataFrame()
    )

    mercados_evaluados = []
    for k_m in claves_disponibles_med:
        meta_m = MERCADOS_PRIORITARIOS[k_m]
        grp_m = rx_med_raw[rx_med_raw["Clave_Gutis"] == k_m] if not rx_med_raw.empty else pd.DataFrame()
        pm = int(grp_m["Pxs-MES"].sum()) if not grp_m.empty and "Pxs-MES" in grp_m.columns else 0
        py = int(grp_m["Pxs-YTD"].sum()) if not grp_m.empty and "Pxs-YTD" in grp_m.columns else 0
        gm = int(grp_m[grp_m["Es_Gutis"]]["Pxs-MES"].sum()) if not grp_m.empty and "Pxs-MES" in grp_m.columns else 0
        gy = int(grp_m[grp_m["Es_Gutis"]]["Pxs-YTD"].sum()) if not grp_m.empty and "Pxs-YTD" in grp_m.columns else 0
        cm = max(pm - gm, 0)
        cy = max(py - gy, 0)
        msm = round((gm / pm * 100.0), 1) if pm > 0 else 0.0
        msy = round((gy / py * 100.0), 1) if py > 0 else 0.0
        diag_sc = diagnosticar_escala_adopcion(gm, pm, msm, gy, py, msy)

        rival_mes_top = 0
        if not grp_m.empty:
            grp_riv = grp_m[~grp_m["Es_Gutis"]].sort_values(by=["Pxs-MES", "Pxs-YTD"], ascending=False)
            if not grp_riv.empty:
                rival_mes_top = int(grp_riv.iloc[0]["Pxs-MES"])
                riv_str = f"{grp_riv.iloc[0]['NOMBRE_PRODUCTO']} ({int(grp_riv.iloc[0]['Pxs-MES'])}M / {int(grp_riv.iloc[0]['Pxs-YTD'])}Y)"
                riv_corto = str(grp_riv.iloc[0]["NOMBRE_PRODUCTO"])[:26]
            else:
                riv_str = f"Líder: {meta_m['producto']} ({msm:.0f}% MS)"
                riv_corto = f"{meta_m['producto']} ({msm:.0f}% MS)"
        else:
            riv_str = "Sin prescripciones registradas en corte"
            riv_corto = "Sin registro en corte"

        mercados_evaluados.append({
            "clave": k_m,
            "prod_gutis": meta_m["producto"],
            "clase_terapeutica": meta_m["clase_terapeutica"],
            "prioridad": meta_m.get("prioridad", 3),
            "tot_mes": pm,
            "gutis_mes": gm,
            "comp_mes": cm,
            "ms_mes": msm,
            "tot_ytd": py,
            "gutis_ytd": gy,
            "comp_ytd": cy,
            "ms_ytd": msy,
            "rival_mes_top": rival_mes_top,
            "meta_objetivo": calcular_meta_objetivo(cm),
            "escala_nivel": diag_sc["nivel"],
            "escala_meta": diag_sc["meta"],
            "modo_tactico": diag_sc["modo"],
            "paso_recomendado": diag_sc["accion"],
            "rival_principal": riv_str,
            "rival_corto": riv_corto,
            "meta_info": meta_m,
        })

    mercados_evaluados.sort(key=lambda x: (-(x["tot_mes"] * 10 + x["tot_ytd"]), x["prioridad"]))
    lista_base_p = mercados_evaluados if mercados_evaluados else []

    if not lista_base_p:
        st.info("Este especialista no tiene mercados evaluables en el corte actual.")
        st.stop()

    opciones_claves_p = [m["clave"] for m in lista_base_p]
    mapa_clave_obj = {m["clave"]: m for m in lista_base_p}

    idx1 = min(st.session_state.pos_m1_idx, max(len(opciones_claves_p) - 1, 0))
    idx2 = min(st.session_state.pos_m2_idx, max(len(opciones_claves_p) - 1, 0))
    if idx2 == idx1 and len(opciones_claves_p) > 1:
        idx2 = (idx1 + 1) % len(opciones_claves_p)
    idx3 = min(st.session_state.pos_m3_idx, max(len(opciones_claves_p) - 1, 0))
    if idx3 in (idx1, idx2) and len(opciones_claves_p) > 2:
        idx3 = next((i for i in range(len(opciones_claves_p)) if i not in (idx1, idx2)), 0)

    m_foco_top = lista_base_p[idx1]

    render_html(f"""
        <div class='kpi-strip' translate='no'>
            <div class='kpi-card' style='border-top: 3px solid #002b5c;'>
                <div class='kpi-lbl'>ESPECIALISTA EN FOCO</div>
                <div style='font-size:1.05rem; font-weight:800; color:#0f172a; margin:6px 0 4px 0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>
                    {esc(medico_sel)}
                </div>
                <div style='font-size:0.74rem; color:#475569; font-weight:700;'>
                    {esc(especialidad)} | Cat {esc(categoria)} | <span style='background:#e0f2fe; color:#0369a1; padding:1px 6px; border-radius:4px;'>{esc(ciudad)}</span>
                </div>
            </div>

            <div class='kpi-card' style='border-top: 3px solid #0284c7;'>
                <div class='kpi-lbl'>AUDITORÍA DE RECETAS (RX)</div>
                <div style='font-size:1.25rem; font-weight:800; color:#0f172a; margin:4px 0;'>
                    {dp_global.get('Pxs Mes', 0):,} Pxs Mes <span style='font-size:0.82rem; color:#0284c7;'>({dp_global.get('Pxs YTD', 0):,} YTD)</span>
                </div>
                <div style='font-size:0.74rem; color:#64748b; font-weight:600;'>
                    Gutis Mes: <b>{dp_global.get('Gutis Mes', 0)}</b> ({dp_global.get('Gutis YTD', 0)} YTD) | Comp Mes: <b>{dp_global.get('Comp Mes', 0)}</b>
                </div>
            </div>

            <div class='kpi-card' style='border-top: 3px solid #f59e0b;'>
                <div class='kpi-lbl'>FOCO PRIMARIO ({esc(m_foco_top['prod_gutis'].upper())})</div>
                <div style='font-size:1.05rem; font-weight:800; color:#0f172a; margin:6px 0 4px 0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>
                    {esc(m_foco_top['rival_corto'])}
                </div>
                <div style='font-size:0.74rem; color:#475569; font-weight:700;'>
                    Escala TVP: <span style='background:#fef3c7; color:#b45309; padding:2px 6px; border-radius:4px;'>{esc(m_foco_top['escala_nivel'])}</span>
                </div>
            </div>

            <div class='kpi-card' style='border-top: 3px solid #10b981;'>
                <div class='kpi-lbl'>SELL-OUT ZONAL ({esc(ciudad)} - {sell_z['pdvs']} PDV)</div>
                <div style='font-size:1.25rem; font-weight:800; color:#047857; margin:4px 0;'>
                    ${sell_z['total']:,.2f}
                </div>
                <div style='font-size:0.73rem; color:#64748b; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>
                    Aliadas: {esc(farmacias_aliadas_str)}
                </div>
            </div>
        </div>
        """)

    st.markdown("<div class='subnav-label'>SELECCIONE LA HERRAMIENTA DE PREVISITA:</div>", unsafe_allow_html=True)
    bp1, bp2, bp3, bp4 = st.columns(4)
    with bp1:
        if st.button("1. Mapa de Mercado del Especialista", width="stretch", type="primary" if st.session_state.sub_previsita == "MAPA" else "secondary"):
            st.session_state.sub_previsita = "MAPA"
            st.rerun()
    with bp2:
        if st.button("2. Canvas TVP (4 Cuadrantes)", width="stretch", type="primary" if st.session_state.sub_previsita == "CANVAS" else "secondary"):
            st.session_state.sub_previsita = "CANVAS"
            st.rerun()
    with bp3:
        if st.button("3. Mapa Conversacional del TVP", width="stretch", type="primary" if st.session_state.sub_previsita == "GUION" else "secondary"):
            st.session_state.sub_previsita = "GUION"
            st.rerun()
    with bp4:
        if st.button("4. Clases Terapéuticas, Labs & 360", width="stretch", type="primary" if st.session_state.sub_previsita == "AUDITORIA" else "secondary"):
            st.session_state.sub_previsita = "AUDITORIA"
            st.rerun()

    st.write("")

    if st.session_state.sub_previsita == "MAPA":
        with st.container(border=True):
            c_mh1, c_mh2 = st.columns([3.0, 1.0])
            with c_mh1:
                st.markdown(
                    "<div style='font-size:0.86rem; font-weight:800; color:#0f172a;'><span style='color:#0284c7;'>●</span> MAPA DE MERCADOS ACTIVOS DEL ESPECIALISTA (VADEMÉCUM NICARAGUA 2026)</div>",
                    unsafe_allow_html=True,
                )
            with c_mh2:
                st.markdown(
                    f"<div style='text-align:right;'><span style='background:#f1f5f9; color:#475569; font-size:0.72rem; font-weight:700; padding:3px 10px; border-radius:6px;'>{min(len(lista_base_p), 9)} Productos Monitoreados</span></div>",
                    unsafe_allow_html=True,
                )

            st.write("")
            top9_mercados = lista_base_p[:9]

            for row_start in range(0, len(top9_mercados), 3):
                cols_3 = st.columns(3)
                for offset in range(3):
                    idx_card = row_start + offset
                    if idx_card < len(top9_mercados):
                        m_it = top9_mercados[idx_card]
                        es_lealtad = m_it["modo_tactico"] == "LEALTAD"
                        es_lider_vol = (not es_lealtad) and (m_it["gutis_mes"] > 0) and (m_it["gutis_mes"] >= m_it["rival_mes_top"])

                        borde_top = "#10b981" if es_lealtad else ("#0284c7" if es_lider_vol else "#ef4444")
                        prio_lbl = f"P{m_it['prioridad']}"
                        bg_prio = "#002b5c" if m_it["prioridad"] == 1 else "#0284c7"

                        if es_lealtad:
                            linea_riv = f"<span style='color:#059669; font-weight:800;'>Líder Consolidado: {esc(m_it['prod_gutis'])} ({m_it['ms_mes']:.0f}% MS)</span>"
                            cta_txt = "Agradecer, Blindar y Puente"
                            cta_icon = "✓"
                            bg_esc = "#dcfce7"
                            col_esc = "#15803d"
                        elif es_lider_vol:
                            linea_riv = f"<span style='color:#0284c7; font-weight:800;'>Líder #1 ({m_it['ms_mes']:.0f}% MS)</span> · Rival: <b>{esc(m_it['rival_corto'])}</b>"
                            cta_txt = f"Consolidar liderazgo ({esc(m_it['prod_gutis'])})"
                            cta_icon = "★"
                            bg_esc = "#e0f2fe"
                            col_esc = "#0369a1"
                        else:
                            linea_riv = f"Rival: <b style='color:#b91c1c;'>{esc(m_it['rival_corto'])}</b>"
                            cta_txt = f"Impulsar {esc(m_it['prod_gutis'])}"
                            cta_icon = "→"
                            bg_esc = "#f1f5f9"
                            col_esc = "#1e293b"

                        with cols_3[offset]:
                            render_html(f"""
                                <div class='quad-card' translate='no' style='border-top: 4px solid {borde_top}; margin-bottom: 6px; padding: 14px 16px;'>
                                    <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>
                                        <span style='font-size:0.82rem; font-weight:800; color:#0f172a; text-transform:uppercase;'>{esc(m_it['prod_gutis'])}</span>
                                        <span style='background:{bg_prio}; color:#ffffff; font-size:0.65rem; font-weight:800; padding:2px 7px; border-radius:4px;'>{prio_lbl}</span>
                                    </div>
                                    <div style='font-size:0.78rem; color:#475569; margin-bottom:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>
                                        {linea_riv}
                                    </div>
                                    <div style='font-size:0.76rem; color:#64748b; margin-bottom:8px;'>
                                        Mes: <b style='color:#0f172a;'>{m_it['tot_mes']}</b> (Gutis: {m_it['gutis_mes']} | Comp: {m_it['comp_mes']})<br>
                                        YTD: <b style='color:#0f172a;'>{m_it['tot_ytd']}</b> (Gutis: {m_it['gutis_ytd']} | Comp: {m_it['comp_ytd']})
                                    </div>
                                    <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; font-size:0.74rem; color:#64748b;'>
                                        <span>Escala TVP:</span>
                                        <span style='background:{bg_esc}; color:{col_esc}; font-weight:800; padding:2px 8px; border-radius:4px;'>{esc(m_it['escala_nivel'])}</span>
                                    </div>
                                    <div style='border-top:1px dashed #e2e8f0; padding-top:6px; display:flex; justify-content:space-between; align-items:center; font-size:0.75rem; font-weight:800; color:#059669;'>
                                        <span>{cta_txt}</span>
                                        <span>{cta_icon}</span>
                                    </div>
                                </div>
                            """)
                            esta_abierto = st.session_state.mercado_drill_sel == m_it["clave"]
                            lbl_btn = f"Cerrar {m_it['prod_gutis']} ▲" if esta_abierto else f"Ver recetario {m_it['prod_gutis']} ↓"
                            if st.button(
                                lbl_btn,
                                key=f"btn_drill_{m_it['clave']}_{idx_card}",
                                width="stretch",
                                type="primary" if esta_abierto else "secondary",
                            ):
                                st.session_state.mercado_drill_sel = None if esta_abierto else m_it["clave"]
                                st.rerun()

            if st.session_state.mercado_drill_sel:
                k_drill = st.session_state.mercado_drill_sel
                info_drill = mapa_clave_obj.get(k_drill, {})
                prod_drill_lbl = info_drill.get("prod_gutis", k_drill)
                st.write("")
                with st.container(border=True):
                    cd1, cd2 = st.columns([4, 1])
                    with cd1:
                        st.markdown(
                            f"<div style='font-size:0.86rem; font-weight:800; color:#002b5c;'>📋 DETALLE DE PRESCRIPCIÓN EN LA CLASE: {esc(prod_drill_lbl.upper())} (GUTIS VS. COMPETENCIA)</div>",
                            unsafe_allow_html=True,
                        )
                    with cd2:
                        if st.button("Cerrar detalle ✕", key="btn_cerrar_drill_top", width="stretch"):
                            st.session_state.mercado_drill_sel = None
                            st.rerun()

                    df_drill = productos_medico(df_productos, medico_sel, criterio_mercado=k_drill)
                    if not df_drill.empty:
                        st.dataframe(
                            df_drill[["Marca Prescrita", "Origen", "Pxs Mes", "% MS Mes (Categoría)", "Pxs YTD", "% MS YTD (Categoría)"]],
                            width="stretch",
                            hide_index=True,
                        )
                    else:
                        st.info("Este médico aún no registra recetas auditadas en esta clase terapéutica.")

    elif st.session_state.sub_previsita == "CANVAS":
        with st.container(border=True):
            sp1, sp2, sp3 = st.columns(3)
            with sp1:
                k_p1 = st.selectbox(
                    "1RA POSICIÓN (FOCO / ANCLA):",
                    opciones_claves_p,
                    index=idx1,
                    format_func=lambda k: f"[{mapa_clave_obj[k]['modo_tactico']}] {mapa_clave_obj[k]['prod_gutis']} | Mes: {mapa_clave_obj[k]['tot_mes']} ({mapa_clave_obj[k]['ms_mes']:.1f}% MS) | YTD: {mapa_clave_obj[k]['tot_ytd']} ({mapa_clave_obj[k]['ms_ytd']:.1f}% MS)",
                    key="canvas_k_p1",
                )
                st.session_state.pos_m1_idx = opciones_claves_p.index(k_p1)
            with sp2:
                k_p2 = st.selectbox(
                    "2DA POSICIÓN (PUENTE CLÍNICO):",
                    opciones_claves_p,
                    index=idx2,
                    format_func=lambda k: f"[{mapa_clave_obj[k]['modo_tactico']}] {mapa_clave_obj[k]['prod_gutis']} | Mes: {mapa_clave_obj[k]['tot_mes']} ({mapa_clave_obj[k]['ms_mes']:.1f}% MS) | YTD: {mapa_clave_obj[k]['tot_ytd']} ({mapa_clave_obj[k]['ms_ytd']:.1f}% MS)",
                    key="canvas_k_p2",
                )
                st.session_state.pos_m2_idx = opciones_claves_p.index(k_p2)
            with sp3:
                k_p3 = st.selectbox(
                    "3RA POSICIÓN (RECORDACIÓN):",
                    opciones_claves_p,
                    index=idx3,
                    format_func=lambda k: f"[{mapa_clave_obj[k]['modo_tactico']}] {mapa_clave_obj[k]['prod_gutis']} | Mes: {mapa_clave_obj[k]['tot_mes']} ({mapa_clave_obj[k]['ms_mes']:.1f}% MS) | YTD: {mapa_clave_obj[k]['tot_ytd']} ({mapa_clave_obj[k]['ms_ytd']:.1f}% MS)",
                    key="canvas_k_p3",
                )
                st.session_state.pos_m3_idx = opciones_claves_p.index(k_p3)

            sc1, sc2 = st.columns(2)
            opciones_cita = ["Visita con cita previa", "Visita de pasillo (45 seg)", "Visita de improvisto"]
            opciones_ndn = [
                "Desempeño (Eficacia y adherencia clínica)",
                "Imagen (Prestigio clínico y satisfacción familiar)",
                "Finanzas (Economía del paciente y apego completo)",
            ]
            with sc1:
                st.session_state.ctx_cita_global = st.selectbox(
                    "CONTEXTO DE VISITA:",
                    opciones_cita,
                    index=opciones_cita.index(st.session_state.ctx_cita_global) if st.session_state.ctx_cita_global in opciones_cita else 0,
                    key="canvas_ctx_cita",
                )
            with sc2:
                st.session_state.ctx_ndn_global = st.selectbox(
                    "NECESIDAD DETRÁS DE LA NECESIDAD (NDN):",
                    opciones_ndn,
                    index=opciones_ndn.index(st.session_state.ctx_ndn_global) if st.session_state.ctx_ndn_global in opciones_ndn else 0,
                    key="canvas_ctx_ndn",
                )

        m_p1 = mapa_clave_obj[k_p1]
        m_p2 = mapa_clave_obj[k_p2]
        m_p3 = mapa_clave_obj[k_p3]
        meta1 = m_p1["meta_info"]
        meta2 = m_p2["meta_info"]
        riv1_marca, riv1_forma, _ = limpiar_sku_competencia(m_p1["rival_principal"])
        pac_meta_1 = meta1.get("paciente_meta_ped", meta1["paciente_meta"]) if es_pediatra else meta1["paciente_meta"]
        ndn_corto = st.session_state.ctx_ndn_global.split("(")[0].strip()
        arg_ndn_txt = (
            meta1["beneficio"]
            if "Desempeño" in ndn_corto
            else (meta1["arg_imagen"] if "Imagen" in ndn_corto else meta1["arg_finanzas"])
        )
        n_obj_p1 = m_p1["meta_objetivo"]
        txt_meta_smart = (
            f"Agradecer su confianza en <b>{esc(m_p1['prod_gutis'])}</b> y <b>{esc(texto_objetivo_clinico(n_obj_p1))}</b> "
            f"con este perfil clínico (categoría donde también figura <b>{esc(riv1_marca)}</b> en {esc(riv1_forma.lower())})."
            if n_obj_p1 > 0
            else f"Agradecer su respaldo en <b>{esc(m_p1['prod_gutis'])}</b> y <b>{esc(texto_objetivo_clinico(0))}</b>."
        )
        farmacia_top1 = farmacias_aliadas_str.split(",")[0].strip() if farmacias_aliadas_str else "Farmacia Aliada"

        q_col1, q_col2, q_col3, q_col4 = st.columns(4)
        with q_col1:
            render_html(f"""
                <div class='quad-card' translate='no' style='border-top: 4px solid #002b5c; min-height: 390px;'>
                    <div class='quad-title' style='color:#002b5c;'>I. DIAGNÓSTICO Y OBJETIVO SMART ({esc(m_p1['modo_tactico'])})</div>
                    <div class='quad-body'>
- <b>Escala Actual:</b><br>
                        <div style='background:#eff6ff; color:#002b5c; font-weight:700; padding:6px 8px; border-radius:6px; margin:4px 0;'>
                            {esc(m_p1['escala_nivel'])} ({m_p1['ms_mes']:.1f}% MS Mes | {m_p1['gutis_mes']} Pxs)
                        </div>
- <b>Escalón Meta Hoy:</b><br>
                        <div style='background:#dcfce7; color:#15803d; font-weight:700; padding:5px 8px; border-radius:6px; margin:4px 0 8px 0;'>
                            {esc(m_p1['escala_meta'])}
                        </div>
- <b>Meta SMART:</b> {txt_meta_smart}<br><br>
- <b>Plan de Respaldo:</b> Atender el subgrupo clínico de <i>{esc(meta1['nicho_flanqueo'])}</i>.
                    </div>
                </div>
                """)
        with q_col2:
            render_html(f"""
                <div class='quad-card' translate='no' style='border-top: 4px solid #0284c7; min-height: 390px;'>
                    <div class='quad-title' style='color:#0284c7;'>II. APERTURA ADAPTADA ({esc(especialidad)})</div>
                    <div class='quad-body'>
- <b>Postura ({esc(st.session_state.ctx_cita_global)}):</b> Explorar su experiencia positiva con los pacientes ya tratados con la molécula y formulación actual.<br><br>
- <b>Agenda ({esc(especialidad)}):</b> Analizar evolución clínica en <i>{esc(pac_meta_1)}</i>.<br><br>
- <b>Pregunta Sutil:</b><br>
                        <div style='background:#f8fafc; border-left:3px solid #0284c7; padding:8px; border-radius:4px; font-style:italic; margin-top:4px;'>
                            «En los casos donde ya prescribió {esc(m_p1['prod_gutis'])} frente a otras opciones como {esc(riv1_marca)}, ¿qué diferencias observó en tolerabilidad y apego?»
                        </div>
                    </div>
                </div>
                """)
        with q_col3:
            render_html(f"""
                <div class='quad-card' translate='no' style='border-top: 4px solid #10b981; min-height: 390px;'>
                    <div class='quad-title' style='color:#059669;'>III. EMBUDO, APOYO Y MENSAJE DE MARCA</div>
                    <div class='quad-body'>
- <b>Sondeo de Valor Clínico:</b><br>
                        <div style='background:#f8fafc; border-left:3px solid #10b981; padding:8px; border-radius:4px; font-style:italic; margin:4px 0 8px 0;'>
                            «¿En qué perfil específico de paciente suele alternar con opciones como {esc(riv1_marca)} en {esc(riv1_forma.lower())}?»
                        </div>
- <b>Ventaja Diferencial ({esc(m_p1['prod_gutis'])}):</b> {esc(meta1['caracteristica'])}.<br><br>
- <b>Enfoque ({esc(ndn_corto)}):</b> {esc(arg_ndn_txt.capitalize())}.
                    </div>
                </div>
                """)
        with q_col4:
            render_html(f"""
                <div class='quad-card' translate='no' style='border-top: 4px solid #f59e0b; min-height: 390px;'>
                    <div class='quad-title' style='color:#d97706;'>IV. CIERRE BILATERAL Y PUENTE P1 - P2 - P3</div>
                    <div class='quad-body'>
- <b>Propuesta Clínica:</b> Considerar a <b>{esc(m_p1['prod_gutis'])}</b> como primera alternativa en el perfil clínico evaluado.<br><br>
- <b>Mi Compromiso:</b><br>
                        <div style='background:#fffbeb; border:1px solid #fde68a; color:#92400e; font-weight:700; padding:6px 8px; border-radius:6px; margin:4px 0 8px 0;'>
                            Garantizar inventario en {esc(farmacia_top1)}.
                        </div>
- <b>Puente a 2da Posición ({esc(m_p2['prod_gutis'])}):</b><br>
                        <div style='background:#f8fafc; border-left:3px solid #f59e0b; padding:8px; border-radius:4px; font-style:italic; margin-top:4px;'>
                            «Y siguiendo con eficacia clínica, cuente con <b>{esc(m_p2['prod_gutis'])}</b> ({esc(meta2['beneficio'])}) y respaldo de <b>{esc(m_p3['prod_gutis'])}</b>.»
                        </div>
                    </div>
                </div>
                """)

    elif st.session_state.sub_previsita == "GUION":
        with st.container(border=True):
            st.markdown("<div class='subnav-label'>PARÁMETROS DE SELECCIÓN TÁCTICA:</div>", unsafe_allow_html=True)
            g_c1, g_c2, g_c3 = st.columns(3)
            with g_c1:
                k_p1_g = st.selectbox(
                    "PRODUCTO FOCO (1RA POSICIÓN):",
                    opciones_claves_p,
                    index=idx1,
                    format_func=lambda k: f"[{mapa_clave_obj[k]['modo_tactico']}] {mapa_clave_obj[k]['prod_gutis']} ({mapa_clave_obj[k]['ms_mes']:.1f}% MS)",
                    key="guion_sel_p1",
                )
                st.session_state.pos_m1_idx = opciones_claves_p.index(k_p1_g)
            with g_c2:
                cita_sel = st.selectbox(
                    "CONTEXTO DE VISITA:",
                    ["Visita con cita previa", "Visita de pasillo (45 seg)", "Visita de improvisto"],
                    key="guion_tipo_cita",
                )
            with g_c3:
                ndn_sel = st.selectbox(
                    "RESORTE PSICOLÓGICO (NDN):",
                    [
                        "Desempeño (Eficacia y adherencia clínica)",
                        "Imagen (Prestigio clínico y satisfacción familiar)",
                        "Finanzas (Economía del paciente y apego completo)",
                    ],
                    key="guion_ndn",
                )

            b_var1, b_var2 = st.columns([2.2, 1.0])
            with b_var1:
                if st.button(f"✦ Generar / Cambiar Variante Táctica de Guion   [VARIANTE A-{st.session_state.tvp_variant_counter + 1}]", type="primary", width="stretch"):
                    st.session_state.tvp_variant_counter += 1
                    st.rerun()
            with b_var2:
                btn_ia_guion = st.button("Potenciar Redacción con Gemini AI", width="stretch")

        n_claves = len(opciones_claves_p)
        i1g = min(st.session_state.pos_m1_idx, n_claves - 1)
        i2g = min(st.session_state.pos_m2_idx, n_claves - 1)
        i3g = min(st.session_state.pos_m3_idx, n_claves - 1)
        m_p1 = mapa_clave_obj[opciones_claves_p[i1g]]
        m_p2 = mapa_clave_obj[opciones_claves_p[i2g]]
        m_p3 = mapa_clave_obj[opciones_claves_p[i3g]]
        meta1 = m_p1["meta_info"]
        riv1_marca, riv1_forma, _ = limpiar_sku_competencia(m_p1["rival_principal"])
        pac_meta_1 = meta1.get("paciente_meta_ped", meta1["paciente_meta"]) if es_pediatra else meta1["paciente_meta"]
        vocativo_doc = formatear_nombre_medico(medico_sel)
        ndn_corto = ndn_sel.split("(")[0].strip()
        arg_ndn_txt = (
            meta1["beneficio"]
            if "Desempeño" in ndn_corto
            else (meta1["arg_imagen"] if "Imagen" in ndn_corto else meta1["arg_finanzas"])
        )
        n_obj_g = m_p1["meta_objetivo"]
        if n_obj_g > 0:
            frase_cierre_clinico = (
                f"¿consideramos a <b>{esc(m_p1['prod_gutis'])}</b> como alternativa terapéutica en "
                f"{'ese próximo paciente' if n_obj_g == 1 else f'sus próximos {n_obj_g} pacientes'} con este perfil clínico, "
                f"con disponibilidad garantizada en <b>{esc(farmacias_aliadas_str)}</b>?"
            )
        else:
            frase_cierre_clinico = (
                f"¿cómo seguimos consolidando la adherencia de sus pacientes actuales con disponibilidad garantizada en <b>{esc(farmacias_aliadas_str)}</b>?"
            )

        with st.container(border=True):
            render_html(f"""
                <div translate='no'>
                    <div style='font-size:1.05rem; font-weight:800; color:#0f172a; margin-bottom:2px;'>
                        Guion Táctico TVP — {esc(m_p1['modo_tactico'].capitalize())} ({esc(ndn_sel)})
                    </div>
                    <div style='font-size:0.78rem; color:#64748b; margin-bottom:14px;'>
                        Adaptado a la matriz de prescripción actual ({m_p1['gutis_mes']} Pxs {esc(m_p1['prod_gutis'])} vs. {m_p1['comp_mes']} Pxs competencia en el mes)
                    </div>

                    <div class='quad-card' style='margin-bottom:12px; border-left:4px solid #0284c7;'>
                        <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>
                            <div style='font-size:0.82rem; font-weight:800; color:#0f172a;'>
                                <span style='background:#e0f2fe; color:#0369a1; padding:2px 8px; border-radius:999px; margin-right:6px;'>1</span>
                                Apertura de Seguimiento Clínico ({esc(cita_sel)}):
                            </div>
                            <span style='background:#f1f5f9; color:#475569; font-size:0.68rem; font-weight:700; padding:2px 8px; border-radius:4px;'>Fase 1: Conexión</span>
                        </div>
                        <div style='background:#f8fafc; padding:10px 14px; border-radius:8px; font-style:italic; font-size:0.84rem; color:#1e293b;'>
                            «<b>{esc(vocativo_doc)}</b>, qué gusto saludarlo(a) en esta {esc(cita_sel.lower())}. Quiero agradecerle los pacientes que ya está tratando con <b>{esc(m_p1['prod_gutis'])} ({m_p1['gutis_mes']} en el mes / {m_p1['gutis_ytd']} en el año)</b> y proponerle revisar cómo consolidar la adherencia en <b>{esc(pac_meta_1.lower())}</b>. ¿Le parece bien?»
                        </div>
                    </div>

                    <div class='quad-card' style='margin-bottom:12px; border-left:4px solid #f59e0b;'>
                        <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>
                            <div style='font-size:0.82rem; font-weight:800; color:#0f172a;'>
                                <span style='background:#fef3c7; color:#b45309; padding:2px 8px; border-radius:999px; margin-right:6px;'>2</span>
                                Sondeo de Valor Mutuo (Perfil Clínico frente a {esc(riv1_marca)}):
                            </div>
                            <span style='background:#f1f5f9; color:#475569; font-size:0.68rem; font-weight:700; padding:2px 8px; border-radius:4px;'>Fase 2: Indagación</span>
                        </div>
                        <div style='background:#f8fafc; padding:10px 14px; border-radius:8px; font-style:italic; font-size:0.84rem; color:#1e293b;'>
                            «Al comparar la evolución de sus pacientes tratados con <b>{esc(m_p1['prod_gutis'])}</b> frente a los casos donde se emplean alternativas como <span style='background:#fef3c7; color:#92400e; font-weight:700; padding:1px 5px; border-radius:4px;'>{esc(riv1_marca)} ({esc(riv1_forma)}) ({m_p1['comp_mes']} recetas categoría en el mes)</span>, ¿en qué perfil específico considera prioritario optimizar la rapidez de acción y tolerabilidad?»
                        </div>
                    </div>

                    <div class='quad-card' style='margin-bottom:12px; border-left:4px solid #10b981;'>
                        <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>
                            <div style='font-size:0.82rem; font-weight:800; color:#0f172a;'>
                                <span style='background:#dcfce7; color:#15803d; padding:2px 8px; border-radius:999px; margin-right:6px;'>3</span>
                                Apoyo Galénico Diferencial y Love Brand:
                            </div>
                            <span style='background:#f1f5f9; color:#475569; font-size:0.68rem; font-weight:700; padding:2px 8px; border-radius:4px;'>Fase 3: Argumentación Galénica</span>
                        </div>
                        <div style='background:#f8fafc; padding:10px 14px; border-radius:8px; font-style:italic; font-size:0.84rem; color:#1e293b;'>
                            «Comprendo su criterio, <b>{esc(vocativo_doc)}</b>. Justamente para atender también a ese subgrupo de <b>{esc(meta1['nicho_flanqueo'])}</b>, <b>{esc(m_p1['prod_gutis'])}</b> cuenta con <b>{esc(meta1['caracteristica'])}</b>, con lo cual <b>{esc(arg_ndn_txt)}</b>. <i>{esc(meta1['love_brand'])}</i>»
                        </div>
                    </div>

                    <div class='quad-card' style='border-left:4px solid #002b5c;'>
                        <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>
                            <div style='font-size:0.82rem; font-weight:800; color:#0f172a;'>
                                <span style='background:#e0e7ff; color:#1e40af; padding:2px 8px; border-radius:999px; margin-right:6px;'>4</span>
                                Acuerdo Clínico y Puente hacia {esc(m_p2['prod_gutis'])}:
                            </div>
                            <span style='background:#f1f5f9; color:#475569; font-size:0.68rem; font-weight:700; padding:2px 8px; border-radius:4px;'>Fase 4: Acuerdo SMART &amp; Puente</span>
                        </div>
                        <div style='background:#f8fafc; padding:10px 14px; border-radius:8px; font-style:italic; font-size:0.84rem; color:#1e293b;'>
                            «Ya que conoce de primera mano la respuesta de <b>{esc(m_p1['prod_gutis'])}</b>, {frase_cierre_clinico} Y como puente clínico, recuerde que cuenta también con <b>{esc(m_p2['prod_gutis'])}</b> ({esc(m_p2['meta_info']['beneficio'])}) y <b>{esc(m_p3['prod_gutis'])}</b>.»
                        </div>
                    </div>
                </div>
                """)

        guion_base = construir_guion_tvp_dinamico(
            medico_raw=medico_sel,
            especialidad=especialidad,
            ciudad=ciudad,
            m_primario=m_p1,
            prod2=m_p2["prod_gutis"],
            benef2=m_p2["meta_info"]["beneficio"],
            rival2_raw=m_p2["rival_principal"],
            prod3=m_p3["prod_gutis"],
            tipo_cita_sel=cita_sel,
            nec_detras_sel=ndn_sel,
            top_farmacias_str=farmacias_aliadas_str,
            num_variante=st.session_state.tvp_variant_counter,
            notas_rapport="",
        )

        if btn_ia_guion:
            if obtener_api_key():
                with st.spinner("Gemini AI está estructurando una versión ejecutiva personalizada del guion TVP..."):
                    prompt_tvp = (
                        f"Mejora la redacción de este guion TVP para {medico_sel} ({especialidad} en {ciudad}) "
                        f"con tono ético, consultivo y basado en valor clínico, respetando las 4 etapas y sin alterar "
                        f"los porcentajes ni las cifras de recetas Close-Up:\n\n{guion_base}"
                    )
                    resp_ia = llamar_gemini(prompt_tvp, max_tok=2200)
                    if resp_ia:
                        if respuesta_ia_conserva_cifras(resp_ia, guion_base):
                            st.info("Versión Generada por Gemini AI:")
                            st.markdown(resp_ia)
                        else:
                            st.warning("La versión de IA alteró métricas de auditoría (%, Pxs o $). Se mantiene el guion calculado localmente.")
                    else:
                        st.warning("Gemini no devolvió respuesta. Se mantiene el guion calculado localmente.")
            else:
                st.warning("No se detectó GEMINI_API_KEY configurada. Se muestran las 4 fases tácticas locales.")

        st.write("")
        st.download_button(
            "Descargar Guion TVP (.md)",
            data=guion_base.encode("utf-8"),
            file_name=f"Guion_TVP_{medico_sel.replace(' ', '_')}.md",
            mime="text/markdown",
            width="stretch",
        )

    elif st.session_state.sub_previsita == "AUDITORIA":
        ba1, ba2, ba3, ba4 = st.columns(4)
        with ba1:
            if st.button("A. Matriz Clases Terapéuticas (LY/YTD/Mes)", width="stretch", type="primary" if st.session_state.sub_previsita_auditoria == "CLASES" else "secondary"):
                st.session_state.sub_previsita_auditoria = "CLASES"
                st.rerun()
        with ba2:
            if st.button("B. Marcas por Categoría Terapéutica", width="stretch", type="primary" if st.session_state.sub_previsita_auditoria == "MARCAS" else "secondary"):
                st.session_state.sub_previsita_auditoria = "MARCAS"
                st.rerun()
        with ba3:
            if st.button("C. Radar de Laboratorios (Doble Barra)", width="stretch", type="primary" if st.session_state.sub_previsita_auditoria == "LABS" else "secondary"):
                st.session_state.sub_previsita_auditoria = "LABS"
                st.rerun()
        with ba4:
            if st.button("D. Ficha de Omnicanalidad 360", width="stretch", type="primary" if st.session_state.sub_previsita_auditoria == "FICHA360" else "secondary"):
                st.session_state.sub_previsita_auditoria = "FICHA360"
                st.rerun()

        st.write("")

        if st.session_state.sub_previsita_auditoria == "CLASES":
            df_mat_ct = obtener_matriz_clases_terapeuticas_medico(df_clases, df_productos, medico_sel)
            render_html(f"""
                <div translate='no' style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>
                    <div style='font-size:0.88rem; font-weight:800; color:#0f172a;'><span style='color:#0284c7;'>●</span> Matriz Corporativa de Clases Terapéuticas — Dr(a). {esc(medico_sel)}</div>
                    <span style='background:#eff6ff; color:#0284c7; font-size:0.72rem; font-weight:700; padding:3px 10px; border-radius:6px;'>Fuente: Close-Up Audit · {len(df_mat_ct)} Registros Activos</span>
                </div>
                """)
            show_table(df_mat_ct, 440)

        elif st.session_state.sub_previsita_auditoria == "MARCAS":
            st.markdown(f"##### Desglose Completo de Marcas Prescritas por {medico_sel}")
            show_table(productos_medico(df_productos, medico_sel), 440)

        elif st.session_state.sub_previsita_auditoria == "LABS":
            st.markdown(f"##### Radar de Laboratorios en el Recetario de {medico_sel} (Doble Barra: % MS Mes vs. % MS YTD)")
            df_lab_doc = radar_laboratorios(df_labs, df_panel, medico=medico_sel)
            show_table(df_lab_doc, 420)

        elif st.session_state.sub_previsita_auditoria == "FICHA360":
            col_f360_l, col_f360_r = st.columns([1.2, 1.2])
            with col_f360_l:
                st.markdown("##### Ficha Omnicanal 360 del Especialista (Guardado Seguro SQLite)")
                with st.form("form_ficha_360_previsita"):
                    f_minsa = st.text_input("Código MINSA:", value=str(perfil_360_actual.get("MINSA") or ""))
                    f_cel = st.text_input("Celular / WhatsApp:", value=str(perfil_360_actual.get("Celular") or ""))
                    f_cumple = st.text_input("Cumpleaños (DD/MM):", value=str(perfil_360_actual.get("Cumpleaños") or ""))
                    estilos_op = ["Científica / Basada en Evidencia", "Ultra-ejecutiva (Al grano)", "Casos Clínicos / Práctica", "Relacional / Empática"]
                    est_act = perfil_360_actual.get("Estilo_Visita")
                    idx_est = estilos_op.index(est_act) if est_act in estilos_op else 0
                    f_estilo = st.selectbox("Estilo de Visita Preferido:", estilos_op, index=idx_est)
                    f_deporte = st.text_area(
                        "Afinidad / Hobby / Notas Personales de Rapport:",
                        value=str(perfil_360_actual.get("Deporte") or ""),
                        height=90,
                    )
                    guardar_360_btn = st.form_submit_button("Guardar Ficha 360 en Base de Datos", type="primary", width="stretch")

                if guardar_360_btn:
                    guardar_perfil_360(
                        {
                            "Médico": medico_sel,
                            "MINSA": f_minsa,
                            "Celular": f_cel,
                            "Cumpleaños": f_cumple,
                            "Deporte": f_deporte,
                            "Estilo_Visita": f_estilo,
                            "Ultima_Actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        },
                        DB_PATH,
                    )
                    st.toast("✅ Ficha 360 guardada correctamente en gutis_bi.db.")
                    time.sleep(1.5)
                    st.rerun()

            with col_f360_r:
                st.markdown("##### Últimas Visitas Registradas a este Médico (SQLite)")
                df_vis_med = leer_visitas(medico_sel, DB_PATH)
                if not df_vis_med.empty:
                    show_table(df_vis_med[["Fecha", "Producto_Foco", "Producto_Puente", "Escala_TVP", "Acuerdo_Medico"]], 320)
                else:
                    st.info("Aún no hay visitas registradas en el CRM para este especialista.")

# -----------------------------------------------------------------------------
# PARTE 4: MÓDULO 3 (ANÁLISIS MERCADO), MÓDULO 4 (CENTRO SELL-OUT 6M) Y MÓDULO 5 (CHIRA & CRM)
# -----------------------------------------------------------------------------
elif st.session_state.modulo_activo == "ANALISIS_MERCADO":
    c_back, c_tit = st.columns([0.85, 3.15])
    with c_back:
        st.button("← Volver al Menú Principal", width="stretch", on_click=ir_a_modulo, args=("HUB",))
    with c_tit:
        render_html("""
            <div class='module-banner' translate='no'>
                <span>MÓDULO 3: ANÁLISIS DE MERCADO (INF.MARKET) — CLASES TERAPÉUTICAS Y DOBLE BARRA MES / YTD</span>
                <span style='font-size:0.68rem; background:rgba(56,189,248,0.2); color:#7dd3fc; padding:3px 8px; border-radius:4px;'>AUDITORÍA CLOSE-UP</span>
            </div>
            """)

    bam1, bam2, bam3, bam4 = st.columns(4)
    with bam1:
        if st.button("1. Radar de Laboratorios (% MS Mes vs. YTD)", width="stretch", type="primary" if st.session_state.sub_analisis_mercado == "LABS" else "secondary"):
            st.session_state.sub_analisis_mercado = "LABS"
            st.rerun()
    with bam2:
        if st.button("2. Matriz de Penetración por Especialidad", width="stretch", type="primary" if st.session_state.sub_analisis_mercado == "PENETRACION" else "secondary"):
            st.session_state.sub_analisis_mercado = "PENETRACION"
            st.rerun()
    with bam3:
        if st.button("3. Desempeño Mercados Prioritarios", width="stretch", type="primary" if st.session_state.sub_analisis_mercado == "MERCADOS" else "secondary"):
            st.session_state.sub_analisis_mercado = "MERCADOS"
            st.rerun()
    with bam4:
        if st.button("4. Close-Up por Marca Competidora", width="stretch", type="primary" if st.session_state.sub_analisis_mercado == "AUDITORIA_MARCAS" else "secondary"):
            st.session_state.sub_analisis_mercado = "AUDITORIA_MARCAS"
            st.rerun()

    st.write("")

    if st.session_state.sub_analisis_mercado == "LABS":
        with st.container(border=True):
            fl1, fl2, fl3 = st.columns(3)
            with fl1:
                am_ciu = st.selectbox("1. Territorio / Ciudad:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="am_lab_ciu")
            with fl2:
                am_esp = st.selectbox("2. Especialidad:", ["TODAS"] + LISTA_ESPECIALIDADES_REALES, key="am_lab_esp")
            with fl3:
                am_alc = st.selectbox("3. Nivel de Radar de Laboratorios:", ["Agregado Territorial / Especialidad", f"Solo Médico Activo ({medico_sel})"], key="am_lab_alc")

        doc_filtro_lab = medico_sel if am_alc.startswith("Solo") else None
        df_rk_labs = radar_laboratorios(
            df_labs,
            df_panel,
            ciudad=None if am_ciu == "TODO MI PANEL" else am_ciu,
            especialidad=None if am_esp == "TODAS" else am_esp,
            medico=doc_filtro_lab,
        )

        if not df_rk_labs.empty:
            df_rk_labs = df_rk_labs.reset_index(drop=True)
            fila_gut = df_rk_labs[df_rk_labs["Laboratorio"].str.contains("GUTIS", case=False, na=False)]
            pos_gut = int(fila_gut.index[0]) + 1 if not fila_gut.empty else 0
            ms_m_gut = float(fila_gut.iloc[0]["% MS Mes"]) if not fila_gut.empty else 0.0
            ms_y_gut = float(fila_gut.iloc[0]["% MS YTD"]) if not fila_gut.empty else 0.0
            delta_gut = round(ms_m_gut - ms_y_gut, 2)

            render_html(f"""
                <div class='quad-card' translate='no' style='margin-bottom:12px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;'>
                    <div style='display:flex; align-items:center; gap:12px;'>
                        <div style='width:34px; height:34px; border-radius:8px; background:#002b5c; color:#fff; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:0.85rem;'>{len(df_rk_labs)}</div>
                        <div>
                            <div style='font-size:0.88rem; font-weight:800; color:#0f172a;'>RANKING DE LABORATORIOS AUDITADOS EN MERCADO OBJETIVO</div>
                            <div style='font-size:0.74rem; color:#64748b;'>Doble métrica de cuota: Participación en el Mes Actual (% MS) vs. Histórico Anual Acumulado (% MS YTD)</div>
                        </div>
                    </div>
                    <div style='display:flex; align-items:center; gap:10px;'>
                        <span style='background:#eff6ff; border:1px solid #bfdbfe; color:#002b5c; font-size:0.74rem; font-weight:800; padding:5px 12px; border-radius:6px;'>
                            Posición #{pos_gut if pos_gut > 0 else '-'}: [GUTIS] {ms_m_gut:.2f}% MS Mes ({delta_gut:+.2f} pp vs YTD)
                        </span>
                    </div>
                </div>
                """)

            df_labs_vista = df_rk_labs.copy()
            if "% MS Mes" in df_labs_vista.columns and "% MS YTD" in df_labs_vista.columns and "Delta MS (Mes vs YTD)" not in df_labs_vista.columns:
                df_labs_vista["Delta MS (Mes vs YTD)"] = (df_labs_vista["% MS Mes"] - df_labs_vista["% MS YTD"]).round(2)

            show_table(df_labs_vista, 440)

            tot_px_m_all = int(df_rk_labs["Pxs Mes"].sum()) if "Pxs Mes" in df_rk_labs.columns else 0
            tot_px_y_all = int(df_rk_labs["Pxs YTD"].sum()) if "Pxs YTD" in df_rk_labs.columns else 0
            clase_delta_tot = "background:#dcfce7; color:#15803d;" if delta_gut >= 0 else "background:#fee2e2; color:#b91c1c;"
            render_html(f"""
                <div class='stitch-nav-header' translate='no' style='margin-top:8px; background:#f8fafc;'>
                    <div style='font-size:0.78rem; font-weight:800; color:#0f172a;'>TOTAL AUDITORÍA SELECCIÓN</div>
                    <div style='display:flex; gap:22px; font-size:0.78rem; font-weight:700; color:#334155;'>
                        <span>Volumen Mes: <b>{tot_px_m_all:,} Pxs</b></span>
                        <span>Volumen YTD: <b>{tot_px_y_all:,} Pxs</b></span>
                        <span>Cuota Gutis: <b>{ms_m_gut:.2f}% Mes | {ms_y_gut:.2f}% YTD</b></span>
                        <span style='{clase_delta_tot} padding:2px 8px; border-radius:4px;'>{delta_gut:+.2f} pp</span>
                    </div>
                </div>
                """)
        else:
            st.info("No hay registros de laboratorios para esta combinación.")

    elif st.session_state.sub_analisis_mercado == "PENETRACION":
        pen_ciu = st.selectbox("Filtrar Territorio de Mi Panel:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="am_pen_ciu")
        df_pan_sub = df_panel if pen_ciu == "TODO MI PANEL" else df_panel[df_panel["CIUDAD"] == pen_ciu]
        df_rend_esp, df_top5_esp = matriz_penetracion(df_pan_sub, df_labs)

        st.markdown(f"##### 1. Matriz de Cobertura, Penetración y Posicionamiento por Especialidad (Panel {VISITADOR_NOMBRE})")
        show_table(df_rend_esp, 360)

        st.markdown("##### 2. Top 5 Laboratorios Dominantes por Especialidad (Cuota Mes | YTD)")
        show_table(df_top5_esp, 340)

    elif st.session_state.sub_analisis_mercado == "MERCADOS":
        mp_c1, mp_c2 = st.columns([1.2, 1.2])
        with mp_c1:
            mp_ciu = st.selectbox("Territorio:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="am_mp_ciu")
        with mp_c2:
            mp_univ = st.selectbox("Universo:", [f"Solo Mi Panel ({VISITADOR_NOMBRE})", "Universo Total Nicaragua"], key="am_mp_univ")

        df_mp = resumen_mercados(
            df_productos,
            df_panel,
            ciudad=None if mp_ciu == "TODO MI PANEL" else mp_ciu,
            incluir_fuera_panel=not mp_univ.startswith("Solo"),
        )
        if not df_mp.empty:
            show_table(df_mp, 420)
            with st.container(border=True):
                k_sel_mp = st.selectbox(
                    "Auditar médicos prescriptores de la marca:",
                    df_mp["Clave"].tolist(),
                    format_func=lambda k: f"{MERCADOS_PRIORITARIOS[k]['producto']} — {MERCADOS_PRIORITARIOS[k]['clase_terapeutica']}",
                    key="am_mp_drill",
                )
                df_rk_mp = ranking_medicos(
                    df_productos,
                    df_panel,
                    ciudad=None if mp_ciu == "TODO MI PANEL" else mp_ciu,
                    mercado=k_sel_mp,
                    modo_panel="PANEL" if mp_univ.startswith("Solo") else "TODOS",
                )
                show_table(df_rk_mp, 320)
        else:
            st.info("No hay datos disponibles para estos filtros.")

    elif st.session_state.sub_analisis_mercado == "AUDITORIA_MARCAS":
        au1, au2, au3 = st.columns(3)
        zonas_au = ["Todas"] + sorted([z for z in df_auditoria_docs["Zona"].dropna().unique() if z not in ["", "NAN"]]) if not df_auditoria_docs.empty else ["Todas"]
        esps_au = ["Todas"] + sorted(df_auditoria_docs["Especialidad"].dropna().unique().tolist()) if not df_auditoria_docs.empty else ["Todas"]
        with au1:
            z_au = st.selectbox("Zona:", zonas_au, key="am_au_zona")
        with au2:
            e_au = st.selectbox("Especialidad:", esps_au, key="am_au_esp")
        with au3:
            m_au = st.selectbox(
                "Mercado Prioritario:",
                ["Todos"] + LISTA_MERCADOS_GUTIS_KEYS,
                format_func=lambda k: "Todos" if k == "Todos" else MERCADOS_PRIORITARIOS[k]["producto"],
                key="am_au_mer",
            )
        df_au_res = auditoria_marcas(df_auditoria_docs, df_auditoria_tot, zona=z_au, medico="Todos", especialidad=e_au, mercado=m_au)
        show_table(df_au_res, 460)


# -----------------------------------------------------------------------------
# MÓDULO 4: CENTRO DE ANÁLISIS SELL-OUT VS. CUOTA (6M) & SINCRONÍA CLOSE-UP
# -----------------------------------------------------------------------------
elif st.session_state.modulo_activo == "EVOLUCION":
    c_back, c_tit = st.columns([0.85, 3.15])
    with c_back:
        st.button("← Volver al Menú Principal", width="stretch", on_click=ir_a_modulo, args=("HUB",))
    with c_tit:
        render_html("""
            <div class='module-banner' translate='no'>
                <span>MÓDULO 4: EVOLUCIÓN — CENTRO DE ANÁLISIS SELL-OUT VS. CUOTA &amp; RECETAS CLOSE-UP</span>
                <span style='font-size:0.68rem; background:rgba(16,185,129,0.25); color:#6ee7b7; padding:3px 8px; border-radius:4px;'>AUDITORÍA MENSUAL 6M</span>
            </div>
            """)

    bev1, bev2 = st.columns(2)
    with bev1:
        if st.button("1. Centro de Análisis Sell-Out vs. Cuota (May – Oct 2026)", width="stretch", type="primary" if st.session_state.sub_evolucion == "SINCRONIA" else "secondary"):
            st.session_state.sub_evolucion = "SINCRONIA"
            st.rerun()
    with bev2:
        if st.button("2. Sincronía con Cuota Prescriptiva Close-Up (Mes vs. YTD)", width="stretch", type="primary" if st.session_state.sub_evolucion == "PDVS" else "secondary"):
            st.session_state.sub_evolucion = "PDVS"
            st.rerun()

    st.write("")

    if st.session_state.sub_evolucion == "SINCRONIA":
        render_centro_analisis(DATA_DIR, BASE_DIR)
    else:
        ev_ciu = st.selectbox("Seleccionar Territorio Close-Up:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="ev_sel_ciu_rx")
        df_ev_rx = resumen_mercados(df_productos, df_panel, None if ev_ciu == "TODO MI PANEL" else ev_ciu, incluir_fuera_panel=False)
        if not df_ev_rx.empty:
            df_ev_tabla = df_ev_rx.copy()
            df_ev_tabla["Prioridad"] = df_ev_tabla["Clave"].map(lambda k: f"P{MERCADOS_PRIORITARIOS.get(k, {}).get('prioridad', 2)}")
            df_ev_tabla["Delta % MS (Mes vs YTD)"] = (df_ev_tabla["% MS Mes"] - df_ev_tabla["% MS YTD"]).round(2)
            df_ev_tabla["Diagnóstico de Evolución"] = np.where(
                df_ev_tabla["Delta % MS (Mes vs YTD)"] >= 1.0,
                "▲ CRECE CUOTA (" + df_ev_tabla["Delta % MS (Mes vs YTD)"].map(lambda x: f"{x:+.1f} pp vs YTD") + ")",
                np.where(
                    df_ev_tabla["Delta % MS (Mes vs YTD)"] <= -1.0,
                    "▼ PIERDE CUOTA (" + df_ev_tabla["Delta % MS (Mes vs YTD)"].map(lambda x: f"{x:+.1f} pp vs YTD") + ")",
                    "● ESTABLE (" + df_ev_tabla["Delta % MS (Mes vs YTD)"].map(lambda x: f"{x:+.1f} pp vs YTD") + ")",
                ),
            )
            cols_orden_ev = [
                "Prioridad", "Marca Gutis", "Clase Terapéutica",
                "Mercado Mes", "Gutis Mes", "Competencia Mes", "% MS Mes",
                "Mercado YTD", "Gutis YTD", "Competencia YTD", "% MS YTD",
                "Delta % MS (Mes vs YTD)", "Diagnóstico de Evolución",
            ]
            show_table(df_ev_tabla[[c for c in cols_orden_ev if c in df_ev_tabla.columns]], 430)
        else:
            st.info("Sin registros Close-Up para este territorio.")


# -----------------------------------------------------------------------------
# MÓDULO 5: CONSOLA COGNITIVA CHIRA NEURAL ENGINE & BITÁCORA CRM SQLITE
# -----------------------------------------------------------------------------
elif st.session_state.modulo_activo == "CHIRA":
    c_back, c_tit = st.columns([0.85, 3.15])
    with c_back:
        st.button("← Volver al Menú Principal", width="stretch", on_click=ir_a_modulo, args=("HUB",))
    with c_tit:
        render_html(f"""
            <div class='module-banner' translate='no'>
                <span>MÓDULO 5: CHIRA {esc(APP_VERSION)} — COPILOTO COLOQUIAL DE CAMPO, CUOTA &amp; SELL-OUT MENSUAL</span>
                <span style='font-size:0.68rem; background:rgba(16,185,129,0.25); color:#6ee7b7; padding:3px 8px; border-radius:4px;'>● 12 MOTORES TÁCTICOS ACTIVOS</span>
            </div>
            """)

    bch1, bch2 = st.columns(2)
    with bch1:
        if st.button("1. Consola Copiloto CHIRA (Lenguaje Natural, Voz y Auditoría)", width="stretch", type="primary" if st.session_state.sub_chira == "COPILOTO" else "secondary"):
            st.session_state.sub_chira = "COPILOTO"
            st.rerun()
    with bch2:
        if st.button(f"2. Bitácora CRM Post-Visita ({medico_sel[:24] if medico_sel else 'SQLite'})", width="stretch", type="primary" if st.session_state.sub_chira == "CRM" else "secondary"):
            st.session_state.sub_chira = "CRM"
            st.rerun()

    st.write("")

    if st.session_state.sub_chira == "COPILOTO":
        sell_z_chira = resumen_ventas_ciudad(df_ventas, ciudad)

        render_html(f"""
            <div class='chira-neural-hero' translate='no'>
                <div style='display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:16px;'>
                    <div style='flex: 1 1 380px;'>
                        <span class='chira-neural-badge'>● CHIRA NEURAL ENGINE {esc(APP_VERSION)} · CLOSE-UP + SELL-OUT MENSUAL</span>
                        <div style='font-size:1.35rem; font-weight:800; color:#ffffff; margin-bottom:6px;'>
                            Copiloto Táctico Coloquial &amp; Inteligencia de Cuota <span style='color:#38bdf8; font-size:0.88rem;'>✦ Enterprise AI</span>
                        </div>
                        <div style='font-size:0.8rem; color:#cbd5e1; line-height:1.45;'>
                            Háblale natural por voz o texto sobre cualquiera de tus marcas: detecta médicos con caída, responde 15 objeciones reales, detecta apagones, calcula Pareto 80/20, prioriza sucursales y cruza recetas contra venta mensual.
                        </div>
                    </div>
                    <div class='chira-mem-grid' style='flex: 1 1 420px; margin-top:0;'>
                        <div class='chira-mem-box'>
                            <div class='chira-mem-lbl'>MÉDICO EN FOCO</div>
                            <div class='chira-mem-val'>{esc(medico_sel[:22]) if medico_sel else 'Panel General'}</div>
                            <div class='chira-mem-sub'>Cat {esc(categoria)} · {esc(ciudad)}</div>
                        </div>
                        <div class='chira-mem-box'>
                            <div class='chira-mem-lbl'>OPORTUNIDAD MES</div>
                            <div class='chira-mem-val'>{dp_global.get('Comp Mes', 0)} Rx/mes en disputa</div>
                            <div class='chira-mem-sub'>Gutis actual: {dp_global.get('% MS Mes', 0.0):.1f}% MS</div>
                        </div>
                        <div class='chira-mem-box'>
                            <div class='chira-mem-lbl'>BASE SELL-OUT</div>
                            <div class='chira-mem-val'>{esc(bundle.archivos.get('Ventas Mensual', 'Trimestral')[:22])}</div>
                            <div class='chira-mem-sub'>Real vs. Cuota Activo</div>
                        </div>
                        <div class='chira-mem-box'>
                            <div class='chira-mem-lbl'>SELL-OUT ZONAL</div>
                            <div class='chira-mem-val'>${sell_z_chira['total']:,.2f}</div>
                            <div class='chira-mem-sub'>{sell_z_chira['pdvs']} PDVs en {esc(ciudad)}</div>
                        </div>
                    </div>
                </div>
            </div>
            """)

        opciones_prod_chira = ["TODO EL PORTAFOLIO"] + [m["producto"] for m in MERCADOS_PRIORITARIOS.values()]
        sel_p_c1, sel_p_c2 = st.columns([1.4, 2.6])
        with sel_p_c1:
            prod_foco_chira = st.selectbox(
                "Producto Foco para Disparadores Rápidos:",
                opciones_prod_chira,
                key="chira_prod_foco_btn",
            )
        with sel_p_c2:
            st.markdown(
                "<div style='padding-top:28px; font-size:0.75rem; color:#64748b; font-weight:600;'>Elige «TODO EL PORTAFOLIO» o una marca específica (Talerdín, Biotos, Mometzona, Clembroxil, Ventilar, Mupiral, Bicorpan, Dalivio, Gastroalivio, Valerpan, Conflexil, Renovart) y dispara el análisis con 1 clic.</div>",
                unsafe_allow_html=True,
            )

        es_todo_port = prod_foco_chira == "TODO EL PORTAFOLIO"
        lbl_prod_btn = "Todo el Portafolio" if es_todo_port else prod_foco_chira
        q_prod_suffix = "" if es_todo_port else f" en {prod_foco_chira}"
        prod_obj_default = "Biotos Inmune" if es_todo_port else prod_foco_chira

        quick_prompt = None
        q_b1, q_b2, q_b3, q_b4 = st.columns(4)
        with q_b1:
            render_html(f"""
                <div class='chira-prompt-card' translate='no'>
                    <div class='chira-prompt-title'>✦ Alerta Caída de Recetas</div>
                    <div class='chira-prompt-desc'>«¿Qué médicos bajaron recetas o se están enfriando{esc(q_prod_suffix)}?»</div>
                </div>
                """)
            if st.button(f"Caídas ({lbl_prod_btn[:14]}) →", key="ch_p1", width="stretch"):
                quick_prompt = f"Dime qué médicos muestran tendencia de caída o se me están enfriando{q_prod_suffix} este mes"

        with q_b2:
            render_html(f"""
                <div class='chira-prompt-card' translate='no'>
                    <div class='chira-prompt-title'>✦ Evolución Sucursales (6M)</div>
                    <div class='chira-prompt-desc'>«¿Qué sucursales están creciendo más{esc(q_prod_suffix)} en el semestre?»</div>
                </div>
                """)
            if st.button("Sucursales Creciendo →", key="ch_p2", width="stretch"):
                quick_prompt = f"¿Qué sucursales están creciendo más{q_prod_suffix}?"

        with q_b3:
            render_html(f"""
                <div class='chira-prompt-card' translate='no'>
                    <div class='chira-prompt-title'>✦ Abordaje PDVs en {esc(ciudad)}</div>
                    <div class='chira-prompt-desc'>«¿Qué sucursales debo abordar en {esc(ciudad)} y con qué productos?»</div>
                </div>
                """)
            if st.button(f"Abordar PDVs {ciudad[:10]} →", key="ch_p3", width="stretch"):
                quick_prompt = f"¿Qué sucursales debería ir a abordar en {ciudad}{q_prod_suffix} y con qué productos?"

        with q_b4:
            render_html(f"""
                <div class='chira-prompt-card' translate='no'>
                    <div class='chira-prompt-title'>✦ Cruce Rx vs. Venta Mensual</div>
                    <div class='chira-prompt-desc'>«¿Qué departamento subió o bajó{esc(q_prod_suffix)} contra su venta real?»</div>
                </div>
                """)
            if st.button("Cruzar Rx vs. Venta →", key="ch_p4", width="stretch"):
                quick_prompt = f"¿Qué departamento presentó incremento o disminución{q_prod_suffix} y analízalo contra la venta?"

        q_extra1, q_extra2, q_extra3, q_extra4 = st.columns(4)
        with q_extra1:
            if st.button("✦ Briefing Inteligente del Mes", key="ch_px1", width="stretch"):
                quick_prompt = "Dame un briefing inteligente del mes con hallazgos, apagones y Pareto 80/20"
        with q_extra2:
            if st.button("✦ Sucursales en Apagón ($0)", key="ch_px2", width="stretch"):
                quick_prompt = "¿Qué sucursales están en apagón y dejaron de comprar?"
        with q_extra3:
            if st.button(f"✦ Objeción Precio ({prod_obj_default[:12]})", key="ch_px3", width="stretch"):
                quick_prompt = f"¿Qué hacer cuando me dicen que {prod_obj_default} es muy caro?"
        with q_extra4:
            if st.button(f"✦ Guion TVP: {medico_sel[:16]}", key="ch_px4", width="stretch"):
                quick_prompt = f"Analiza el expediente completo y dame el guion TVP para {medico_sel}"

        with st.container(border=True):
            v_col1, v_col2 = st.columns([1.8, 1.2])
            texto_voz = None
            with v_col1:
                widget_audio = getattr(st, "audio_input", None)
                if widget_audio is not None:
                    audio_grabado = widget_audio("🎙️ Consulta Coloquial por Voz a CHIRA (Transcripción en vivo con IA):")
                    if audio_grabado is not None:
                        bytes_a = audio_grabado.getvalue()
                        hash_a = hashlib.md5(bytes_a).hexdigest()
                        if hash_a != st.session_state.ultimo_audio_hash:
                            if obtener_api_key():
                                with st.spinner("Transcribiendo consulta por voz con Gemini..."):
                                    texto_voz = transcribir_audio_gemini(bytes_a, getattr(audio_grabado, "type", "audio/wav"))
                                if texto_voz:
                                    st.session_state.ultimo_audio_hash = hash_a
                                else:
                                    st.warning("No se pudo transcribir el audio. Vuelve a intentarlo.")
                            else:
                                st.warning("Configura GEMINI_API_KEY en tus Secrets de Streamlit para transcribir voz.")
            with v_col2:
                st.caption("CHIRA traduce tu lenguaje natural y calcula las cifras directamente sobre Close-Up y datos 2026.xlsx.")
                allow_gemini = st.checkbox(
                    "Potenciar redacción estratégica con Gemini AI",
                    value=bool(obtener_api_key()),
                    key="chira_allow_gemini",
                )
                if st.button("Limpiar Historial de Conversación", width="stretch"):
                    st.session_state.chira_history = []
                    st.rerun()

        for msg in st.session_state.chira_history[-12:]:
            if msg["role"] == "user":
                render_html(f"""
                    <div translate='no' style='display:flex; justify-content:flex-end; margin: 10px 0;'>
                        <div style='background:#002b5c; color:#ffffff; padding:12px 18px; border-radius:12px 12px 2px 12px; max-width:78%; box-shadow:0 2px 6px rgba(0,43,92,0.15);'>
                            <div style='font-size:0.66rem; color:#93c5fd; font-weight:700; margin-bottom:4px;'>VISITADOR MÉDICO ({esc(VISITADOR_NOMBRE.upper())})</div>
                            <div style='font-size:0.86rem; font-weight:600;'>«{esc(msg['content'])}»</div>
                        </div>
                    </div>
                    """)
            else:
                motor_lbl = esc(msg.get("motor", "Auditoría Close-Up Verificada"))
                render_html(f"""
                    <div translate='no' style='background:#ffffff; border:1px solid #cbd5e1; border-left:5px solid #0284c7; border-radius:10px; padding:12px 16px; margin-top:10px;'>
                        <div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;'>
                            <div style='display:flex; align-items:center; gap:8px;'>
                                <span style='background:#002b5c; color:#38bdf8; width:26px; height:26px; border-radius:6px; display:inline-flex; align-items:center; justify-content:center; font-weight:800;'>✦</span>
                                <span style='font-size:0.82rem; font-weight:800; color:#0f172a;'>CHIRA AI Strategic Advisor</span>
                                <span style='background:#e0f2fe; color:#0369a1; font-size:0.66rem; font-weight:800; padding:2px 8px; border-radius:999px;'>{motor_lbl}</span>
                            </div>
                            <span style='font-size:0.68rem; color:#64748b; font-weight:700;'>Datos Close-Up &amp; Sell-Out Verificados</span>
                        </div>
                    </div>
                    """)
                with st.container(border=True):
                    st.markdown(msg["content"])
                    render_html(f"""
                        <div translate='no' style='border-top:1px solid #e2e8f0; padding-top:10px; margin-top:10px; display:flex; justify-content:space-between; flex-wrap:wrap; gap:12px; font-size:0.74rem;'>
                            <div><span style='color:#64748b; font-weight:700;'>MÉDICO EN FOCO:</span> <b style='color:#0f172a;'>{esc(medico_sel[:26])} ({dp_global.get('% MS Mes', 0.0):.1f}% MS)</b></div>
                            <div><span style='color:#64748b; font-weight:700;'>SELL-OUT {esc(ciudad)}:</span> <b style='color:#059669;'>${sell_z_chira['total']:,.2f}</b></div>
                            <div><span style='color:#64748b; font-weight:700;'>FARMACIAS LÍDERES:</span> <b style='color:#0284c7;'>{esc(sell_z_chira['top_farmacias'][:42])}</b></div>
                        </div>
                        """)

        pregunta_chat = st.chat_input("Pregúntale natural a CHIRA (ej: 'dame un briefing del mes', 'qué sucursales están en apagón', 'el doctor dice que Mometzona arde en la nariz')...")
        consulta_final = quick_prompt or texto_voz or pregunta_chat

        if consulta_final:
            st.session_state.chira_history.append({"role": "user", "content": consulta_final})

            todos_medicos = (
                sorted(set(meds_panel_default) | set(df_productos["Médico"].dropna().unique().tolist()))
                if not df_productos.empty and "Médico" in df_productos.columns
                else meds_panel_default
            )

            respuesta_local, motor_usado = enrutar_consulta_chira(
                bundle=bundle,
                consulta_final=consulta_final,
                medico_sel=medico_sel,
                especialidad_sel=especialidad,
                ciudad_sel=ciudad,
                alcance_sb=alcance_sb,
                lista_ciudades=LISTA_CIUDADES_REALES,
                lista_medicos_busqueda=todos_medicos,
            )

            respuesta_final = respuesta_local
            if allow_gemini and obtener_api_key():
                with st.spinner(f"CHIRA ({motor_usado}) está sintetizando tu plan táctico con Gemini AI..."):
                    es_playbook = any(k in motor_usado for k in ("Objeciones", "Comparativa", "WhatsApp"))
                    prompt_chira = (
                        f"Eres CHIRA, copiloto estratégico de {VISITADOR_NOMBRE} (Visitador Médico de Laboratorio Gutis en Nicaragua). "
                        f"Habla con tono directo, cercano, profesional y práctico de calle.\n\n"
                        f"Consulta del visitador: «{consulta_final}»\n"
                        f"Motor activado: {motor_usado}\n\n"
                        f"Datos exactos verificados por Python (PROHIBIDO alterar porcentajes, montos $, cuotas o cantidades de recetas):\n"
                        f"{respuesta_local}\n\n"
                        f"Instrucción: Conserva intactas las tablas y cifras clave anteriores y agrega una lectura ejecutiva ultra-práctica "
                        f"(máximo 3 a 5 bullets accionables) para ejecutar hoy mismo en consultorio y farmacia."
                    )
                    mejora_ia = llamar_gemini(prompt_chira, max_tok=2500)
                    if mejora_ia:
                        if es_playbook or respuesta_ia_conserva_cifras(mejora_ia, respuesta_local):
                            respuesta_final = mejora_ia
                        else:
                            respuesta_final = respuesta_local

            st.session_state.chira_history.append({"role": "assistant", "content": respuesta_final, "motor": motor_usado})
            st.rerun()

    elif st.session_state.sub_chira == "CRM":
        st.markdown("##### Registro Oficial de Visitas y Acuerdos SMART (Base de Datos SQLite Blindada)")
        with st.form("form_crm_sqlite"):
            c_f1, c_f2, c_f3, c_f4 = st.columns(4)
            lista_prods_crm = [m["producto"] for m in MERCADOS_PRIORITARIOS.values()]
            with c_f1:
                crm_foco = st.selectbox("Producto Foco (P1):", lista_prods_crm)
            with c_f2:
                crm_puente = st.selectbox("Producto Puente (P2):", ["Ninguno"] + lista_prods_crm, index=1 if len(lista_prods_crm) > 1 else 0)
            with c_f3:
                crm_smart = st.selectbox("Estatus Objetivo SMART:", ["Objetivo Principal Logrado", "Objetivo de Respaldo Logrado", "En Seguimiento Próxima Visita"])
            with c_f4:
                crm_escala = st.selectbox("Escalón TVP Validado:", ["1. No Consciente", "2. Consciente", "3. Prueba", "4. Adopción", "5. Lealtad"])

            c_ac1, c_ac2 = st.columns(2)
            with c_ac1:
                crm_ac_med = st.text_input("Compromiso del Médico (ej. Evaluar en próximos 4 pacientes con rinitis):")
            with c_ac2:
                crm_ac_vis = st.text_input("Compromiso del Visitador (ej. Garantizar stock en Farmacia Saba / Kielsa):")

            crm_notas = st.text_area("Observaciones Clínicas y Seguimiento para Próxima Visita:", height=95)
            btn_guardar_visita = st.form_submit_button(f"Guardar Visita a {medico_sel} en SQLite", type="primary", width="stretch")

        if btn_guardar_visita:
            guardar_visita(
                {
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Ciudad": ciudad,
                    "Médico": medico_sel,
                    "Especialidad": especialidad,
                    "Producto_Foco": crm_foco,
                    "Producto_Puente": crm_puente,
                    "Logro_SMART": crm_smart,
                    "Escala_TVP": crm_escala,
                    "Acuerdo_Medico": crm_ac_med,
                    "Acuerdo_Visitador": crm_ac_vis,
                    "Notas": crm_notas,
                },
                DB_PATH,
            )
            st.toast(f"✅ Visita registrada exitosamente para {medico_sel} en gutis_bi.db.")
            time.sleep(1.2)
            st.rerun()

        st.write("")
        filtro_hist = st.radio("Ver Historial de Visitas:", [f"Solo Médico en Foco ({medico_sel})", "Todas las Visitas de Mi Territorio"], horizontal=True)
        df_hist_crm = leer_visitas(medico_sel if filtro_hist.startswith("Solo") else None, DB_PATH)
        show_table(df_hist_crm, 340)

        st.download_button(
            "Exportar Bitácora Completa CRM a Excel / CSV",
            data=csv_para_excel(exportar_visitas_csv(DB_PATH)),
            file_name=f"Bitacora_CRM_{VISITADOR_NOMBRE.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            width="stretch",
        )

# -----------------------------------------------------------------------------
# PIE DE PÁGINA CORPORATIVO ESTILO STITCH
# -----------------------------------------------------------------------------
render_html(f"""
    <div class='stitch-nav-header' translate='no' style='margin-top:26px; background:#ffffff; color:#64748b; font-size:0.73rem;'>
        <div>
            Fuente: <b>Close-Up ({esc(corte_nombre)}) &amp; Sell-Out ({esc(bundle.archivos.get('Ventas Mensual', 'Trimestral'))})</b> ·
            Registros activos: <b>{kpi_hub['medicos_panel']} médicos en panel</b> ·
            <span style='color:#059669; font-weight:700;'>● Sincronizado con SQLite Local</span>
        </div>
        <div style='font-weight:800; color:#002b5c;'>
            GUTIS BI {esc(APP_VERSION)} · Arquitectura TVP · {esc(VISITADOR_NOMBRE)} © 2026
        </div>
    </div>
    """)
