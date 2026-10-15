import streamlit as st
import pandas as pd
import requests
import os
import json
import re
import unicodedata
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

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
ARCHIVO_BITACORA = "HISTORIAL_VISITAS.xlsx"
ARCHIVO_PERFIL_360 = "PERFIL_360_MEDICOS.xlsx"

# --- UTILIDAD DE NORMALIZACIÓN SIN TILDES PARA BÚSQUEDA LIBRE ---
def normalizar_txt(texto):
    if pd.isna(texto): return ""
    t = str(texto).strip().upper()
    return ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')

# --- MAPEO ESTRATÉGICO CON PONDERACIÓN POR MERCADO ---
MERCADOS_PRIORITARIOS = {
    "MR TALERDIN": {"producto": "Talerdín", "peso": 2, "prioridad": 1, "keywords": ["TALERDIN", "CETIRIZINA", "CETRILER", "ALERCET", "DEGRALER"]},
    "MR BIOTOS": {"producto": "Biotos Inmune", "peso": 2, "prioridad": 1, "keywords": ["BIOTOS", "HEDERA", "PELARGONIUM", "ABRILAR"]},
    "MR CLEMBROXIL": {"producto": "Clembroxil Compuesto", "peso": 2, "prioridad": 1, "keywords": ["CLEMBROXIL", "CLENBUTEROL", "AMBROXOL", "MUCOSOLVAN"]},
    "MR MOMETZONA": {"producto": "Mometzona", "peso": 2, "prioridad": 1, "keywords": ["MOMETZONA", "MOMETASONA", "NASONEX"]},
    "MR VENTILAR": {"producto": "Ventilar", "peso": 2, "prioridad": 1, "keywords": ["VENTILAR", "MONTELUKAST", "SINGULAIR", "AIRUM"]},
    "MR GASTROALIVIO": {"producto": "Gastroalivio", "peso": 2, "prioridad": 1, "keywords": ["GASTROALIVIO", "ESOMEPRAZOL", "CARBUM", "NEXIUM"]},
    "MR DALIVIO": {"producto": "Dalivio", "peso": 2, "prioridad": 1, "keywords": ["DALIVIO", "DALIVIUM", "DEXKETOPROFENO", "ENANTYUM", "STADIUM"]},
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
3. TALERDÍN es CETIRIZINA. Ventaja: 100% libre de alcohol, dosificación pediátrica en gotas exactas y alta tolerabilidad.
4. GASTROALIVIO es ESOMEPRAZOL. Ventaja: Micropellets gastrorresistentes.
5. VENTILAR es MONTELUKAST SÓDICO.
6. MOMETZONA es FUROATO DE MOMETASONA (Spray nasal acuoso sin alcohol).
7. BIOTOS INMUNE es HEDERA HELIX + PELARGONIUM SIDOIDES (Doble acción antiviral y mucolítica).
8. PEDIATRÍA: PROHIBIDO GASTROALIVIO (solo adulto en Nicaragua). Priorizar Talerdín, Biotos, Clembroxil o Ventilar.
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
    if not df_p.empty and "Especialidad" in df_p.columns: df_p["Especialidad"] = df_p["Especialidad"].astype(str).str.strip().str.upper()
    if not df_v.empty and "DESCRIPCION_RUTA" in df_v.columns: df_v["DESCRIPCION_RUTA"] = df_v["DESCRIPCION_RUTA"].astype(str).str.strip().str.upper()
    
    return df_p, df_rx, df_labs_raw, df_v

df_panel, df_productos, df_labs, df_ventas = cargar_datos()

# --- LISTAS DINÁMICAS EXTRAÍDAS DIRECTAMENTE DE TUS EXCEL (CERO CONDICIONAMIENTO) ---
LISTA_CIUDADES_REALES = sorted([c for c in df_panel["CIUDAD"].dropna().unique() if str(c).strip() not in ["", "NAN"]]) if not df_panel.empty and "CIUDAD" in df_panel.columns else []
LISTA_ESPECIALIDADES_REALES = sorted([e for e in df_panel["Especialidad"].dropna().unique() if str(e).strip() not in ["", "NAN"]]) if not df_panel.empty and "Especialidad" in df_panel.columns else []
LISTA_MERCADOS_REALES = sorted([m for m in df_productos["MERCADO"].dropna().unique() if str(m).strip() not in ["", "NAN", "TOTAL"]]) if not df_productos.empty and "MERCADO" in df_productos.columns else []
LISTA_RUTAS_VENTAS = sorted([r for r in df_ventas["DESCRIPCION_RUTA"].dropna().unique() if str(r).strip() not in ["", "NAN", "TOTAL"]]) if not df_ventas.empty and "DESCRIPCION_RUTA" in df_ventas.columns else []

# --- INICIALIZACIÓN DE SESIÓN ---
if "chira_history" not in st.session_state: st.session_state.chira_history = []
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "tvp_result" not in st.session_state: st.session_state.tvp_result = None
if "pasillo_result" not in st.session_state: st.session_state.pasillo_result = None
if "perfiles_memoria" not in st.session_state: st.session_state.perfiles_memoria = {}
if "bitacora_memoria" not in st.session_state: st.session_state.bitacora_memoria = []

# --- ENCABEZADO CORPORATIVO ---
st.markdown("""
<div style='background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); padding: 22px 26px; border-radius: 8px; margin-bottom: 22px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); border-left: 6px solid #38bdf8;'>
    <h2 style='color: #ffffff; margin: 0; font-size: 1.7rem; letter-spacing: 0.5px; font-weight: 800;'>[GUTIS BI] - TERMINAL DE INTELIGENCIA COMERCIAL</h2>
    <p style='color: #93c5fd; margin: 0; font-size: 0.82rem; text-transform: uppercase; font-weight: 600; margin-top: 5px; letter-spacing: 1px;'>Sistema Integrado de Análisis Táctico, Cuotas y Gestión Territorial</p>
</div>
""", unsafe_allow_html=True)

# --- MENÚ LATERAL MULTIFILTRO ---
st.sidebar.markdown("### [FILTROS DEL PANEL MÉDICO]")
ciudades_sb = ["TODAS"] + LISTA_CIUDADES_REALES
ciudad_filtro = st.sidebar.selectbox("1. Zona / Ciudad:", ciudades_sb)

df_filtrado = df_panel if ciudad_filtro == "TODAS" else df_panel[df_panel["CIUDAD"] == ciudad_filtro]

esps_sb = ["TODAS"] + sorted([e for e in df_filtrado["Especialidad"].dropna().unique() if str(e).strip() not in ["", "NAN"]])
esp_filtro_sb = st.sidebar.selectbox("2. Especialidad:", esps_sb)
if esp_filtro_sb != "TODAS":
    df_filtrado = df_filtrado[df_filtrado["Especialidad"] == esp_filtro_sb]

lista_medicos = sorted(df_filtrado["Médico"].dropna().unique().tolist())

if not lista_medicos:
    st.warning("[SISTEMA] No existen registros para la combinación seleccionada.")
    st.stop()

medico_sel = st.sidebar.selectbox("3. Médico Objetivo:", lista_medicos)

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
perfil_360_actual = st.session_state.perfiles_memoria.get(medico_sel, {})
if not perfil_360_actual and os.path.exists(ARCHIVO_PERFIL_360):
    try:
        df_p360 = pd.read_excel(ARCHIVO_PERFIL_360)
        coincidencias = df_p360[df_p360["Médico"].astype(str).str.upper() == medico_sel]
        if not coincidencias.empty: perfil_360_actual = coincidencias.iloc[0].to_dict()
    except: pass

contexto_rapport_str = ""
if perfil_360_actual:
    cumple = perfil_360_actual.get("Cumpleaños", "")
    deporte = perfil_360_actual.get("Deporte", "")
    estilo_visita = perfil_360_actual.get("Estilo_Visita", "")
    partes_rapport = []
    if cumple and str(cumple) not in ["nan", ""]: partes_rapport.append(f"Cumpleaños: {cumple}")
    if deporte and str(deporte) not in ["nan", ""]: partes_rapport.append(f"Afinidad/Hobby: {deporte}")
    if estilo_visita and str(estilo_visita) not in ["nan", ""]: partes_rapport.append(f"Estilo de Visita Preferido: {estilo_visita}")
    if partes_rapport: contexto_rapport_str = " | ".join(partes_rapport)

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
col_pxs_ytd_prod = next((c for c in rx_clean.columns if c.upper() == "PXS-YTD"), None) if not rx_clean.empty else None
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
opciones_mercados_medico = []

if not rx_gutis_markets.empty:
    mercados_unicos = rx_gutis_markets["MERCADO"].unique()
    num_mercados = len(mercados_unicos)
    
    def calc_score(row):
        meta = obtener_meta_mercado(row["MERCADO"])
        peso = meta["peso"] if meta else 1
        return (row[col_pxs] if col_pxs else 1) * peso

    rx_gutis_markets["Score_Estrategico"] = rx_gutis_markets.apply(calc_score, axis=1)
    rx_gutis_markets = rx_gutis_markets.sort_values(by="Score_Estrategico", ascending=False)
    mercados_ordenados = rx_gutis_markets["MERCADO"].drop_duplicates().tolist()
        
    for m in mercados_ordenados:
        df_m = rx_gutis_markets[rx_gutis_markets["MERCADO"] == m]
        df_m = df_m.sort_values(by=col_pxs if col_pxs else col_mes, ascending=False)
        meta = obtener_meta_mercado(m)
        prod_gutis_esperado = meta["producto"]
        lider = df_m.iloc[0]
        lider_nombre, lider_es_gutis = str(lider["NOMBRE_PRODUCTO"]).strip(), lider["Es_Gutis"]
        lider_ms = (lider[col_mes] * 100) if col_mes else 0.0
        lider_pxs = int(lider[col_pxs]) if col_pxs and not pd.isna(lider[col_pxs]) else 0

        opciones_mercados_medico.append({
            "mercado": m,
            "lider_actual": lider_nombre,
            "prod_gutis": prod_gutis_esperado,
            "pxs": lider_pxs,
            "ms": lider_ms
        })

        if mercado_principal_str == "[S/D]" and (lider_pxs > 0 or lider_ms > 0):
            mercado_principal_str, producto_ataque_str, prod_gutis_ataque_oficial, share_lider = m, lider_nombre, prod_gutis_esperado, lider_ms

        pxs_txt = f" | Pxs: <b>{lider_pxs}</b>" if col_pxs else ""
        if lider_ms > 0 or lider_pxs > 0:
            if not lider_es_gutis:
                cards_ataque_html += f"""<div style="background: linear-gradient(180deg, #fff1f2 0%, #ffffff 100%); border: 1px solid #fecdd3; border-top: 4px solid #e11d48; border-radius: 6px; padding: 12px; min-width: 210px; flex: 1 1 calc(25% - 15px); box-shadow: 0 2px 4px rgba(0,0,0,0.02);"><div style="font-size: 0.65rem; font-weight: 800; color: #9f1239; text-transform: uppercase;">{m.replace('MR ', '')}</div><div style="font-size: 0.88rem; color: #0f172a; margin: 5px 0;">Líder: <b style="color:#be123c;">{lider_nombre[:16]}</b></div><div style="font-size: 0.78rem; color: #475569;">Cuota: {lider_ms:.1f}% {pxs_txt}</div><div style="margin-top: 6px; font-size: 0.75rem; font-weight: 800; color: #047857; border-top: 1px dashed #cbd5e1; padding-top: 5px;">➔ Conquistar con {prod_gutis_esperado}</div></div>"""
            else:
                cards_ataque_html += f"""<div style="background: linear-gradient(180deg, #ecfdf5 0%, #ffffff 100%); border: 1px solid #a7f3d0; border-top: 4px solid #059669; border-radius: 6px; padding: 12px; min-width: 210px; flex: 1 1 calc(25% - 15px); box-shadow: 0 2px 4px rgba(0,0,0,0.02);"><div style="font-size: 0.65rem; font-weight: 800; color: #065f46; text-transform: uppercase;">{m.replace('MR ', '')}</div><div style="font-size: 0.88rem; color: #0f172a; margin: 5px 0;">Dominio: <b style="color:#047857;">{prod_gutis_esperado}</b></div><div style="font-size: 0.78rem; color: #475569;">Fidelidad: {lider_ms:.1f}% {pxs_txt}</div><div style="margin-top: 6px; font-size: 0.75rem; font-weight: 800; color: #047857; border-top: 1px dashed #cbd5e1; padding-top: 5px;">[BLINDAR RECETARIO]</div></div>"""

# DATOS DE VENTAS Y TOP FARMACIAS ZONALES
ventas_producto_lider_zona, total_sellout_zona, total_puntos_venta = 0.0, 0.0, 0
top_farmacias_ciudad_str = "principales farmacias de la zona"

if not df_ventas.empty and "DESCRIPCION_RUTA" in df_ventas.columns:
    ventas_zona_global = df_ventas[df_ventas["DESCRIPCION_RUTA"].str.contains(re.escape(ciudad), na=False)].copy()
    if not ventas_zona_global.empty:
        ventas_zona_global = ventas_zona_global[~ventas_zona_global["NOMBRE_CLIENTE_1"].str.upper().isin(["TOTAL", "NAN", ""])]
        col_pv_global = "VM4" if "VM4" in ventas_zona_global.columns else next((c for c in ventas_zona_global.columns if "PRODUCTO" in c.upper()), None)
        if col_pv_global:
            ventas_zona_global = ventas_zona_global[~ventas_zona_global[col_pv_global].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
        df_farmacias_totales = ventas_zona_global.groupby("NOMBRE_CLIENTE_1")["Monto Real"].sum().reset_index().sort_values(by="Monto Real", ascending=False)
        total_sellout_zona = df_farmacias_totales["Monto Real"].sum()
        total_puntos_venta = len(df_farmacias_totales)
        if not df_farmacias_totales.empty:
            top_farmacias_ciudad_str = ", ".join(df_farmacias_totales["NOMBRE_CLIENTE_1"].head(3).tolist())

# --- FUNCIÓN DE LLAMADA API A GOOGLE GEMINI ---
def llamar_gemini(prompt_text, max_tok=4096):
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key: return None

    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt_text}]}], "generationConfig": {"maxOutputTokens": max_tok, "temperature": 0.2}}

    modelos_a_probar = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash"]
    try:
        r_list = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}", timeout=5)
        if r_list.status_code == 200:
            todos = r_list.json().get('models', [])
            dinamicos = [m['name'].replace('models/', '') for m in todos if 'generateContent' in m.get('supportedGenerationMethods', [])]
            for d in dinamicos:
                if d not in modelos_a_probar and "flash" in d.lower():
                    modelos_a_probar.insert(0, d)
    except: pass

    for mod in modelos_a_probar:
        try:
            url_p = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            res = requests.post(url_p, headers=headers, json=payload, timeout=15)
            if res.status_code == 200:
                cands = res.json().get('candidates', [])
                if cands and 'content' in cands[0] and 'parts' in cands[0]['content']:
                    return cands[0]['content']['parts'][0].get('text', '')
        except: continue
    return None

# --- TARJETAS KPI CORPORATIVAS ---
col1, col2, col3 = st.columns(3)
with col1: 
    st.markdown(f"""<div class='metric-card'><div class='metric-title'>MÉDICO OBJETIVO</div><div class='metric-value'>{medico_sel}</div><div style='color: #475569; font-size: 0.85rem; margin-top:5px; font-weight:600;'>{especialidad} | Categoría {categoria} | {ciudad}</div></div>""", unsafe_allow_html=True)
with col2: 
    sub_potencial = f"Pacientes Mes: <b>{total_pxs_medico}</b> (Gutis: {gutis_pxs_medico} | Comp: {comp_pxs_medico})" if total_pxs_medico > 0 else f"Cuota: {share_lider:.1f}%"
    st.markdown(f"""<div class='metric-card' style='border-left-color: #0ea5e9;'><div class='metric-title'>FOCO ESTRATÉGICO ({mercado_principal_str})</div><div class='metric-value'>{producto_ataque_str[:15]}</div><div style='color: #475569; font-size: 0.85rem; margin-top:5px; font-weight:600;'>{sub_potencial}</div></div>""", unsafe_allow_html=True)
with col3: 
    st.markdown(f"""<div class='metric-card' style='border-left-color: #8b5cf6;'><div class='metric-title'>SELL-OUT TERRITORIAL ({ciudad} - {total_puntos_venta} PDV)</div><div class='metric-value'>${total_sellout_zona:,.2f}</div><div style='color: #475569; font-size: 0.85rem; margin-top:5px; font-weight:600;'>Líderes: {top_farmacias_ciudad_str[:38]}...</div></div>""", unsafe_allow_html=True)

if not rx_gutis_markets.empty and cards_ataque_html:
    st.components.v1.html(f"""<div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-left: 5px solid #1e3a8a; padding: 16px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.03);"><div style="font-size: 0.85rem; font-weight: 800; color: #0f172a; margin-bottom: 12px; letter-spacing: 0.5px;">[SINOPSIS DE MERCADOS ACTIVOS - {num_mercados} REGISTROS]</div><div style="display: flex; flex-wrap: wrap; gap: 10px;">{cards_ataque_html}</div></div>""", height=180, scrolling=True)

# --- PESTAÑAS DEL SISTEMA COMPLETAS ---
tab_chira, tab_estrategia, tab_perfil360, tab_rx, tab_sellout, tab_bitacora, tab_ruta = st.tabs([
    "[ASISTENTE CHIRA]", "Fase 1: Táctica Comercial", "Perfil 360°", "Fase 2: Análisis Rx", "Fase 3: Sell-Out", "Fase 4: Bitácora CRM", "Itinerario de Ruta"
])

# ==============================================================================
# PESTAÑA 1: CHIRA 2.0 - CONSOLA DINÁMICA MULTIDIMENSIONAL + LENGUAJE LIBRE
# ==============================================================================
with tab_chira:
    st.markdown("### [CHIRA 2.0] - Consultor de Inteligencia Comercial Senior")
    st.caption("Combina libremente cualquier Ciudad, Especialidad y Mercado en la consola interactiva o escribe tu consulta abajo.")
    
    # CONSOLA PARAMÉTRICA DINÁMICA (CERO VALORES CONDICIONADOS)
    with st.container(border=True):
        st.markdown("**🎛️ Consola Dinámica de Cruce Territorial, Especialidades y Mercados:**")
        p_c1, p_c2, p_c3, p_c4 = st.columns([1.3, 1.3, 1.3, 0.7])
        with p_c1:
            chira_ciu_sel = st.selectbox("📍 Territorio / Ciudad:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="ch_ciu")
        with p_c2:
            chira_esp_sel = st.selectbox("🩺 Especialidad Médica:", ["TODAS LAS ESPECIALIDADES"] + LISTA_ESPECIALIDADES_REALES, key="ch_esp")
        with p_c3:
            chira_mer_sel = st.selectbox("💊 Mercado / Producto:", ["TODOS LOS MERCADOS"] + LISTA_MERCADOS_REALES, key="ch_mer")
        with p_c4:
            chira_top_sel = st.selectbox("🔢 Top N:", [5, 10, 15, 20], index=0, key="ch_top")

        b_c1, b_c2, b_c3, b_c4 = st.columns(4)
        accion_consola = None
        if b_c1.button("🔬 Auditar Laboratorios (YTD/Mes)", use_container_width=True):
            accion_consola = "LABS"
        if b_c2.button("📊 Pareto 80/20 de Médicos", use_container_width=True):
            accion_consola = "MEDICOS_PARETO"
        if b_c3.button("🎯 Oportunidades de Conquista", use_container_width=True):
            accion_consola = "MEDICOS_CONQUISTA"
        if b_c4.button("🏥 Auditar Sell-Out Farmacias", use_container_width=True):
            accion_consola = "SELLOUT"

    chat_container_chira = st.container(height=360)
    for msg in st.session_state.chira_history:
        with chat_container_chira.chat_message(msg["role"]): st.write(msg["content"])
        
    input_chat_chira = st.chat_input("Escribe cualquier consulta libre (ej: Top 10 médicos en Masaya / Laboratorios más recetados en Ginecología / Sell-Out en Boaco)...")

    if accion_consola or input_chat_chira:
        # Determinar parámetros según si usó la Consola Dinámica o el Chat de Lenguaje Libre
        if accion_consola:
            top_n = chira_top_sel
            ciu_target = None if chira_ciu_sel == "TODO MI PANEL" else chira_ciu_sel
            esp_target = None if chira_esp_sel == "TODAS LAS ESPECIALIDADES" else chira_esp_sel
            mer_target = None if chira_mer_sel == "TODOS LOS MERCADOS" else chira_mer_sel
            modo_motor = accion_consola
            pregunta_mostrar = f"[Consola BI] Ejecutar {accion_consola} | Zona: {chira_ciu_sel} | Esp: {chira_esp_sel} | Mercado: {chira_mer_sel} (Top {top_n})"
        else:
            pregunta_mostrar = input_chat_chira
            texto_norm = normalizar_txt(input_chat_chira)
            
            # 1. Detectar Top N en texto libre
            match_num = re.search(r'\b(\d+)\b', texto_norm)
            top_n = int(match_num.group(1)) if match_num and 1 <= int(match_num.group(1)) <= 50 else 5

            # 2. Detectar Ciudad dinámicamente desde las ciudades reales del Excel + municipios conocidos
            ciu_target = None
            alias_municipios = {
                "JINOTEPE": "CARAZO", "DIRIAMBA": "CARAZO", "SAN MARCOS": "CARAZO",
                "NANDAIME": "GRANADA", "NINDIRI": "MASAYA", "SAN JORGE": "RIVAS", "JUIGALPA": "CHONTALES"
            }
            for c_real in LISTA_CIUDADES_REALES:
                if normalizar_txt(c_real) in texto_norm:
                    ciu_target = c_real
                    break
            if not ciu_target:
                for mun, dep in alias_municipios.items():
                    if mun in texto_norm:
                        ciu_target = next((c for c in LISTA_CIUDADES_REALES if dep in normalizar_txt(c)), dep)
                        break

            # 3. Detectar Especialidad dinámicamente desde TODAS las especialidades reales de tu Excel
            esp_target = None
            for e_real in LISTA_ESPECIALIDADES_REALES:
                e_norm = normalizar_txt(e_real)
                # Comparar por raíz de palabra (primeras 5 letras, ej: PEDIAT, GINEC, CARDI, ORTOP, INTER, GENER, OTORR)
                palabras_esp = [p for p in re.split(r'[\s/,-]+', e_norm) if len(p) >= 4]
                if e_norm in texto_norm or any(p[:5] in texto_norm for p in palabras_esp):
                    esp_target = e_real
                    break

            # 4. Detectar Mercado / Producto dinámicamente desde tu Excel y catálogo
            mer_target = None
            for m_real in LISTA_MERCADOS_REALES:
                m_limpio = normalizar_txt(m_real.replace("MR ", ""))
                if m_limpio in texto_norm:
                    mer_target = m_real
                    break
            if not mer_target:
                for m_key, m_val in MERCADOS_PRIORITARIOS.items():
                    if any(normalizar_txt(k) in texto_norm for k in m_val["keywords"]):
                        mer_target = next((m for m in LISTA_MERCADOS_REALES if normalizar_txt(m_key) in normalizar_txt(m)), m_key)
                        break

            # 5. Clasificar motor solicitado
            if any(k in texto_norm for k in ["LABORATORIO", "FABRICANTE", "CASA", "INDUSTRIA"]):
                modo_motor = "LABS"
            elif any(k in texto_norm for k in ["FARMACIA", "SELL", "SUCURSAL", "PDV", "FACTURACION", "CLIENTE"]):
                modo_motor = "SELLOUT"
            elif any(k in texto_norm for k in ["CONQUISTA", "ROBAR", "ATAQUE", "COMPETENCIA", "OPORTUNIDAD"]):
                modo_motor = "MEDICOS_CONQUISTA"
            else:
                modo_motor = "MEDICOS_PARETO"

        st.session_state.chira_history.append({"role": "user", "content": pregunta_mostrar})
        with chat_container_chira.chat_message("user"): st.write(pregunta_mostrar)

        with st.spinner("[CHIRA PROCESANDO CRUCE DINÁMICO EN BASE DE DATOS...]"):
            df_panel_sub = df_panel.copy()
            etiqueta_z = ciu_target if ciu_target else "TODO TU PANEL ASIGNADO"
            etiqueta_e = esp_target if esp_target else "Todas las Especialidades"
            etiqueta_m = mer_target if mer_target else "Todos los Mercados"

            if ciu_target and "CIUDAD" in df_panel_sub.columns:
                df_panel_sub = df_panel_sub[df_panel_sub["CIUDAD"].astype(str).str.upper().str.contains(re.escape(ciu_target), na=False)]
            if esp_target and "Especialidad" in df_panel_sub.columns:
                df_panel_sub = df_panel_sub[df_panel_sub["Especialidad"].astype(str).str.upper() == esp_target.upper()]

            medicos_segmento = set(df_panel_sub["Médico"].dropna().unique())
            num_meds_seg = len(medicos_segmento)

            # -----------------------------------------------------------------
            # EJECUCIÓN MOTOR 1: LABORATORIOS / FABRICANTES
            # -----------------------------------------------------------------
            if modo_motor == "LABS":
                if not df_labs.empty and "FABRICANTE" in df_labs.columns and "Médico" in df_labs.columns:
                    df_l_seg = df_labs[df_labs["Médico"].isin(medicos_segmento)].copy()
                    if df_l_seg.empty and esp_target and "Especialidad" in df_labs.columns:
                        raiz_e = normalizar_txt(esp_target)[:5]
                        df_l_seg = df_labs[df_labs["Especialidad"].apply(normalizar_txt).str.contains(raiz_e, na=False)].copy()

                    df_l_seg = df_l_seg[~df_l_seg["FABRICANTE"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
                    col_ytd = "Pxs-YTD" if "Pxs-YTD" in df_l_seg.columns else next((c for c in df_l_seg.columns if "YTD" in c.upper() and "PXS" in c.upper()), None)
                    col_mes_l = "Pxs-MES" if "Pxs-MES" in df_l_seg.columns else next((c for c in df_l_seg.columns if "MES" in c.upper() and "PXS" in c.upper()), None)

                    if not df_l_seg.empty and (col_ytd or col_mes_l):
                        if col_ytd: df_l_seg[col_ytd] = pd.to_numeric(df_l_seg[col_ytd], errors='coerce').fillna(0)
                        if col_mes_l: df_l_seg[col_mes_l] = pd.to_numeric(df_l_seg[col_mes_l], errors='coerce').fillna(0)
                        col_ord = col_ytd if col_ytd else col_mes_l

                        agg_d = {col_ord: 'sum', 'Médico': lambda x: len(set(x))}
                        if col_mes_l and col_mes_l != col_ord: agg_d[col_mes_l] = 'sum'

                        df_rk = df_l_seg.groupby("FABRICANTE").agg(agg_d).reset_index().rename(columns={"Médico": "Meds_Activos"})
                        univ_ytd = df_rk[col_ord].sum()
                        df_rk["MS_YTD"] = (df_rk[col_ord] / univ_ytd * 100) if univ_ytd > 0 else 0.0
                        if col_mes_l and col_mes_l in df_rk.columns:
                            univ_m = df_rk[col_mes_l].sum()
                            df_rk["MS_MES"] = (df_rk[col_mes_l] / univ_m * 100) if univ_m > 0 else 0.0
                        else: df_rk["MS_MES"] = 0.0

                        df_rk = df_rk.sort_values(by=col_ord, ascending=False).reset_index(drop=True)
                        df_rk["Pos"] = df_rk.index + 1

                        lineas = [
                            f"### 🔬 Auditoría de Fabricantes | {etiqueta_e} | {etiqueta_z}",
                            f"**Médicos del Panel en Segmento:** {num_meds_seg} | **Universo Acumulado (YTD):** {int(univ_ytd):,} Pacientes (Pxs)\n",
                            f"#### 🏆 Top {top_n} Laboratorios Más Recetados:"
                        ]
                        for _, r_l in df_rk.head(top_n).iterrows():
                            es_g = "GUTIS" in str(r_l["FABRICANTE"]).upper()
                            ic = "🟢 **[GUTIS]**" if es_g else "🏢"
                            t_m = f" | **Mes:** `{int(r_l[col_mes_l]):,} Pxs` ({r_l['MS_MES']:.2f}% MS)" if col_mes_l else ""
                            lineas.append(
                                f"**{int(r_l['Pos'])}. {r_l['FABRICANTE']}** {ic}\n"
                                f"- **Acumulado YTD:** `{int(r_l[col_ord]):,} Pxs` (**{r_l['MS_YTD']:.2f}% MS YTD**){t_m} | **Prescriptores en tu Panel:** {int(r_l['Meds_Activos'])} médicos.\n"
                            )

                        fila_g = df_rk[df_rk["FABRICANTE"].astype(str).str.upper().str.contains("GUTIS", na=False)]
                        if not fila_g.empty:
                            gr = fila_g.iloc[0]
                            lr = df_rk.iloc[0]
                            dif = int(lr[col_ord] - gr[col_ord])
                            lineas.append(
                                f"---\n#### 🎯 Posicionamiento de GUTIS en este Segmento:\n"
                                f"- **Puesto Actual:** **#{int(gr['Pos'])}** de {len(df_rk)} laboratorios con **{int(gr[col_ord]):,} Pxs YTD** (**{gr['MS_YTD']:.2f}% MS YTD**).\n"
                                f"- **Distancia hacia el #1 ({lr['FABRICANTE']}):** {dif:,} pacientes acumulados."
                            )
                        resultado_final = "\n".join(lineas)
                    else:
                        resultado_final = f"No se encontraron registros de laboratorios para **{etiqueta_e}** en **{etiqueta_z}**."
                else:
                    resultado_final = "⚠️ Verifica que el archivo `DATA MEDICOS AGOSTO LABORATORIOS.xlsx` esté cargado."

            # -----------------------------------------------------------------
            # EJECUCIÓN MOTOR 2: AUDITORÍA DE SELL-OUT / FARMACIAS
            # -----------------------------------------------------------------
            elif modo_motor == "SELLOUT":
                if not df_ventas.empty and "DESCRIPCION_RUTA" in df_ventas.columns:
                    df_vs = df_ventas[df_ventas["DESCRIPCION_RUTA"].str.contains(re.escape(ciu_target), na=False)].copy() if ciu_target else df_ventas.copy()
                    df_vs = df_vs[~df_vs["NOMBRE_CLIENTE_1"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
                    col_pv = "VM4" if "VM4" in df_vs.columns else next((c for c in df_vs.columns if "PRODUCTO" in c.upper()), None)
                    if col_pv:
                        df_vs = df_vs[~df_vs[col_pv].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
                        if mer_target:
                            meta_m = obtener_meta_mercado(mer_target)
                            kw_p = meta_m["producto"].split()[0].upper() if meta_m else mer_target.replace("MR ", "").strip().upper()
                            df_vs = df_vs[df_vs[col_pv].astype(str).str.upper().str.contains(re.escape(kw_p), na=False)]

                    if not df_vs.empty:
                        rk_f = df_vs.groupby("NOMBRE_CLIENTE_1")["Monto Real"].sum().reset_index().sort_values(by="Monto Real", ascending=False)
                        tot_z = rk_f["Monto Real"].sum()
                        lineas = [
                            f"### 🏥 Auditoría de Sell-Out Farmacéutico | {etiqueta_z}",
                            f"**Filtro de Producto/Mercado:** {etiqueta_m} | **Facturación Total:** `${tot_z:,.2f}` ({len(rk_f)} PDV activos)\n",
                            f"#### 🏆 Top {top_n} Puntos de Venta (Pareto):"
                        ]
                        acum_s = 0.0
                        for idx, rf in enumerate(rk_f.head(top_n).itertuples(), 1):
                             sh = (rf._2 / tot_z * 100) if tot_z > 0 else 0
                             acum_s += sh
                             lineas.append(f"**{idx}. {rf.NOMBRE_CLIENTE_1}:** `${rf._2:,.2f}` (**{sh:.1f}%** de participación | Pareto Acum: **{acum_s:.1f}%**)")
                        resultado_final = "\n".join(lineas)
                    else:
                        resultado_final = f"No hay registros de Sell-Out para **{etiqueta_z}** con el filtro **{etiqueta_m}**."
                else:
                    resultado_final = "No se encontró base de datos de Sell-Out."

            # -----------------------------------------------------------------
            # EJECUCIÓN MOTOR 3: PARETO 80/20 DE MÉDICOS Y OPORTUNIDADES DE CONQUISTA
            # -----------------------------------------------------------------
            else:
                ranking_medicos = []
                if not df_productos.empty and "Médico" in df_productos.columns:
                    col_pxs_c = next((c for c in df_productos.columns if c.upper() == "PXS-MES"), None)
                    if not col_pxs_c: col_pxs_c = next((c for c in df_productos.columns if any(x in c.upper() for x in ["PXS-TRIM", "PXS-YTD", "PXS"])), None)
                    col_ytd_c = next((c for c in df_productos.columns if c.upper() == "PXS-YTD"), None)
                    col_ms_c = next((c for c in df_productos.columns if c.upper() == "%MS-MES"), None)

                    df_rx_sub = df_productos[df_productos["Médico"].isin(medicos_segmento)].copy()
                    df_rx_sub = df_rx_sub[~df_rx_sub["NOMBRE_PRODUCTO"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]

                    if mer_target:
                        kw_m = mer_target.replace("MR ", "").strip().upper()
                        df_rx_sub = df_rx_sub[df_rx_sub["MERCADO"].astype(str).str.upper().str.contains(re.escape(kw_m), na=False)]

                    if not df_rx_sub.empty and col_pxs_c:
                        df_rx_sub[col_pxs_c] = pd.to_numeric(df_rx_sub[col_pxs_c], errors='coerce').fillna(0)
                        if col_ytd_c: df_rx_sub[col_ytd_c] = pd.to_numeric(df_rx_sub[col_ytd_c], errors='coerce').fillna(0)
                        df_rx_sub["Es_G"] = df_rx_sub["NOMBRE_PRODUCTO"].apply(es_gutis)

                        info_panel_map = df_panel_sub.drop_duplicates(subset=["Médico"]).set_index("Médico").to_dict("index")

                        for nom_doc, grp_doc in df_rx_sub.groupby("Médico"):
                            pxs_mes_tot = int(grp_doc[col_pxs_c].sum())
                            pxs_ytd_tot = int(grp_doc[col_ytd_c].sum()) if col_ytd_c else 0
                            if pxs_mes_tot <= 0 and pxs_ytd_tot <= 0:
                                continue

                            pxs_gut = int(grp_doc[grp_doc["Es_G"]][col_pxs_c].sum())
                            pxs_comp = pxs_mes_tot - pxs_gut

                            grp_ord = grp_doc.sort_values(by=[col_pxs_c, col_ytd_c] if col_ytd_c else [col_pxs_c], ascending=False)
                            lider_r = grp_ord.iloc[0]
                            lider_nom = str(lider_r["NOMBRE_PRODUCTO"]).strip()
                            lider_px = int(lider_r[col_pxs_c])

                            meta_doc = info_panel_map.get(nom_doc, {})
                            ranking_medicos.append({
                                "nombre": nom_doc,
                                "especialidad": str(meta_doc.get("Especialidad", "N/D")),
                                "categoria": str(meta_doc.get("CATEGORIA", "N/D")),
                                "ciudad": str(meta_doc.get("CIUDAD", "N/D")),
                                "pxs_totales": pxs_mes_tot,
                                "pxs_ytd": pxs_ytd_tot,
                                "gutis_pxs": pxs_gut,
                                "comp_pxs": pxs_comp,
                                "lider_producto": lider_nom,
                                "lider_pxs": lider_px,
                                "es_gutis": es_gutis(lider_nom)
                            })

                # Si pidió CONQUISTA, ordenar por pacientes de la competencia (robo directo); si pidió PARETO, por volumen total
                criterio_orden = "comp_pxs" if modo_motor == "MEDICOS_CONQUISTA" else "pxs_totales"
                ranking_medicos = sorted(ranking_medicos, key=lambda x: (x[criterio_orden], x["pxs_ytd"]), reverse=True)
                universo_pxs_seg = sum(x["pxs_totales"] for x in ranking_medicos)

                if ranking_medicos:
                    titulo_m = "🎯 Top Oportunidades de Conquista (Pxs Competencia)" if modo_motor == "MEDICOS_CONQUISTA" else "📊 Pareto 80/20 de Médicos Prescriptores"
                    lineas = [
                        f"### {titulo_m}",
                        f"**Territorio:** {etiqueta_z} | **Especialidad:** {etiqueta_e} | **Mercado:** {etiqueta_m}",
                        f"**Médicos Activos con Receta:** {len(ranking_medicos)} | **Volumen Mensual del Segmento:** {universo_pxs_seg:,} Pxs-MES\n"
                    ]
                    acum_p = 0.0
                    for idx, m_i in enumerate(ranking_medicos[:top_n], 1):
                        peso_m = (m_i["pxs_totales"] / universo_pxs_seg * 100) if universo_pxs_seg > 0 else 0
                        acum_p += peso_m
                        est_str = "🟢 **DOMINIO GUTIS**" if m_i["es_gutis"] and m_i["comp_pxs"] == 0 else f"🔴 **OPORTUNIDAD: {m_i['comp_pxs']} Pxs de Competencia**"
                        lineas.append(
                            f"**{idx}. Dr(a). {m_i['nombre']}** ({m_i['especialidad']} | Cat {m_i['categoria']} | {m_i['ciudad']})\n"
                            f"- **Volumen Mes:** `{m_i['pxs_totales']} Pxs-MES` (Gutis: {m_i['gutis_pxs']} | Comp: **{m_i['comp_pxs']}**) | **Acumulado YTD:** `{m_i['pxs_ytd']} Pxs` | **Pareto Acum:** `{acum_p:.1f}%`\n"
                            f"- **Marca Dominante Actual:** `{m_i['lider_producto']}` ({m_i['lider_pxs']} Pxs-MES) ➔ {est_str}\n"
                        )
                    resultado_final = "\n".join(lineas)
                else:
                    resultado_final = f"No se encontraron médicos con prescripción activa para la combinación: **Zona:** {etiqueta_z} | **Especialidad:** {etiqueta_e} | **Mercado:** {etiqueta_m}."

            prompt_ia = f"""{REGLAS_FARMA}
Eres CHIRA, Consultora Senior de BI de Laboratorios Gutis.
Respeta ÍNTEGRAMENTE todas las cifras y nombres del siguiente reporte y añade al final un bloque breve titulado '⚡ Recomendación Táctica Ejecutiva' con 2 acciones concretas para Erick Calderón:

{resultado_final}"""
            respuesta_ia = llamar_gemini(prompt_ia)
            if respuesta_ia and len(respuesta_ia.strip()) > 80:
                resultado_final = respuesta_ia

        st.session_state.chira_history.append({"role": "assistant", "content": resultado_final})
        st.rerun()

# ==============================================================================
# PESTAÑA 2: FASE 1 - TÁCTICA COMERCIAL (CON SELECTOR DE MERCADO Y CRUCE PDV)
# ==============================================================================
with tab_estrategia:
    col_izq_ia, col_der_ia = st.columns([1.1, 1.1])
    with col_izq_ia:
        st.markdown("#### [GENERACIÓN DE ARGUMENTOS TÁCTICOS]")
        
        if opciones_mercados_medico:
            etiquetas_m = [f"{o['mercado']} (Líder: {o['lider_actual'][:15]} -> Atacar con {o['prod_gutis']})" for o in opciones_mercados_medico]
            idx_m_sel = st.selectbox("🎯 Seleccionar Mercado del Médico a Atacar Hoy:", range(len(etiquetas_m)), format_func=lambda i: etiquetas_m[i])
            merc_tactico = opciones_mercados_medico[idx_m_sel]["mercado"]
            competidor_tactico = opciones_mercados_medico[idx_m_sel]["lider_actual"]
            gutis_tactico = opciones_mercados_medico[idx_m_sel]["prod_gutis"]
        else:
            merc_tactico, competidor_tactico, gutis_tactico = mercado_principal_str, producto_ataque_str, prod_gutis_ataque_oficial

        if st.button("[EJECUTAR ANÁLISIS FLASH - 30s]", use_container_width=True, type="primary"):
            with st.spinner("[COMPILANDO ARGUMENTO GALÉNICO...]"):
                prompt_flash = f"{REGLAS_FARMA}\nGenera un pitch de pasillo de 2 oraciones para {medico_sel} ({especialidad}). Receta {competidor_tactico}. Misión: Cambiar hoy a {gutis_tactico} respaldado en {top_farmacias_ciudad_str}."
                res_f = llamar_gemini(prompt_flash)
                if not res_f:
                    res_f = f"Doctor(a) {medico_sel}, para los pacientes en los que hoy prescribe {competidor_tactico}, **{gutis_tactico}** le ofrece superioridad galénica comprobada, máxima tolerabilidad y disponibilidad inmediata garantizada en {top_farmacias_ciudad_str}."
                st.session_state.pasillo_result = res_f
        if st.session_state.pasillo_result: st.info(st.session_state.pasillo_result)

        if st.button("[EJECUTAR ANÁLISIS TVP COMPLETO]", use_container_width=True):
            with st.spinner("[ESTRUCTURANDO PLAN DE VISITA INTEGRAL...]"):
                rapport_nota = f"Integrar datos de Perfil 360: {contexto_rapport_str}." if contexto_rapport_str else "Apertura ejecutiva enfocada en su prestigio clínico en la zona."
                prompt_tvp = f"""{REGLAS_FARMA}
Genera un Plan de Visita Médica (TVP) en 6 pasos exactos para {medico_sel} ({especialidad}, Cat {categoria}, {ciudad}).
Contexto: En el mercado {merc_tactico} prescribe {competidor_tactico}. Debe cambiar a {gutis_tactico}.
{rapport_nota}
En el Cierre Directo menciona disponibilidad activa en las farmacias líderes de su zona: {top_farmacias_ciudad_str}."""
                res_tvp = llamar_gemini(prompt_tvp)
                if not res_tvp:
                    res_tvp = f"""### Plan de Visita Médica Táctico (TVP) - {medico_sel}
* **1. Pre-Visita (Análisis de escenario):** Especialista en **{especialidad}** (Cat {categoria}) en **{ciudad}**. En el mercado `{merc_tactico}`, su prescripción actual la lidera `{competidor_tactico}`. Objetivo: Conversión directa hacia **{gutis_tactico}**.
* **2. Rapport (Apertura 360°):** {rapport_nota}
* **3. Sondeo Clínico (Pregunta de dolor):** ¿Doctor(a), qué relevancia tiene para la adherencia de sus pacientes contar con una formulación de alta pureza galénica que reduzca los efectos adversos asociados a opciones convencionales como `{competidor_tactico}`?
* **4. Presentación de Valor:** Posicionar **{gutis_tactico}** destacando sus ventajas diferenciales (tecnología galénica superior, dosificación exacta y respaldo centroamericano de Laboratorios Gutis).
* **5. Manejo de Objeciones:** Si menciona hábito prescriptivo con `{competidor_tactico}`, validar su experiencia pero contrastar la rapidez de acción y seguridad superior de **{gutis_tactico}**.
* **6. Cierre Directo (Cruzado con Sell-Out):** Solicitar el compromiso para sus próximos 5 pacientes de esta semana, confirmándole inventario completo de **{gutis_tactico}** en **{top_farmacias_ciudad_str}**."""
                st.session_state.tvp_result = res_tvp
        if st.session_state.tvp_result: st.markdown(st.session_state.tvp_result)

    with col_der_ia:
        st.markdown("#### [SIMULADOR DE OBJECIONES CLÍNICAS]")
        chat_container = st.container(height=320)
        for msg in st.session_state.chat_history:
            with chat_container.chat_message(msg["role"]): st.write(msg["content"])
        if prompt_chat := st.chat_input("Ingrese refutación clínica al médico..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt_chat})
            with chat_container.chat_message("user"): st.write(prompt_chat)
            with st.spinner("[PROCESANDO...]"):
                res_sim = llamar_gemini(f"{REGLAS_FARMA}\nEres {medico_sel} defendiendo {competidor_tactico} ante {gutis_tactico}. Responde en 2 líneas a este argumento del visitador: {prompt_chat}")
                if not res_sim:
                    res_sim = f"Interesante su punto sobre {gutis_tactico}, colega. Si me garantiza que hay inventario constante en {top_farmacias_ciudad_str} y no me cambian la receta en mostrador, lo pondré a prueba esta semana."
            st.session_state.chat_history.append({"role": "assistant", "content": res_sim})
            st.rerun()

# ==============================================================================
# PESTAÑA 3: PERFIL 360° (CON GUARDADO REAL EN EXCEL Y MEMORIA)
# ==============================================================================
with tab_perfil360:
    st.markdown(f"#### [ACTUALIZACIÓN DE PERFIL OMNICANAL - {medico_sel}]")
    st.caption("Los datos guardados aquí se inyectan automáticamente en el Paso 2 (Rapport) del Análisis TVP.")
    with st.form("form_perfil_360"):
        c1, c2, c3 = st.columns(3)
        with c1: 
            val_minsa = st.text_input("Código MINSA:", value=str(perfil_360_actual.get("MINSA", "")) if str(perfil_360_actual.get("MINSA", "")) != "nan" else "")
            val_cel = st.text_input("Celular / WhatsApp:", value=str(perfil_360_actual.get("Celular", "")) if str(perfil_360_actual.get("Celular", "")) != "nan" else "")
        with c2: 
            val_correo = st.text_input("Correo Electrónico:", value=str(perfil_360_actual.get("Correo", "")) if str(perfil_360_actual.get("Correo", "")) != "nan" else "")
            val_cumple = st.text_input("Fecha de Cumpleaños:", value=str(perfil_360_actual.get("Cumpleaños", "")) if str(perfil_360_actual.get("Cumpleaños", "")) != "nan" else "")
        with c3: 
            val_deporte = st.text_input("Afinidad / Hobby / Familia:", value=str(perfil_360_actual.get("Deporte", "")) if str(perfil_360_actual.get("Deporte", "")) != "nan" else "")
            opc_visita = ["Ultra-ejecutiva", "Discusión científica", "Casos clínicos"]
            idx_vis = opc_visita.index(perfil_360_actual.get("Estilo_Visita", opc_visita[0])) if perfil_360_actual.get("Estilo_Visita") in opc_visita else 0
            val_estilo_visita = st.selectbox("Estilo de Visita Preferido:", opc_visita, index=idx_vis)

        if st.form_submit_button("💾 [GUARDAR EN BASE DE DATOS E INYECTAR AL TVP]", use_container_width=True, type="primary"):
            nuevo_registro = {
                "Médico": medico_sel, "MINSA": val_minsa, "Celular": val_cel,
                "Correo": val_correo, "Cumpleaños": val_cumple, "Deporte": val_deporte,
                "Estilo_Visita": val_estilo_visita, "Ultima_Actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            st.session_state.perfiles_memoria[medico_sel] = nuevo_registro
            try:
                if os.path.exists(ARCHIVO_PERFIL_360):
                    df_p_save = pd.read_excel(ARCHIVO_PERFIL_360)
                    df_p_save = df_p_save[df_p_save["Médico"].astype(str).str.upper() != medico_sel]
                    df_p_save = pd.concat([df_p_save, pd.DataFrame([nuevo_registro])], ignore_index=True)
                else:
                    df_p_save = pd.DataFrame([nuevo_registro])
                df_p_save.to_excel(ARCHIVO_PERFIL_360, index=False)
            except: pass
            st.success(f"✅ Perfil 360° de {medico_sel} guardado y sincronizado con el generador TVP.")

# ==============================================================================
# PESTAÑA 4: FASE 2 - ANÁLISIS RX (CON BARRAS VISUALES Y PXS-YTD)
# ==============================================================================
with tab_rx:
    st.markdown("#### [AUDITORÍA DE PRESCRIPCIÓN Y LABORATORIOS]")
    m_p1, m_p2, m_p3 = st.columns(3)
    with m_p1: st.metric("Pacientes Mes (Pxs-MES)", total_pxs_medico)
    with m_p2: st.metric("Pacientes Gutis (Mes)", gutis_pxs_medico)
    with m_p3: st.metric("Oportunidad Conquista (Competencia)", comp_pxs_medico)
    st.divider()

    if not rx_clean.empty:
        col_f1, col_f2 = st.columns([3, 1])
        with col_f1:
            mercados_disponibles = sorted(rx_clean["MERCADO"].dropna().unique().tolist())
            mercados_filtro = st.multiselect("🔍 Filtrar visualización por Mercados Estratégicos:", mercados_disponibles, placeholder="Seleccione uno o varios mercados...")
        with col_f2:
            ocultar_ceros = st.checkbox("Ocultar productos con 0 Pxs", value=False)
        
        rx_vista = rx_clean[rx_clean["MERCADO"].isin(mercados_filtro)].copy() if mercados_filtro else rx_clean.copy()

        col_r1, col_r2 = st.columns([2.2, 1.3])
        with col_r1:
            st.markdown("##### 📋 Priorización por Pacientes Reales (Mes y Acumulado YTD)")
            cols_to_show = ["NOMBRE_PRODUCTO", "MERCADO"]
            if col_pxs: cols_to_show.append(col_pxs)
            if col_pxs_ytd_prod and col_pxs_ytd_prod not in cols_to_show: cols_to_show.append(col_pxs_ytd_prod)
            if col_mes: cols_to_show.append(col_mes)
            
            df_rx_view = rx_vista[cols_to_show].copy()
            df_rx_view["Origen"] = df_rx_view["NOMBRE_PRODUCTO"].apply(lambda x: "🟢 GUTIS" if es_gutis(x) else "🔴 COMPETENCIA")
            
            if col_mes: df_rx_view[col_mes] = (pd.to_numeric(df_rx_view[col_mes], errors='coerce').fillna(0) * 100).round(2)
            if col_pxs: df_rx_view[col_pxs] = pd.to_numeric(df_rx_view[col_pxs], errors='coerce').fillna(0).astype(int)
            if col_pxs_ytd_prod: df_rx_view[col_pxs_ytd_prod] = pd.to_numeric(df_rx_view[col_pxs_ytd_prod], errors='coerce').fillna(0).astype(int)
            
            if ocultar_ceros and col_pxs:
                df_rx_view = df_rx_view[df_rx_view[col_pxs] > 0]

            sort_cols = [c for c in [col_pxs, col_pxs_ytd_prod, col_mes] if c]
            if sort_cols:
                df_rx_view = df_rx_view.sort_values(by=sort_cols, ascending=[False]*len(sort_cols))
            
            renombrar = {
                "NOMBRE_PRODUCTO": "Producto",
                "MERCADO": "Mercado",
                col_pxs: "Pxs-MES",
                col_pxs_ytd_prod: "Pxs-YTD",
                col_mes: "% Cuota Mercado"
            }
            df_rx_view = df_rx_view.rename(columns=renombrar)
            
            st.dataframe(
                df_rx_view,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "% Cuota Mercado": st.column_config.ProgressColumn(
                        "% Cuota Mercado",
                        format="%.1f%%",
                        min_value=0,
                        max_value=100
                    )
                }
            )

        with col_r2:
            st.markdown("##### 🔬 [RADAR DE FABRICANTES (YTD & MES)]")
            
            if not df_labs.empty and "FABRICANTE" in df_labs.columns and "Médico" in df_labs.columns:
                df_labs_medico = df_labs[df_labs["Médico"] == medico_sel].copy()
                df_labs_medico = df_labs_medico[~df_labs_medico["FABRICANTE"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
                
                if not df_labs_medico.empty:
                    col_pxs_ytd = "Pxs-YTD" if "Pxs-YTD" in df_labs_medico.columns else next((c for c in df_labs_medico.columns if "YTD" in c.upper() and "PXS" in c.upper()), None)
                    col_pxs_m_lab = "Pxs-MES" if "Pxs-MES" in df_labs_medico.columns else next((c for c in df_labs_medico.columns if "MES" in c.upper() and "PXS" in c.upper()), None)
                    
                    if col_pxs_ytd:
                        df_labs_medico[col_pxs_ytd] = pd.to_numeric(df_labs_medico[col_pxs_ytd], errors='coerce').fillna(0)
                        agg_l = {col_pxs_ytd: 'sum'}
                        if col_pxs_m_lab:
                            df_labs_medico[col_pxs_m_lab] = pd.to_numeric(df_labs_medico[col_pxs_m_lab], errors='coerce').fillna(0)
                            agg_l[col_pxs_m_lab] = 'sum'

                        df_agrupado = df_labs_medico.groupby("FABRICANTE").agg(agg_l).reset_index()
                        
                        total_ytd_medico = df_agrupado[col_pxs_ytd].sum()
                        df_agrupado["% MS YTD"] = ((df_agrupado[col_pxs_ytd] / total_ytd_medico) * 100).round(2) if total_ytd_medico > 0 else 0.0

                        df_agrupado = df_agrupado.sort_values(by=col_pxs_ytd, ascending=False).head(12)
                        df_agrupado["FABRICANTE"] = df_agrupado["FABRICANTE"].apply(lambda x: f"🟢 {x}" if "GUTIS" in str(x).upper() else str(x))
                        df_agrupado[col_pxs_ytd] = df_agrupado[col_pxs_ytd].astype(int)
                        if col_pxs_m_lab: df_agrupado[col_pxs_m_lab] = df_agrupado[col_pxs_m_lab].astype(int)

                        ren_labs = {"FABRICANTE": "Laboratorio", col_pxs_ytd: "Pxs YTD"}
                        if col_pxs_m_lab: ren_labs[col_pxs_m_lab] = "Pxs MES"
                        df_agrupado = df_agrupado.rename(columns=ren_labs)
                        
                        st.dataframe(
                            df_agrupado,
                            hide_index=True,
                            use_container_width=True,
                            column_config={
                                "% MS YTD": st.column_config.ProgressColumn(
                                    "% MS YTD",
                                    format="%.2f%%",
                                    min_value=0,
                                    max_value=100
                                )
                            }
                        )
                    else: st.info("Columna 'Pxs-YTD' no detectada.")
                else: st.info("Sin registros de laboratorio para este médico.")
            else: st.info("ℹ️ Sube a GitHub el archivo de Laboratorios.")
    else: st.info("[SISTEMA] Sin datos de prescripción.")

# ==============================================================================
# PESTAÑA 5: FASE 3 - SELL-OUT LIBRE POR TERRITORIO, SUCURSAL Y LÍNEA
# ==============================================================================
with tab_sellout:
    st.markdown("#### [INTELIGENCIA DE SELL-OUT Y TENDENCIAS TRIMESTRALES]")
    if not df_ventas.empty and "DESCRIPCION_RUTA" in df_ventas.columns:
        cf_s0, cf_s1, cf_s2 = st.columns([1.2, 1.4, 1.4])
        with cf_s0:
            opciones_z_so = ["ZONA DEL MÉDICO ACTIVO (" + ciudad + ")", "TODAS LAS RUTAS"] + LISTA_RUTAS_VENTAS
            zona_so_sel = st.selectbox("🗺️ Territorio / Ruta:", opciones_z_so)

        if zona_so_sel.startswith("ZONA DEL MÉDICO"):
            ventas_zona = df_ventas[df_ventas["DESCRIPCION_RUTA"].str.contains(re.escape(ciudad), na=False)].copy()
        elif zona_so_sel == "TODAS LAS RUTAS":
            ventas_zona = df_ventas.copy()
        else:
            ventas_zona = df_ventas[df_ventas["DESCRIPCION_RUTA"] == zona_so_sel].copy()
        
        if not ventas_zona.empty:
            col_prod_v = "VM4" if "VM4" in ventas_zona.columns else next((c for c in ventas_zona.columns if "PRODUCTO" in c.upper()), None)
            
            if col_prod_v:
                ventas_zona[col_prod_v] = ventas_zona[col_prod_v].astype(str).str.strip()
                ventas_zona = ventas_zona[~ventas_zona[col_prod_v].str.upper().isin(["TOTAL", "NAN", ""])]
            ventas_zona = ventas_zona[~ventas_zona["NOMBRE_CLIENTE_1"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]

            with cf_s1:
                farmacias_disp = sorted(ventas_zona["NOMBRE_CLIENTE_1"].dropna().unique().tolist())
                farm_sel = st.multiselect("🏥 Filtrar Farmacia(s):", farmacias_disp, placeholder="Todas las farmacias...")
            with cf_s2:
                prods_disp_v = sorted(ventas_zona[col_prod_v].dropna().unique().tolist()) if col_prod_v else []
                prod_v_sel = st.multiselect("💊 Filtrar Línea / Producto:", prods_disp_v, placeholder="Todos los productos...")
            
            df_v_mostrar = ventas_zona.copy()
            if farm_sel: df_v_mostrar = df_v_mostrar[df_v_mostrar["NOMBRE_CLIENTE_1"].isin(farm_sel)]
            if prod_v_sel and col_prod_v: df_v_mostrar = df_v_mostrar[df_v_mostrar[col_prod_v].isin(prod_v_sel)]

            if col_prod_v and "Trimestre" in df_v_mostrar.columns and not df_v_mostrar.empty:
                df_pivot = pd.pivot_table(
                    df_v_mostrar,
                    values="Monto Real",
                    index=["NOMBRE_CLIENTE_1", col_prod_v],
                    columns=["Trimestre"],
                    aggfunc="sum",
                    fill_value=0.0
                ).reset_index()
                
                for q_col in ["Q1", "Q2", "Q3"]:
                    if q_col not in df_pivot.columns:
                        df_pivot[q_col] = 0.0
                    df_pivot[q_col] = df_pivot[q_col].round(2)

                df_pivot["Venta Total"] = (df_pivot["Q1"] + df_pivot["Q2"] + df_pivot["Q3"]).round(2)

                def evaluar_tendencia(row):
                    q2, q3 = row["Q2"], row["Q3"]
                    if q2 <= 0 and q3 > 0: return "🚀 Nuevo / Explosión (+100%)"
                    if q2 <= 0 and q3 <= 0: return "⚪ Sin Movimiento"
                    var_pct = ((q3 - q2) / q2) * 100
                    if var_pct >= 10: return f"🟢 Creciendo (+{var_pct:.1f}%)"
                    elif var_pct <= -15: return f"🔴 Alerta Caída ({var_pct:.1f}%)"
                    else: return f"🟡 Estable ({var_pct:+.1f}%)"

                df_pivot["Tendencia Q3 vs Q2"] = df_pivot.apply(evaluar_tendencia, axis=1)
                df_pivot = df_pivot.sort_values(by="Venta Total", ascending=False)

                tot_q1, tot_q2, tot_q3 = df_pivot["Q1"].sum(), df_pivot["Q2"].sum(), df_pivot["Q3"].sum()
                tot_general = df_pivot["Venta Total"].sum()
                var_global_q3 = ((tot_q3 - tot_q2) / tot_q2 * 100) if tot_q2 > 0 else 0.0

                ks1, ks2, ks3, ks4 = st.columns(4)
                ks1.metric("Venta Q1", f"${tot_q1:,.2f}")
                ks2.metric("Venta Q2", f"${tot_q2:,.2f}")
                ks3.metric("Venta Q3", f"${tot_q3:,.2f}", f"{var_global_q3:+.1f}% vs Q2")
                ks4.metric("Acumulado Selección", f"${tot_general:,.2f}")

                st.markdown("##### Detalle de Ventas por Farmacia, Trimestre y Producto")
                df_mostrar_sellout = df_pivot[["NOMBRE_CLIENTE_1", col_prod_v, "Q1", "Q2", "Q3", "Venta Total", "Tendencia Q3 vs Q2"]].rename(
                    columns={"NOMBRE_CLIENTE_1": "Punto de Venta / Farmacia", col_prod_v: "Línea / Producto"}
                )

                st.dataframe(
                    df_mostrar_sellout,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Q1": st.column_config.NumberColumn("Q1", format="$%.2f"),
                        "Q2": st.column_config.NumberColumn("Q2", format="$%.2f"),
                        "Q3": st.column_config.NumberColumn("Q3", format="$%.2f"),
                        "Venta Total": st.column_config.NumberColumn("Venta Total", format="$%.2f"),
                    }
                )
                
                st.markdown("#### [ANÁLISIS IA DE SELL-OUT]")
                if st.button("⚡ [EJECUTAR ANÁLISIS DE VENTAS Y DETECCIÓN DE FUGAS]", use_container_width=True, type="primary"):
                    with st.spinner("Ejecutando auditoría matemática de Trade Marketing..."):
                        en_caida = df_pivot[df_pivot["Tendencia Q3 vs Q2"].str.contains("🔴")].copy()
                        en_alza = df_pivot[df_pivot["Tendencia Q3 vs Q2"].str.contains("🟢|🚀")].copy()
                        top_fila = df_pivot.iloc[0]

                        lineas_so = [
                            f"### 📊 Diagnóstico de Sell-Out y Trade Marketing ({zona_so_sel})",
                            f"- **Líder de Facturación en Selección:** `{top_fila['NOMBRE_CLIENTE_1']}` con la línea **{top_fila[col_prod_v]}** (`${top_fila['Venta Total']:,.2f}` acumulados: Q1 `${top_fila['Q1']:,.2f}` | Q2 `${top_fila['Q2']:,.2f}` | Q3 `${top_fila['Q3']:,.2f}`).",
                            f"- **Desempeño Trimestral Consolidado:** El bloque pasó de `${tot_q2:,.2f}` en Q2 a `${tot_q3:,.2f}` en Q3 (**{var_global_q3:+.1f}%**)."
                        ]
                        if not en_alza.empty:
                            top_crec = ", ".join([f"**{r[col_prod_v]}** en {r['NOMBRE_CLIENTE_1']} (${r['Q2']:,.2f} ➔${r['Q3']:,.2f})" for _, r in en_alza.head(3).iterrows()])
                            lineas_so.append(f"- **🟢 Motores de Crecimiento (Q3):** Excelente tracción en {top_crec}. Asegurar stock de seguridad.")
                        if not en_caida.empty:
                            top_fuga = ", ".join([f"**{r[col_prod_v]}** en {r['NOMBRE_CLIENTE_1']} (cayó de ${r['Q2']:,.2f} a${r['Q3']:,.2f})" for _, r in en_caida.head(3).iterrows()])
                            lineas_so.append(f"- **🔴 Alerta de Fuga / Desabasto en Q3:** Revisar inventario y rotación en {top_fuga}. Cruzar con la receta de los médicos de la zona.")

                        reporte_base_so = "\n".join(lineas_so)
                        prompt_ventas = f"{REGLAS_FARMA}\nCon base en este diagnóstico exacto de Sell-Out, agrega 2 recomendaciones de Trade Marketing para Erick Calderón:\n{reporte_base_so}"
                        res_v = llamar_gemini(prompt_ventas)
                        st.info(res_v if (res_v and len(res_v) > 60) else reporte_base_so)
            else:
                st.info("No hay datos para la combinación de filtros seleccionada.")
    else: st.error("[SISTEMA] No hay cruce de rutas de venta.")

# ==============================================================================
# PESTAÑA 6: FASE 4 - BITÁCORA CRM FUNCIONAL CON DESCARGA EXCEL
# ==============================================================================
with tab_bitacora:
    st.markdown(f"#### [CONSOLA DE CAPTURA CRM - {medico_sel}]")
    with st.form("form_bitacora_crm"):
        cb1, cb2, cb3 = st.columns(3)
        with cb1:
            prod_promovido = st.selectbox("Producto Principal Promovido:", [m["producto"] for m in MERCADOS_PRIORITARIOS.values()])
        with cb2:
            compromiso_rx = st.number_input("Compromiso de Recetas Semanales:", min_value=0, max_value=100, value=5)
        with cb3:
            farmacia_aliada = st.text_input("Farmacia de Referencia:", value=top_farmacias_ciudad_str.split(",")[0] if top_farmacias_ciudad_str else "")
        
        notas_visita = st.text_area("Acuerdos Clínicos / Objeciones Detectadas en Visita:", placeholder="Ej: Aceptó iniciar tratamiento en próximos pacientes; solicitó muestras médicas...")
        
        if st.form_submit_button("✅ [REGISTRAR VISITA EN BITÁCORA CRM]", use_container_width=True, type="primary"):
            nueva_visita = {
                "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Ciudad": ciudad,
                "Médico": medico_sel,
                "Especialidad": especialidad,
                "Categoría": categoria,
                "Producto_Promovido": prod_promovido,
                "Compromiso_Rx": compromiso_rx,
                "Farmacia_Referencia": farmacia_aliada,
                "Acuerdos_Notas": notas_visita
            }
            st.session_state.bitacora_memoria.append(nueva_visita)
            try:
                if os.path.exists(ARCHIVO_BITACORA):
                    df_bit_old = pd.read_excel(ARCHIVO_BITACORA)
                    df_bit_new = pd.concat([df_bit_old, pd.DataFrame([nueva_visita])], ignore_index=True)
                else:
                    df_bit_new = pd.DataFrame([nueva_visita])
                df_bit_new.to_excel(ARCHIVO_BITACORA, index=False)
            except: pass
            st.success(f"Visita a {medico_sel} registrada exitosamente en el historial CRM.")

    df_hist_crm = pd.DataFrame(st.session_state.bitacora_memoria)
    if os.path.exists(ARCHIVO_BITACORA):
        try: df_hist_crm = pd.read_excel(ARCHIVO_BITACORA)
        except: pass
    if not df_hist_crm.empty:
        st.markdown("##### 📂 Historial de Visitas Registradas")
        st.dataframe(df_hist_crm.tail(20), hide_index=True, use_container_width=True)
        csv_crm = df_hist_crm.to_csv(index=False).encode('utf-8-sig')
        st.download_button("⬇️ Descargar Bitácora CRM (CSV/Excel)", data=csv_crm, file_name=f"Bitacora_CRM_Gutis_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")

# ==============================================================================
# PESTAÑA 7: ITINERARIO DE RUTA MULTIDIMENSIONAL (LIBRE POR CIUDAD, ESP Y MERCADO)
# ==============================================================================
with tab_ruta:
    st.markdown("#### [ITINERARIO INTELIGENTE POR TERRITORIO, ESPECIALIDAD, MERCADO Y POTENCIAL]")
    st.caption("Filtra cualquier ciudad o todo tu panel simultáneamente para planificar tu cobertura sobre los médicos con mayor volumen.")
    
    cr0, cr1, cr2, cr3 = st.columns([1.2, 1.6, 1.2, 0.8])
    with cr0:
        ciudades_ruta_sel = st.multiselect("📍 1. Ciudad / Zona:", LISTA_CIUDADES_REALES, default=[ciudad] if ciudad in LISTA_CIUDADES_REALES else [], placeholder="Todo el panel...")
    
    df_ruta_zona = df_panel[df_panel["CIUDAD"].isin(ciudades_ruta_sel)].copy() if ciudades_ruta_sel else df_panel.copy()

    with cr1:
        mercados_ruta_sel = st.multiselect("🎯 2. Mercados Estratégicos:", LISTA_MERCADOS_REALES, placeholder="Todos los mercados...")
    with cr2:
        esps_ruta_disp = sorted(df_ruta_zona["Especialidad"].dropna().unique().tolist()) if "Especialidad" in df_ruta_zona.columns else []
        esps_ruta_sel = st.multiselect("🩺 3. Especialidad:", esps_ruta_disp, placeholder="Todas...")
    with cr3:
        cats_ruta_disp = sorted([str(c) for c in df_ruta_zona["CATEGORIA"].dropna().unique().tolist()]) if "CATEGORIA" in df_ruta_zona.columns else []
        cats_ruta_sel = st.multiselect("⭐ 4. Categoría:", cats_ruta_disp, placeholder="Todas...")

    if esps_ruta_sel and "Especialidad" in df_ruta_zona.columns:
        df_ruta_zona = df_ruta_zona[df_ruta_zona["Especialidad"].isin(esps_ruta_sel)]
    if cats_ruta_sel and "CATEGORIA" in df_ruta_zona.columns:
        df_ruta_zona = df_ruta_zona[df_ruta_zona["CATEGORIA"].astype(str).isin(cats_ruta_sel)]

    columnas_deseadas = ["Médico", "Especialidad", "CATEGORIA", "DIRECCION", "Dirección", "CLINICA", "CIUDAD"]
    columnas_existentes = [col for col in columnas_deseadas if col in df_ruta_zona.columns]
    df_mostrar = df_ruta_zona[columnas_existentes].dropna(subset=["Médico"]).copy() if "Médico" in columnas_existentes else df_ruta_zona.copy()

    if not df_productos.empty and "Médico" in df_mostrar.columns:
        rx_ruta = df_productos[df_productos["MERCADO"].isin(mercados_ruta_sel)].copy() if mercados_ruta_sel else df_productos.copy()
        rx_ruta = rx_ruta[~rx_ruta["NOMBRE_PRODUCTO"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
        col_pxs_ruta = next((c for c in rx_ruta.columns if c.upper() == "PXS-MES"), None)
        if not col_pxs_ruta: col_pxs_ruta = next((c for c in rx_ruta.columns if "PXS" in c.upper() or "TRX" in c.upper()), None)
        
        if col_pxs_ruta and not rx_ruta.empty:
            rx_ruta[col_pxs_ruta] = pd.to_numeric(rx_ruta[col_pxs_ruta], errors='coerce').fillna(0)
            rx_ruta["Es_G"] = rx_ruta["NOMBRE_PRODUCTO"].apply(es_gutis)
            
            tot_med = rx_ruta.groupby("Médico")[col_pxs_ruta].sum().reset_index().rename(columns={col_pxs_ruta: "Pxs Totales"})
            gut_med = rx_ruta[rx_ruta["Es_G"]].groupby("Médico")[col_pxs_ruta].sum().reset_index().rename(columns={col_pxs_ruta: "Pxs Gutis"})
            
            resumen_r = pd.merge(tot_med, gut_med, on="Médico", how="left").fillna(0)
            resumen_r["Pxs Competencia (Oportunidad)"] = (resumen_r["Pxs Totales"] - resumen_r["Pxs Gutis"]).astype(int)
            resumen_r["Pxs Totales"] = resumen_r["Pxs Totales"].astype(int)
            resumen_r["Pxs Gutis"] = resumen_r["Pxs Gutis"].astype(int)

            how_merge = "inner" if mercados_ruta_sel else "left"
            df_mostrar = pd.merge(df_mostrar, resumen_r, on="Médico", how=how_merge).fillna(0)
            for c_int in ["Pxs Totales", "Pxs Gutis", "Pxs Competencia (Oportunidad)"]:
                if c_int in df_mostrar.columns: df_mostrar[c_int] = df_mostrar[c_int].astype(int)
            df_mostrar = df_mostrar.sort_values(by=["Pxs Competencia (Oportunidad)", "Pxs Totales"], ascending=[False, False])

    st.dataframe(df_mostrar, hide_index=True, use_container_width=True)
    csv_ruta = df_mostrar.to_csv(index=False).encode('utf-8-sig')
    st.download_button("⬇️ Exportar Hoja de Ruta Filtrada (CSV/Excel)", data=csv_ruta, file_name="Hoja_De_Ruta_Gutis.csv", mime="text/csv")
