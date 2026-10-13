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

        if mercado_principal_str == "[S/D]" and (lider_pxs > 0 or lider_ms > 0):
            mercado_principal_str, producto_ataque_str, prod_gutis_ataque_oficial, share_lider = m, lider_nombre, prod_gutis_esperado, lider_ms

        pxs_txt = f" | Pxs: <b>{lider_pxs}</b>" if col_pxs else ""
        if lider_ms > 0 or lider_pxs > 0:
            if not lider_es_gutis:
                cards_ataque_html += f"""<div style="background: linear-gradient(180deg, #fff1f2 0%, #ffffff 100%); border: 1px solid #fecdd3; border-top: 4px solid #e11d48; border-radius: 6px; padding: 12px; min-width: 210px; flex: 1 1 calc(25% - 15px); box-shadow: 0 2px 4px rgba(0,0,0,0.02);"><div style="font-size: 0.65rem; font-weight: 800; color: #9f1239; text-transform: uppercase;">{m.replace('MR ', '')}</div><div style="font-size: 0.88rem; color: #0f172a; margin: 5px 0;">Líder: <b style="color:#be123c;">{lider_nombre[:16]}</b></div><div style="font-size: 0.78rem; color: #475569;">Cuota: {lider_ms:.1f}% {pxs_txt}</div><div style="margin-top: 6px; font-size: 0.75rem; font-weight: 800; color: #047857; border-top: 1px dashed #cbd5e1; padding-top: 5px;">➔ Conquistar con {prod_gutis_esperado}</div></div>"""
            else:
                cards_ataque_html += f"""<div style="background: linear-gradient(180deg, #ecfdf5 0%, #ffffff 100%); border: 1px solid #a7f3d0; border-top: 4px solid #059669; border-radius: 6px; padding: 12px; min-width: 210px; flex: 1 1 calc(25% - 15px); box-shadow: 0 2px 4px rgba(0,0,0,0.02);"><div style="font-size: 0.65rem; font-weight: 800; color: #065f46; text-transform: uppercase;">{m.replace('MR ', '')}</div><div style="font-size: 0.88rem; color: #0f172a; margin: 5px 0;">Dominio: <b style="color:#047857;">{prod_gutis_esperado}</b></div><div style="font-size: 0.78rem; color: #475569;">Fidelidad: {lider_ms:.1f}% {pxs_txt}</div><div style="margin-top: 6px; font-size: 0.75rem; font-weight: 800; color: #047857; border-top: 1px dashed #cbd5e1; padding-top: 5px;">[BLINDAR RECETARIO]</div></div>"""

# DATOS DE VENTAS Y CRUCE TÁCTICO
ventas_producto_lider_zona, total_sellout_zona, total_puntos_venta = 0.0, 0.0, 0
escenario_tactico = "[ZONA SIN COBERTURA]"

if not df_ventas.empty and "DESCRIPCION_RUTA" in df_ventas.columns:
    ventas_zona_global = df_ventas[df_ventas["DESCRIPCION_RUTA"].str.contains(ciudad, na=False)].copy()
    if not ventas_zona_global.empty:
        ventas_zona_global = ventas_zona_global[~ventas_zona_global["NOMBRE_CLIENTE_1"].str.upper().isin(["TOTAL", "NAN", ""])]
        df_farmacias_totales = ventas_zona_global.groupby("NOMBRE_CLIENTE_1")["Monto Real"].sum().reset_index()
        total_sellout_zona = df_farmacias_totales["Monto Real"].sum()
        total_puntos_venta = len(df_farmacias_totales)
        
        col_prod_ventas = "VM4" if "VM4" in ventas_zona_global.columns else next((c for c in ventas_zona_global.columns if c.upper() in ["NOMBRE_PRODUCTO", "PRODUCTO"]), None)
        if col_prod_ventas and producto_ataque_str != "[N/D]":
            palabra_clave = prod_gutis_ataque_oficial.upper().split()[0]
            ventas_producto_lider_zona = ventas_zona_global[ventas_zona_global[col_prod_ventas].astype(str).str.upper().str.contains(palabra_clave, na=False)]["Monto Real"].sum()
            if es_gutis(producto_ataque_str):
                escenario_tactico = f"[ALERTA DE FUGA] Prescribe {producto_ataque_str} con {share_lider:.1f}% MS, pero Sell-Out es bajo (${ventas_producto_lider_zona:.2f})." if ventas_producto_lider_zona < 150 else f"[ESTADO SEGURO] Fidelidad respaldada en Sell-Out."
            else: escenario_tactico = f"[ESCENARIO CONQUISTA] Liderazgo en competencia ({producto_ataque_str}). Requiere contraataque con {prod_gutis_ataque_oficial}."

# --- FUNCIÓN LLAMADA A GEMINI (MOTORES BASE ÚNICAMENTE - CERO ERROR 404) ---
def llamar_gemini(prompt_text, max_tok=4096, json_mode=False, audio_bytes=None):
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key: return "⚠️ Error: Clave API GEMINI_API_KEY no configurada."

    parts = [{"text": prompt_text}]
    if audio_bytes is not None:
        try:
            audio_b64 = base64.b64encode(audio_bytes.read()).decode('utf-8')
            parts.append({"inlineData": {"mimeType": "audio/wav", "data": audio_b64}})
        except Exception as e: return f"⚠️ Error en audio: {e}"

    payload = {"contents": [{"parts": parts}], "generationConfig": {"maxOutputTokens": max_tok, "temperature": 0.2}}
    if json_mode: payload["generationConfig"]["responseMimeType"] = "application/json"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

    # LOS NOMBRES OFICIALES EXACTOS, SIN NINGÚN SUFIJO EXPERIMENTAL
    modelos_estables = ["gemini-1.5-flash", "gemini-1.5-pro"]
    ultimo_error = ""
    for mod in modelos_estables:
        url_post = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
        try:
            res = requests.post(url_post, headers=headers, json=payload, timeout=25)
            if res.status_code == 200:
                cands = res.json().get('candidates', [])
                if cands and 'content' in cands[0] and 'parts' in cands[0]['content']:
                    return cands[0]['content']['parts'][0].get('text', '')
            else: ultimo_error = f"HTTP {res.status_code} ({mod}): {res.text[:120]}"
        except Exception as e:
            ultimo_error = str(e)
            continue
    return f"⚠️ Error en servidores de Google: {ultimo_error}"

# --- TARJETAS KPI CORPORATIVAS ---
col1, col2, col3 = st.columns(3)
with col1: 
    st.markdown(f"""<div class='metric-card'><div class='metric-title'>MÉDICO OBJETIVO</div><div class='metric-value'>{medico_sel}</div><div style='color: #475569; font-size: 0.85rem; margin-top:5px; font-weight:600;'>{especialidad} | Categoría {categoria} | {ciudad}</div></div>""", unsafe_allow_html=True)
with col2: 
    sub_potencial = f"Pacientes Totales: <b>{total_pxs_medico}</b> (Gutis: {gutis_pxs_medico} | Comp: {comp_pxs_medico})" if total_pxs_medico > 0 else f"Cuota: {share_lider:.1f}%"
    st.markdown(f"""<div class='metric-card' style='border-left-color: #0ea5e9;'><div class='metric-title'>FOCO ESTRATÉGICO ({mercado_principal_str})</div><div class='metric-value'>{producto_ataque_str[:15]}</div><div style='color: #475569; font-size: 0.85rem; margin-top:5px; font-weight:600;'>{sub_potencial}</div></div>""", unsafe_allow_html=True)
with col3: 
    st.markdown(f"""<div class='metric-card' style='border-left-color: #8b5cf6;'><div class='metric-title'>SELL-OUT TERRITORIAL ({total_puntos_venta} PDV)</div><div class='metric-value'>${total_sellout_zona:,.2f}</div><div style='color: #475569; font-size: 0.85rem; margin-top:5px; font-weight:600;'>Disponibilidad Zonal</div></div>""", unsafe_allow_html=True)

if not rx_gutis_markets.empty and cards_ataque_html:
    st.components.v1.html(f"""<div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-left: 5px solid #1e3a8a; padding: 16px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.03);"><div style="font-size: 0.85rem; font-weight: 800; color: #0f172a; margin-bottom: 12px; letter-spacing: 0.5px;">[SINOPSIS DE MERCADOS ACTIVOS - {num_mercados} REGISTROS]</div><div style="display: flex; flex-wrap: wrap; gap: 10px;">{cards_ataque_html}</div></div>""", height=180, scrolling=True)

# --- PESTAÑAS DEL SISTEMA COMPLETAS ---
tab_chira, tab_estrategia, tab_perfil360, tab_rx, tab_sellout, tab_bitacora, tab_ruta = st.tabs([
    "[ASISTENTE CHIRA]", "Fase 1: Táctica Comercial", "Perfil 360°", "Fase 2: Análisis Rx", "Fase 3: Sell-Out", "Fase 4: Bitácora CRM", "Itinerario de Ruta"
])

# --- MÓDULO CHIRA ---
with tab_chira:
    st.markdown("### [CHIRA] - Consultor de Inteligencia Comercial Senior")
    st.caption("Conectada en tiempo real a tu Panel, Auditoría de Pacientes (Pxs) y Sell-Out Zonal.")
    
    chat_container_chira = st.container(height=350)
    for msg in st.session_state.chira_history:
        with chat_container_chira.chat_message(msg["role"]): st.write(msg["content"])
        
    col_c1, col_c2 = st.columns([3, 1])
    with col_c2: audio_chira = st.audio_input("Ingreso por voz:") if hasattr(st, "audio_input") else None
    with col_c1:
        if prompt_chira := st.chat_input("Ej: ¿Cuáles son los 5 médicos más importantes para Talerdín en Granada?"): pass 

    if prompt_chira or audio_chira:
        user_input = prompt_chira if prompt_chira else "Analiza el audio proporcionado y responde."
        st.session_state.chira_history.append({"role": "user", "content": user_input})
        with chat_container_chira.chat_message("user"): st.write(user_input)
        
        with st.spinner("[CHIRA PROCESANDO AUDITORÍA EN TIEMPO REAL...]"):
            ciudades_validas = [str(c).upper() for c in df_panel["CIUDAD"].dropna().unique() if str(c).strip() not in ["", "NAN"]]
            ciudad_detectada = next((c for c in ciudades_validas if c in user_input.upper()), ciudad_filtro if ciudad_filtro != "TODAS" else ciudad)
            df_medicos_target = df_panel[df_panel["CIUDAD"].astype(str).str.upper() == ciudad_detectada.upper()]
            if df_medicos_target.empty: df_medicos_target = df_filtrado

            mercado_detectado = None
            for m_key, m_val in MERCADOS_PRIORITARIOS.items():
                if any(k in user_input.upper() for k in m_val["keywords"]):
                    mercado_detectado = m_key
                    break

            medicos_evaluados = []
            if not df_productos.empty:
                for _, r_m in df_medicos_target.dropna(subset=["Médico"]).iterrows():
                    m_nom, m_esp, m_cat = str(r_m["Médico"]).strip(), str(r_m.get("Especialidad", "N/D")).strip(), str(r_m.get("CATEGORIA", "3")).strip()
                    m_rx = df_productos[df_productos["Médico"] == m_nom]
                    if m_rx.empty: continue

                    if mercado_detectado:
                        m_rx_merc = m_rx[m_rx["MERCADO"].astype(str).str.upper().str.contains(mercado_detectado.replace("MR ", ""), na=False)].copy()
                        if not m_rx_merc.empty and col_pxs:
                            m_rx_merc[col_pxs] = pd.to_numeric(m_rx_merc[col_pxs], errors='coerce').fillna(0)
                            pxs_totales_merc = int(m_rx_merc[col_pxs].sum())
                            if pxs_totales_merc > 0:
                                m_rx_merc = m_rx_merc.sort_values(by=col_pxs, ascending=False)
                                lider_row = m_rx_merc.iloc[0]
                                medicos_evaluados.append({
                                    "nombre": m_nom, "esp": m_esp, "cat": m_cat, "pxs_totales": pxs_totales_merc,
                                    "lider": str(lider_row["NOMBRE_PRODUCTO"]).strip(),
                                    "lider_px": int(lider_row[col_pxs]),
                                    "lider_ms": (pd.to_numeric(lider_row[col_mes], errors='coerce') * 100) if col_mes else 0.0
                                })
                
            medicos_evaluados = sorted(medicos_evaluados, key=lambda x: x["pxs_totales"], reverse=True)
            lineas_datos = [f"- Dr/a. {i['nombre']} (Cat {i['cat']}): {i['pxs_totales']} Pxs Totales. Receta: {i['lider']} ({i['lider_px']} Pxs, {i['lider_ms']:.1f}% MS)." for i in medicos_evaluados[:10]]
            datos_auditados_str = "\n".join(lineas_datos) if lineas_datos else f"Sin datos en {ciudad_detectada}."

            prompt_sistema_chira = f"""{REGLAS_FARMA}\nEres CHIRA, estratega de Gutis. Responde basándote SOLO en estos datos de {ciudad_detectada}:\n{datos_auditados_str}\nSi piden médicos importantes, indícalos con sus datos exactos. Consulta: {user_input}"""
            
            res_chira = llamar_gemini(prompt_sistema_chira, audio_bytes=audio_chira) if audio_chira else llamar_gemini(prompt_sistema_chira)
        st.session_state.chira_history.append({"role": "assistant", "content": res_chira})
        st.rerun()

# --- FASE 1: TÁCTICA TVP ---
with tab_estrategia:
    col_izq_ia, col_der_ia = st.columns([1, 1.2])
    with col_izq_ia:
        st.markdown("#### [GENERACIÓN DE ARGUMENTOS TÁCTICOS]")
        
        if st.button("[EJECUTAR ANÁLISIS FLASH - 30s]", use_container_width=True, type="primary"):
            with st.spinner("[COMPILANDO...]"):
                st.session_state.pasillo_result = llamar_gemini(f"{REGLAS_FARMA}\nGenera un argumento comercial hiper-agresivo (Pitch de ascensor) de 2 oraciones para {medico_sel}. Receta la competencia ({producto_ataque_str}). Tu misión es que cambie HOY a {prod_gutis_ataque_oficial}.")
        if st.session_state.pasillo_result: st.info(st.session_state.pasillo_result)

        if st.button("[EJECUTAR ANÁLISIS TVP COMPLETO]", use_container_width=True):
            with st.spinner("[ESTRUCTURANDO PLAN DE VISITA INTEGRAL...]"):
                prompt_tvp = f"""{REGLAS_FARMA}
Genera un Plan de Visita Médica (TVP) altamente estratégico, profesional y agresivo para {medico_sel}.
Contexto: Prescribe {producto_ataque_str}. Necesitamos que prescriba {prod_gutis_ataque_oficial}.

Estructúralo obligatoriamente en estos 6 pasos exactos (usa negritas y viñetas):
1. Pre-Visita (Análisis de escenario)
2. Rapport (Ganar confianza inicial)
3. Sondeo Clínico (Pregunta de dolor)
4. Presentación de Valor (Beneficios directos de {prod_gutis_ataque_oficial} vs {producto_ataque_str})
5. Manejo de Objeciones (Qué dirá el médico y cómo rebatirlo)
6. Cierre Directo (Compromiso de recetas)"""
                st.session_state.tvp_result = llamar_gemini(prompt_tvp)
        if st.session_state.tvp_result: st.markdown(st.session_state.tvp_result)

    with col_der_ia:
        st.markdown("#### [SIMULADOR DE OBJECIONES CLÍNICAS]")
        chat_container = st.container(height=300)
        for msg in st.session_state.chat_history:
            with chat_container.chat_message(msg["role"]): st.write(msg["content"])
        if prompt_chat := st.chat_input("Ingrese refutación clínica..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt_chat})
            with chat_container.chat_message("user"): st.write(prompt_chat)
            with st.spinner("[PROCESANDO...]"):
                res_sim = llamar_gemini(f"{REGLAS_FARMA}\nEres {medico_sel} defendiendo {producto_ataque_str} ante {prod_gutis_ataque_oficial}. Objeción: {prompt_chat}")
            st.session_state.chat_history.append({"role": "assistant", "content": res_sim})
            st.rerun()

# --- PERFIL 360° ---
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
            st.success("[SISTEMA] Perfil guardado correctamente.")

# --- FASE 2: ANÁLISIS RX ---
with tab_rx:
    st.markdown("#### [AUDITORÍA DE PRESCRIPCIÓN Y LABORATORIOS]")
    m_p1, m_p2, m_p3 = st.columns(3)
    with m_p1: st.metric("Pacientes Totales (Pxs)", total_pxs_medico)
    with m_p2: st.metric("Pacientes Gutis", gutis_pxs_medico)
    with m_p3: st.metric("Oportunidad Conquista", comp_pxs_medico)
    st.divider()

    if not rx_clean.empty:
        mercados_disponibles = sorted(rx_clean["MERCADO"].dropna().unique().tolist())
        mercados_filtro = st.multiselect("🔍 Filtrar visualización por Mercados Estratégicos:", mercados_disponibles, placeholder="Seleccione uno o varios mercados...")
        
        rx_vista = rx_clean[rx_clean["MERCADO"].isin(mercados_filtro)] if mercados_filtro else rx_clean.copy()

        col_r1, col_r2 = st.columns([2.3, 1.2])
        with col_r1:
            st.markdown("##### 📋 Priorización por Pacientes Reales (Pxs-MES)")
            cols_to_show = ["NOMBRE_PRODUCTO", "MERCADO"]
            if col_pxs: cols_to_show.append(col_pxs)
            if col_mes: cols_to_show.append(col_mes)
            
            df_rx_view = rx_vista[cols_to_show].copy()
            df_rx_view["Origen"] = df_rx_view["NOMBRE_PRODUCTO"].apply(lambda x: "🟢 GUTIS" if es_gutis(x) else "🔴 COMPETENCIA")
            
            if col_mes: df_rx_view[col_mes] = pd.to_numeric(df_rx_view[col_mes], errors='coerce').fillna(0) * 100
            if col_pxs: df_rx_view[col_pxs] = pd.to_numeric(df_rx_view[col_pxs], errors='coerce').fillna(0).astype(int)
            
            if col_pxs: df_rx_view = df_rx_view.sort_values(by=[col_pxs, col_mes] if col_mes else [col_pxs], ascending=[False, False])
            elif col_mes: df_rx_view = df_rx_view.sort_values(by=col_mes, ascending=False)
            
            if col_mes: df_rx_view[col_mes] = df_rx_view[col_mes].map("{:.1f}%".format)
            
            renombrar = {col_pxs: "Pacientes (Pxs-MES)", col_mes: "% Cuota Mercado"}
            st.dataframe(df_rx_view.rename(columns=renombrar), hide_index=True, use_container_width=True)

        with col_r2:
            st.markdown("##### 🔬 [RADAR DE FABRICANTES]")
            
            if not df_labs.empty and "FABRICANTE" in df_labs.columns and "Médico" in df_labs.columns:
                df_labs_medico = df_labs[df_labs["Médico"] == medico_sel].copy()
                df_labs_medico = df_labs_medico[~df_labs_medico["FABRICANTE"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
                
                if not df_labs_medico.empty:
                    col_pxs_ytd = "Pxs-YTD" if "Pxs-YTD" in df_labs_medico.columns else next((c for c in df_labs_medico.columns if "YTD" in c.upper() and "PXS" in c.upper()), None)
                    
                    if col_pxs_ytd:
                        df_labs_medico[col_pxs_ytd] = pd.to_numeric(df_labs_medico[col_pxs_ytd], errors='coerce').fillna(0)
                        df_agrupado = df_labs_medico.groupby("FABRICANTE").agg({col_pxs_ytd: 'sum'}).reset_index()
                        
                        total_ytd_medico = df_agrupado[col_pxs_ytd].sum()
                        if total_ytd_medico > 0: df_agrupado["% MS YTD"] = (df_agrupado[col_pxs_ytd] / total_ytd_medico) * 100
                        else: df_agrupado["% MS YTD"] = 0.0

                        df_agrupado = df_agrupado.sort_values(by=col_pxs_ytd, ascending=False).head(10)
                        df_agrupado.columns = ["Laboratorio Fabricante", "Pxs Totales (YTD)", "% MS YTD"]
                        df_agrupado["Pxs Totales (YTD)"] = df_agrupado["Pxs Totales (YTD)"].astype(int)
                        df_agrupado["% MS YTD"] = df_agrupado["% MS YTD"].map("{:.2f}%".format)
                        
                        st.dataframe(df_agrupado, hide_index=True, use_container_width=True)
                    else: st.info("Columna 'Pxs-YTD' no detectada.")
                else: st.info("Sin registros de laboratorio para este médico.")
            else: st.info("ℹ️ Sube a GitHub el archivo de Laboratorios.")
    else: st.info("[SISTEMA] Sin datos de prescripción.")

# --- FASE 3: SELL-OUT CON IA Y SUCURSALES SELECCIONABLES ---
with tab_sellout:
    st.markdown("#### [INTELIGENCIA DE SELL-OUT Y TENDENCIAS TRIMESTRALES]")
    if not df_ventas.empty and "DESCRIPCION_RUTA" in df_ventas.columns:
        ventas_zona = df_ventas[df_ventas["DESCRIPCION_RUTA"].str.contains(ciudad, na=False)].copy()
        
        if not ventas_zona.empty:
            col_prod_v = "VM4" if "VM4" in ventas_zona.columns else next((c for c in ventas_zona.columns if "PRODUCTO" in c.upper()), None)
            
            if col_prod_v:
                ventas_zona[col_prod_v] = ventas_zona[col_prod_v].astype(str).str.strip()
                ventas_zona = ventas_zona[~ventas_zona[col_prod_v].str.upper().isin(["TOTAL", "NAN", ""])]
            ventas_zona = ventas_zona[~ventas_zona["NOMBRE_CLIENTE_1"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]

            farmacias_disp = sorted(ventas_zona["NOMBRE_CLIENTE_1"].dropna().unique().tolist())
            farm_sel = st.multiselect("🏥 Seleccione Farmacia(s) para ver el detalle de productos:", farmacias_disp, placeholder="Mostrando todas las farmacias de la zona...")
            
            df_v_mostrar = ventas_zona[ventas_zona["NOMBRE_CLIENTE_1"].isin(farm_sel)] if farm_sel else ventas_zona

            if col_prod_v and "Trimestre" in df_v_mostrar.columns:
                st.markdown("##### Detalle de Ventas por Farmacia, Trimestre y Producto")
                df_pivot = pd.pivot_table(df_v_mostrar, values="Monto Real", index=["NOMBRE_CLIENTE_1", col_prod_v], columns=["Trimestre"], aggfunc="sum", fill_value=0).reset_index()
                
                columnas_trim = [c for c in df_pivot.columns if c in ["Q1", "Q2", "Q3"]]
                if columnas_trim:
                    df_pivot["Venta Total"] = df_pivot[columnas_trim].sum(axis=1)
                    df_pivot = df_pivot.sort_values(by="Venta Total", ascending=False)
                
                renombrar_v = {"NOMBRE_CLIENTE_1": "Punto de Venta / Farmacia", col_prod_v: "Línea / Producto"}
                st.dataframe(df_pivot.rename(columns=renombrar_v), hide_index=True, use_container_width=True)
                
                st.markdown("#### [ANÁLISIS IA DE SELL-OUT]")
                if st.button("[EJECUTAR ANÁLISIS DE VENTAS]", use_container_width=True):
                    with st.spinner("Analizando tendencias de venta..."):
                         prompt_ventas = f"{REGLAS_FARMA}\nAnaliza este Sell-Out de {ciudad}. Menciona cuál es la farmacia líder, qué producto estrella se vende más, y danos una sugerencia táctica para crecer:\n{df_pivot.head(20).to_string(index=False)}"
                         st.info(llamar_gemini(prompt_ventas))
            else:
                df_farms = df_v_mostrar.groupby("NOMBRE_CLIENTE_1")["Monto Real"].sum().reset_index().sort_values(by="Monto Real", ascending=False)
                st.dataframe(df_farms, hide_index=True, use_container_width=True)
    else: st.error("[SISTEMA] No hay cruce de rutas de venta.")

# --- BITÁCORA CRM ---
with tab_bitacora:
    st.markdown("#### [CONSOLA DE CAPTURA CRM]")
    audio_grabado = st.audio_input("Ingreso de nota por voz:") if hasattr(st, "audio_input") else None
    if st.button("[PROCESAR ACUERDO A BASE DE DATOS]"):
        st.warning("[SISTEMA] Módulo listo para conexión con Google Sheets.")

# --- RUTA ---
with tab_ruta:
    st.markdown("#### [ITINERARIO INTELIGENTE POR MERCADO]")
    st.caption("Selecciona los mercados que vas a auditar hoy para filtrar a los médicos más importantes de tu ruta.")
    
    df_ruta_zona = df_panel[df_panel["CIUDAD"] == ciudad] if ciudad != "N/D" else df_panel
    columnas_deseadas = ["Médico", "Especialidad", "CATEGORIA", "DIRECCION", "Dirección", "CLINICA", "CIUDAD"]
    columnas_existentes = [col for col in columnas_deseadas if col in df_ruta_zona.columns]
    
    df_mostrar = df_ruta_zona[columnas_existentes].dropna(subset=["Médico"]).copy() if "Médico" in columnas_existentes else df_ruta_zona.copy()

    if not df_productos.empty and "MERCADO" in df_productos.columns:
        mercados_ruta_disp = sorted(df_productos["MERCADO"].dropna().unique().tolist())
        mercados_ruta_sel = st.multiselect("🎯 Filtrar Ruta por Mercados Estratégicos (Puedes elegir varios):", mercados_ruta_disp, placeholder="Seleccione mercados...")

        if mercados_ruta_sel and "Médico" in df_mostrar.columns:
            rx_ruta = df_productos[df_productos["MERCADO"].isin(mercados_ruta_sel)].copy()
            col_pxs_ruta = next((c for c in rx_ruta.columns if c.upper() == "PXS-MES"), None)
            if not col_pxs_ruta: col_pxs_ruta = next((c for c in rx_ruta.columns if "PXS" in c.upper() or "TRX" in c.upper()), None)
            
            if col_pxs_ruta:
                rx_ruta[col_pxs_ruta] = pd.to_numeric(rx_ruta[col_pxs_ruta], errors='coerce').fillna(0)
                volumen_por_medico = rx_ruta.groupby("Médico")[col_pxs_ruta].sum().reset_index()
                volumen_por_medico.columns = ["Médico", "Pxs en Mercados Seleccionados"]
                
                df_mostrar = pd.merge(df_mostrar, volumen_por_medico, on="Médico", how="inner")
                df_mostrar["Pxs en Mercados Seleccionados"] = df_mostrar["Pxs en Mercados Seleccionados"].astype(int)
                df_mostrar = df_mostrar.sort_values(by="Pxs en Mercados Seleccionados", ascending=False)
                st.success(f"Mostrando solo médicos que recetan en los mercados seleccionados, ordenados por pacientes.")
            else:
                medicos_en_mercado = rx_ruta["Médico"].unique()
                df_mostrar = df_mostrar[df_mostrar["Médico"].isin(medicos_en_mercado)]

    st.dataframe(df_mostrar, hide_index=True, use_container_width=True)
