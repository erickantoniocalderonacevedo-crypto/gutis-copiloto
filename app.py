import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import os
import json
from datetime import datetime
import numpy as np
from urllib.parse import quote
import base64

# --- CONFIGURACIÓN EJECUTIVA DE PÁGINA ---
st.set_page_config(
    page_title="Gutis BI - Copiloto Táctico",
    page_icon="🧬",
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

# --- DICCIONARIO FARMACOLÓGICO ESTRICTO ---
REGLAS_FARMA = """
REGLAS FARMACOLÓGICAS Y DE COMPETENCIA (ESTRICTO):
1. CETRILER es CETIRIZINA (NO es Montelukast, NO es Desloratadina).
2. CARBUM es ESOMEPRAZOL.
3. TALERDÍN es CETIRIZINA. Ventaja competitiva: 100% libre de alcohol (cero irritación gástrica en pediatría/adultos), gotas exactas y mejor perfil de tolerabilidad.
4. GASTROALIVIO es ESOMEPRAZOL. Ventaja competitiva: Micropellets gastrorresistentes y Plan Paciente 2+1.
5. VENTILAR es MONTELUKAST SÓDICO.
6. MOMETZONA es FUROATO DE MOMETASONA (Spray nasal acuoso libre de alcohol, previene epistaxis).
7. BIOTOS INMUNE es HEDERA HELIX + PELARGONIUM SIDOIDES (Doble acción mucolítica e inmunomoduladora antiviral).
8. SI EL MÉDICO ES PEDIATRA: NUNCA sugieras ni menciones GASTROALIVIO (en Nicaragua solo existe cápsula 40mg para adultos, sin presentación pediátrica). Ofrece Talerdín, Biotos, Clembroxil o Ventilar.
¡NUNCA INVENTES EFECTOS NEUROPSIQUIÁTRICOS PARA LA CETIRIZINA! Apégate estrictamente a las ventajas galénicas y clínicas reales.
"""

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    h1, h2, h3 { color: #0f172a; font-weight: 700; }
    .metric-card { background-color: #ffffff; border-radius: 12px; padding: 20px; border-left: 6px solid #0284c7; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); margin-bottom: 15px; }
    .metric-title { color: #64748b; font-size: 0.875rem; text-transform: uppercase; font-weight: 700; margin-bottom: 5px; }
    .metric-value { color: #0f172a; font-size: 1.875rem; font-weight: 900; }
    .stTabs [data-baseweb="tab-list"] { border-bottom: 2px solid #e2e8f0; gap: 8px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] { font-size: 0.95rem; font-weight: 600; color: #64748b; padding: 8px 14px; }
    .stTabs [aria-selected="true"] { color: #0284c7; border-bottom: 3px solid #0284c7; background-color: #f0f9ff; border-radius: 8px 8px 0 0; }
    .zonal-alert { background-color: #fffbeb; border-left: 6px solid #f59e0b; padding: 16px; border-radius: 8px; margin-top: 15px; font-size: 0.95rem; color: #92400e; line-height: 1.5; }
    .pasillo-card { background: linear-gradient(135deg, #e11d48, #9f1239); color: white; padding: 22px; border-radius: 12px; font-size: 1.25rem; font-weight: 600; line-height: 1.5; box-shadow: 0 10px 15px -3px rgba(225, 29, 72, 0.4); border: 2px solid #fecdd3;}
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

# --- ENCABEZADO ---
st.markdown("""<div style='background-color:#0f172a; padding: 15px; border-radius: 8px; margin-bottom: 20px;'>
    <h1 style='color: white; margin: 0; font-size: 1.8rem;'>🧬 Gutis BI: Copiloto Táctico</h1>
    <p style='color: #94a3b8; margin: 0;'>Inteligencia Comercial, CRM de Voz y Perfilamiento Omnicanal 360°</p>
</div>""", unsafe_allow_html=True)

# --- MENÚ LATERAL ---
st.sidebar.header("🎯 Filtros Territoriales")
ciudades = ["TODAS"] + sorted([c for c in df_panel["CIUDAD"].dropna().unique() if str(c).strip() != ""])
ciudad_filtro = st.sidebar.selectbox("Filtrar por Zona / Ciudad:", ciudades)

df_filtrado = df_panel if ciudad_filtro == "TODAS" else df_panel[df_panel["CIUDAD"] == ciudad_filtro]
lista_medicos = sorted(df_filtrado["Médico"].dropna().unique().tolist())

if not lista_medicos:
    st.warning("No hay médicos registrados para esta zona.")
    st.stop()

medico_sel = st.sidebar.selectbox("👨‍⚕️ Médico a visitar:", lista_medicos)

if "medico_chat" not in st.session_state or st.session_state.medico_chat != medico_sel:
    st.session_state.chat_history = []
    st.session_state.gira_chat_history = []
    st.session_state.medico_chat = medico_sel
    st.session_state.tvp_result = None
    st.session_state.pasillo_result = None

info_medico = df_filtrado[df_filtrado["Médico"] == medico_sel].iloc[0]
ciudad = str(info_medico.get("CIUDAD", "N/D")).strip().upper()
especialidad = str(info_medico.get("Especialidad", "N/D")).strip().upper()
categoria = str(info_medico.get("CATEGORIA", "N/D")).strip()
es_pediatra = "PEDIAT" in especialidad

# --- RECUPERAR PERFIL OMNICANAL 360° ---
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
    hobby = perfil_360_actual.get("Hobby", "")
    estilo_visita = perfil_360_actual.get("Estilo_Visita", "")
    canal_pref = perfil_360_actual.get("Canal_Digital", "")
    
    partes_rapport = []
    if cumple and str(cumple) != "nan": partes_rapport.append(f"Cumpleaños: {cumple}")
    if deporte and str(deporte) != "nan": partes_rapport.append(f"Deporte/Equipo: {deporte}")
    if hobby and str(hobby) != "nan": partes_rapport.append(f"Hobby: {hobby}")
    if estilo_visita and str(estilo_visita) != "nan": partes_rapport.append(f"Estilo de visita preferido: {estilo_visita}")
    if canal_pref and str(canal_pref) != "nan": partes_rapport.append(f"Canal digital de seguimiento: {canal_pref}")
    
    if partes_rapport:
        contexto_rapport_str = "\nDATOS DE PERFIL 360° Y RAPPORT:\n- " + "\n- ".join(partes_rapport)

# --- PROCESAMIENTO ANALÍTICO ---
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

col_mes = "%MS-MES" if "%MS-MES" in rx_clean.columns else "%MS-YTD" if "%MS-YTD" in rx_clean.columns else "%MS-TAM"
rx_gutis_markets = rx_clean[rx_clean["Es_Mercado_Gutis"]].copy()
if col_mes in rx_gutis_markets.columns: rx_gutis_markets[col_mes] = pd.to_numeric(rx_gutis_markets[col_mes], errors='coerce').fillna(0)

cards_ataque_html, total_amenazas, num_mercados, mercado_principal_str, producto_ataque_str, share_lider = "", 0, 0, "Sin mercado activo", "N/D", 0.0
prod_gutis_ataque_oficial = "Talerdín" if es_pediatra else "Gastroalivio"

if not rx_gutis_markets.empty:
    mercados_unicos = rx_gutis_markets["MERCADO"].unique()
    num_mercados = len(mercados_unicos)
    mercados_n1 = [m for m in mercados_unicos if obtener_meta_mercado(m)["prioridad"] == 1]
    mercados_n2 = [m for m in mercados_unicos if obtener_meta_mercado(m)["prioridad"] == 2]

    rx_gutis_markets = rx_gutis_markets.sort_values(by=col_mes, ascending=False)
    for m in (mercados_n1 if mercados_n1 else mercados_n2):
        df_m = rx_gutis_markets[rx_gutis_markets["MERCADO"] == m].sort_values(by=col_mes, ascending=False)
        meta = obtener_meta_mercado(m)
        prod_gutis_esperado = meta["producto"]
        
        lider = df_m.iloc[0]
        lider_nombre, lider_share, lider_es_gutis = str(lider["NOMBRE_PRODUCTO"]).strip(), lider[col_mes] * 100, lider["Es_Gutis"]

        if mercado_principal_str == "Sin mercado activo" and lider_share > 0:
            mercado_principal_str, producto_ataque_str, prod_gutis_ataque_oficial, share_lider = m, lider_nombre, prod_gutis_esperado, lider_share

        if lider_share > 0:
            if not lider_es_gutis:
                total_amenazas += 1
                cards_ataque_html += f"""<div style="background: #ffffff; border: 1px solid #fecdd3; border-top: 4px solid #e11d48; border-radius: 8px; padding: 12px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); min-width: 220px; flex: 1 1 calc(25% - 15px);"><div style="font-size: 0.75rem; font-weight: 800; color: #9f1239; text-transform: uppercase; margin-bottom: 4px;">{m.replace('MR ', '')}</div><div style="font-size: 0.85rem; color: #64748b; margin-bottom: 6px;">Prescribe: <b style="color: #0f172a;">{lider_nombre[:20]}</b></div><div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px dashed #e2e8f0; padding-top: 6px;"><span style="background: #ffe4e6; color: #be123c; font-size: 0.75rem; font-weight: 700; padding: 2px 6px; border-radius: 4px;">{lider_share:.1f}% Cuota</span><span style="color: #059669; font-size: 0.8rem; font-weight: 800;">➔ {prod_gutis_esperado}</span></div></div>"""
            else:
                cards_ataque_html += f"""<div style="background: #ffffff; border: 1px solid #a7f3d0; border-top: 4px solid #10b981; border-radius: 8px; padding: 12px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); min-width: 220px; flex: 1 1 calc(25% - 15px);"><div style="font-size: 0.75rem; font-weight: 800; color: #065f46; text-transform: uppercase; margin-bottom: 4px;">{m.replace('MR ', '')}</div><div style="font-size: 0.85rem; color: #047857; margin-bottom: 6px;">Dominio: <b>{prod_gutis_esperado}</b></div><div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px dashed #e2e8f0; padding-top: 6px;"><span style="background: #d1fae5; color: #047857; font-size: 0.75rem; font-weight: 700; padding: 2px 6px; border-radius: 4px;">{lider_share:.1f}% Fidelidad</span><span style="color: #047857; font-size: 0.8rem; font-weight: 800;">Blindar</span></div></div>"""

tendencia_global = "peligro" if total_amenazas > 0 else "éxito"

# DATOS DE VENTAS Y CRUCE TÁCTICO
df_farmacias_totales = pd.DataFrame()
total_sellout_zona, total_puntos_venta, ventas_producto_lider_zona = 0.0, 0, 0.0
top_farmacias_str, top_farmacias_lista, escenario_tactico = "Farmacias clave de la zona", [], ""

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
        if col_prod_ventas and producto_ataque_str != "N/D":
            palabra_clave = prod_gutis_ataque_oficial.upper().split()[0]
            ventas_producto_lider_zona = ventas_zona_global[ventas_zona_global[col_prod_ventas].astype(str).str.upper().str.contains(palabra_clave, na=False)]["Monto Real"].sum()

            if es_gutis(producto_ataque_str):
                escenario_tactico = f"**ESCENARIO A (ALERTA FUGA):** Prescribe {producto_ataque_str} con {share_lider:.1f}% de fidelidad, pero el sell-out es bajo (${ventas_producto_lider_zona:.2f}). Evidencia riesgo en mostrador." if ventas_producto_lider_zona < 150 else f"**ESCENARIO C (DOMINIO):** Fidelidad alta en {producto_ataque_str} respaldada por sell-out sano."
            else: escenario_tactico = f"**ESCENARIO B (CONQUISTA):** Prescribe a la competencia ({producto_ataque_str}) al {share_lider:.1f}%. Contraataque clínico con {prod_gutis_ataque_oficial}."

# LEER MEMORIA CRM
historial_crm = "No hay acuerdos registrados previamente."
if os.path.exists(ARCHIVO_BITACORA):
    try:
        df_hist_full = pd.read_excel(ARCHIVO_BITACORA)
        df_hist_med = df_hist_full[df_hist_full["Médico"].astype(str) == medico_sel].sort_values(by="Fecha", ascending=False)
        if not df_hist_med.empty:
            historial_crm = f"({str(df_hist_med.iloc[0]['Fecha'])[:10]}) {df_hist_med.iloc[0]['Compromiso']}"
    except: pass

# --- FUNCIÓN DEFINITIVA (RADAR AUTOMÁTICO DE MODELOS ACTUALIZADO) ---
def llamar_gemini(prompt_text, max_tok=4096, json_mode=False, audio_bytes=None):
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key:
        return "⚠️ Error: Clave API no encontrada en los Secrets de Streamlit."

    parts = [{"text": prompt_text}]
    if audio_bytes is not None:
        try:
            audio_b64 = base64.b64encode(audio_bytes.read()).decode('utf-8')
            parts.append({"inlineData": {"mimeType": "audio/wav", "data": audio_b64}})
        except Exception as e:
            return f"Error procesando audio: {e}"

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "maxOutputTokens": max_tok,
            "temperature": 0.2
        }
    }
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }

    # Modelos principales actualizados (usando los que están activos ahora)
    modelos_principales = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
    ultimo_detalle = ""

    # 1. RADAR: Preguntamos a Google qué modelos existen y están habilitados para tu clave hoy
    url_lista = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        r_list = requests.get(url_lista, timeout=15)
        if r_list.status_code == 200:
            todos_modelos = r_list.json().get('models', [])
            compatibles = [
                m['name'].replace('models/', '') 
                for m in todos_modelos 
                if 'generateContent' in m.get('supportedGenerationMethods', [])
            ]
            
            if not compatibles:
                return "⚠️ Tu clave es válida pero no tiene modelos de generación de texto habilitados."
            
            # Seleccionamos el mejor disponible automáticamente, dando prioridad a gemini-3.8-flash o gemini-3.5-flash-lite
            modelo_ideal = compatibles[0]
            for m in compatibles:
                if m in modelos_principales:
                    modelo_ideal = m
                    break

            # 2. LLAMADA: Usamos el modelo exacto que el radar confirmó que existe
            url_post = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo_ideal}:generateContent?key={api_key}"
            res = requests.post(url_post, headers=headers, json=payload, timeout=25)
            
            if res.status_code == 200:
                return res.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                return f"⚠️ Error con el modelo confirmado ({modelo_ideal}): HTTP {res.status_code} - {res.text[:100]}"
        else:
            return f"⚠️ Error de red al listar modelos: HTTP {r_list.status_code} - {r_list.text[:100]}"
            
    except Exception as e:
        return f"⚠️ Error interno del código: {str(e)}"

# --- TARJETAS KPI ---
col1, col2, col3 = st.columns(3)
with col1: st.markdown(f"<div class='metric-card'><div class='metric-title'>Médico y Zona</div><div class='metric-value' style='font-size:1.35rem;'>{medico_sel}</div><div style='color: #64748b; font-weight:600;'>{especialidad} | Cat: {categoria} | {ciudad}</div></div>", unsafe_allow_html=True)
with col2: st.markdown(f"<div class='metric-card'><div class='metric-title'>Mercado Clave ({mercado_principal_str})</div><div class='metric-value' style='font-size:1.35rem;'>{producto_ataque_str[:18]}</div><div style='color: #64748b; font-weight:600;'>Cuota: {share_lider:.1f}% ({'🟢 Gutis' if es_gutis(producto_ataque_str) else '🔴 Competencia'})</div></div>", unsafe_allow_html=True)
with col3: st.markdown(f"<div class='metric-card'><div class='metric-title'>Sell-Out Territorio ({total_puntos_venta} Sucursales)</div><div class='metric-value'>${total_sellout_zona:,.2f}</div><div style='color: #0284c7; font-weight:600;'>Disponibilidad en {ciudad}</div></div>", unsafe_allow_html=True)

if not rx_gutis_markets.empty and cards_ataque_html:
    color_f, color_b, color_t, badge = ("#fff1f2", "#e11d48", "#be123c", f"{total_amenazas} Oportunidades Clave") if tendencia_global == "peligro" else ("#ecfdf5", "#10b981", "#047857", "Dominio Total")
    html_completo = f"""<div style="background-color: {color_f}; border-left: 6px solid {color_b}; padding: 18px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.04);"><div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;"><div style="color: {color_t}; font-weight: 800; font-size: 1.1rem; display: flex; align-items: center; gap: 8px;"><span>🧠</span> LECTURA ESTRATÉGICA COMERCIAL</div><span style="background: #ffffff; color: {color_t}; font-size: 0.8rem; font-weight: 700; padding: 4px 10px; border-radius: 20px; border: 1px solid {color_b};">{badge} | {num_mercados} Mercados</span></div><p style="color: #475569; font-size: 0.95rem; margin: 0 0 14px 0;">Enfoca tu abordaje en desplazar a los siguientes líderes activos:</p><div style="display: flex; flex-wrap: wrap; gap: 12px;">{cards_ataque_html}</div></div>"""
    st.components.v1.html(html_completo, height=220, scrolling=True)

# --- PESTAÑAS PRINCIPALES ---
tab_estrategia, tab_perfil360, tab_rx, tab_sellout, tab_bitacora, tab_proyeccion, tab_onepager, tab_ruta = st.tabs([
    "⚡ Fase 1: Copiloto", "📋 Perfil 360°", "📊 Fase 2: Cuotas", "🏪 Fase 3: Sell-Out", "🎙️ CRM IA", "📈 Fase 5: Simulador", "📱 Ficha Rápida", "📍 Ruta"
])

# --- FASE 1: COPILOTO TVP Y PITCH PASILLO ---
with tab_estrategia:
    col_izq_ia, col_der_ia = st.columns([1, 1.2])
    with col_izq_ia:
        st.markdown("### ⚡ Estrategia TVP Automática")
        
        if st.button("🚨 MODO PASILLO (30 Segundos)", type="primary", use_container_width=True):
            with st.spinner("Generando argumento de alto impacto..."):
                prompt_pasillo = f"""{REGLAS_FARMA}
                Genera UN PITCH DE ASCENSOR de máximo 2 oraciones (30 segundos) para el doctor {medico_sel}.
                Él receta {producto_ataque_str}, tu misión es que cambie a {prod_gutis_ataque_oficial}. 
                {contexto_rapport_str}
                El pitch debe tener un gancho clínico galénico destructivo REAL contra su marca y un cierre directo. Escríbelo en tono conversacional como si caminaras a su lado."""
                st.session_state.pasillo_result = llamar_gemini(prompt_pasillo)
        
        if st.session_state.pasillo_result:
            st.markdown(f"<div class='pasillo-card'>🏃‍♂️ {st.session_state.pasillo_result}</div>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

        if st.button("🚀 Generar TVP Completo (6 Pasos)", use_container_width=True):
            with st.spinner("Analizando matriz de combate..."):
                prompt_tvp = f"""{REGLAS_FARMA}
                Actúa como estratega comercial EXCLUSIVO de GUTIS para Erick Calderón. 
                Elabora el TVP para {medico_sel}. ESPECIALIDAD: {especialidad}. ZONA: {ciudad}.
                DIAGNÓSTICO: {escenario_tactico}. TOP FARMACIAS: {top_farmacias_str}. CRM PREVIO: {historial_crm}.
                Ataca a {producto_ataque_str} para ganar con {prod_gutis_ataque_oficial}.
                {contexto_rapport_str}
                
                REGLAS OBLIGATORIAS:
                - En el Paso 2 (Apertura y Sondeo), utiliza los datos de perfil 360° (hobby, deporte o cumpleaños si existen) para generar un rapport natural antes del tema médico.
                - Adapta la profundidad del Paso 3 según su estilo de visita preferido.
                
                FORMATO OBLIGATORIO:
                ### 1. 🎯 Pre-Visita y Objetivo
                ### 2. 🚪 Apertura y Sondeo (Rapport Personal + CRM)
                ### 3. 💡 Apoyo / Storytelling Clínico (Galénico)
                ### 4. 🛡️ Manejo de Objeciones
                ### 5. 🤝 Cierre de Ventas
                ### 6. 📅 Próxima Visita y Agenda"""
                st.session_state.tvp_result = llamar_gemini(prompt_tvp)
        
        if st.session_state.tvp_result: 
            st.success("Plan detallado generado:")
            st.markdown(st.session_state.tvp_result)

    with col_der_ia:
        st.markdown("### 🎭 Simulador de Objeciones")
        st.info(f"La IA actuará como el **{medico_sel}**, defendiendo a **{producto_ataque_str[:15]}**.")
        chat_container = st.container(height=350)
        for msg in st.session_state.chat_history:
            with chat_container.chat_message(msg["role"]): st.write(msg["content"])
        if prompt_chat := st.chat_input("Escribe tu argumento para convencer al médico..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt_chat})
            with chat_container.chat_message("user"): st.write(prompt_chat)
            with st.spinner("El doctor está pensando..."):
                respuesta_doc = llamar_gemini(f"{REGLAS_FARMA}\nEres el médico {medico_sel}, especialista en {especialidad}. Tu producto es {producto_ataque_str}. Erick quiere cambiarte a {prod_gutis_ataque_oficial}. Pon una objeción realista en 1 párrafo. Mensaje de Erick: {prompt_chat}")
            st.session_state.chat_history.append({"role": "assistant", "content": respuesta_doc})
            st.rerun()

# --- PESTAÑA: PERFIL 360° OMNICANAL ---
with tab_perfil360:
    st.markdown(f"### 📋 Perfilamiento Estratégico 360°: {medico_sel}")
    st.caption("Captura de datos de contacto profesional, preferencias de visita y rapport personal.")
    
    with st.form("form_perfil_360"):
        st.markdown("#### 1. Identificación y Acreditación Profesional")
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            val_minsa = st.text_input("Código MINSA:", value=str(perfil_360_actual.get("MINSA", "")) if str(perfil_360_actual.get("MINSA", "")) != "nan" else "")
            val_cel = st.text_input("Celular / WhatsApp Profesional:", value=str(perfil_360_actual.get("Celular", "")) if str(perfil_360_actual.get("Celular", "")) != "nan" else "")
        with col_p2:
            val_correo = st.text_input("Correo Electrónico:", value=str(perfil_360_actual.get("Correo", "")) if str(perfil_360_actual.get("Correo", "")) != "nan" else "")
            val_clinica = st.text_input("Clínica / Hospital Principal:", value=str(perfil_360_actual.get("Clinica", "")) if str(perfil_360_actual.get("Clinica", "")) != "nan" else "")
        with col_p3:
            opc_horario = ["Mañanas", "Tardes", "Mediodía", "Indiferente"]
            idx_hor = opc_horario.index(perfil_360_actual.get("Horario_Contacto", "Mañanas")) if perfil_360_actual.get("Horario_Contacto") in opc_horario else 0
            val_horario = st.selectbox("Mejor momento para contacto:", opc_horario, index=idx_hor)

        st.divider()
        st.markdown("#### 2. Seguimiento Digital y Formatos Científicos")
        col_p4, col_p5 = st.columns(2)
        with col_p4:
            opc_canal = ["WhatsApp", "Correo Electrónico", "Ambos (WhatsApp + Correo)"]
            idx_can = opc_canal.index(perfil_360_actual.get("Canal_Digital", "WhatsApp")) if perfil_360_actual.get("Canal_Digital") in opc_canal else 0
            val_canal = st.selectbox("Canal preferido para respaldo científico:", opc_canal, index=idx_can)

            opc_formato = ["Infografías / Perlas de dosificación rápida", "Estudios clínicos PubMed completos", "Fichas técnicas y calculadoras de dosis", "Invitaciones a simposios / webinars"]
            idx_form = opc_formato.index(perfil_360_actual.get("Formato_Cientifico", opc_formato[0])) if perfil_360_actual.get("Formato_Cientifico") in opc_formato else 0
            val_formato = st.selectbox("Formato científico más valorado:", opc_formato, index=idx_form)
        with col_p5:
            opc_frec = ["Quincenal", "Mensual", "Solo ante lanzamientos o nueva evidencia"]
            idx_frec = opc_frec.index(perfil_360_actual.get("Frecuencia_Digital", "Mensual")) if perfil_360_actual.get("Frecuencia_Digital") in opc_frec else 1
            val_frecuencia = st.selectbox("Frecuencia de contacto digital:", opc_frec, index=idx_frec)

        st.divider()
        st.markdown("#### 3. Modalidad de Visita Presencial y Rapport Personal")
        col_p6, col_p7 = st.columns(2)
        with col_p6:
            opc_visita = [
                "Ultra-ejecutiva (2-3 min, muestras y cierre)",
                "Discusión científica profunda (farmacología y tablas)",
                "Basada en perfiles de pacientes de su día a día"
            ]
            idx_vis = opc_visita.index(perfil_360_actual.get("Estilo_Visita", opc_visita[0])) if perfil_360_actual.get("Estilo_Visita") in opc_visita else 0
            val_estilo_visita = st.selectbox("Dinámica preferida en visita presencial:", opc_visita, index=idx_vis)

            val_cumple = st.text_input("Fecha de Cumpleaños (ej. 15 de Mayo):", value=str(perfil_360_actual.get("Cumpleaños", "")) if str(perfil_360_actual.get("Cumpleaños", "")) != "nan" else "")
        with col_p7:
            val_deporte = st.text_input("Deporte / Equipo preferido:", value=str(perfil_360_actual.get("Deporte", "")) if str(perfil_360_actual.get("Deporte", "")) != "nan" else "")
            val_hobby = st.text_input("Hobby / Afición / Tema de conversación casual:", value=str(perfil_360_actual.get("Hobby", "")) if str(perfil_360_actual.get("Hobby", "")) != "nan" else "")

        btn_guardar_perfil = st.form_submit_button("💾 Guardar Perfil 360° en Base de Datos", use_container_width=True, type="primary")
        
        if btn_guardar_perfil:
            registro_nuevo = {
                "Médico": medico_sel,
                "MINSA": val_minsa.strip(),
                "Celular": val_cel.strip(),
                "Correo": val_correo.strip(),
                "Clinica": val_clinica.strip(),
                "Horario_Contacto": val_horario,
                "Canal_Digital": val_canal,
                "Formato_Cientifico": val_formato,
                "Frecuencia_Digital": val_frecuencia,
                "Estilo_Visita": val_estilo_visita,
                "Cumpleaños": val_cumple.strip(),
                "Deporte": val_deporte.strip(),
                "Hobby": val_hobby.strip(),
                "Ultima_Actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            
            if os.path.exists(ARCHIVO_PERFIL_360):
                df_existente = pd.read_excel(ARCHIVO_PERFIL_360)
                df_existente = df_existente[df_existente["Médico"].astype(str) != medico_sel]
                df_guardar = pd.concat([df_existente, pd.DataFrame([registro_nuevo])], ignore_index=True)
            else:
                df_guardar = pd.DataFrame([registro_nuevo])
                
            df_guardar.to_excel(ARCHIVO_PERFIL_360, index=False)
            st.success("✅ ¡Perfil 360° guardado exitosamente! El Copiloto ya lo usará en sus próximos planes.")
            st.rerun()

with tab_rx:
    if not rx_gutis_markets.empty:
        share_cols = [c for c in ["%MS-YTD", "%MS-TRIM", "%MS-MES"] if c in rx_gutis_markets.columns]
        df_rx_view = rx_gutis_markets[["NOMBRE_PRODUCTO", "MERCADO"] + share_cols].copy()
        df_rx_view["LABORATORIO"] = df_rx_view["NOMBRE_PRODUCTO"].apply(lambda x: "GUTIS" if es_gutis(x) else "COMPETENCIA")
        for c in share_cols: df_rx_view[c] = pd.to_numeric(df_rx_view[c], errors='coerce').fillna(0) * 100
        if share_cols: df_rx_view = df_rx_view.sort_values(by=share_cols[-1], ascending=False)
        mercado_activo = st.radio("🎯 Seleccionar Mercado:", ["TODOS LOS MERCADOS GUTIS"] + df_rx_view["MERCADO"].value_counts().index.tolist(), horizontal=True) if not hasattr(st, "pills") else st.pills("🎯 Seleccionar Mercado:", ["TODOS LOS MERCADOS GUTIS"] + df_rx_view["MERCADO"].value_counts().index.tolist(), default="TODOS LOS MERCADOS GUTIS")
        if mercado_activo != "TODOS LOS MERCADOS GUTIS": df_rx_view = df_rx_view[df_rx_view["MERCADO"] == mercado_activo]
        st.dataframe(df_rx_view, column_config={c: st.column_config.NumberColumn(c, format="%.1f%%") for c in share_cols}, height=430, use_container_width=True, hide_index=True)
    else: st.info("Sin prescripciones en mercados Gutis.")

with tab_sellout:
    st.markdown("### 🏪 Inteligencia de Sell-Out Multi-Trimestre")
    trim_activo = st.radio("📅 Analizar Periodo:", ["Acumulado", "Q1", "Q2", "Q3", "Q4"], horizontal=True) if not hasattr(st, "pills") else st.pills("📅 Analizar Periodo:", ["Acumulado", "Q1", "Q2", "Q3", "Q4"], default="Acumulado")
    if not df_ventas.empty and "DESCRIPCION_RUTA" in df_ventas.columns:
        ventas_zona = df_ventas[(df_ventas["DESCRIPCION_RUTA"].str.contains(ciudad, na=False)) & (df_ventas["Trimestre"] == trim_activo)].copy() if trim_activo != "Acumulado" and "Trimestre" in df_ventas.columns else df_ventas[df_ventas["DESCRIPCION_RUTA"].str.contains(ciudad, na=False)].copy()
        if not ventas_zona.empty:
            ventas_zona = ventas_zona[~ventas_zona["NOMBRE_CLIENTE_1"].str.upper().isin(["TOTAL", "NAN", ""])]
            df_farms = ventas_zona.groupby("NOMBRE_CLIENTE_1")["Monto Real"].sum().reset_index().sort_values(by="Monto Real", ascending=False)
            col_prod_ventas = "VM4" if "VM4" in ventas_zona.columns else next((c for c in ventas_zona.columns if c.upper() in ["NOMBRE_PRODUCTO", "PRODUCTO"]), None)
            for idx, row in df_farms.head(10).iterrows():
                with st.expander(f"🏢 {row['NOMBRE_CLIENTE_1']} | Facturación: ${row['Monto Real']:,.2f}"):
                    if col_prod_ventas:
                        df_cliente = ventas_zona[ventas_zona["NOMBRE_CLIENTE_1"] == row['NOMBRE_CLIENTE_1']]
                        df_prod = df_cliente.groupby(col_prod_ventas).agg({c: "sum" for c in ["Monto Real", "Und Real", "Monto Cuota"] if c in df_cliente.columns}).reset_index()
                        if "Monto Cuota" in df_prod.columns: df_prod["% Alcance"] = (df_prod["Monto Real"] / df_prod["Monto Cuota"].replace(0, np.nan)).fillna(0) * 100
                        st.dataframe(df_prod.sort_values(by="Monto Real", ascending=False).rename(columns={col_prod_ventas: "Producto"}), hide_index=True, use_container_width=True)
        else: st.info("Sin ventas en el periodo.")
    else: st.error("Sin datos de ventas.")

# --- CRM POR VOZ Y TEXTO ---
with tab_bitacora:
    st.markdown("### 🎙️ CRM por Voz Inteligente")
    col_b1, col_b2 = st.columns([1.5, 1])
    
    with col_b1:
        audio_grabado = st.audio_input("🎤 Toca para grabar tu acuerdo:") if hasattr(st, "audio_input") else None
        compromiso_texto = st.text_area("O escribe aquí de forma rápida:", height=68)
        
    with col_b2:
        st.write("")
        st.write("")
        if st.button("Procesar y Guardar 🚀", use_container_width=True, type="primary"):
            if audio_grabado is not None or compromiso_texto.strip():
                with st.spinner("IA procesando información..."):
                    prompt_crm = """Transcribe el audio (si lo hay) y extrae la información de la visita médica.
                    Devuelve UNICAMENTE un JSON válido con estas claves:
                    {"producto": "Producto mencionado", "volumen": "Cantidad o recetas", "seguimiento": "Fecha de retorno", "resumen": "Resumen ejecutivo limpio"}"""
                    
                    if audio_grabado is not None:
                        res_json = llamar_gemini(prompt_crm, json_mode=True, audio_bytes=audio_grabado)
                    else:
                        res_json = llamar_gemini(prompt_crm + f"\n\nTEXTO: {compromiso_texto}", json_mode=True)
                        
                    try:
                        datos_extraidos = json.loads(res_json)
                        texto_guardar = f"{datos_extraidos.get('producto','N/D')} | {datos_extraidos.get('volumen','N/D')} | {datos_extraidos.get('resumen', 'Acuerdo guardado')}"
                    except:
                        texto_guardar = compromiso_texto.strip() if compromiso_texto else "Audio procesado sin formato."
                        
                    n = pd.DataFrame([{"Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "Médico": medico_sel, "Estatus": tendencia_global.upper(), "Compromiso": texto_guardar}])
                    df_g = pd.concat([pd.read_excel(ARCHIVO_BITACORA), n], ignore_index=True) if os.path.exists(ARCHIVO_BITACORA) else n
                    df_g.to_excel(ARCHIVO_BITACORA, index=False)
                    st.success("¡Acuerdo Guardado Exitosamente!")
            else: st.warning("Graba un audio o escribe una nota primero.")
            
    if os.path.exists(ARCHIVO_BITACORA):
        df_h = pd.read_excel(ARCHIVO_BITACORA)
        if not df_h.empty and medico_sel in df_h["Médico"].values:
            st.dataframe(df_h[df_h["Médico"] == medico_sel][["Fecha", "Estatus", "Compromiso"]].sort_values(by="Fecha", ascending=False), use_container_width=True, hide_index=True)

with tab_proyeccion:
    st.markdown("### 📈 Predictivo de Cierre de Cuota Trimestral")
    if not df_ventas.empty and "Monto Cuota" in df_ventas.columns:
        ventas_zona = df_ventas[df_ventas["DESCRIPCION_RUTA"].str.contains(ciudad, na=False)].copy()
        col_prod_ventas = "VM4" if "VM4" in ventas_zona.columns else next((c for c in ventas_zona.columns if c.upper() in ["NOMBRE_PRODUCTO", "PRODUCTO"]), None)
        if col_prod_ventas and not ventas_zona.empty:
            dias_totales, dias_transcurridos = 90, st.slider("🗓️ Días transcurridos del trimestre:", 1, 90, 45)
            df_grp = ventas_zona.groupby(col_prod_ventas).agg({"Monto Real": "sum", "Monto Cuota": "sum"}).reset_index()
            df_grp = df_grp[df_grp["Monto Cuota"] > 0].copy()
            df_grp["% Alcance Actual"] = (df_grp["Monto Real"] / df_grp["Monto Cuota"]) * 100
            df_grp["Venta Diaria Promedio"] = df_grp["Monto Real"] / dias_transcurridos
            df_grp["Proyección Cierre ($)"] = df_grp["Venta Diaria Promedio"] * dias_totales
            df_grp["% Proyectado Cierre"] = (df_grp["Proyección Cierre ($)"] / df_grp["Monto Cuota"]) * 100
            df_grp["Brecha para 100% ($)"] = np.where(df_grp["Proyección Cierre ($)"] < df_grp["Monto Cuota"], df_grp["Monto Cuota"] - df_grp["Proyección Cierre ($)"], 0)
            df_mostrar = df_grp.sort_values(by="Monto Cuota", ascending=False).head(8)[[col_prod_ventas, "Monto Cuota", "Monto Real", "% Alcance Actual", "Proyección Cierre ($)", "% Proyectado Cierre", "Brecha para 100% ($)"]].rename(columns={col_prod_ventas: "Producto Oficial Gutis"})
            st.dataframe(df_mostrar, column_config={"Monto Cuota": st.column_config.NumberColumn(format="$ %.2f"), "Monto Real": st.column_config.NumberColumn(format="$ %.2f"), "% Alcance Actual": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100), "Proyección Cierre ($)": st.column_config.NumberColumn(format="$ %.2f"), "% Proyectado Cierre": st.column_config.NumberColumn(format="%.1f%%"), "Brecha para 100% ($)": st.column_config.NumberColumn("Falta para el Bono ($)", format="$ %.2f")}, hide_index=True, use_container_width=True)
            st.info("💡 Fíjate en **'Falta para el Bono ($)'**. Eso es lo que necesitas facturar antes que cierre el mes.")
    else: st.warning("No hay datos de cuota o ventas para simular proyección.")

with tab_onepager:
    st.markdown(f"## 📱 Ficha Táctica: {medico_sel}")
    
    if perfil_360_actual:
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            st.caption(f"📞 Contacto: {perfil_360_actual.get('Celular','N/D')} | MINSA: {perfil_360_actual.get('MINSA','N/D')}")
        with c_p2:
            st.caption(f"🎂 Cumpleaños: {perfil_360_actual.get('Cumpleaños','N/D')} | ⚽ Afición: {perfil_360_actual.get('Deporte','N/D')}")
    
    texto_wa = f"🎯 *FICHA TÁCTICA: {medico_sel}*\n📍 Zona: {ciudad} | Esp: {especialidad}\n⚔️ *OBJETIVO:* Desplazar a {producto_ataque_str} con {prod_gutis_ataque_oficial}\n📝 *CRM Previo:* {historial_crm}\n🏪 *Top Farmacias:* {top_farmacias_str}\n"
    c_w1, c_w2 = st.columns(2)
    with c_w1: st.link_button("📲 Enviar a WhatsApp", f"https://wa.me/?text={quote(texto_wa)}", type="primary", use_container_width=True)
    with c_w2: st.code(texto_wa, language="markdown")

with tab_ruta:
    st.markdown(f"### 📍 Hoja de Ruta e Itinerario: {ciudad}")
    if ciudad_filtro != "TODAS":
        medicos_ciudad = df_filtrado["Médico"].unique()
        lista_gira_completa = []
        for med_gira in medicos_ciudad:
            info_m = df_filtrado[df_filtrado["Médico"] == med_gira].iloc[0]
            cat_num = pd.to_numeric(info_m.get("CATEGORIA", 3), errors='coerce')
            lista_gira_completa.append({"Médico": med_gira, "Especialidad": info_m.get("Especialidad", "N/D"), "Cat": int(cat_num) if not pd.isna(cat_num) else 3, "Productos a Abordar": "Talerdín, Biotos, Ventilar" if "PEDIAT" in str(info_m.get("Especialidad", "")).upper() else "Gastroalivio, Talerdín, Valerpan"})
        if lista_gira_completa:
            df_gira = pd.DataFrame(lista_gira_completa).sort_values(by="Cat", ascending=True).reset_index(drop=True)
            df_gira.index = [f"Visita {i+1}" for i in range(len(df_gira))]
            st.dataframe(df_gira.reset_index().rename(columns={"index": "Orden", "Médico": "Médico (Objetivo)"}), use_container_width=True, hide_index=True)
            st.divider()
            st.markdown("#### 🧭 Asesor Táctico de Ruta")
            for chat_g in st.session_state.gira_chat_history:
                with st.chat_message(chat_g["role"]): st.write(chat_g["content"])
            if pregunta_gira := st.chat_input("¿A qué médico voy ahora?"):
                st.session_state.gira_chat_history.append({"role": "user", "content": pregunta_gira})
                with st.chat_message("user"): st.write(pregunta_gira)
                with st.spinner("Calculando recomendación..."):
                    respuesta_asesor = llamar_gemini(f"Eres el supervisor de Gutis en {ciudad}. Responde conciso a la pregunta de ruta: {pregunta_gira}")
                st.session_state.gira_chat_history.append({"role": "assistant", "content": respuesta_asesor})
                st.rerun()
