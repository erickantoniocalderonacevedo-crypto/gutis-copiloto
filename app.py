import streamlit as st
import pandas as pd
import requests
import os
import json
from datetime import datetime
import numpy as np
from urllib.parse import quote
import base64

# --- CONFIGURACIÓN CORPORATIVA DE PÁGINA ---
st.set_page_config(
    page_title="Gutis BI | Terminal Comercial",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Lectura segura desde Streamlit Secrets
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
ARCHIVO_BITACORA = "HISTORIAL_VISITAS.xlsx"
ARCHIVO_PERFIL_360 = "PERFIL_360_MEDICOS.xlsx"

# --- MAPEO ESTRATÉGICO CON PONDERACIÓN POR MERCADO ---
MERCADOS_PRIORITARIOS = {
    "MR TALERDIN": {"producto": "Talerdín", "peso": 2, "prioridad": 1, "keywords": ["TALERDIN", "TALERDÍN", "CETIRIZINA", "CETRILER", "ALERCET", "DEGRALER"]},
    "MR BIOTOS": {"producto": "Biotos Inmune", "peso": 2, "prioridad": 1, "keywords": ["BIOTOS", "HEDERA", "PELARGONIUM", "ABRILAR"]},
    "MR CLEMBROXIL": {"producto": "Clembroxil Compuesto", "peso": 2, "prioridad": 1, "keywords": ["CLEMBROXIL", "CLENBUTEROL", "AMBROXOL", "MUCOSOLVAN"]},
    "MR MOMETZONA": {"producto": "Mometzona", "peso": 2, "prioridad": 1, "keywords": ["MOMETZONA", "MOMETASONA", "NASONEX"]},
    "MR VENTILAR": {"producto": "Ventilar", "peso": 2, "prioridad": 1, "keywords": ["VENTILAR", "MONTELUKAST", "SINGULAIR", "AIRUM"]},
    "MR GASTROALIVIO": {"producto": "Gastroalivio", "peso": 2, "prioridad": 1, "keywords": ["GASTROALIVIO", "ESOMEPRAZOL", "CARBUM", "NEXIUM"]},
    "MR DALIVIO": {"producto": "Dalivio", "peso": 2, "prioridad": 1, "keywords": ["DALIVIO", "DEXKETOPROFENO", "ENANTYUM", "STADIUM"]},
    "MR VALERPAN": {"producto": "Valerpan", "peso": 1, "prioridad": 2, "keywords": ["VALERPAN", "BETAMETASONA"]},
    "MR CONFLEXIL": {"producto": "Conflexil", "peso": 1, "prioridad": 2, "keywords": ["CONFLEXIL", "TIZANIDINA", "MELOXICAM"]},
    "MR RENOVART": {"producto": "Renovart Platinum", "peso": 1, "prioridad": 2, "keywords": ["RENOVART", "COLAGENO", "GLUCOSAMINA"]},
    "MR FEMGYL": {"producto": "Femgyl", "peso": 1, "prioridad": 2, "keywords": ["FEMGYL"]},
    "MR NORGYLEN": {"producto": "Norgylen", "peso": 1, "prioridad": 2, "keywords": ["NORGYLEN"]},
    "MR BICORPAN": {"producto": "Bicorpan", "peso": 1, "prioridad": 2, "keywords": ["BICORPAN"]},
    "MR MUPIRAL": {"producto": "Mupiral", "peso": 1, "prioridad": 2, "keywords": ["MUPIRAL", "MUPIROCINA", "BACTROBAN"]},
    "MR ANSIOLIT": {"producto": "Ansiolit", "peso": 1, "prioridad": 2, "keywords": ["ANSIOLIT"]},
    "MR DEPAX": {"producto": "Depax", "peso": 1, "prioridad": 2, "keywords": ["DEPAX"]},
    "MR FELICITAT": {"producto": "Felicitat", "peso": 1, "prioridad": 2, "keywords": ["FELICITAT"]}
}

PRODUCTOS_GUTIS = [
    "GASTROALIVIO", "TALERDIN", "TALERDÍN", "DALIVIO", "DALIVIUM", "CONFLEXIL",
    "VALERPAN", "RENOVART PLATINUM", "BIOTOS", "CLEMBROXIL", "MOMETZONA",
    "VENTILAR", "FEMGYL", "NORGYLEN", "BICORPAN", "MUPIRAL", "ANSIOLIT",
    "DEPAX", "FELICITAT"
]

REGLAS_FARMA = """
REGLAS FARMACOLÓGICAS Y DE COMPETENCIA (ESTRICTO):
1. CETRILER es CETIRIZINA.
2. CARBUM es ESOMEPRAZOL.
3. TALERDÍN es CETIRIZINA. Ventaja: 100% libre de alcohol, gotas exactas pediátricas.
4. GASTROALIVIO es ESOMEPRAZOL. Ventaja: Micropellets gastrorresistentes.
5. VENTILAR es MONTELUKAST SÓDICO.
6. MOMETZONA es FUROATO DE MOMETASONA.
7. BIOTOS INMUNE es HEDERA HELIX + PELARGONIUM SIDOIDES.
8. PEDIATRÍA: PROHIBIDO GASTROALIVIO. Priorizar Talerdín, Biotos, Clembroxil o Ventilar.
"""

# --- ESTILOS CSS ELEGANTES Y PREMIUM ---
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
    h1, h2, h3, h4, h5 { color: #0f172a; font-weight: 700; letter-spacing: -0.3px; }
    .metric-card { background-color: #ffffff; border-radius: 8px; padding: 20px; border-left: 5px solid #1e3a8a; box-shadow: 0 2px 8px rgba(0,0,0,0.04); margin-bottom: 15px; transition: transform 0.2s ease, box-shadow 0.2s ease; }
    .metric-card:hover { transform: translateY(-2px); box-shadow: 0 6px 14px rgba(0,0,0,0.07); }
    .metric-title { color: #64748b; font-size: 0.72rem; text-transform: uppercase; font-weight: 800; margin-bottom: 5px; letter-spacing: 0.8px; }
    .metric-value { color: #0f172a; font-size: 1.55rem; font-weight: 800; }
    .stTabs [data-baseweb="tab-list"] { border-bottom: 2px solid #e2e8f0; gap: 6px; padding-bottom: 0; }
    .stTabs [data-baseweb="tab"] { font-size: 0.85rem; font-weight: 700; color: #475569; padding: 10px 16px; border-radius: 6px 6px 0 0; background-color: #f1f5f9; transition: all 0.2s ease; border: 1px solid transparent; border-bottom: none; }
    .stTabs [aria-selected="true"] { color: #ffffff; background-color: #1e3a8a; border-bottom: none; box-shadow: inset 0 -3px 0 #38bdf8; }
</style>
""", unsafe_allow_html=True)

# --- CARGA INTELIGENTE Y ROBUSTA DE DATOS ---
@st.cache_data
def cargar_datos():
    df_p = pd.read_excel("PANEL ERICK 2026.xlsx")
    
    archivo_rx = next((p for p in ["DATOS MEDICOS AGOSTO PRODUCTOS TOTAL NICARAGUA.xlsx", "DATA MEDICOS AGOSTO PRODUCTOS TOTAL NICARAGUA.xlsx"] if os.path.exists(p)), None)
    df_rx = pd.read_excel(archivo_rx) if archivo_rx else pd.DataFrame()
    
    archivo_labs = next((p for p in ["DATA MEDICOS AGOSTO LABORATORIOS.xlsx", "DATOS MEDICOS AGOSTO LABORATORIOS.xlsx"] if os.path.exists(p)), None)
    df_labs_raw = pd.read_excel(archivo_labs) if archivo_labs else pd.DataFrame()
    
    try: df_v1 = pd.read_excel("VENTA PRIMER TRIMESTRE 2026.xlsx"); df_v1['Trimestre'] = 'Q1'
    except: df_v1 = pd.DataFrame()
    try: df_v2 = pd.read_excel("VENTAS SEGUNDO TRIMESTRE 2026.xlsx"); df_v2['Trimestre'] = 'Q2'
    except: df_v2 = pd.DataFrame()
    try: df_v3 = pd.read_excel("VENTAS TERCER TRIMESTRE 2026.xlsx", sheet_name="Export"); df_v3['Trimestre'] = 'Q3'
    except:
        try: df_v3 = pd.read_excel("VENTAS TERCER TRIMESTRE 2026.xlsx"); df_v3['Trimestre'] = 'Q3'
        except: df_v3 = pd.DataFrame()

    dataframes_ventas = [df for df in [df_v1, df_v2, df_v3] if not df.empty]
    df_v = pd.concat(dataframes_ventas, ignore_index=True) if dataframes_ventas else pd.DataFrame()

    for d in [df_p, df_rx, df_v, df_labs_raw]: 
        if not d.empty: d.columns = d.columns.str.strip()
            
    if not df_p.empty and "Médico" in df_p.columns: df_p["Médico"] = df_p["Médico"].astype(str).str.strip().str.upper()
    if not df_rx.empty and "Médico" in df_rx.columns: df_rx["Médico"] = df_rx["Médico"].astype(str).str.strip().str.upper()
    if not df_labs_raw.empty and "Médico" in df_labs_raw.columns: df_labs_raw["Médico"] = df_labs_raw["Médico"].astype(str).str.strip().str.upper()
    if not df_p.empty and "CIUDAD" in df_p.columns: df_p["CIUDAD"] = df_p["CIUDAD"].astype(str).str.strip().str.upper()
    if not df_v.empty and "DESCRIPCION_RUTA" in df_v.columns: df_v["DESCRIPCION_RUTA"] = df_v["DESCRIPCION_RUTA"].astype(str).str.strip().str.upper()
    
    return df_p, df_rx, df_labs_raw, df_v

df_panel, df_productos, df_labs, df_ventas = cargar_datos()

# --- INICIALIZACIÓN DE SESIÓN ---
if "chira_history" not in st.session_state: st.session_state.chira_history = []
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "tvp_result" not in st.session_state: st.session_state.tvp_result = None
if "pasillo_result" not in st.session_state: st.session_state.pasillo_result = None

# --- ENCABEZADO CORPORATIVO ---
st.markdown("""
<div style='background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); padding: 22px 26px; border-radius: 8px; margin-bottom: 22px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); border-left: 6px solid #38bdf8;'>
    <h2 style='color: #ffffff; margin: 0; font-size: 1.7rem; letter-spacing: 0.5px; font-weight: 800;'>[GUTIS BI] - TERMINAL DE INTELIGENCIA COMERCIAL</h2>
    <p style='color: #93c5fd; margin: 0; font-size: 0.82rem; text-transform: uppercase; font-weight: 600; margin-top: 5px; letter-spacing: 1px;'>Sistema Integrado de Análisis Táctico, Cuotas y Gestión Territorial</p>
</div>
""", unsafe_allow_html=True)

# --- MENÚ LATERAL ---
st.sidebar.markdown("### [FILTROS TERRITORIALES]")
ciudades = ["TODAS"] + sorted([c for c in df_panel["CIUDAD"].dropna().unique() if str(c).strip() not in ["", "NAN"]])
ciudad_filtro = st.sidebar.selectbox("Zona / Ciudad:", ciudades)

df_filtrado = df_panel if ciudad_filtro == "TODAS" else df_panel[df_panel["CIUDAD"] == ciudad_filtro]
lista_medicos = sorted(df_filtrado["Médico"].dropna().unique().tolist())

if not lista_medicos:
    st.warning("[SISTEMA] No existen registros para la zona seleccionada.")
    st.stop()

medico_sel = st.sidebar.selectbox("Médico Objetivo:", lista_medicos)

if "medico_chat" not in st.session_state or st.session_state.medico_chat != medico_sel:
    st.session_state.chat_history = []
    st.session_state.tvp_result = None
    st.session_state.pasillo_result = None
    st.session_state.medico_chat = medico_sel

info_medico = df_filtrado[df_filtrado["Médico"] == medico_sel].iloc[0]
ciudad = str(info_medico.get("CIUDAD", "N/D")).strip().upper()
especialidad = str(info_medico.get("Especialidad", "N/D")).strip().upper()
categoria = str(info_medico.get("CATEGORIA", "N/D")).strip()
es_pediatra = "PEDIAT" in especialidad

# --- PERFIL OMNICANAL 360 ---
perfil_360_actual = {}
if os.path.exists(ARCHIVO_PERFIL_360):
    try:
        df_p360 = pd.read_excel(ARCHIVO_PERFIL_360)
        coincidencias = df_p360[df_p360["Médico"].astype(str) == medico_sel]
        if not coincidencias.empty: perfil_360_actual = coincidencias.iloc[0].to_dict()
    except: pass

contexto_rapport_str = ""
if perfil_360_actual:
    cumple = perfil_360_actual.get("Cumpleaños", "")
    deporte = perfil_360_actual.get("Deporte", "")
    estilo_visita = perfil_360_actual.get("Estilo_Visita", "")
    partes_rapport = []
    if cumple and str(cumple) != "nan": partes_rapport.append(f"Cumpleaños: {cumple}")
    if deporte and str(deporte) != "nan": partes_rapport.append(f"Afinidad: {deporte}")
    if estilo_visita and str(estilo_visita) != "nan": partes_rapport.append(f"Estilo Visita: {estilo_visita}")
    if partes_rapport: contexto_rapport_str = "\nDATOS DE RAPPORT:\n- " + "\n- ".join(partes_rapport)

# --- DETECCIÓN DE COLUMNAS EN CLOSE-UP ---
rx_raw = df_productos[df_productos["Médico"] == medico_sel].copy() if not df_productos.empty else pd.DataFrame()
rx_clean = rx_raw.dropna(subset=["NOMBRE_PRODUCTO"]) if not rx_raw.empty and "NOMBRE_PRODUCTO" in rx_raw.columns else pd.DataFrame()
if not rx_clean.empty: rx_clean = rx_clean[~rx_clean["NOMBRE_PRODUCTO"].str.upper().isin(["TOTAL", "NAN", ""])]

def es_gutis(nombre_prod): return any(g in str(nombre_prod).upper() for g in PRODUCTOS_GUTIS)
def obtener_meta_mercado(mercado_val):
    for m_key, m_info in MERCADOS_PRIORITARIOS.items():
        if m_key in str(mercado_val).strip().upper(): return m_info
    return None

if not rx_clean.empty:
    rx_clean["Es_Gutis"] = rx_clean["NOMBRE_PRODUCTO"].apply(es_gutis)
    rx_clean["Meta_Mercado"] = rx_clean["MERCADO"].apply(obtener_meta_mercado)
    rx_clean["Es_Mercado_Gutis"] = rx_clean["Meta_Mercado"].notnull()
    if es_pediatra: rx_clean = rx_clean[~rx_clean["MERCADO"].str.upper().str.contains("GASTROALIVIO", na=False)]

col_pxs = next((c for c in rx_clean.columns if c.upper() == "PXS-MES"), None) if not rx_clean.empty else None
if not col_pxs and not rx_clean.empty: col_pxs = next((c for c in rx_clean.columns if any(x in c.upper() for x in ["PXS-TRIM", "PXS-YTD", "PXS", "TRX", "RECETAS"])), None)
col_mes = next((c for c in rx_clean.columns if c.upper() == "%MS-MES"), None) if not rx_clean.empty else None
if not col_mes and not rx_clean.empty: col_mes = next((c for c in rx_clean.columns if any(x in c.upper() for x in ["%MS-YTD", "%MS-TRIM", "%MS-TAM"])), None)

rx_gutis_markets = rx_clean[rx_clean["Es_Mercado_Gutis"]].copy() if not rx_clean.empty else pd.DataFrame()
if not rx_gutis_markets.empty:
    if col_mes and col_mes in rx_gutis_markets.columns: rx_gutis_markets[col_mes] = pd.to_numeric(rx_gutis_markets[col_mes], errors='coerce').fillna(0)
    if col_pxs and col_pxs in rx_gutis_markets.columns: rx_gutis_markets[col_pxs] = pd.to_numeric(rx_gutis_markets[col_pxs], errors='coerce').fillna(0)

total_pxs_medico = int(pd.to_numeric(rx_clean[col_pxs], errors='coerce').fillna(0).sum()) if not rx_clean.empty and col_pxs else 0
gutis_pxs_medico = int(rx_clean[rx_clean["Es_Gutis"]][col_pxs].sum()) if total_pxs_medico > 0 else 0
comp_pxs_medico = total_pxs_medico - gutis_pxs_medico

cards_ataque_html, num_mercados, mercado_principal_str, producto_ataque_str, share_lider = "", 0, "[S/D]", "[N/D]", 0.0
prod_gutis_ataque_oficial = "Talerdín" if es_pediatra else "Gastroalivio"

if not rx_gutis_markets.empty:
    mercados_unicos =
