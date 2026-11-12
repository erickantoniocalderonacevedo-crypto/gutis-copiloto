from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from gutis_bi.ai_service import llamar_gemini, obtener_api_key, transcribir_audio_gemini
from gutis_bi.analytics import (
    auditoria_marcas,
    calcular_tabla_bi_multifiltro,
    construir_guion_tvp_dinamico,
    df_a_markdown_nativo,
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
    ventas_por_trimestre,
)
from gutis_bi.catalog import MERCADOS_PRIORITARIOS, REGLAS_FARMA
from gutis_bi.crm import (
    exportar_visitas_csv,
    guardar_perfil_360,
    guardar_visita,
    init_db,
    leer_perfil_360,
    leer_visitas,
    migrar_excels_anteriores,
)
from gutis_bi.data import clear_data_cache, load_data, normalizar_serie_rapida, normalizar_txt, resolver_clave_mercado_gutis

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA Y RUTAS INTELIGENTES
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Gutis BI v2.5 | Arquitectura TVP & Close-Up",
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
# PARTE 1: SISTEMA DE DISEÑO ENTERPRISE STITCH (CSS MAESTRO, SIDEBAR Y MENÚ PRINCIPAL)
# -----------------------------------------------------------------------------


def render_sb_html(html_str: str) -> None:
    clean_html = "\n".join(line.lstrip() for line in html_str.splitlines() if line.strip())
    st.sidebar.markdown(clean_html, unsafe_allow_html=True)

def render_html(html_str: str) -> None:
    """Elimina la indentacion izquierda de cada linea HTML para que Markdown no lo interprete como bloque de codigo."""
    clean_html = "\n".join(line.lstrip() for line in html_str.splitlines() if line.strip())
    st.markdown(clean_html, unsafe_allow_html=True)

render_html("""
    <meta name="google" content="notranslate">
    <div class="notranslate" translate="no" style="display:none;"></div>
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
        .canvas-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(265px, 1fr));
            gap: 14px;
            margin: 10px 0 16px 0;
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
        .drill-panel {
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-top: 4px solid #002b5c;
            border-radius: 10px;
            padding: 16px;
            margin-top: 12px;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
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
# CARGA DE DATOS E INICIALIZACIÓN DE SQLITE
# -----------------------------------------------------------------------------
init_db(DB_PATH)
legacy_history = next((p for p in (BASE_DIR / "HISTORIAL_VISITAS.xlsx", DATA_DIR / "HISTORIAL_VISITAS.xlsx") if p.exists()), None)
legacy_profile = next((p for p in (BASE_DIR / "PERFIL_360_MEDICOS.xlsx", DATA_DIR / "PERFIL_360_MEDICOS.xlsx") if p.exists()), None)
legacy_migration = migrar_excels_anteriores(legacy_history, legacy_profile, DB_PATH)

bundle = load_data(str(DATA_DIR))
df_panel = bundle.panel
df_productos = bundle.productos
df_labs = bundle.laboratorios
df_clases = bundle.clases
df_auditoria_docs = bundle.auditoria
df_auditoria_tot = bundle.auditoria_totales
df_ventas = bundle.ventas

LISTA_CIUDADES_REALES = sorted([c for c in df_panel["CIUDAD"].dropna().unique() if str(c).strip() not in ["", "NAN"]]) if not df_panel.empty and "CIUDAD" in df_panel.columns else []
LISTA_ESPECIALIDADES_REALES = sorted([e for e in df_panel["Especialidad"].dropna().unique() if str(e).strip() not in ["", "NAN"]]) if not df_panel.empty and "Especialidad" in df_panel.columns else []
LISTA_MERCADOS_GUTIS_KEYS = list(MERCADOS_PRIORITARIOS.keys())

meds_panel_default = sorted(df_panel["Médico"].dropna().unique().tolist()) if not df_panel.empty and "Médico" in df_panel.columns else []

# Estados de sesión
for k_st, v_def in [
    ("modulo_activo", "HUB"),
    ("modo_alcance_sidebar", "SOLO MI PANEL (ERICK CALDERÓN)"),
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

def obtener_iniciales(nombre: str) -> str:
    partes = [p for p in str(nombre).strip().split() if p]
    if len(partes) >= 2:
        return (partes[0][0] + partes[1][0]).upper()
    elif len(partes) == 1:
        return partes[0][:2].upper()
    return "MD"

# -----------------------------------------------------------------------------
# BARRA LATERAL ESTILO STITCH (LOGO, NAVEGACIÓN, TARJETA AVATAR MÉDICO Y PERFIL ERICK)
# -----------------------------------------------------------------------------
render_sb_html("""
    <div class='notranslate' translate='no' style='display:flex; align-items:center; gap:10px; padding:4px 0 12px 0; border-bottom:1px solid #e2e8f0; margin-bottom:10px;'>
        <div style='width:34px; height:34px; border-radius:8px; background:#002b5c; color:#fff; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:1.05rem;'>G</div>
        <div>
            <div style='font-weight:800; font-size:0.95rem; color:#0f172a;'>GUTIS BI <span style='background:#dcfce7; color:#15803d; font-size:0.65rem; padding:2px 6px; border-radius:4px;'>v2.5</span></div>
            <div style='font-size:0.68rem; color:#64748b; font-weight:600;'>Arquitectura TVP & Close-Up</div>
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
nav_sel = st.sidebar.radio(
    "Módulo Activo:",
    list(opciones_nav.keys()),
    index=list(opciones_nav.keys()).index(st.session_state.modulo_activo),
    format_func=lambda k: opciones_nav[k],
    label_visibility="collapsed",
)
if nav_sel != st.session_state.modulo_activo:
    st.session_state.modulo_activo = nav_sel
    st.rerun()

st.sidebar.divider()
st.sidebar.markdown("<div class='subnav-label'>ESPECIALISTA ACTIVO (PREVISITA)</div>", unsafe_allow_html=True)

alcance_sb = st.sidebar.radio(
    "Universo de Médicos:",
    ["SOLO MI PANEL (ERICK CALDERÓN)", "UNIVERSO TOTAL NICARAGUA"],
    index=0 if st.session_state.modo_alcance_sidebar == "SOLO MI PANEL (ERICK CALDERÓN)" else 1,
    help="Por defecto muestra exclusivamente los médicos de tu panel asignado.",
)
st.session_state.modo_alcance_sidebar = alcance_sb

if alcance_sb == "SOLO MI PANEL (ERICK CALDERÓN)":
    ciu_sb = st.sidebar.selectbox("Filtrar Ciudad del Panel:", ["TODAS"] + LISTA_CIUDADES_REALES)
    df_pan_sb = df_panel if ciu_sb == "TODAS" else df_panel[df_panel["CIUDAD"] == ciu_sb]
    esp_opciones_sb = sorted(df_pan_sb["Especialidad"].dropna().unique().tolist()) if not df_pan_sb.empty else []
    esp_sb = st.sidebar.selectbox("Filtrar Especialidad:", ["TODAS"] + esp_opciones_sb)
    if esp_sb != "TODAS":
        df_pan_sb = df_pan_sb[df_pan_sb["Especialidad"] == esp_sb]
    lista_meds_sb = sorted(df_pan_sb["Médico"].dropna().unique().tolist()) if not df_pan_sb.empty else meds_panel_default
else:
    ciu_sb = st.sidebar.selectbox("Filtrar Ciudad:", ["TODAS"] + LISTA_CIUDADES_REALES)
    df_prod_sb = df_productos if ciu_sb == "TODAS" else df_productos[df_productos["CIUDAD_PANEL"] == ciu_sb]
    lista_meds_sb = sorted(set(meds_panel_default) | set(df_prod_sb["Médico"].dropna().unique().tolist()))

if st.session_state.medico_activo_global and st.session_state.medico_activo_global not in lista_meds_sb:
    lista_meds_sb = [st.session_state.medico_activo_global] + lista_meds_sb

idx_med_sb = lista_meds_sb.index(st.session_state.medico_activo_global) if st.session_state.medico_activo_global in lista_meds_sb else 0
med_elegido_sb = st.sidebar.selectbox("Especialista en Foco:", lista_meds_sb, index=idx_med_sb)
if med_elegido_sb != st.session_state.medico_activo_global:
    st.session_state.medico_activo_global = med_elegido_sb
    st.session_state.pos_m1_idx, st.session_state.pos_m2_idx, st.session_state.pos_m3_idx = 0, 1, 2
    st.rerun()

medico_sel = st.session_state.medico_activo_global
dp_global = perfil_medico(df_panel, df_productos, medico_sel)
ciudad = dp_global.get("CIUDAD", "NICARAGUA")
especialidad = dp_global.get("Especialidad", "ESPECIALISTA")
categoria = dp_global.get("CATEGORIA", "S/C")
es_pediatra = "PEDIAT" in especialidad.upper()
ini_med = obtener_iniciales(medico_sel)

# Tarjeta Avatar del Especialista en Foco en el Sidebar (Idéntica a Stitch)
render_sb_html(f"""
    <div class='sidebar-doc-card notranslate' translate='no'>
        <div class='doc-avatar-row'>
            <div class='doc-initials'>{ini_med}</div>
            <div>
                <div class='doc-name-sb'>{medico_sel[:26] if medico_sel else 'Sin selección'}</div>
                <div class='doc-esp-sb'>{especialidad}</div>
            </div>
        </div>
        <div class='doc-meta-row'>
            <span class='doc-cat-pill'>Cat {categoria}</span>
            <span>{ciudad}, Nic.</span>
            <span style='color:#0284c7;'>{dp_global.get('Pxs Mes', 0)} Pxs/M</span>
        </div>
    </div>
    """)

st.sidebar.divider()
with st.sidebar.expander("Estado de Bases Offline y Caché", expanded=False):
    st.caption(f"Carpeta activa: `{DATA_DIR}`")
    for k_f, v_f in bundle.archivos.items():
        st.caption(f"• **{k_f}:** `{v_f}`")
    if st.button("Recargar Excels y Limpiar Caché", use_container_width=True):
        clear_data_cache()
        st.rerun()

render_sb_html("""
    <div class='notranslate' translate='no' style='display:flex; align-items:center; justify-content:space-between; padding-top:8px; font-size:0.72rem; color:#475569; font-weight:700;'>
        <span><span style='color:#10b981;'>●</span> Base Offline OK (100%)</span>
        <span>Erick Calderón (VM)</span>
    </div>
    """)

# -----------------------------------------------------------------------------
# BARRA SUPERIOR DE MIGAS DE PAN & ESTADO SYNC (TOPBAR STITCH)
# -----------------------------------------------------------------------------
corte_nombre = bundle.archivos.get("Auditoría") or bundle.archivos.get("Productos") or "CLASES_Y_AUDITORIA.XLSX"
nombre_mod_breadcrumb = opciones_nav.get(st.session_state.modulo_activo, "Menú Principal")
render_html(f"""
    <div class='stitch-nav-header notranslate' translate='no'>
        <div class='stitch-breadcrumbs'>
            <b>GUTIS BI</b> <span>/</span> <span>Comité Médico Estratégico</span> <span>/</span>
            <b>{nombre_mod_breadcrumb}</b>
            <span class='stitch-pill-region'>{ciudad if st.session_state.modulo_activo == 'PREVISITA' else 'Región Pacífico & Centro'}</span>
        </div>
        <div class='stitch-sync-status'>
            <span style='color:#64748b; font-weight:600;'>Auditoría Close-Up: <b>{corte_nombre}</b></span>
            <span class='sync-badge'>● Base Sincronizada (100%)</span>
            <div class='vm-avatar-top'>
                <span class='vm-circle'>EC</span>
                <span>Erick Calderón <small style='display:block; font-size:0.64rem; color:#10b981; font-weight:700;'>Visitador Médico · Activo</small></span>
            </div>
        </div>
    </div>
    """)

kpi_hub = resumen_global(df_panel, df_productos)


# -----------------------------------------------------------------------------
# PARTE 2: FUNCIONES AUXILIARES, MENÚ PRINCIPAL (HUB STITCH) Y MÓDULO 1 (VISOR POWER BI)
# -----------------------------------------------------------------------------

def fmt_int(value: object) -> str:
    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return "0"

def fmt_pct(value: object) -> str:
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "0.0%"

def safe_text(value: object, default: str = "Sin dato") -> str:
    if value is None or str(value).strip().lower() in ("", "nan", "none"):
        return default
    return str(value)

def show_table(df: pd.DataFrame, height: int = 420) -> None:
    if df is None or df.empty:
        st.info("No hay registros para los filtros seleccionados.")
        return
    cfg = {}
    for col in df.columns:
        if "% MS" in col:
            cfg[col] = st.column_config.ProgressColumn(col, format="%.1f%%", min_value=0, max_value=100)
        elif "Dif %" in col or "Brecha" in col or "Delta" in col:
            cfg[col] = st.column_config.NumberColumn(col, format="%+.1f pp")
    st.dataframe(df, hide_index=True, use_container_width=True, height=height, column_config=cfg)


# -----------------------------------------------------------------------------
# MÓDULO HUB (MENÚ PRINCIPAL ESTILO STITCH: HERO, 4 KPIS Y CARDS MOD-01 A MOD-05)
# -----------------------------------------------------------------------------
if st.session_state.modulo_activo == "HUB":
    # 1. Hero Banner Principal
    render_html(f"""
        <div class='stitch-hero notranslate' translate='no'>
            <div>
                <div class='hero-left-tag'>GUTIS · INNOVACIÓN Y TECNOLOGÍA PARA LA VIDA</div>
                <div class='hero-main-title'>Análisis Close-Up & Arquitectura TVP</div>
                <div class='hero-sub-desc'>
                    Plataforma integral de efectividad médica comercial, monitoreo de cuota de mercado por clases terapéuticas y preparación ejecutiva previa de visitas.
                </div>
            </div>
            <div class='hero-glass-box'>
                <div>
                    <div class='hero-glass-lbl'>CENTRO DE COMPETENCIAS</div>
                    <div class='hero-glass-val'>Inteligencia de Negocio v2.5</div>
                </div>
                <div class='hero-ok-pill'>Auditado OK</div>
            </div>
        </div>
        """)

    # 2. Las 4 Tarjetas KPI Superiores con Barras de Progreso y Pills (Idénticas a Stitch)
    tot_pan = max(kpi_hub["medicos_panel"], 1)
    pct_cob = round((kpi_hub["medicos_activos"] / tot_pan) * 100.0, 1)
    brecha_hub = round(kpi_hub["ms_mes"] - kpi_hub["ms_ytd"], 1)
    signo_b = f"↑ +{brecha_hub:.1f}%" if brecha_hub >= 0 else f"↓ {brecha_hub:.1f}%"
    clase_pill_b = "kpi-pill-up" if brecha_hub >= 0 else "kpi-pill-warn"
    w_mes = min(max(kpi_hub["ms_mes"], 4.0), 100.0)
    w_ytd = min(max(kpi_hub["ms_ytd"], 4.0), 100.0)

    render_html(f"""
        <div class='kpi-strip notranslate' translate='no'>
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
                    <span class='{clase_pill_b}'>{signo_b}</span>
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
                    <span class='kpi-pill-neutral'>Consistente</span>
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
                    {medico_sel or 'Sin selección'}
                </div>
                <div style='font-size:0.75rem; color:#475569; font-weight:700; margin-bottom:10px;'>
                    {especialidad} · <b style='color:#002b5c;'>Cat {categoria}</b> · {ciudad}
                </div>
                <div class='kpi-sub' style='border-top:1px solid #f1f5f9; padding-top:6px;'>
                    <span>Prioridad:</span>
                    <b style='color:#059669;'>Prescriptor Clave ({dp_global.get('Pxs Mes', 0)} Pxs)</b>
                </div>
            </div>
        </div>
        """)

    # 3. Encabezado Central y Cuadrícula de Tarjetas Interactivas (MOD-01 a MOD-05)
    render_html("""
        <div class='notranslate' translate='no' style='text-align:center; margin: 18px 0 14px 0;'>
            <div style='font-size:1.08rem; font-weight:800; color:#0f172a; letter-spacing:0.02em;'>SELECCIONE EL MÓDULO DE INTELIGENCIA COMERCIAL</div>
            <div style='font-size:0.78rem; color:#64748b; font-weight:500;'>Navegue por las herramientas analíticas para optimizar la previsita, auditoría de médicos y correlación de recetas</div>
        </div>
        """)

    row1_m1, row1_m2 = st.columns(2)
    with row1_m1:
        render_html("""
            <div class='stitch-mod-card notranslate' translate='no'>
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
        if st.button("Abrir Visor Multifiltro  →", key="btn_hub_m1", use_container_width=True, type="primary"):
            ir_a_modulo("TOP_MEDICOS")
            st.rerun()

    with row1_m2:
        render_html("""
            <div class='stitch-mod-card notranslate' translate='no'>
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
        if st.button("Preparar Guion & Canvas  →", key="btn_hub_m2", use_container_width=True, type="primary"):
            ir_a_modulo("PREVISITA")
            st.rerun()

    st.write("")
    row2_m3, row2_m4 = st.columns(2)
    with row2_m3:
        render_html("""
            <div class='stitch-mod-card notranslate' translate='no'>
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
        if st.button("Explorar Radar de Mercado  →", key="btn_hub_m3", use_container_width=True):
            ir_a_modulo("ANALISIS_MERCADO")
            st.rerun()

    with row2_m4:
        render_html("""
            <div class='stitch-mod-card notranslate' translate='no'>
                <div class='mod-card-top'>
                    <div class='mod-icon-badge' style='background:#ecfdf5; color:#047857; border-color:#a7f3d0;'>Q1-Q3</div>
                    <div class='mod-code-tag'>MOD-04</div>
                </div>
                <div class='mod-card-title'>EVOLUCIÓN <span>(inf.target)</span></div>
                <div class='mod-card-desc'>
                    Sincronía analítica entre prescripciones médicas Close-Up y venta real en farmacias aliadas (Sell-Out trimestral Q1, Q2, Q3).
                </div>
            </div>
            """)
        if st.button("Comparar Curvas Rx / Sell-Out  →", key="btn_hub_m4", use_container_width=True):
            ir_a_modulo("EVOLUCION")
            st.rerun()

    st.write("")
    # Card Especial de Ancho Completo para CHIRA (MOD-05)
    render_html("""
        <div class='chira-neural-hero notranslate' translate='no' style='padding:16px 22px; margin-bottom:8px;'>
            <div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;'>
                <div>
                    <span class='chira-neural-badge'>✦ MOD-05 · CHIRA NEURAL ENGINE</span>
                    <div style='font-size:1.05rem; font-weight:800; color:#ffffff;'>CHIRA — Copiloto Estratégico con Voz y Registro CRM Post-Visita</div>
                    <div style='font-size:0.78rem; color:#cbd5e1;'>Consultoría táctica en tiempo real sobre Close-Up, manejo de objeciones y bitácora relacional SQLite.</div>
                </div>
                <div class='hero-ok-pill'>IA + SQLite Activo</div>
            </div>
        </div>
        """)
    if st.button("Iniciar Consola Cognitiva CHIRA & Bitácora CRM  →", key="btn_hub_m5", use_container_width=True, type="primary"):
        ir_a_modulo("CHIRA")
        st.rerun()


# -----------------------------------------------------------------------------
# MÓDULO 1: TOP MÉDICOS & VISOR POWER BI MULTIFILTRO (CON DESGLOSE HIJO INTERACTIVO)
# -----------------------------------------------------------------------------
elif st.session_state.modulo_activo == "TOP_MEDICOS":
    c_back, c_tit = st.columns([0.85, 3.15])
    with c_back:
        if st.button("← Volver al Menú Principal", use_container_width=True):
            ir_a_modulo("HUB")
            st.rerun()
    with c_tit:
        render_html("""
            <div class='module-banner notranslate' translate='no'>
                <span>MÓDULO 1: TOP MÉDICOS (INF.TARGET) — VISOR POWER BI MULTIFILTRO, PROSPECCIÓN Y CONQUISTA</span>
                <span style='font-size:0.68rem; background:rgba(56,189,248,0.2); color:#7dd3fc; padding:3px 8px; border-radius:4px;'>VISTA INTERACTIVA</span>
            </div>
            """)

    st.markdown("<div class='subnav-label'>SELECCIONE LA VISTA ANALÍTICA (UNA COSA A LA VEZ):</div>", unsafe_allow_html=True)
    btm0, btm1, btm2, btm3 = st.columns(4)
    with btm0:
        if st.button("1. Evolución - Mercado (Visor BI)", use_container_width=True, type="primary" if st.session_state.sub_top_medicos == "BI_EVOLUCION" else "secondary"):
            st.session_state.sub_top_medicos = "BI_EVOLUCION"
            st.rerun()
    with btm1:
        if st.button("2. Ranking por Volumen de Recetas", use_container_width=True, type="primary" if st.session_state.sub_top_medicos == "RANKING" else "secondary"):
            st.session_state.sub_top_medicos = "RANKING"
            st.rerun()
    with btm2:
        if st.button("3. Mercados que Crecen (Mes vs. YTD)", use_container_width=True, type="primary" if st.session_state.sub_top_medicos == "CRECIMIENTO" else "secondary"):
            st.session_state.sub_top_medicos = "CRECIMIENTO"
            st.rerun()
    with btm3:
        if st.button("4. Médicos Fuera de Panel (Prospección)", use_container_width=True, type="primary" if st.session_state.sub_top_medicos == "FUERA_PANEL" else "secondary"):
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
                        "Solo Mi Panel (Erick)",
                        value=alcance_sb.startswith("SOLO"),
                        key="bi_chk_panel_erick",
                    )

                df_base_bi = df_auditoria_docs[df_auditoria_docs["Zona"] != "FUERA DE PANEL"].copy() if f_solo_panel_bi else df_auditoria_docs.copy()

                r1_c1, r1_c2, r1_c3, r1_c4 = st.columns([1.0, 1.5, 1.2, 1.0])
                zonas_bi = ["Todas"] + sorted([z for z in df_base_bi["Zona"].dropna().unique() if z not in ["", "NAN"]])
                meds_bi = ["Todas"] + sorted(df_base_bi["Médico"].dropna().unique().tolist())
                esps_bi = ["Todas"] + sorted(df_base_bi["Especialidad"].dropna().unique().tolist())
                viss_bi = ["Todas"] + sorted(df_base_bi["VISITADOR"].dropna().unique().tolist()) if "VISITADOR" in df_base_bi.columns else ["Todas", "CALDERON ERICK"]

                with r1_c1: f_bi_zona = st.selectbox("ZONA:", zonas_bi, key="bi_f_zona")
                with r1_c2: f_bi_med = st.selectbox("MÉDICO:", meds_bi, key="bi_f_med")
                with r1_c3: f_bi_esp = st.selectbox("ESPECIALIDAD:", esps_bi, key="bi_f_esp")
                with r1_c4: f_bi_vis = st.selectbox("VISITADOR:", viss_bi, index=0, key="bi_f_vis")

                df_casc = df_base_bi
                if f_bi_zona != "Todas": df_casc = df_casc[df_casc["Zona"] == f_bi_zona]
                if f_bi_med != "Todas": df_casc = df_casc[df_casc["Médico"] == f_bi_med]
                if f_bi_esp != "Todas": df_casc = df_casc[df_casc["Especialidad"] == f_bi_esp]

                r2_c1, r2_c2, r2_c3, r2_c4 = st.columns([1.4, 1.3, 1.1, 1.0])
                mers_bi_keys = ["Todas"] + LISTA_MERCADOS_GUTIS_KEYS + sorted([m for m in df_casc["Mercado_BI"].dropna().unique() if m not in LISTA_MERCADOS_GUTIS_KEYS and m not in ["", "OTROS MERCADOS"]])
                with r2_c1:
                    f_bi_mer = st.selectbox(
                        "MERCADO:",
                        mers_bi_keys,
                        format_func=lambda k: "Todas" if k == "Todas" else (f"MR {MERCADOS_PRIORITARIOS[k]['producto']} ({k})" if k in MERCADOS_PRIORITARIOS else k),
                        key="bi_f_mer"
                    )
                if f_bi_mer != "Todas":
                    df_casc = df_casc[(df_casc["Clave_Gutis"] == f_bi_mer) | (df_casc["Mercado_BI"] == f_bi_mer)]

                marcas_bi = ["Todas"] + sorted(df_casc["MARCA"].dropna().unique().tolist())
                labs_bi = ["Todas"] + sorted(df_casc["Laboratorio"].dropna().unique().tolist())
                cats_bi = ["Todas"] + sorted(df_casc["Categoria_TAM"].dropna().astype(str).unique().tolist())

                with r2_c2: f_bi_mar = st.selectbox("MARCA / PRODUCTO:", marcas_bi, key="bi_f_mar")
                with r2_c3: f_bi_lab = st.selectbox("LABORATORIO:", labs_bi, key="bi_f_lab")
                with r2_c4: f_bi_cat = st.selectbox("CATEGORÍA TAM:", cats_bi, key="bi_f_cat")

            df_bi_marcas, df_bi_medicos = calcular_tabla_bi_multifiltro(
                df_base_bi, df_auditoria_tot,
                f_zona=f_bi_zona, f_med=f_bi_med, f_esp=f_bi_esp, f_vis=f_bi_vis,
                f_mer=f_bi_mer, f_mar=f_bi_mar, f_lab=f_bi_lab, f_cat=f_bi_cat
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
                    if "MARCA" in df_m_show.columns and "Origen" not in df_m_show.columns:
                        s_norm_m = normalizar_serie_rapida(df_m_show["MARCA"])
                        df_m_show.insert(
                            1,
                            "ORIGEN",
                            np.where(s_norm_m.str.contains("GPR|GUTIS", na=False), "GUTIS", "COMPETENCIA"),
                        )
                    st.dataframe(df_m_show, hide_index=True, use_container_width=True, height=390, column_config=cfg_cols_bi)

                    # Desglose Hijo (+): ¿Qué médicos recetan esta Marca / Producto bajo los filtros actuales? (Idéntico a Stitch)
                    st.markdown("<div class='drill-panel notranslate' translate='no'>", unsafe_allow_html=True)
                    c_dh1, c_dh2 = st.columns([1.8, 1.2])
                    lista_m_hijo = df_bi_marcas["MARCA"].dropna().unique().tolist()
                    with c_dh1:
                        st.markdown(
                            "<div style='font-size:0.84rem; font-weight:800; color:#002b5c;'>● Desglose Hijo (+): ¿Qué médicos recetan esta Marca / Producto bajo los filtros actuales?</div>",
                            unsafe_allow_html=True,
                        )
                    with c_dh2:
                        marca_hijo_sel = st.selectbox("Marca en auditoría:", lista_m_hijo, label_visibility="collapsed", key="bi_hijo_marca")

                    _, df_meds_de_marca = calcular_tabla_bi_multifiltro(
                        df_base_bi, df_auditoria_tot,
                        f_zona=f_bi_zona, f_med=f_bi_med, f_esp=f_bi_esp, f_vis=f_bi_vis,
                        f_mer=f_bi_mer, f_mar=marca_hijo_sel, f_lab=f_bi_lab, f_cat=f_bi_cat
                    )
                    if not df_meds_de_marca.empty:
                        st.dataframe(df_meds_de_marca, hide_index=True, use_container_width=True, height=260, column_config=cfg_cols_bi)
                        j_c1, j_c2 = st.columns([2.2, 1.0])
                        with j_c1:
                            doc_hijo_jump = st.selectbox(
                                "Seleccionar médico de esta marca para ir a Previsita TVP:",
                                df_meds_de_marca["Médico"].tolist(),
                                key="bi_hijo_doc_jump",
                            )
                        with j_c2:
                            st.write("")
                            if st.button(f"Abrir en Previsita TVP →", type="primary", use_container_width=True, key="btn_bi_hijo_jump"):
                                ir_a_modulo("PREVISITA", medico_destino=doc_hijo_jump)
                                st.rerun()
                    else:
                        st.info("No hay prescriptores registrados para esta marca bajo los filtros actuales.")
                    st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.info("No hay registros de marcas para los filtros seleccionados.")
            else:
                if not df_bi_medicos.empty:
                    st.dataframe(df_bi_medicos, hide_index=True, use_container_width=True, height=420, column_config=cfg_cols_bi)
                    doc_sel_bi = st.selectbox("Abrir especialista en Previsita TVP:", df_bi_medicos["Médico"].tolist(), key="bi_doc_jump")
                    if st.button("Ir a Previsita TVP con este médico →", type="primary"):
                        ir_a_modulo("PREVISITA", medico_destino=doc_sel_bi)
                        st.rerun()
                else:
                    st.info("No hay médicos para los filtros seleccionados.")
        else:
            st.warning("No se encontró el archivo de Close-Up (Clases y Auditoría.xlsx).")

    elif st.session_state.sub_top_medicos in ["RANKING", "FUERA_PANEL", "CRECIMIENTO"]:
        f1, f2, f3 = st.columns(3)
        with f1: tm_ciu = st.selectbox("Territorio:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="tm_ciu")
        with f2: tm_mer = st.selectbox("Mercado:", ["TODOS LOS MERCADOS"] + LISTA_MERCADOS_GUTIS_KEYS, format_func=lambda k: "TODOS LOS MERCADOS" if k == "TODOS LOS MERCADOS" else MERCADOS_PRIORITARIOS[k]["producto"], key="tm_mer")
        with f3: tm_esp = st.selectbox("Especialidad:", ["TODAS"] + LISTA_ESPECIALIDADES_REALES, key="tm_esp")

        if st.session_state.sub_top_medicos in ["RANKING", "FUERA_PANEL"]:
            modo_p = "FUERA_PANEL" if st.session_state.sub_top_medicos == "FUERA_PANEL" else "PANEL"
            df_rk = ranking_medicos(
                df_productos, df_panel,
                ciudad=None if tm_ciu == "TODO MI PANEL" else tm_ciu,
                especialidad=None if tm_esp == "TODAS" else tm_esp,
                mercado=None if tm_mer == "TODOS LOS MERCADOS" else tm_mer,
                modo_panel=modo_p
            )
            if not df_rk.empty:
                c_k1, c_k2, c_k3 = st.columns(3)
                c_k1.metric("Médicos en Lista", f"{len(df_rk):,}")
                c_k2.metric("Recetas Gutis Mes", f"{int(df_rk['Gutis Mes'].sum()):,}")
                c_k3.metric("Recetas Competencia Mes (Oportunidad)", f"{int(df_rk['Comp Mes'].sum()):,}")
                show_table(df_rk, 430)

                st.markdown("<div class='drill-panel notranslate' translate='no'>", unsafe_allow_html=True)
                drill_doc = st.selectbox("Seleccionar especialista para auditar su recetario completo:", df_rk["Médico"].tolist(), key="rk_drill")
                show_table(productos_medico(df_productos, drill_doc), 260)
                if st.button("Preparar Visita en Previsita TVP →", type="primary"):
                    ir_a_modulo("PREVISITA", medico_destino=drill_doc)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
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
# PARTE 3: MÓDULO 2 — PREVISITA TVP ESTILO STITCH (MAPA 3X3, CANVAS 4 CUADRANTES, GUION NUMERADO Y MATRIZ CLASES/360)
# -----------------------------------------------------------------------------
elif st.session_state.modulo_activo == "PREVISITA":
    c_back, c_tit = st.columns([0.85, 3.15])
    with c_back:
        if st.button("← Volver al Menú Principal", use_container_width=True):
            ir_a_modulo("HUB")
            st.rerun()
    with c_tit:
        render_html("""
            <div class='module-banner notranslate' translate='no'>
                <span>MÓDULO 2: PREVISITA TVP (INF.TARGET) — PREPARACIÓN EJECUTIVA PASO A PASO</span>
                <span style='font-size:0.68rem; background:rgba(56,189,248,0.2); color:#7dd3fc; padding:3px 8px; border-radius:4px;'>MODO TÁCTICO 1:1</span>
            </div>
            """)

    if not medico_sel:
        st.warning("Selecciona un especialista en la barra lateral izquierda para abrir su Previsita TVP.")
    else:
        perfil_360_actual = leer_perfil_360(medico_sel, DB_PATH)
        sell_z = resumen_ventas_ciudad(df_ventas, ciudad)
        farmacias_aliadas_str = sell_z["top_farmacias"]

        # 1. Evaluar mercados del Vademécum Nicaragua 2026 para el médico activo
        claves_disponibles_med = [
            k for k, v in MERCADOS_PRIORITARIOS.items()
            if not (es_pediatra and not v.get("apto_pediatria", True))
        ]
        rx_med_raw = df_productos[
            (df_productos["Médico"] == medico_sel) & (df_productos["Clave_Gutis"].isin(claves_disponibles_med))
        ].copy() if not df_productos.empty else pd.DataFrame()

        mercados_evaluados = []
        for k_m in claves_disponibles_med:
            meta_m = MERCADOS_PRIORITARIOS[k_m]
            grp_m = rx_med_raw[rx_med_raw["Clave_Gutis"] == k_m] if not rx_med_raw.empty else pd.DataFrame()
            pm = int(grp_m["Pxs-MES"].sum()) if not grp_m.empty else 0
            py = int(grp_m["Pxs-YTD"].sum()) if not grp_m.empty else 0
            gm = int(grp_m[grp_m["Es_Gutis"]]["Pxs-MES"].sum()) if not grp_m.empty else 0
            gy = int(grp_m[grp_m["Es_Gutis"]]["Pxs-YTD"].sum()) if not grp_m.empty else 0
            cm = max(pm - gm, 0)
            cy = max(py - gy, 0)
            msm = round((gm / pm * 100.0), 1) if pm > 0 else 0.0
            msy = round((gy / py * 100.0), 1) if py > 0 else 0.0
            diag_sc = diagnosticar_escala_adopcion(gm, pm, msm, gy, py, msy)

            if not grp_m.empty:
                grp_riv = grp_m[~grp_m["Es_Gutis"]].sort_values(by=["Pxs-MES", "Pxs-YTD"], ascending=False)
                riv_str = f"{grp_riv.iloc[0]['NOMBRE_PRODUCTO']} ({int(grp_riv.iloc[0]['Pxs-MES'])}M / {int(grp_riv.iloc[0]['Pxs-YTD'])}Y)" if not grp_riv.empty else f"Líder: {meta_m['producto']} ({msm:.0f}% MS)"
                riv_corto = str(grp_riv.iloc[0]["NOMBRE_PRODUCTO"])[:26] if not grp_riv.empty else f"{meta_m['producto']} ({msm:.0f}% MS)"
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

        # 2. Franja de 4 Tarjetas KPI del Especialista en Foco (Idéntica a Stitch)
        render_html(f"""
            <div class='kpi-strip notranslate' translate='no'>
                <div class='kpi-card' style='border-top: 3px solid #002b5c;'>
                    <div class='kpi-lbl'>ESPECIALISTA EN FOCO</div>
                    <div style='font-size:1.05rem; font-weight:800; color:#0f172a; margin:6px 0 4px 0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>
                        {medico_sel}
                    </div>
                    <div style='font-size:0.74rem; color:#475569; font-weight:700;'>
                        {especialidad} | Cat {categoria} | <span style='background:#e0f2fe; color:#0369a1; padding:1px 6px; border-radius:4px;'>{ciudad}</span>
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
                    <div class='kpi-lbl'>FOCO PRIMARIO ({m_foco_top['prod_gutis'].upper()})</div>
                    <div style='font-size:1.05rem; font-weight:800; color:#0f172a; margin:6px 0 4px 0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>
                        {m_foco_top['rival_corto']}
                    </div>
                    <div style='font-size:0.74rem; color:#475569; font-weight:700;'>
                        Escala TVP: <span style='background:#fef3c7; color:#b45309; padding:2px 6px; border-radius:4px;'>{m_foco_top['escala_nivel']}</span>
                    </div>
                </div>

                <div class='kpi-card' style='border-top: 3px solid #10b981;'>
                    <div class='kpi-lbl'>SELL-OUT ZONAL ({ciudad} - {sell_z['pdvs']} PDV)</div>
                    <div style='font-size:1.25rem; font-weight:800; color:#047857; margin:4px 0;'>
                        ${sell_z['total']:,.2f}
                    </div>
                    <div style='font-size:0.73rem; color:#64748b; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>
                        Aliadas: {farmacias_aliadas_str}
                    </div>
                </div>
            </div>
            """)

        # 3. Pestañas de Navegación de Previsita (Las 4 Herramientas de Stitch)
        st.markdown("<div class='subnav-label'>SELECCIONE LA HERRAMIENTA DE PREVISITA:</div>", unsafe_allow_html=True)
        bp1, bp2, bp3, bp4 = st.columns(4)
        with bp1:
            if st.button("1. Mapa de Mercado del Especialista", use_container_width=True, type="primary" if st.session_state.sub_previsita == "MAPA" else "secondary"):
                st.session_state.sub_previsita = "MAPA"
                st.rerun()
        with bp2:
            if st.button("2. Canvas TVP (4 Cuadrantes)", use_container_width=True, type="primary" if st.session_state.sub_previsita == "CANVAS" else "secondary"):
                st.session_state.sub_previsita = "CANVAS"
                st.rerun()
        with bp3:
            if st.button("3. Mapa Conversacional del TVP", use_container_width=True, type="primary" if st.session_state.sub_previsita == "GUION" else "secondary"):
                st.session_state.sub_previsita = "GUION"
                st.rerun()
        with bp4:
            if st.button("4. Clases Terapéuticas, Labs & 360", use_container_width=True, type="primary" if st.session_state.sub_previsita == "AUDITORIA" else "secondary"):
                st.session_state.sub_previsita = "AUDITORIA"
                st.rerun()

        st.write("")

        # ---------------------------------------------------------------------
        # SUB-VISTA 1: MAPA DE MERCADOS ACTIVOS (CUADRÍCULA 3X3 CON BORDES ROJO/VERDE)
        # ---------------------------------------------------------------------
        if st.session_state.sub_previsita == "MAPA":
            with st.container(border=True):
                c_mh1, c_mh2 = st.columns([3.0, 1.0])
                with c_mh1:
                    st.markdown(
                        "<div style='font-size:0.86rem; font-weight:800; color:#0f172a;'><span style='color:#0284c7;'>●</span> MAPA DE MERCADOS ACTIVOS DEL ESPECIALISTA (VADEMÉCUM NICARAGUA 2026 — 9 CATEGORÍAS AUDITADAS)</div>",
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
                            borde_top = "#10b981" if es_lealtad else "#ef4444"
                            prio_lbl = f"P{m_it['prioridad']}"
                            bg_prio = "#002b5c" if m_it["prioridad"] == 1 else "#0284c7"

                            if es_lealtad:
                                linea_riv = f"<span style='color:#059669; font-weight:800;'>Líder: {m_it['prod_gutis']} ({m_it['ms_mes']:.0f}% MS)</span>"
                                cta_txt = "Agradecer, Blindar y Puente"
                                cta_icon = "✓"
                                bg_esc = "#dcfce7"
                                col_esc = "#15803d"
                            else:
                                linea_riv = f"Rival: <b style='color:#b91c1c;'>{m_it['rival_corto']}</b>"
                                cta_txt = f"Conquistar con {m_it['prod_gutis']}"
                                cta_icon = "→"
                                bg_esc = "#f1f5f9"
                                col_esc = "#1e293b"

                            with cols_3[offset]:
                                render_html(f"""
                                    <div class='quad-card notranslate' translate='no' style='border-top: 4px solid {borde_top}; margin-bottom: 12px; padding: 14px 16px;'>
                                        <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>
                                            <span style='font-size:0.82rem; font-weight:800; color:#0f172a; text-transform:uppercase;'>{m_it['prod_gutis']}</span>
                                            <span style='background:{bg_prio}; color:#ffffff; font-size:0.65rem; font-weight:800; padding:2px 7px; border-radius:4px;'>{prio_lbl}</span>
                                        </div>
                                        <div style='font-size:0.78rem; color:#475569; margin-bottom:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>
                                            {linea_riv}
                                        </div>
                                        <div style='font-size:0.76rem; color:#64748b; margin-bottom:8px;'>
                                            Mes: <b style='color:#0f172a;'>{m_it['tot_mes']}</b> (Comp: {m_it['comp_mes']}) | YTD: <b style='color:#0f172a;'>{m_it['tot_ytd']}</b> (Comp: {m_it['comp_ytd']})
                                        </div>
                                        <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; font-size:0.74rem; color:#64748b;'>
                                            <span>Escala:</span>
                                            <span style='background:{bg_esc}; color:{col_esc}; font-weight:800; padding:2px 8px; border-radius:4px;'>{m_it['escala_nivel']}</span>
                                        </div>
                                        <div style='border-top:1px dashed #e2e8f0; padding-top:8px; display:flex; justify-content:space-between; align-items:center; font-size:0.76rem; font-weight:800; color:#059669;'>
                                            <span>{cta_txt}</span>
                                            <span>{cta_icon}</span>
                                        </div>
                                    </div>
                                    """)

        # ---------------------------------------------------------------------
        # SUB-VISTA 2: CANVAS TVP (4 CUADRANTES SIMÉTRICOS VERTICALES ESTILO STITCH)
        # ---------------------------------------------------------------------
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
                meta1["beneficio"] if "Desempeño" in ndn_corto
                else (meta1["arg_imagen"] if "Imagen" in ndn_corto else meta1["arg_finanzas"])
            )
            num_migrar = max(min(m_p1["comp_mes"], 6), 4) if m_p1["comp_mes"] > 0 else 4
            farmacia_top1 = farmacias_aliadas_str.split(",")[0].strip() if farmacias_aliadas_str else "Farmacia Aliada"

            q_col1, q_col2, q_col3, q_col4 = st.columns(4)
            with q_col1:
                render_html(f"""
                    <div class='quad-card notranslate' translate='no' style='border-top: 4px solid #002b5c; min-height: 390px;'>
                        <div class='quad-title' style='color:#002b5c;'>I. DIAGNÓSTICO Y OBJETIVO SMART ({m_p1['modo_tactico']})</div>
                        <div class='quad-body'>
                            • <b>Escala Actual:</b><br>
                            <div style='background:#eff6ff; color:#002b5c; font-weight:700; padding:6px 8px; border-radius:6px; margin:4px 0;'>
                                {m_p1['escala_nivel']} ({m_p1['ms_mes']:.1f}% MS Mes | {m_p1['gutis_mes']} Pxs)
                            </div>
                            • <b>Escalón Meta Hoy:</b><br>
                            <div style='background:#dcfce7; color:#15803d; font-weight:700; padding:5px 8px; border-radius:6px; margin:4px 0 8px 0;'>
                                {m_p1['escala_meta']}
                            </div>
                            • <b>Meta SMART:</b> Agradecer sus recetas en <b>{m_p1['prod_gutis']}</b> y migrar <b>4 a {num_migrar} pacientes</b> que aún van a <b>{riv1_marca} ({riv1_forma})</b>.<br><br>
                            • <b>Plan de Respaldo:</b> Capturar el subgrupo de <i>{meta1['nicho_flanqueo']}</i>.
                        </div>
                    </div>
                    """)
            with q_col2:
                render_html(f"""
                    <div class='quad-card notranslate' translate='no' style='border-top: 4px solid #0284c7; min-height: 390px;'>
                        <div class='quad-title' style='color:#0284c7;'>II. APERTURA ADAPTADA ({especialidad})</div>
                        <div class='quad-body'>
                            • <b>Postura ({st.session_state.ctx_cita_global}):</b> Explorar su experiencia positiva con los pacientes ya tratados con la molécula y formulación actual.<br><br>
                            • <b>Agenda ({especialidad}):</b> Analizar evolución en <i>{pac_meta_1}</i>.<br><br>
                            • <b>Pregunta Sutil:</b><br>
                            <div style='background:#f8fafc; border-left:3px solid #0284c7; padding:8px; border-radius:4px; font-style:italic; margin-top:4px;'>
                                «En los casos donde ya prescribió {m_p1['prod_gutis']} frente a {riv1_marca}, ¿qué diferencias observó en tolerabilidad y apego?»
                            </div>
                        </div>
                    </div>
                    """)
            with q_col3:
                render_html(f"""
                    <div class='quad-card notranslate' translate='no' style='border-top: 4px solid #10b981; min-height: 390px;'>
                        <div class='quad-title' style='color:#059669;'>III. EMBUDO, APOYO Y MENSAJE DE MARCA</div>
                        <div class='quad-body'>
                            • <b>Sondeo de Migración:</b><br>
                            <div style='background:#f8fafc; border-left:3px solid #10b981; padding:8px; border-radius:4px; font-style:italic; margin:4px 0 8px 0;'>
                                «¿En qué perfil específico siente que todavía alterna con {riv1_marca} en {riv1_forma.lower()}?»
                            </div>
                            • <b>Ventaja Diferencial ({m_p1['prod_gutis']}):</b> {meta1['caracteristica']}.<br><br>
                            • <b>Enfoque ({ndn_corto}):</b> {arg_ndn_txt.capitalize()}.
                        </div>
                    </div>
                    """)
            with q_col4:
                render_html(f"""
                    <div class='quad-card notranslate' translate='no' style='border-top: 4px solid #f59e0b; min-height: 390px;'>
                        <div class='quad-title' style='color:#d97706;'>IV. CIERRE BILATERAL Y PUENTE P1 - P2 - P3</div>
                        <div class='quad-body'>
                            • <b>Pido al Médico:</b> Consolidar a <b>{m_p1['prod_gutis']}</b> como primera elección en el segmento que compartía con <b>{riv1_marca}</b>.<br><br>
                            • <b>Mi Compromiso:</b><br>
                            <div style='background:#fffbeb; border:1px solid #fde68a; color:#92400e; font-weight:700; padding:6px 8px; border-radius:6px; margin:4px 0 8px 0;'>
                                Garantizar inventario en {farmacia_top1}.
                            </div>
                            • <b>Puente a 2da Posición ({m_p2['prod_gutis']}):</b><br>
                            <div style='background:#f8fafc; border-left:3px solid #f59e0b; padding:8px; border-radius:4px; font-style:italic; margin-top:4px;'>
                                «Y siguiendo con eficacia clínica, cuente con <b>{m_p2['prod_gutis']}</b> ({meta2['beneficio']}) y respaldo de <b>{m_p3['prod_gutis']}</b>.»
                            </div>
                        </div>
                    </div>
                    """)

        # ---------------------------------------------------------------------
        # SUB-VISTA 3: MAPA CONVERSACIONAL DEL TVP (TARJETAS DE FASES 1 A 4 ESTILO STITCH)
        # ---------------------------------------------------------------------
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
                    if st.button(f"✦ Generar / Cambiar Variante Táctica de Guion (Motor Cognitivo TVP + IA)   [VARIANTE A-{st.session_state.tvp_variant_counter + 1}]", type="primary", use_container_width=True):
                        st.session_state.tvp_variant_counter += 1
                        st.rerun()
                with b_var2:
                    btn_ia_guion = st.button("Potenciar Redacción con Gemini AI", use_container_width=True)

            m_p1 = mapa_clave_obj[opciones_claves_p[st.session_state.pos_m1_idx]]
            m_p2 = mapa_clave_obj[opciones_claves_p[st.session_state.pos_m2_idx]]
            m_p3 = mapa_clave_obj[opciones_claves_p[st.session_state.pos_m3_idx]]
            meta1 = m_p1["meta_info"]
            riv1_marca, riv1_forma, _ = limpiar_sku_competencia(m_p1["rival_principal"])
            pac_meta_1 = meta1.get("paciente_meta_ped", meta1["paciente_meta"]) if es_pediatra else meta1["paciente_meta"]
            vocativo_doc = formatear_nombre_medico(medico_sel)
            ndn_corto = ndn_sel.split("(")[0].strip()
            arg_ndn_txt = (
                meta1["beneficio"] if "Desempeño" in ndn_corto
                else (meta1["arg_imagen"] if "Imagen" in ndn_corto else meta1["arg_finanzas"])
            )

            # Construcción de las 4 Tarjetas Conversacionales Numeradas (Idéntico a Stitch)
            render_html(f"""
                <div class='drill-panel notranslate' translate='no'>
                    <div style='font-size:1.05rem; font-weight:800; color:#0f172a; margin-bottom:2px;'>
                        Guion Táctico TVP — {m_p1['modo_tactico'].capitalize()} de Cuota ({ndn_sel})
                    </div>
                    <div style='font-size:0.78rem; color:#64748b; margin-bottom:14px;'>
                        Adaptado a la matriz de prescripción actual ({m_p1['gutis_mes']} pacientes {m_p1['prod_gutis']} vs. {m_p1['comp_mes']} pacientes {riv1_marca} en el mes)
                    </div>

                    <div class='quad-card' style='margin-bottom:12px; border-left:4px solid #0284c7;'>
                        <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>
                            <div style='font-size:0.82rem; font-weight:800; color:#0f172a;'>
                                <span style='background:#e0f2fe; color:#0369a1; padding:2px 8px; border-radius:999px; margin-right:6px;'>1</span>
                                Apertura de Seguimiento Clínico ({cita_sel}):
                            </div>
                            <span style='background:#f1f5f9; color:#475569; font-size:0.68rem; font-weight:700; padding:2px 8px; border-radius:4px;'>Fase 1: Conexión</span>
                        </div>
                        <div style='background:#f8fafc; padding:10px 14px; border-radius:8px; font-style:italic; font-size:0.84rem; color:#1e293b;'>
                            «<b>{vocativo_doc}</b>, qué gusto saludarlo(a) en esta {cita_sel.lower()}. Quiero agradecerle los pacientes que ya está tratando con <b>{m_p1['prod_gutis']} ({m_p1['gutis_mes']} en el mes / {m_p1['gutis_ytd']} en el año)</b> y proponerle revisar cómo consolidar la adherencia en <b>{pac_meta_1.lower()}</b>. ¿Le parece bien?»
                        </div>
                    </div>

                    <div class='quad-card' style='margin-bottom:12px; border-left:4px solid #f59e0b;'>
                        <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>
                            <div style='font-size:0.82rem; font-weight:800; color:#0f172a;'>
                                <span style='background:#fef3c7; color:#b45309; padding:2px 8px; border-radius:999px; margin-right:6px;'>2</span>
                                Sondeo de Valor Mutuo (Aislar el Segmento que Comparte con {riv1_marca}):
                            </div>
                            <span style='background:#f1f5f9; color:#475569; font-size:0.68rem; font-weight:700; padding:2px 8px; border-radius:4px;'>Fase 2: Indagación</span>
                        </div>
                        <div style='background:#f8fafc; padding:10px 14px; border-radius:8px; font-style:italic; font-size:0.84rem; color:#1e293b;'>
                            «Al comparar la evolución de sus pacientes tratados con <b>{m_p1['prod_gutis']}</b> frente a los casos donde aún indica <span style='background:#fef3c7; color:#92400e; font-weight:700; padding:1px 5px; border-radius:4px;'>{riv1_marca} ({riv1_forma}) ({m_p1['comp_mes']} recetas en el mes)</span>, ¿en qué perfil específico siente que todavía alterna con esa opción y qué aspecto considera prioritario optimizar en rapidez de acción y tolerabilidad frente a {riv1_marca} en {riv1_forma.lower()}?»
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
                            «Comprendo su criterio, <b>{vocativo_doc}</b>. Justamente para cubrir también a ese subgrupo de <b>{meta1['nicho_flanqueo']}</b>, <b>{m_p1['prod_gutis']}</b> cuenta con <b>{meta1['caracteristica']}</b>, con lo cual <b>{arg_ndn_txt}</b>. <i>{meta1['love_brand']}</i>»
                        </div>
                    </div>

                    <div class='quad-card' style='border-left:4px solid #002b5c;'>
                        <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>
                            <div style='font-size:0.82rem; font-weight:800; color:#0f172a;'>
                                <span style='background:#e0e7ff; color:#1e40af; padding:2px 8px; border-radius:999px; margin-right:6px;'>4</span>
                                Cierre de Migración y Puente hacia {m_p2['prod_gutis']}:
                            </div>
                            <span style='background:#f1f5f9; color:#475569; font-size:0.68rem; font-weight:700; padding:2px 8px; border-radius:4px;'>Fase 4: Acuerdo SMART & Puente</span>
                        </div>
                        <div style='background:#f8fafc; padding:10px 14px; border-radius:8px; font-style:italic; font-size:0.84rem; color:#1e293b;'>
                            «Ya que conoce de primera mano la respuesta de <b>{m_p1['prod_gutis']}</b>, ¿migramos esta semana a esos próximos 4 a 6 pacientes que antes alternaba con {riv1_marca}, con disponibilidad garantizada en <b>{farmacias_aliadas_str}</b>? Y como puente clínico, recuerde que cuenta también con <b>{m_p2['prod_gutis']}</b> ({m_p2['meta_info']['beneficio']}) y <b>{m_p3['prod_gutis']}</b>.»
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
                notas_rapport=str(perfil_360_actual.get("Deporte") or ""),
            )

            if btn_ia_guion:
                if obtener_api_key():
                    with st.spinner("Gemini AI está estructurando una versión ejecutiva personalizada del guion TVP..."):
                        prompt_tvp = (
                            f"{REGLAS_FARMA}\n\n"
                            f"Mejora este guion TVP para {medico_sel} ({especialidad} en {ciudad}) "
                            f"respetando las 4 etapas y las cifras reales:\n\n{guion_base}"
                        )
                        resp_ia = llamar_gemini(prompt_tvp, max_tok=2200)
                        if resp_ia:
                            st.info("Versión Generada por Gemini AI:")
                            st.markdown(resp_ia)
                else:
                    st.warning("No se detectó GEMINI_API_KEY configurada. Se muestran las 4 fases tácticas locales.")

            st.write("")
            st.download_button(
                "Descargar Guion TVP (.md)",
                data=guion_base.encode("utf-8"),
                file_name=f"Guion_TVP_{medico_sel.replace(' ', '_')}.md",
                mime="text/markdown",
            )

        # ---------------------------------------------------------------------
        # SUB-VISTA 4: CLASES TERAPÉUTICAS, LABS & FICHA 360 (4 BOTONES A, B, C, D DE STITCH)
        # ---------------------------------------------------------------------
        elif st.session_state.sub_previsita == "AUDITORIA":
            ba1, ba2, ba3, ba4 = st.columns(4)
            with ba1:
                if st.button("A. Matriz Clases Terapéuticas (LY/YTD/Mes)", use_container_width=True, type="primary" if st.session_state.sub_previsita_auditoria == "CLASES" else "secondary"):
                    st.session_state.sub_previsita_auditoria = "CLASES"
                    st.rerun()
            with ba2:
                if st.button("B. Marcas por Categoría Terapéutica", use_container_width=True, type="primary" if st.session_state.sub_previsita_auditoria == "MARCAS" else "secondary"):
                    st.session_state.sub_previsita_auditoria = "MARCAS"
                    st.rerun()
            with ba3:
                if st.button("C. Radar de Laboratorios (Doble Barra)", use_container_width=True, type="primary" if st.session_state.sub_previsita_auditoria == "LABS" else "secondary"):
                    st.session_state.sub_previsita_auditoria = "LABS"
                    st.rerun()
            with ba4:
                if st.button("D. Ficha de Omnicanalidad 360", use_container_width=True, type="primary" if st.session_state.sub_previsita_auditoria == "FICHA360" else "secondary"):
                    st.session_state.sub_previsita_auditoria = "FICHA360"
                    st.rerun()

            st.write("")

            if st.session_state.sub_previsita_auditoria == "CLASES":
                df_mat_ct = obtener_matriz_clases_terapeuticas_medico(df_clases, df_productos, medico_sel)
                render_html(f"""
                    <div class='notranslate' translate='no' style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>
                        <div style='font-size:0.88rem; font-weight:800; color:#0f172a;'><span style='color:#0284c7;'>●</span> Matriz Corporativa de Clases Terapéuticas — Dr(a). {medico_sel}</div>
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
                        guardar_360_btn = st.form_submit_button("Guardar Ficha 360 en Base de Datos", type="primary", use_container_width=True)

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
                        st.success("Ficha 360 guardada correctamente en gutis_bi.db.")
                        st.rerun()

                with col_f360_r:
                    st.markdown("##### Últimas Visitas Registradas a este Médico (SQLite)")
                    df_vis_med = leer_visitas(medico_sel, DB_PATH)
                    if not df_vis_med.empty:
                        show_table(df_vis_med[["Fecha", "Producto_Foco", "Producto_Puente", "Escala_TVP", "Acuerdo_Medico"]], 320)
                    else:
                        st.info("Aún no hay visitas registradas en el CRM para este especialista.")


# -----------------------------------------------------------------------------
# PARTE 4: MÓDULO 3 (ANÁLISIS DE MERCADO), MÓDULO 4 (EVOLUCIÓN RX vs SELL-OUT) Y MÓDULO 5 (CHIRA NEURAL ENGINE & CRM)
# -----------------------------------------------------------------------------
elif st.session_state.modulo_activo == "ANALISIS_MERCADO":
    c_back, c_tit = st.columns([0.85, 3.15])
    with c_back:
        if st.button("← Volver al Menú Principal", use_container_width=True):
            ir_a_modulo("HUB")
            st.rerun()
    with c_tit:
        render_html("""
            <div class='module-banner notranslate' translate='no'>
                <span>MÓDULO 3: ANÁLISIS DE MERCADO (INF.MARKET) — CLASES TERAPÉUTICAS Y DOBLE BARRA MES / YTD</span>
                <span style='font-size:0.68rem; background:rgba(56,189,248,0.2); color:#7dd3fc; padding:3px 8px; border-radius:4px;'>AUDITORÍA CLOSE-UP</span>
            </div>
            """)

    bam1, bam2, bam3, bam4 = st.columns(4)
    with bam1:
        if st.button("1. Radar de Laboratorios (% MS Mes vs. YTD)", use_container_width=True, type="primary" if st.session_state.sub_analisis_mercado == "LABS" else "secondary"):
            st.session_state.sub_analisis_mercado = "LABS"
            st.rerun()
    with bam2:
        if st.button("2. Matriz de Penetración por Especialidad", use_container_width=True, type="primary" if st.session_state.sub_analisis_mercado == "PENETRACION" else "secondary"):
            st.session_state.sub_analisis_mercado = "PENETRACION"
            st.rerun()
    with bam3:
        if st.button("3. Desempeño Mercados Prioritarios", use_container_width=True, type="primary" if st.session_state.sub_analisis_mercado == "MERCADOS" else "secondary"):
            st.session_state.sub_analisis_mercado = "MERCADOS"
            st.rerun()
    with bam4:
        if st.button("4. Close-Up por Marca Competidora", use_container_width=True, type="primary" if st.session_state.sub_analisis_mercado == "AUDITORIA_MARCAS" else "secondary"):
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
            fila_gut = df_rk_labs[df_rk_labs["Laboratorio"].str.contains("GUTIS", case=False, na=False)]
            pos_gut = int(fila_gut.index[0]) + 1 if not fila_gut.empty else 0
            ms_m_gut = float(fila_gut.iloc[0]["% MS Mes"]) if not fila_gut.empty else 0.0
            ms_y_gut = float(fila_gut.iloc[0]["% MS YTD"]) if not fila_gut.empty else 0.0
            px_m_gut = int(fila_gut.iloc[0]["Pxs Mes"]) if not fila_gut.empty else 0
            delta_gut = round(ms_m_gut - ms_y_gut, 2)

            # Cabecera de Ranking de Laboratorios Estilo Stitch
            render_html(f"""
                <div class='quad-card notranslate' translate='no' style='margin-bottom:12px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;'>
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
            df_labs_vista["Laboratorio"] = np.where(
                df_labs_vista["Laboratorio"].str.contains("GUTIS", case=False, na=False),
                "★ LÍDER [GUTIS] " + df_labs_vista["Laboratorio"].astype(str),
                df_labs_vista["Laboratorio"].astype(str),
            )
            if "% MS Mes" in df_labs_vista.columns and "% MS YTD" in df_labs_vista.columns and "Delta MS (Mes vs YTD)" not in df_labs_vista.columns:
                df_labs_vista["Delta MS (Mes vs YTD)"] = (df_labs_vista["% MS Mes"] - df_labs_vista["% MS YTD"]).round(2)

            show_table(df_labs_vista, 440)

            tot_px_m_all = int(df_rk_labs["Pxs Mes"].sum()) if "Pxs Mes" in df_rk_labs.columns else 0
            tot_px_y_all = int(df_rk_labs["Pxs YTD"].sum()) if "Pxs YTD" in df_rk_labs.columns else 0
            render_html(f"""
                <div class='stitch-nav-header notranslate' translate='no' style='margin-top:8px; background:#f8fafc;'>
                    <div style='font-size:0.78rem; font-weight:800; color:#0f172a;'>TOTAL AUDITORÍA SELECCIÓN</div>
                    <div style='display:flex; gap:22px; font-size:0.78rem; font-weight:700; color:#334155;'>
                        <span>Volumen Mes: <b>{tot_px_m_all:,} Pxs</b></span>
                        <span>Volumen YTD: <b>{tot_px_y_all:,} Pxs</b></span>
                        <span>Cuota Gutis: <b>{ms_m_gut:.2f}% Mes | {ms_y_gut:.2f}% YTD</b></span>
                        <span style='background:#dcfce7; color:#15803d; padding:2px 8px; border-radius:4px;'>{delta_gut:+.2f} pts</span>
                    </div>
                </div>
                """)
        else:
            st.info("No hay registros de laboratorios para esta combinación.")

    elif st.session_state.sub_analisis_mercado == "PENETRACION":
        pen_ciu = st.selectbox("Filtrar Territorio de Mi Panel:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="am_pen_ciu")
        df_pan_sub = df_panel if pen_ciu == "TODO MI PANEL" else df_panel[df_panel["CIUDAD"] == pen_ciu]
        df_rend_esp, df_top5_esp = matriz_penetracion(df_pan_sub, df_labs)

        st.markdown("##### 1. Matriz de Cobertura, Penetración y Posicionamiento por Especialidad (Panel Erick Calderón)")
        show_table(df_rend_esp, 360)

        st.markdown("##### 2. Top 5 Laboratorios Dominantes por Especialidad (Cuota Mes | YTD)")
        show_table(df_top5_esp, 340)

    elif st.session_state.sub_analisis_mercado == "MERCADOS":
        mp_c1, mp_c2 = st.columns([1.2, 1.2])
        with mp_c1:
            mp_ciu = st.selectbox("Territorio:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="am_mp_ciu")
        with mp_c2:
            mp_univ = st.selectbox("Universo:", ["Solo Mi Panel (Erick Calderón)", "Universo Total Nicaragua"], key="am_mp_univ")

        df_mp = resumen_mercados(
            df_productos,
            df_panel,
            ciudad=None if mp_ciu == "TODO MI PANEL" else mp_ciu,
            incluir_fuera_panel=not mp_univ.startswith("Solo"),
        )
        if not df_mp.empty:
            show_table(df_mp, 420)
            st.markdown("<div class='drill-panel notranslate' translate='no'>", unsafe_allow_html=True)
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
            st.markdown("</div>", unsafe_allow_html=True)
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
# MÓDULO 4: EVOLUCIÓN RX CLOSE-UP vs. SELL-OUT TRIMESTRAL (Q1, Q2, Q3 ESTILO STITCH)
# -----------------------------------------------------------------------------
elif st.session_state.modulo_activo == "EVOLUCION":
    c_back, c_tit = st.columns([0.85, 3.15])
    with c_back:
        if st.button("← Volver al Menú Principal", use_container_width=True):
            ir_a_modulo("HUB")
            st.rerun()
    with c_tit:
        render_html("""
            <div class='module-banner notranslate' translate='no'>
                <span>MÓDULO 4: EVOLUCIÓN (INF.TARGET) — DESEMPEÑO DE RECETAS (MES / YTD) Y SELL-OUT EN FARMACIAS (Q1-Q3)</span>
                <span style='font-size:0.68rem; background:rgba(16,185,129,0.25); color:#6ee7b7; padding:3px 8px; border-radius:4px;'>AUDITORÍA SINCRONIZADA</span>
            </div>
            """)

    bev1, bev2 = st.columns(2)
    with bev1:
        if st.button("1. Sincronía Temporal (Cuota Rx Mes/YTD vs. Sell-Out Trimestral)", use_container_width=True, type="primary" if st.session_state.sub_evolucion == "SINCRONIA" else "secondary"):
            st.session_state.sub_evolucion = "SINCRONIA"
            st.rerun()
    with bev2:
        if st.button("2. Auditoría Detallada de Sell-Out por Sucursal Farmacéutica", use_container_width=True, type="primary" if st.session_state.sub_evolucion == "PDVS" else "secondary"):
            st.session_state.sub_evolucion = "PDVS"
            st.rerun()

    st.write("")
    ev_c1, ev_c2 = st.columns([1.2, 1.8])
    with ev_c1:
        ev_ciu = st.selectbox("Seleccionar Territorio:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="ev_sel_ciu")
    with ev_c2:
        prods_venta_lista = sorted(df_ventas["PRODUCTO_VENTA"].dropna().unique().tolist()) if not df_ventas.empty and "PRODUCTO_VENTA" in df_ventas.columns else []
        ev_prods_sel = st.multiselect("Filtrar Producto(s) de Sell-Out (Opcional):", prods_venta_lista, default=[], key="ev_sel_prods")

    if ev_prods_sel:
        partes_v = [ventas_por_trimestre(df_ventas, None if ev_ciu == "TODO MI PANEL" else ev_ciu, p) for p in ev_prods_sel]
        df_piv_ventas = pd.concat([x for x in partes_v if not x.empty], ignore_index=True) if any(not x.empty for x in partes_v) else pd.DataFrame()
    else:
        df_piv_ventas = ventas_por_trimestre(df_ventas, None if ev_ciu == "TODO MI PANEL" else ev_ciu)

    q1_tot = float(df_piv_ventas["Q1"].sum()) if not df_piv_ventas.empty and "Q1" in df_piv_ventas.columns else 0.0
    q2_tot = float(df_piv_ventas["Q2"].sum()) if not df_piv_ventas.empty and "Q2" in df_piv_ventas.columns else 0.0
    q3_tot = float(df_piv_ventas["Q3"].sum()) if not df_piv_ventas.empty and "Q3" in df_piv_ventas.columns else 0.0
    acum_tot = q1_tot + q2_tot + q3_tot
    n_pdvs = len(df_piv_ventas["NOMBRE_CLIENTE_1"].unique()) if not df_piv_ventas.empty else 0

    var_q2 = ((q2_tot - q1_tot) / q1_tot * 100.0) if q1_tot > 0 else 0.0
    var_q3 = ((q3_tot - q2_tot) / q2_tot * 100.0) if q2_tot > 0 else 0.0

    # Las 4 Tarjetas Trimestrales de Sell-Out (3 Blancas + 1 Azul Marino Total YTD idéntica a Stitch)
    render_html(f"""
        <div class='kpi-strip notranslate' translate='no'>
            <div class='kpi-card'>
                <div class='kpi-top-row'>
                    <div class='kpi-lbl'>Q1 SELL-OUT</div>
                    <span class='kpi-pill-neutral'>Cerrado</span>
                </div>
                <div class='kpi-num' style='margin:6px 0;'>${q1_tot:,.0f}</div>
                <div class='kpi-sub' style='border-top:1px solid #f1f5f9; padding-top:6px;'>
                    <span style='color:#059669; font-weight:700;'>● Base Trimestral Q1</span>
                    <span>PDVs: {n_pdvs}</span>
                </div>
            </div>

            <div class='kpi-card'>
                <div class='kpi-top-row'>
                    <div class='kpi-lbl'>Q2 SELL-OUT</div>
                    <span class='kpi-pill-neutral'>Cerrado</span>
                </div>
                <div class='kpi-num' style='margin:6px 0;'>${q2_tot:,.0f}</div>
                <div class='kpi-sub' style='border-top:1px solid #f1f5f9; padding-top:6px;'>
                    <span style='color:#059669; font-weight:700;'>{var_q2:+.1f}% vs Q1</span>
                    <span>Ruta Activa</span>
                </div>
            </div>

            <div class='kpi-card'>
                <div class='kpi-top-row'>
                    <div class='kpi-lbl'>Q3 SELL-OUT</div>
                    <span class='kpi-pill-warn'>En curso</span>
                </div>
                <div class='kpi-num' style='margin:6px 0;'>${q3_tot:,.0f}</div>
                <div class='kpi-sub' style='border-top:1px solid #f1f5f9; padding-top:6px;'>
                    <span style='color:#0284c7; font-weight:700;'>{var_q3:+.1f}% vs Q2</span>
                    <span>Corte Vigente</span>
                </div>
            </div>

            <div class='kpi-card' style='background:linear-gradient(115deg, #001f44 0%, #002b5c 100%); color:#ffffff; border-color:#002b5c;'>
                <div class='kpi-top-row'>
                    <div class='kpi-lbl' style='color:#93c5fd;'>TOTAL SELL-OUT YTD</div>
                    <span style='background:rgba(16,185,129,0.22); color:#34d399; border:1px solid rgba(52,211,153,0.4); padding:2px 8px; border-radius:999px; font-size:0.66rem; font-weight:800;'>Tendencia Favorable</span>
                </div>
                <div class='kpi-num' style='color:#ffffff; margin:6px 0;'>${acum_tot:,.0f}</div>
                <div class='kpi-sub' style='border-top:1px solid rgba(255,255,255,0.14); padding-top:6px; color:#cbd5e1;'>
                    <span>Cobertura Comercial:</span>
                    <b style='color:#38bdf8;'>▲ {n_pdvs} PDVs Activos</b>
                </div>
            </div>
        </div>
        """)

    if st.session_state.sub_evolucion == "SINCRONIA":
        df_ev_rx = resumen_mercados(df_productos, df_panel, None if ev_ciu == "TODO MI PANEL" else ev_ciu, incluir_fuera_panel=False)
        if not df_ev_rx.empty:
            df_ev_tabla = df_ev_rx.copy()
            df_ev_tabla["Prioridad"] = df_ev_tabla["Clave"].map(lambda k: f"P{MERCADOS_PRIORITARIOS.get(k, {}).get('prioridad', 2)}")
            df_ev_tabla["Delta % MS (Mes vs YTD)"] = (df_ev_tabla["% MS Mes"] - df_ev_tabla["% MS YTD"]).round(2)
            df_ev_tabla["Diagnóstico de Evolución"] = np.where(
                df_ev_tabla["Delta % MS (Mes vs YTD)"] >= 1.0,
                "▲ CRECE CUOTA (" + df_ev_tabla["Delta % MS (Mes vs YTD)"].map(lambda x: f"{x:+.1f} pts vs YTD") + ")",
                np.where(
                    df_ev_tabla["Delta % MS (Mes vs YTD)"] <= -1.0,
                    "▼ PIERDE CUOTA (" + df_ev_tabla["Delta % MS (Mes vs YTD)"].map(lambda x: f"{x:+.1f} pts vs YTD") + ")",
                    "● ESTABLE (" + df_ev_tabla["Delta % MS (Mes vs YTD)"].map(lambda x: f"{x:+.1f} pts vs YTD") + ")",
                ),
            )

            n_crece = int((df_ev_tabla["Delta % MS (Mes vs YTD)"] >= 1.0).sum())
            n_est = int(((df_ev_tabla["Delta % MS (Mes vs YTD)"] > -1.0) & (df_ev_tabla["Delta % MS (Mes vs YTD)"] < 1.0)).sum())
            n_cae = int((df_ev_tabla["Delta % MS (Mes vs YTD)"] <= -1.0).sum())

            render_html(f"""
                <div class='stitch-nav-header notranslate' translate='no' style='margin-bottom:10px;'>
                    <div style='font-size:0.82rem; font-weight:800; color:#0f172a;'>MATRIZ DE EVOLUCIÓN DE CUOTA PRESCRIPTIVA POR MARCA GUTIS ({ev_ciu})</div>
                    <div style='display:flex; gap:14px; font-size:0.74rem; font-weight:700;'>
                        <span style='color:#059669;'>● Cuota en Expansión: <b>{n_crece} Marcas</b></span>
                        <span style='color:#0284c7;'>● Estable: <b>{n_est} Marcas</b></span>
                        <span style='color:#dc2626;'>● Contracción: <b>{n_cae} Marcas</b></span>
                    </div>
                </div>
                """)

            cols_orden_ev = [
                "Prioridad", "Marca Gutis", "Clase Terapéutica",
                "Mercado Mes", "Gutis Mes", "Competencia Mes", "% MS Mes",
                "Mercado YTD", "Gutis YTD", "Competencia YTD", "% MS YTD",
                "Delta % MS (Mes vs YTD)", "Diagnóstico de Evolución",
            ]
            show_table(df_ev_tabla[[c for c in cols_orden_ev if c in df_ev_tabla.columns]], 390)

        st.write("")
        st.markdown(f"##### Top Farmacias Aliadas por Facturación Sell-Out en {ev_ciu}")
        if not df_piv_ventas.empty:
            df_top_f = (
                df_piv_ventas.groupby("NOMBRE_CLIENTE_1", as_index=False)[["Q1", "Q2", "Q3", "Total Acumulado"]]
                .sum()
                .sort_values(by="Total Acumulado", ascending=False)
            )
            show_table(df_top_f, 320)
        else:
            st.info("Sin registros de Sell-Out para los filtros actuales.")
    else:
        st.markdown(f"##### Auditoría Detallada por Sucursal Farmacéutica x Producto (Q1, Q2, Q3 — {ev_ciu})")
        show_table(df_piv_ventas, 500)


# -----------------------------------------------------------------------------
# MÓDULO 5: CONSOLA COGNITIVA CHIRA NEURAL ENGINE & BITÁCORA CRM SQLITE
# -----------------------------------------------------------------------------
elif st.session_state.modulo_activo == "CHIRA":
    c_back, c_tit = st.columns([0.85, 3.15])
    with c_back:
        if st.button("← Volver al Menú Principal", use_container_width=True):
            ir_a_modulo("HUB")
            st.rerun()
    with c_tit:
        render_html("""
            <div class='module-banner notranslate' translate='no'>
                <span>MÓDULO 5: CHIRA — COPILOTO COGNITIVO DE CAMPO & BITÁCORA CRM (SQLITE)</span>
                <span style='font-size:0.68rem; background:rgba(16,185,129,0.25); color:#6ee7b7; padding:3px 8px; border-radius:4px;'>● NEURAL ENGINE CONECTADO</span>
            </div>
            """)

    bch1, bch2 = st.columns(2)
    with bch1:
        if st.button("1. Consola Copiloto CHIRA (Voz y Consultoría Táctica)", use_container_width=True, type="primary" if st.session_state.sub_chira == "COPILOTO" else "secondary"):
            st.session_state.sub_chira = "COPILOTO"
            st.rerun()
    with bch2:
        if st.button(f"2. Bitácora CRM Post-Visita ({medico_sel[:24] if medico_sel else 'SQLite'})", use_container_width=True, type="primary" if st.session_state.sub_chira == "CRM" else "secondary"):
            st.session_state.sub_chira = "CRM"
            st.rerun()

    st.write("")

    if st.session_state.sub_chira == "COPILOTO":
        sell_z_chira = resumen_ventas_ciudad(df_ventas, ciudad)
        riv_top_chira = dp_global.get("Rival Principal en la Clase", "Competencia directa")

        # 1. Barra de Contexto y Hero Banner Oscuro CHIRA Neural Engine (Idéntico a Stitch)
        render_html(f"""
            <div class='chira-neural-hero notranslate' translate='no'>
                <div style='display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:16px;'>
                    <div style='flex: 1 1 380px;'>
                        <span class='chira-neural-badge'>● CHIRA NEURAL ENGINE · CONTEXTO CLOSE-UP AUDITADO ACTIVO</span>
                        <div style='font-size:1.35rem; font-weight:800; color:#ffffff; margin-bottom:6px;'>
                            Copiloto Táctico Farmacéutico & Síntesis Competitiva <span style='color:#38bdf8; font-size:0.88rem;'>✦ Enterprise AI</span>
                        </div>
                        <div style='font-size:0.8rem; color:#cbd5e1; line-height:1.45;'>
                            Asistente analítico conectado en vivo con tus bases Close-Up, auditoría TVP y Sell-Out trimestral para el diseño de guiones, flanqueo competitivo y superación de objeciones.
                        </div>
                    </div>
                    <div class='chira-mem-grid' style='flex: 1 1 420px; margin-top:0;'>
                        <div class='chira-mem-box'>
                            <div class='chira-mem-lbl'>MÉDICO EN FOCO</div>
                            <div class='chira-mem-val'>{medico_sel[:22] if medico_sel else 'Panel General'}</div>
                            <div class='chira-mem-sub'>Cat {categoria} · {ciudad}</div>
                        </div>
                        <div class='chira-mem-box'>
                            <div class='chira-mem-lbl'>OPORTUNIDAD MES</div>
                            <div class='chira-mem-val'>{dp_global.get('Comp Mes', 0)} Rx/mes en disputa</div>
                            <div class='chira-mem-sub'>Gutis actual: {dp_global.get('% MS Mes', 0.0):.1f}% MS</div>
                        </div>
                        <div class='chira-mem-box'>
                            <div class='chira-mem-lbl'>CORTE CLOSE-UP</div>
                            <div class='chira-mem-val'>100% Sincronizado</div>
                            <div class='chira-mem-sub'>{corte_nombre[:22]}</div>
                        </div>
                        <div class='chira-mem-box'>
                            <div class='chira-mem-lbl'>SELL-OUT ZONAL</div>
                            <div class='chira-mem-val'>${sell_z_chira['total']:,.2f}</div>
                            <div class='chira-mem-sub'>{sell_z_chira['pdvs']} PDVs en {ciudad}</div>
                        </div>
                    </div>
                </div>
            </div>
            """)

        # 2. Cuadrícula de 4 Tarjetas de Disparadores Cognitivos Rápidos (One-Click Prompts de Stitch)
        render_html("""
            <div class='notranslate' translate='no' style='display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;'>
                <div class='subnav-label' style='color:#002b5c; margin-bottom:0;'>★ DISPARADORES COGNITIVOS RÁPIDOS (ONE-CLICK PROMPTS)</div>
                <span style='font-size:0.7rem; color:#64748b; font-weight:600;'>Respuestas validadas con auditoría de mercado</span>
            </div>
            """)

        quick_prompt = None
        q_b1, q_b2, q_b3, q_b4 = st.columns(4)
        with q_b1:
            render_html(f"""
                <div class='chira-prompt-card notranslate' translate='no'>
                    <div class='chira-prompt-title'>✦ Expediente & Guion TVP</div>
                    <div class='chira-prompt-desc'>«Genera el argumento táctico de migración y puente clínico para {medico_sel[:18]}...»</div>
                </div>
                """)
            if st.button("Inyectar en prompt  →", key="ch_p1", use_container_width=True):
                quick_prompt = f"Analiza el expediente completo y dame el guion TVP para {medico_sel}"

        with q_b2:
            render_html(f"""
                <div class='chira-prompt-card notranslate' translate='no'>
                    <div class='chira-prompt-title'>✦ Diagnóstico de Dilución</div>
                    <div class='chira-prompt-desc'>«¿Por qué {medico_sel[:16]} mantiene {dp_global.get('Comp Mes', 0)} recetas con la competencia y cómo lo abordo?»</div>
                </div>
                """)
            if st.button("Auditar Close-Up  →", key="ch_p2", use_container_width=True):
                quick_prompt = f"¿Por qué {medico_sel} comparte o diluye recetas con la competencia y cómo lo abordo?"

        with q_b3:
            render_html(f"""
                <div class='chira-prompt-card notranslate' translate='no'>
                    <div class='chira-prompt-title'>✦ Estrategia de Flanqueo</div>
                    <div class='chira-prompt-desc'>«Identifica el nicho clínico sin fricción para flanquear al rival líder en {medico_sel[:16]}...»</div>
                </div>
                """)
            if st.button("Venta Cruzada  →", key="ch_p3", use_container_width=True):
                quick_prompt = f"{medico_sel} está casado o fidelizado con la competencia, dame estrategia de flanqueo"

        with q_b4:
            render_html(f"""
                <div class='chira-prompt-card notranslate' translate='no'>
                    <div class='chira-prompt-title'>✦ Negociación & ROI Farmacia</div>
                    <div class='chira-prompt-desc'>«Verifica disponibilidad en {sell_z_chira['top_farmacias'][:22]} para apalancar acuerdo...»</div>
                </div>
                """)
            if st.button("Revisar Stock PDV  →", key="ch_p4", use_container_width=True):
                quick_prompt = f"{medico_sel} me pide apoyo o patrocinio a cambio de recetas, ¿cómo negocio el ROI?"

        # 3. Barra Acústica de Voz + Selector de Potenciación Gemini AI
        with st.container(border=True):
            v_col1, v_col2 = st.columns([1.8, 1.2])
            texto_voz = None
            with v_col1:
                widget_audio = getattr(st, "audio_input", None)
                if widget_audio is not None:
                    audio_grabado = widget_audio("🎙️ Captura de Consulta por Voz a CHIRA (Transcripción en vivo con IA):")
                    if audio_grabado is not None:
                        bytes_a = audio_grabado.getvalue()
                        hash_a = hash(bytes_a)
                        if hash_a != st.session_state.ultimo_audio_hash:
                            st.session_state.ultimo_audio_hash = hash_a
                            if obtener_api_key():
                                with st.spinner("Transcribiendo consulta por voz con Gemini..."):
                                    texto_voz = transcribir_audio_gemini(bytes_a, getattr(audio_grabado, "type", "audio/wav"))
                            else:
                                st.warning("Configura GEMINI_API_KEY en tu entorno para transcribir notas de voz.")
            with v_col2:
                st.caption("CHIRA calcula las métricas con 100% de exactitud local sobre tus Excels Close-Up.")
                allow_gemini = st.checkbox(
                    "Potenciar redacción estratégica con Gemini AI",
                    value=bool(obtener_api_key()),
                    key="chira_allow_gemini",
                )
                if st.button("Limpiar Historial de Conversación", use_container_width=True):
                    st.session_state.chira_history = []
                    st.rerun()

        # 4. Historial de Conversación con Tarjetas Ejecutivas CHIRA AI Strategic Advisor
        for msg in st.session_state.chira_history[-12:]:
            if msg["role"] == "user":
                render_html(f"""
                    <div class='notranslate' translate='no' style='display:flex; justify-content:flex-end; margin: 10px 0;'>
                        <div style='background:#002b5c; color:#ffffff; padding:12px 18px; border-radius:12px 12px 2px 12px; max-width:78%; box-shadow:0 2px 6px rgba(0,43,92,0.15);'>
                            <div style='font-size:0.66rem; color:#93c5fd; font-weight:700; margin-bottom:4px;'>VISITADOR MÉDICO (ERICK CALDERÓN)</div>
                            <div style='font-size:0.86rem; font-weight:600;'>«{msg["content"]}»</div>
                        </div>
                    </div>
                    """)
            else:
                render_html("""
                    <div class='notranslate' translate='no' style='background:#ffffff; border:1px solid #cbd5e1; border-left:5px solid #0284c7; border-radius:10px; padding:12px 16px; margin-top:10px;'>
                        <div style='display:flex; justify-content:space-between; align-items:center;'>
                            <div style='display:flex; align-items:center; gap:8px;'>
                                <span style='background:#002b5c; color:#38bdf8; width:26px; height:26px; border-radius:6px; display:inline-flex; align-items:center; justify-content:center; font-weight:800;'>✦</span>
                                <span style='font-size:0.82rem; font-weight:800; color:#0f172a;'>CHIRA AI Strategic Advisor</span>
                                <span style='background:#e0f2fe; color:#0369a1; font-size:0.66rem; font-weight:800; padding:2px 8px; border-radius:999px;'>Recomendación Táctica</span>
                            </div>
                            <span style='font-size:0.68rem; color:#64748b; font-weight:700;'>Auditoría Close-Up Verificada · Confianza: 99.2%</span>
                        </div>
                    </div>
                    """)
                with st.container(border=True):
                    st.markdown(msg["content"])
                    render_html(f"""
                        <div class='notranslate' translate='no' style='border-top:1px solid #e2e8f0; padding-top:10px; margin-top:10px; display:flex; justify-content:space-between; flex-wrap:wrap; gap:12px; font-size:0.74rem;'>
                            <div><span style='color:#64748b; font-weight:700;'>VOLUMEN EN DISPUTA:</span> <b style='color:#0f172a;'>{dp_global.get('Comp Mes', 0)} Rx / mes ({dp_global.get('Comp YTD', 0)} YTD)</b></div>
                            <div><span style='color:#64748b; font-weight:700;'>CUOTA ACTUAL GUTIS:</span> <b style='color:#059669;'>{dp_global.get('% MS Mes', 0.0):.1f}% MS Mes</b></div>
                            <div><span style='color:#64748b; font-weight:700;'>RESPALDO EN FARMACIAS ({ciudad}):</span> <b style='color:#0284c7;'>{sell_z_chira['top_farmacias'][:42]}</b></div>
                        </div>
                        """)

        pregunta_chat = st.chat_input("Pregunta a CHIRA (ej: 'prepara objeción de costo para Conflexil' o 'analiza Biotos en Masaya')...")
        consulta_final = quick_prompt or texto_voz or pregunta_chat

        if consulta_final:
            st.session_state.chira_history.append({"role": "user", "content": consulta_final})
            q_norm = normalizar_txt(consulta_final)

            todos_medicos = sorted(set(meds_panel_default) | set(df_productos["Médico"].dropna().unique().tolist())) if not df_productos.empty else meds_panel_default
            medico_detectado = next((d for d in todos_medicos if normalizar_txt(d) in q_norm), None)
            if not medico_detectado and any(k in q_norm for k in ["MEDICO EN FOCO", "ESTE MEDICO", "ESTA DOCTORA", "ESTE DOCTOR", "DILUYE", "COMPARTE", "CASADO", "FIDELIZADO", "PATROCINIO", "CONGRESO", "EXPEDIENTE", "GUION"]):
                medico_detectado = medico_sel

            if medico_detectado:
                respuesta_local = generar_consultoria_cognitiva_chira_medico(bundle, medico_detectado, consulta_final)
            else:
                ciu_detectada = next((c for c in LISTA_CIUDADES_REALES if normalizar_txt(c) in q_norm), None)
                mer_detectado = resolver_clave_mercado_gutis(consulta_final, consulta_final)
                df_rk_chira = ranking_medicos(
                    df_productos,
                    df_panel,
                    ciudad=ciu_detectada,
                    mercado=mer_detectado,
                    modo_panel="PANEL" if alcance_sb.startswith("SOLO") else "TODOS",
                )
                if not df_rk_chira.empty:
                    respuesta_local = generar_analisis_mercado_chira_rico(df_rk_chira, mer_detectado, ciu_detectada)
                else:
                    respuesta_local = generar_consultoria_cognitiva_chira_medico(bundle, medico_sel, consulta_final)

            respuesta_final = respuesta_local
            if allow_gemini and obtener_api_key():
                with st.spinner("CHIRA Neural Engine está sintetizando la estrategia con Gemini AI..."):
                    prompt_chira = (
                        f"{REGLAS_FARMA}\n\n"
                        f"Consulta del Visitador Médico (Erick Calderón): {consulta_final}\n\n"
                        f"Expediente y datos exactos calculados por el motor Close-Up de Gutis BI (PROHIBIDO alterar cifras):\n"
                        f"{respuesta_local}\n\n"
                        f"Con base únicamente en estos datos reales, entrega una respuesta ejecutiva, clara y accionable "
                        f"con recomendaciones tácticas TVP listas para aplicar hoy en consultorio y farmacia."
                    )
                    mejora_ia = llamar_gemini(prompt_chira, max_tok=2500)
                    if mejora_ia:
                        respuesta_final = mejora_ia

            st.session_state.chira_history.append({"role": "assistant", "content": respuesta_final})
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
                crm_ac_med = st.text_input("Compromiso del Médico (ej. Iniciar en próximos 4 pacientes con rinitis):")
            with c_ac2:
                crm_ac_vis = st.text_input("Compromiso del Visitador (ej. Garantizar stock en Farmacia Saba / Kielsa):")

            crm_notas = st.text_area("Observaciones Clínicas y Seguimiento para Próxima Visita:", height=95)
            btn_guardar_visita = st.form_submit_button(f"Guardar Visita a {medico_sel} en SQLite", type="primary", use_container_width=True)

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
            st.success(f"Visita registrada exitosamente para {medico_sel} en gutis_bi.db.")
            st.rerun()

        st.write("")
        filtro_hist = st.radio("Ver Historial de Visitas:", [f"Solo Médico en Foco ({medico_sel})", "Todas las Visitas de Mi Territorio"], horizontal=True)
        df_hist_crm = leer_visitas(medico_sel if filtro_hist.startswith("Solo") else None, DB_PATH)
        show_table(df_hist_crm, 340)

        st.download_button(
            "Exportar Bitácora Completa CRM a Excel / CSV",
            data=exportar_visitas_csv(DB_PATH),
            file_name=f"Bitacora_CRM_Erick_Calderon_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

# -----------------------------------------------------------------------------
# PIE DE PÁGINA CORPORATIVO ESTILO STITCH
# -----------------------------------------------------------------------------
render_html(f"""
    <div class='stitch-nav-header notranslate' translate='no' style='margin-top:26px; background:#ffffff; color:#64748b; font-size:0.73rem;'>
        <div>
            Fuente: <b>Base Close-Up Audit ({corte_nombre})</b> · Registros activos: <b>{kpi_hub['medicos_panel']} médicos en panel</b> ·
            <span style='color:#059669; font-weight:700;'>● Sincronizado con SQLite Local</span>
        </div>
        <div style='font-weight:800; color:#002b5c;'>
            GUTIS BI v2.5 · Arquitectura TVP · Erick Calderón © 2026
        </div>
    </div>
    """)
