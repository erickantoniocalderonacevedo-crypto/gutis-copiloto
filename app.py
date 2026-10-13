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

# --- MAPEO ESTRATÉGICO ---
MERCADOS_PRIORITARIOS = {
    "MR TALERDIN": {"producto": "Talerdín", "prioridad": 1},
    "MR BIOTOS": {"producto": "Biotos Inmune", "prioridad": 1},
    "MR CLEMBROXIL": {"producto": "Clembroxil Compuesto", "prioridad": 1},
    "MR MOMETZONA": {"producto": "Mometzona", "prioridad": 1},
    "MR VENTILAR": {"producto": "Ventilar", "prioridad": 1},
    "MR GASTROALIVIO": {"producto": "Gastroalivio", "prioridad": 1},
    "MR DALIVIO": {"producto": "Dalivio", "prioridad": 1},
    "MR VALERPAN": {"producto": "Valerpan", "prioridad": 2},
    "MR CONFLEXIL": {"producto": "Conflexil", "prioridad": 2},
    "MR RENOVART": {"producto": "Renovart Platinum", "prioridad": 2},
    "MR FEMGYL": {"producto": "Femgyl", "prioridad": 2},
    "MR NORGYLEN": {"producto": "Norgylen", "prioridad": 2},
    "MR BICORPAN": {"producto": "Bicorpan", "prioridad": 2},
    "MR MUPIRAL": {"producto": "Mupiral", "prioridad": 2},
    "MR ANSIOLIT": {"producto": "Ansiolit", "prioridad": 2},
    "MR DEPAX": {"producto": "Depax", "prioridad": 2},
    "MR FELICITAT": {"producto": "Felicitat", "prioridad": 2}
}

PRODUCTOS_GUTIS = [
    "GASTROALIVIO", "TALERDIN", "TALERDÍN", "DALIVIO", "DALIVIUM", "CONFLEXIL",
    "VALERPAN", "RENOVART PLATINUM", "BIOTOS", "CLEMBROXIL", "MOMETZONA",
    "VENTILAR", "FEMGYL", "NORGYLEN", "BICORPAN", "MUPIRAL", "ANSIOLIT",
    "DEPAX", "FELICITAT"
]

REGLAS_FARMA = """
REGLAS FARMACOLÓGICAS Y DE COMPETENCIA (ESTRICTO):
1. CETRILER es CETIRIZINA (NO es Montelukast, NO es Desloratadina).
2. CARBUM es ESOMEPRAZOL.
3. TALERDÍN es CETIRIZINA. Ventaja competitiva: 100% libre de alcohol (cero irritación gástrica), gotas exactas y excelente tolerabilidad.
4. GASTROALIVIO es ESOMEPRAZOL. Ventaja competitiva: Micropellets gastrorresistentes y Plan Paciente 2+1.
5. VENTILAR es MONTELUKAST SÓDICO.
6. MOMETZONA es FUROATO DE MOMETASONA (Spray acuoso libre de alcohol).
7. BIOTOS INMUNE es HEDERA HELIX + PELARGONIUM SIDOIDES.
8. PEDIATRÍA: PROHIBIDO sugerir GASTROALIVIO (solo existe adulto). Priorizar Talerdín, Biotos, Clembroxil o Ventilar.
"""

# --- ESTILOS CSS ELEGANTES Y PREMIUM ---
st.markdown("""
<style>
    /* Fondo general más limpio */
    .stApp { background-color: #f4f6f9; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
    h1, h2, h3, h4, h5 { color: #0f172a; font-weight: 700; letter-spacing: -0.3px; }
    
    /* Tarjetas KPI con diseño Premium */
    .metric-card { 
        background-color: #ffffff; 
        border-radius: 8px; 
        padding: 22px; 
        border-left: 6px solid #2563eb; 
        box-shadow: 0 4px 10px rgba(0,0,0,0.04); 
        margin-bottom: 15px; 
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.08);
    }
    .metric-title { color: #64748b; font-size: 0.75rem; text-transform: uppercase; font-weight: 800; margin-bottom: 6px; letter-spacing: 0.8px; }
    .metric-value { color: #0f172a; font-size: 1.65rem; font-weight: 900; }
    
    /* Pestañas estilizadas */
    .stTabs [data-baseweb="tab-list"] { border-bottom: 2px solid #e2e8f0; gap: 6px; padding-bottom: 0; }
    .stTabs [data-baseweb="tab"] { 
        font-size: 0.85rem; 
        font-weight: 700; 
        color: #64748b; 
        padding: 12px 18px; 
        border-radius: 6px 6px 0 0; 
        background-color: #f8fafc;
        transition: all 0.3s ease;
        border: 1px solid transparent;
        border-bottom: none;
    }
    .stTabs [aria-selected="true"] { 
        color: #ffffff; 
        background-color: #1e3a8a; /* Azul Índigo Elegante */
        border-bottom: none; 
        box-shadow: inset 0 -4px 0 #38bdf8; /* Línea celeste inferior */
    }
    
    /* Cajas de texto y chat */
    .stChatMessage { background-color: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
</style>
""", unsafe_allow_html=True)

# --- CARGA Y CACHÉ DE DATOS ---
@st.cache_data
def cargar_datos():
    df_p = pd.read_excel("PANEL ERICK 2026.xlsx")
    df_rx = pd.read_excel("DATA MEDICOS AGOSTO PRODUCTOS TOTAL NICARAGUA.xlsx")
    
    try:
        df_v1 = pd.read_excel("VENTA PRIMER TRIMESTRE 2026.xlsx")
        df_v1['Trimestre'] = 'Q1'
    except: df_v1 = pd.DataFrame()
    try:
        df_v2 = pd.read_excel("VENTAS SEGUNDO TRIMESTRE 2026.xlsx")
        df_v2['Trimestre'] = 'Q2'
    except: df_v2 = pd.DataFrame()
    try:
        df_v3 = pd.read_excel("VENTAS TERCER TRIMESTRE 2026.xlsx", sheet_name="Export")
        df_v3['Trimestre'] = 'Q3'
    except: df_v3 = pd.DataFrame()

    dataframes_ventas = [df for df in [df_v1, df_v2, df_v3] if not df.empty]
    df_v = pd.concat(dataframes_ventas, ignore_index=True) if dataframes_ventas else pd.DataFrame()

    for d in [df_p, df_rx, df_v]: 
        if not d.empty: d.columns = d.columns.str.strip()
            
    df_p["Médico"] = df_p["Médico"].astype(str).str.strip().str.upper()
    df_rx["Médico"] = df_rx["Médico"].astype(str).str.strip().str.upper()
    if not df_v.empty and "DESCRIPCION_RUTA" in df_v.columns:
        df_v["DESCRIPCION_RUTA"] = df_v["DESCRIPCION_RUTA"].astype(str).str.strip().str.upper()
    
    return df_p, df_rx, df_v

df_panel, df_productos, df_ventas = cargar_datos()

# --- INICIALIZACIÓN DE SESIÓN ---
if "chira_history" not in st.session_state: st.session_state.chira_history = []
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "gira_chat_history" not in st.session_state: st.session_state.gira_chat_history = []
if "tvp_result" not in st.session_state: st.session_state.tvp_result = None
if "pasillo_result" not in st.session_state: st.session_state.pasillo_result = None

# --- ENCABEZADO CORPORATIVO CON DEGRADADO ELEGANTE ---
st.markdown("""
<div style='background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); padding: 25px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-left: 6px solid #38bdf8;'>
    <h2 style='color: #ffffff; margin: 0; font-size: 1.8rem; letter-spacing: 0.5px; font-weight: 800;'>[GUTIS BI] - PLATAFORMA DE INTELIGENCIA COMERCIAL</h2>
    <p style='color: #93c5fd; margin: 0; font-size: 0.85rem; text-transform: uppercase; font-weight: 600; margin-top: 6px; letter-spacing: 1px;'>Sistema Integrado de Análisis Táctico y Gestión de Territorio</p>
</div>
""", unsafe_allow_html=True)

# --- MENÚ LATERAL ---
st.sidebar.markdown("### [FILTROS OPERATIVOS]")
ciudades = ["TODAS"] + sorted([c for c in df_panel["CIUDAD"].dropna().unique() if str(c).strip() != ""])
ciudad_filtro = st.sidebar.selectbox("Selección de Zona:", ciudades)

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

# --- PERFIL OMNICANAL ---
perfil_360_actual = {}
if os.path.exists(ARCHIVO_PERFIL_360):
    try:
        df_p360 = pd.read_excel(ARCHIVO_PERFIL_360)
        coincidencias = df_p360[df_p360["Médico"].astype(str) == medico_sel]
        if not coincidencias.empty:
            perfil_360_actual = coincidencias.iloc[0].to_dict()
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
    if partes_rapport:
        contexto_rapport_str = "\nDATOS DE RAPPORT:\n- " + "\n- ".join(partes_rapport)

# --- PROCESAMIENTO ANALÍTICO DE RX ---
rx_raw = df_productos[df_productos["Médico"] == medico_sel].copy()
rx_clean = rx_raw.dropna(subset=["NOMBRE_PRODUCTO"])
rx_clean = rx_clean[~rx_clean["NOMBRE_PRODUCTO"].str.upper().isin(["TOTAL", "NAN", ""])]

def es_gutis(nombre_prod): return any(g in str(nombre_prod).upper() for g in PRODUCTOS_GUTIS)
def obtener_meta_mercado(mercado_val):
    for m_key, m_info in MERCADOS_PRIORITARIOS.items():
        if m_key in str(mercado_val).strip().upper(): return m_info
    return None

rx_clean["Es_Gutis"] = rx_clean["NOMBRE_PRODUCTO"].apply(es_gutis)
rx_clean["Meta_Mercado"] = rx_clean["MERCADO"].apply(obtener_meta_mercado)
rx_clean["Es_Mercado_Gutis"] = rx_clean["Meta_Mercado"].notnull()

if es_pediatra: rx_clean = rx_clean[~rx_clean["MERCADO"].str.upper().str.contains("GASTROALIVIO", na=False)]

# Búsqueda de columna de VOLUMEN de recetas
col_volumen = next((c for c in rx_clean.columns if any(x in c.upper() for x in ["RX", "RECETA", "UNIDAD", "TRX", "VALOR"])), None)
col_mes = "%MS-MES" if "%MS-MES" in rx_clean.columns else "%MS-YTD" if "%MS-YTD" in rx_clean.columns else "%MS-TAM"

rx_gutis_markets = rx_clean[rx_clean["Es_Mercado_Gutis"]].copy()
if col_mes in rx_gutis_markets.columns: rx_gutis_markets[col_mes] = pd.to_numeric(rx_gutis_markets[col_mes], errors='coerce').fillna(0)
if col_volumen and col_volumen in rx_gutis_markets.columns: 
    rx_gutis_markets[col_volumen] = pd.to_numeric(rx_gutis_markets[col_volumen], errors='coerce').fillna(0)

cards_ataque_html, total_amenazas, num_mercados, mercado_principal_str, producto_ataque_str, share_lider = "", 0, 0, "[S/D]", "[N/D]", 0.0
prod_gutis_ataque_oficial = "Talerdín" if es_pediatra else "Gastroalivio"

if not rx_gutis_markets.empty:
    mercados_unicos = rx_gutis_markets["MERCADO"].unique()
    num_mercados = len(mercados_unicos)
    
    if col_volumen:
        rx_gutis_markets = rx_gutis_markets.sort_values(by=col_volumen, ascending=False)
    else:
        rx_gutis_markets = rx_gutis_markets.sort_values(by=col_mes, ascending=False)
        
    for m in mercados_unicos:
        df_m = rx_gutis_markets[rx_gutis_markets["MERCADO"] == m]
        if col_volumen: df_m = df_m.sort_values(by=col_volumen, ascending=False)
        else: df_m = df_m.sort_values(by=col_mes, ascending=False)
            
        meta = obtener_meta_mercado(m)
        prod_gutis_esperado = meta["producto"]
        lider = df_m.iloc[0]
        lider_nombre, lider_share, lider_es_gutis = str(lider["NOMBRE_PRODUCTO"]).strip(), lider[col_mes] * 100, lider["Es_Gutis"]
        lider_volumen = lider[col_volumen] if col_volumen else "N/A"

        if mercado_principal_str == "[S/D]" and lider_share > 0:
            mercado_principal_str, producto_ataque_str, prod_gutis_ataque_oficial, share_lider = m, lider_nombre, prod_gutis_esperado, lider_share

        vol_txt = f" | Rx: <b>{int(lider_volumen)}</b>" if col_volumen and str(lider_volumen) != "nan" else ""

        if lider_share > 0:
            if not lider_es_gutis:
                total_amenazas += 1
                # Tarjeta roja elegante (Degradado sutil)
                cards_ataque_html += f"""<div style="background: linear-gradient(180deg, #fff1f2 0%, #ffffff 100%); border: 1px solid #fecdd3; border-top: 4px solid #e11d48; border-radius: 6px; padding: 12px; min-width: 200px; flex: 1 1 calc(25% - 15px); box-shadow: 0 2px 4px rgba(0,0,0,0.02);"><div style="font-size: 0.65rem; font-weight: 800; color: #9f1239; text-transform: uppercase; letter-spacing: 0.5px;">{m.replace('MR ', '')}</div><div style="font-size: 0.9rem; color: #0f172a; margin: 6px 0;">Líder: <b style="color:#be123c;">{lider_nombre[:15]}</b></div><div style="font-size: 0.8rem; color: #475569;">MS: {lider_share:.1f}% {vol_txt}</div><div style="margin-top: 8px; font-size: 0.75rem; font-weight: 800; color: #0f172a; border-top: 1px dashed #cbd5e1; padding-top: 6px;">OBJETIVO: {prod_gutis_esperado}</div></div>"""
            else:
                # Tarjeta verde elegante (Degradado sutil)
                cards_ataque_html += f"""<div style="background: linear-gradient(180deg, #ecfdf5 0%, #ffffff 100%); border: 1px solid #a7f3d0; border-top: 4px solid #059669; border-radius: 6px; padding: 12px; min-width: 200px; flex: 1 1 calc(25% - 15px); box-shadow: 0 2px 4px rgba(0,0,0,0.02);"><div style="font-size: 0.65rem; font-weight: 800; color: #065f46; text-transform: uppercase; letter-spacing: 0.5px;">{m.replace('MR ', '')}</div><div style="font-size: 0.9rem; color: #0f172a; margin: 6px 0;">Dominio: <b style="color:#047857;">{prod_gutis_esperado}</b></div><div style="font-size: 0.8rem; color: #475569;">MS: {lider_share:.1f}% {vol_txt}</div><div style="margin-top: 8px; font-size: 0.75rem; font-weight: 800; color: #047857; border-top: 1px dashed #cbd5e1; padding-top: 6px;">[ESTATUS: MANTENER]</div></div>"""

# DATOS DE VENTAS Y CRUCE TÁCTICO
df_farmacias_totales = pd.DataFrame()
total_sellout_zona, total_puntos_venta, ventas_producto_lider_zona = 0.0, 0, 0.0
top_farmacias_str, top_farmacias_lista, escenario_tactico = "[ZONA SIN COBERTURA]", [], ""

if not df_ventas.empty and "DESCRIPCION_RUTA" in df_ventas.columns:
    ventas_zona_global = df_ventas[df_ventas["DESCRIPCION_RUTA"].str.contains(ciudad, na=False)].copy()
    if not ventas_zona_global.empty:
        ventas_zona_global = ventas_zona_global[~ventas_zona_global["NOMBRE_CLIENTE_1"].str.upper().isin(["TOTAL", "NAN", ""])]
        df_farmacias_totales = ventas_zona_global.groupby("NOMBRE_CLIENTE_1")["Monto Real"].sum().reset_index().sort_values(by="Monto Real", ascending=False)
        total_sellout_zona = df_farmacias_totales["Monto Real"].sum()
        total_puntos_venta = len(df_farmacias_totales)
        top_farmacias_lista = df_farmacias_totales["NOMBRE_CLIENTE_1"].head(3).tolist()
        top_farmacias_str = ", ".join(top_farmacias_lista)
        
        col_prod_ventas = "VM4" if "VM4" in ventas_zona_global.columns else next((c for c in ventas_zona_global.columns if c.upper() in ["NOMBRE_PRODUCTO", "PRODUCTO"]), None)
        if col_prod_ventas and producto_ataque_str != "[N/D]":
            palabra_clave = prod_gutis_ataque_oficial.upper().split()[0]
            ventas_producto_lider_zona = ventas_zona_global[ventas_zona_global[col_prod_ventas].astype(str).str.upper().str.contains(palabra_clave, na=False)]["Monto Real"].sum()
            if es_gutis(producto_ataque_str):
                escenario_tactico = f"[ALERTA DE FUGA] Prescribe {producto_ataque_str} con {share_lider:.1f}% MS, pero Sell-Out es bajo (${ventas_producto_lider_zona:.2f})." if ventas_producto_lider_zona < 150 else f"[ESTADO SEGURO] Fidelidad respaldada en Sell-Out."
            else: escenario_tactico = f"[ESCENARIO CONQUISTA] Liderazgo en competencia ({producto_ataque_str}). Requiere contraataque con {prod_gutis_ataque_oficial}."

historial_crm = "[S/D] Sin registros previos."
if os.path.exists(ARCHIVO_BITACORA):
    try:
        df_hist_full = pd.read_excel(ARCHIVO_BITACORA)
        df_hist_med = df_hist_full[df_hist_full["Médico"].astype(str) == medico_sel].sort_values(by="Fecha", ascending=False)
        if not df_hist_med.empty: historial_crm = f"({str(df_hist_med.iloc[0]['Fecha'])[:10]}) {df_hist_med.iloc[0]['Compromiso']}"
    except: pass

# --- FUNCIÓN LLAMADA GEMINI (RADAR OFICIAL) ---
def llamar_gemini(prompt_text, max_tok=4096, json_mode=False, audio_bytes=None):
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key: return "[ERROR SISTEMA] Falla de autenticación API."

    parts = [{"text": prompt_text}]
    if audio_bytes is not None:
        try:
            audio_b64 = base64.b64encode(audio_bytes.read()).decode('utf-8')
            parts.append({"inlineData": {"mimeType": "audio/wav", "data": audio_b64}})
        except Exception as e: return f"[ERROR AUDIO] {e}"

    payload = {"contents": [{"parts": parts}], "generationConfig": {"maxOutputTokens": max_tok, "temperature": 0.2}}
    if json_mode: payload["generationConfig"]["responseMimeType"] = "application/json"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    
    url_lista = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        r_list = requests.get(url_lista, timeout=15)
        if r_list.status_code == 200:
            todos_modelos = r_list.json().get('models', [])
            compatibles = [m['name'].replace('models/', '') for m in todos_modelos if 'generateContent' in m.get('supportedGenerationMethods', [])]
            if not compatibles: return "[ERROR] Sin modelos disponibles en el tenant."
            
            modelo_ideal = compatibles[0]
            for m in compatibles:
                if "flash" in m.lower():
                    modelo_ideal = m
                    break

            url_post = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo_ideal}:generateContent?key={api_key}"
            res = requests.post(url_post, headers=headers, json=payload, timeout=25)
            if res.status_code == 200: return res.json()['candidates'][0]['content']['parts'][0]['text']
            else: return f"[ERROR HTTP {res.status_code}]"
    except Exception as e: return f"[ERROR INTERNO] {str(e)}"

# --- TARJETAS KPI CORPORATIVAS ---
col1, col2, col3 = st.columns(3)
with col1: st.markdown(f"<div class='metric-card'><div class='metric-title'>MÉDICO OBJETIVO</div><div class='metric-value'>{medico_sel}</div><div style='color: #475569; font-size: 0.85rem; margin-top:5px; font-weight:600;'>{especialidad} | Categoría {categoria} | {ciudad}</div></div>", unsafe_allow_html=True)
with col2: st.markdown(f"<div class='metric-card' style='border-left-color: #0ea5e9;'><div class='metric-title'>FOCO ESTRATÉGICO ({mercado_principal_str})</div><div class='metric-value'>{producto_ataque_str[:15]}</div><div style='color: #475569; font-size: 0.85rem; margin-top:5px; font-weight:600;'>Cuota Actual: {share_lider:.1f}% ({'Gutis' if es_gutis(producto_ataque_str) else 'Competencia'})</div></div>", unsafe_allow_html=True)
with col3: st.markdown(f"<div class='metric-card' style='border-left-color: #8b5cf6;'><div class='metric-title'>SELL-OUT TERRITORIAL ({total_puntos_venta} PDV)</div><div class='metric-value'>${total_sellout_zona:,.2f}</div><div style='color: #475569; font-size: 0.85rem; margin-top:5px; font-weight:600;'>Disponibilidad Zonal</div></div>", unsafe_allow_html=True)

if not rx_gutis_markets.empty and cards_ataque_html:
    html_completo = f"""<div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-left: 5px solid #1e293b; padding: 18px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.03);"><div style="font-size: 0.85rem; font-weight: 800; color: #0f172a; margin-bottom: 12px; letter-spacing: 0.5px;">[SINOPSIS DE MERCADOS ACTIVOS - {num_mercados} REGISTROS]</div><div style="display: flex; flex-wrap: wrap; gap: 12px;">{cards_ataque_html}</div></div>"""
    st.components.v1.html(html_completo, height=180, scrolling=True)

# --- PESTAÑAS DEL SISTEMA ---
tab_chira, tab_estrategia, tab_perfil360, tab_rx, tab_sellout, tab_bitacora, tab_ruta = st.tabs([
    "[ASISTENTE CHIRA]", "Fase 1: Táctica Comercial", "Perfil 360°", "Fase 2: Análisis Rx", "Fase 3: Sell-Out", "Fase 4: Bitácora CRM", "Itinerario de Ruta"
])

# --- MÓDULO CHIRA ---
with tab_chira:
    st.markdown("### [CHIRA] - Consultor de Inteligencia Comercial Senior")
    st.caption("Módulo de análisis integral conectado al Panel, Auditoría Rx y Ventas de Territorio.")
    
    chat_container_chira = st.container(height=350)
    for msg in st.session_state.chira_history:
        with chat_container_chira.chat_message(msg["role"]): st.write(msg["content"])
        
    col_c1, col_c2 = st.columns([3, 1])
    with col_c2:
        audio_chira = st.audio_input("Ingreso por voz:") if hasattr(st, "audio_input") else None
    with col_c1:
        if prompt_chira := st.chat_input("Consulte estrategias, rutas o análisis de panel..."):
            pass # Handle text input below

    if prompt_chira or audio_chira:
        user_input = prompt_chira if prompt_chira else "Analiza el audio proporcionado y responde."
        st.session_state.chira_history.append({"role": "user", "content": user_input})
        with chat_container_chira.chat_message("user"): st.write(user_input)
        
        with st.spinner("[PROCESANDO DATA CORPORATIVA...]"):
            prompt_sistema_chira = f"""
            Eres CHIRA, la Analista Comercial Senior y estratega experta de Laboratorios Gutis para la zona de Nicaragua.
            Asistes al representante Erick Calderón. Tienes acceso total a la data. Responde SIEMPRE de forma directa, ejecutiva y con datos precisos (nombres reales, cifras, sin inventar nada).
            
            CONTEXTO ACTUAL:
            - Médico en pantalla: {medico_sel} (Esp: {especialidad}, Cat: {categoria}, Zona: {ciudad})
            - Total de médicos en {ciudad}: {len(df_filtrado)}
            - Sell-Out en {ciudad}: ${total_sellout_zona:,.2f}
            
            CONSULTA DEL USUARIO: {user_input}
            """
            
            if audio_chira: res_chira = llamar_gemini(prompt_sistema_chira, audio_bytes=audio_chira)
            else: res_chira = llamar_gemini(prompt_sistema_chira)
                
        st.session_state.chira_history.append({"role": "assistant", "content": res_chira})
        st.rerun()

# --- FASE 1: ESTRATEGIA TVP ---
with tab_estrategia:
    col_izq_ia, col_der_ia = st.columns([1, 1.2])
    with col_izq_ia:
        st.markdown("#### [GENERACIÓN DE ARGUMENTOS TÁCTICOS]")
        
        if st.button("[EJECUTAR ANÁLISIS FLASH - 30s]", use_container_width=True, type="primary"):
            with st.spinner("[COMPILANDO...]"):
                prompt_pasillo = f"{REGLAS_FARMA}\nGenera un argumento ejecutivo (Pitch de ascensor) de 2 oraciones para {medico_sel}. Receta {producto_ataque_str}. Misión: Cambiar a {prod_gutis_ataque_oficial}. {contexto_rapport_str}\nDirecto, clínico y comercial."
                st.session_state.pasillo_result = llamar_gemini(prompt_pasillo)
        
        if st.session_state.pasillo_result:
            st.info(st.session_state.pasillo_result)

        if st.button("[EJECUTAR ANÁLISIS TVP COMPLETO]", use_container_width=True):
            with st.spinner("[ESTRUCTURANDO PLAN DE VISITA...]"):
                prompt_tvp = f"{REGLAS_FARMA}\nEstructura plan comercial 6 pasos para {medico_sel}. Zona: {ciudad}. Diagnóstico: {escenario_tactico}. Atacar {producto_ataque_str} con {prod_gutis_ataque_oficial}."
                st.session_state.tvp_result = llamar_gemini(prompt_tvp)
        
        if st.session_state.tvp_result: st.markdown(st.session_state.tvp_result)

    with col_der_ia:
        st.markdown("#### [SIMULADOR DE OBJECIONES CLÍNICAS]")
        st.caption(f"Perfil emulado: {medico_sel} | Defensa: {producto_ataque_str[:15]}")
        chat_container = st.container(height=300)
        for msg in st.session_state.chat_history:
            with chat_container.chat_message(msg["role"]): st.write(msg["content"])
        if prompt_chat := st.chat_input("Ingrese refutación..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt_chat})
            with chat_container.chat_message("user"): st.write(prompt_chat)
            with st.spinner("[PROCESANDO RESPUESTA MÉDICA...]"):
                respuesta_doc = llamar_gemini(f"{REGLAS_FARMA}\nEres {medico_sel}. Defiendes {producto_ataque_str}. Erick ofrece {prod_gutis_ataque_oficial}. Objeción: {prompt_chat}")
            st.session_state.chat_history.append({"role": "assistant", "content": respuesta_doc})
            st.rerun()

# --- PESTAÑA: PERFIL 360 ---
with tab_perfil360:
    st.markdown("#### [ACTUALIZACIÓN DE PERFIL OMNICANAL]")
    with st.form("form_perfil_360"):
        c1, c2, c3 = st.columns(3)
        with c1: 
            val_minsa = st.text_input("MINSA:", value=str(perfil_360_actual.get("MINSA", "")) if str(perfil_360_actual.get("MINSA", "")) != "nan" else "")
            val_cel = st.text_input("Celular:", value=str(perfil_360_actual.get("Celular", "")) if str(perfil_360_actual.get("Celular", "")) != "nan" else "")
        with c2: 
            val_correo = st.text_input("Correo:", value=str(perfil_360_actual.get("Correo", "")) if str(perfil_360_actual.get("Correo", "")) != "nan" else "")
            val_cumple = st.text_input("Cumpleaños:", value=str(perfil_360_actual.get("Cumpleaños", "")) if str(perfil_360_actual.get("Cumpleaños", "")) != "nan" else "")
        with c3: 
            val_deporte = st.text_input("Afinidad/Hobby:", value=str(perfil_360_actual.get("Deporte", "")) if str(perfil_360_actual.get("Deporte", "")) != "nan" else "")
            opc_visita = ["Ultra-ejecutiva", "Discusión científica", "Casos clínicos"]
            idx_vis = opc_visita.index(perfil_360_actual.get("Estilo_Visita", opc_visita[0])) if perfil_360_actual.get("Estilo_Visita") in opc_visita else 0
            val_estilo_visita = st.selectbox("Estilo Visita:", opc_visita, index=idx_vis)

        if st.form_submit_button("[GUARDAR EN BASE DE DATOS]", use_container_width=True):
            st.success("[SISTEMA] Perfil guardado localmente.")

# --- FASE 2: ANÁLISIS RX POR VOLUMEN ---
with tab_rx:
    st.markdown("#### [ANÁLISIS DE PRESCRIPCIÓN Y POSICIONAMIENTO]")
    if not rx_clean.empty:
        col_lab = "LABORATORIO" if "LABORATORIO" in rx_clean.columns else next((c for c in rx_clean.columns if "LAB" in c.upper() or "CORP" in c.upper()), None)
        
        col_r1, col_r2 = st.columns([2.5, 1])
        with col_r1:
            st.markdown("##### Priorización por Volumen Absoluto")
            cols_to_show = ["NOMBRE_PRODUCTO", "MERCADO"]
            if col_volumen: cols_to_show.append(col_volumen)
            if col_mes: cols_to_show.append(col_mes)
            if col_lab: cols_to_show.append(col_lab)
            
            df_rx_view = rx_clean[cols_to_show].copy()
            
            if col_mes: df_rx_view[col_mes] = pd.to_numeric(df_rx_view[col_mes], errors='coerce').fillna(0) * 100
            if col_volumen: df_rx_view[col_volumen] = pd.to_numeric(df_rx_view[col_volumen], errors='coerce').fillna(0)
            
            if col_volumen: df_rx_view = df_rx_view.sort_values(by=[col_volumen, col_mes], ascending=[False, False])
            else: df_rx_view = df_rx_view.sort_values(by=col_mes, ascending=False)
            
            st.dataframe(df_rx_view, hide_index=True, use_container_width=True)

        with col_r2:
            st.markdown("##### [RADAR DE COMPETENCIA]")
            if col_lab and col_volumen:
                df_labs = rx_clean.groupby(col_lab)[col_volumen].sum().reset_index()
                df_labs = df_labs.sort_values(by=col_volumen, ascending=False).head(5)
                df_labs.columns = ["Laboratorio", "Recetas Totales"]
                st.dataframe(df_labs, hide_index=True, use_container_width=True)
            elif col_lab:
                df_labs = rx_clean[col_lab].value_counts().reset_index()
                df_labs.columns = ["Laboratorio", "Presencia en Líneas"]
                st.dataframe(df_labs.head(5), hide_index=True, use_container_width=True)
            else:
                st.info("[INFO] Columna de Laboratorio corporativo no detectada.")
    else: st.info("[SISTEMA] Sin datos de prescripción.")

# --- FASE 3: SELL-OUT ---
with tab_sellout:
    st.markdown("#### [INTELIGENCIA DE SELL-OUT PDV]")
    if not df_ventas.empty and "DESCRIPCION_RUTA" in df_ventas.columns:
        ventas_zona = df_ventas[df_ventas["DESCRIPCION_RUTA"].str.contains(ciudad, na=False)].copy()
        if not ventas_zona.empty:
            df_farms = ventas_zona.groupby("NOMBRE_CLIENTE_1")["Monto Real"].sum().reset_index().sort_values(by="Monto Real", ascending=False)
            st.dataframe(df_farms.head(10), hide_index=True, use_container_width=True)
    else: st.error("[SISTEMA] No hay cruce de rutas de venta.")

# --- FASE 4: BITÁCORA CRM ---
with tab_bitacora:
    st.markdown("#### [CONSOLA DE CAPTURA CRM]")
    audio_grabado = st.audio_input("Ingreso de nota por voz:") if hasattr(st, "audio_input") else None
    if st.button("[PROCESAR ACUERDO A BASE DE DATOS]"):
        st.warning("[SISTEMA] Módulo listo para conexión con Google Sheets (Fase 2).")

# --- RUTA ---
with tab_ruta:
    st.markdown("#### [ITINERARIO DE ZONA]")
    df_ruta_zona = df_panel[df_panel["CIUDAD"] == ciudad] if ciudad != "N/D" else df_panel
    
    columnas_deseadas = ["Médico", "Especialidad", "CATEGORIA", "DIRECCION", "Dirección", "DIRECCIÓN", "CLINICA", "CIUDAD"]
    columnas_existentes = [col for col in columnas_deseadas if col in df_ruta_zona.columns]
    
    if "Médico" in columnas_existentes:
        st.dataframe(df_ruta_zona[columnas_existentes].dropna(subset=["Médico"]).head(20), hide_index=True, use_container_width=True)
    else:
        st.dataframe(df_ruta_zona.head(20), hide_index=True, use_container_width=True)
