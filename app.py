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
    page_title="Gutis BI | Terminal Ejecutiva TVP",
    page_icon="⚜️",
    layout="wide",
    initial_sidebar_state="expanded"
)

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
ARCHIVO_BITACORA = "HISTORIAL_VISITAS.xlsx"
ARCHIVO_PERFIL_360 = "PERFIL_360_MEDICOS.xlsx"

def normalizar_txt(texto):
    if pd.isna(texto): return ""
    t = str(texto).strip().upper()
    return ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')

# --- CONVERSOR NATIVO DE TABLAS A MARKDOWN (INMUNE A FALTA DE 'TABULATE') ---
def df_a_markdown_nativo(df):
    if df is None or df.empty:
        return "_Sin registros disponibles._"
    cols = [str(c) for c in df.columns]
    encabezado = "| " + " | ".join(cols) + " |"
    separador = "| " + " | ".join(["---"] * len(cols)) + " |"
    filas = [encabezado, separador]
    for _, row in df.iterrows():
        valores = [str(val).replace("|", "/") for val in row.values]
        filas.append("| " + " | ".join(valores) + " |")
    return "\n".join(filas)

# --- MATRIZ DE MERCADOS (PRIORIDAD 1, 2 Y 3 CON ATRIBUTOS CLÍNICOS Y LOVE BRANDS) ---
MERCADOS_PRIORITARIOS = {
    "MR TALERDIN": {
        "producto": "Talerdín", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Core)",
        "keywords": ["TALERDIN", "CETIRIZINA", "CETRILER", "ALERCET", "DEGRALER"],
        "paciente_meta": "Pacientes pediátricos y adultos con rinitis alérgica o urticaria que requieren alivio rápido sin sedación ni irritación.",
        "caracteristica": "Cetirizina 100% libre de alcohol, libre de azúcar y con gotero de dosificación exacta pediátrica.",
        "beneficio": "Garantiza apego total al tratamiento pediátrico sin rechazo por sabor ni efectos adversos por excipientes alcohólicos.",
        "love_brand": "Tranquilidad nocturna para el niño y los padres desde la primera toma, protegiendo su desarrollo diario."
    },
    "MR BIOTOS": {
        "producto": "Biotos Inmune", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Core)",
        "keywords": ["BIOTOS", "HEDERA", "PELARGONIUM", "ABRILAR", "TUSILEXIL"],
        "paciente_meta": "Pacientes desde los 2 años y adultos con IVRS virales, tos productiva y dificultad para manejar secreciones.",
        "caracteristica": "Combinación fitofarmacológica dual única de Hedera helix + Pelargonium sidoides.",
        "beneficio": "Cuádruple acción (mucolítica, broncodilatadora, expectorante e inmunomoduladora) que acorta el cuadro viral y previene sobreinfección.",
        "love_brand": "Devolver la respiración libre a las familias con evidencia clínica fitoterapéutica."
    },
    "MR CLEMBROXIL": {
        "producto": "Clembroxil Compuesto", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Core)",
        "keywords": ["CLEMBROXIL", "CLENBUTEROL", "AMBROXOL", "MUCOSOLVAN"],
        "paciente_meta": "Pacientes con broncoespasmo, bronquitis aguda o crónica y retención severa de moco en vías respiratorias.",
        "caracteristica": "Sinergia exacta de Ambroxol (mucolítico mucocinético) + Clenbuterol (broncodilatador selectivo B2).",
        "beneficio": "Despeja las vías aéreas dilatando el bronquio mientras fluidifica el moco espeso, facilitando la ventilación inmediata.",
        "love_brand": "Respaldo respiratorio contundente cuando el paciente siente que le falta el aire."
    },
    "MR MOMETZONA": {
        "producto": "Mometzona", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Core)",
        "keywords": ["MOMETZONA", "MOMETASONA", "NASONEX", "GAMMAFLUX"],
        "paciente_meta": "Pacientes con rinitis alérgica estacional o perenne, congestión nasal persistente o pólipos nasales.",
        "caracteristica": "Furoato de Mometasona en suspensión acuosa nasal 100% libre de alcohol con válvula de micro-nebulización.",
        "beneficio": "Potente control antiinflamatorio local sin resecar ni irritar la mucosa nasal y con biodisponibilidad sistémica <0.1%.",
        "love_brand": "Descongestionar y devolver el descanso reparador sin ardor nasal."
    },
    "MR VENTILAR": {
        "producto": "Ventilar", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Core)",
        "keywords": ["VENTILAR", "MONTELUKAST", "SINGULAIR", "AIRUM", "SUVIAR"],
        "paciente_meta": "Pacientes pediátricos y adultos con asma persistente, broncoespasmo inducido por ejercicio o rinitis alérgica.",
        "caracteristica": "Montelukast sódico de alta pureza galénica en tabletas masticables pediátricas y recubiertas de una toma diaria.",
        "beneficio": "Bloqueo selectivo de leucotrienos que previene crisis respiratorias y reduce el uso de corticoides de rescate.",
        "love_brand": "Libertad para que el paciente juegue y respire sin temor a una crisis nocturna."
    },
    "MR GASTROALIVIO": {
        "producto": "Gastroalivio", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Core)",
        "keywords": ["GASTROALIVIO", "ESOMEPRAZOL", "CARBUM", "NEXIUM"],
        "paciente_meta": "Pacientes adultos con ERGE, esofagitis erosiva, úlcera péptica o gastropatía por AINEs.",
        "caracteristica": "Esomeprazol con tecnología avanzada de micropellets gastrorresistentes.",
        "beneficio": "Mayor superficie de absorción intestinal, ofreciendo inicio de acción más rápido y supresión ácida sostenida por 24 horas.",
        "love_brand": "Innovación galénica que protege el estómago del paciente desde la primera cápsula."
    },
    "MR DALIVIO": {
        "producto": "Dalivio", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Core)",
        "keywords": ["DALIVIO", "DALIVIUM", "DEXKETOPROFENO", "ENANTYUM", "STADIUM", "CETIX"],
        "paciente_meta": "Pacientes con dolor agudo de moderado a severo (musculoesquelético, odontalgia, dismenorrea o postquirúrgico).",
        "caracteristica": "Dexketoprofeno trometamol (enantiómero activo S+) de rápida absorción disponible en sobre bebible y tabletas.",
        "beneficio": "Alivio analgésico explosivo desde los primeros 10-15 minutos con mitad de carga metabólica y menor riesgo gástrico.",
        "love_brand": "Aliviar al paciente del dolor agudo en solo 10 minutos para que recupere su día."
    },
    "MR VALERPAN": {
        "producto": "Valerpan", "peso": 2, "prioridad": 2, "categoria_mercado": "Prioridad 2 (Expansión)",
        "keywords": ["VALERPAN", "BETAMETASONA", "CELESTONE", "DIPROSPAN", "DEXAMETASONA"],
        "paciente_meta": "Pacientes con cuadros inflamatorios agudos, alérgicos severos o patologías osteomusculares que requieren depósito.",
        "caracteristica": "Combinación dual de Betametasona (Fosfato disódico de acción inmediata + Dipropionato de liberación prolongada).",
        "beneficio": "Control rápido de la crisis inflamatoria en las primeras horas y cobertura sostenida que evita recaídas.",
        "love_brand": "Potencia y precisión antiinflamatoria en una sola aplicación segura."
    },
    "MR CONFLEXIL": {
        "producto": "Conflexil", "peso": 2, "prioridad": 2, "categoria_mercado": "Prioridad 2 (Expansión)",
        "keywords": ["CONFLEXIL", "CONRELAX", "TIZANIDINA", "MELOXICAM", "TIOCOLCHICOSIDO"],
        "paciente_meta": "Pacientes activos o mayores con lumbalgia mecánica, contractura muscular aguda o cervicalgia que limita su movilidad.",
        "caracteristica": "Sinergia miorrelajante de acción central medular + potente acción antiinflamatoria y analgésica.",
        "beneficio": "Elimina el espasmo y el dolor recuperando los arcos de movimiento sin producir sedación ni somnolencia diurna.",
        "love_brand": "Reintegrar al paciente a su trabajo y vida diaria sin las ataduras del dolor lumbar."
    },
    "MR RENOVART": {
        "producto": "Renovart Platinum", "peso": 2, "prioridad": 2, "categoria_mercado": "Prioridad 2 (Expansión)",
        "keywords": ["RENOVART", "COLAGENO", "GLUCOSAMINA"],
        "paciente_meta": "Pacientes con desgaste articular, osteoartrosis o deportistas con sobrecarga mecánica articular.",
        "caracteristica": "Colágeno Hidrolizado enzimáticamente en cadenas cortas de aminoácidos de máxima absorción intestinal.",
        "beneficio": "Regenera la matriz del cartílago, mejora la movilidad articular y disminuye el dolor crónico a mediano plazo.",
        "love_brand": "Devolver la vitalidad del movimiento para que la edad o el deporte no detengan al paciente."
    },
    "MR MUPIRAL": {
        "producto": "Mupiral", "peso": 2, "prioridad": 2, "categoria_mercado": "Prioridad 2 (Expansión)",
        "keywords": ["MUPIRAL", "MUPIROCINA", "BACTROBAN"],
        "paciente_meta": "Pacientes con infecciones cutáneas bacterianas primarias o secundarias (impétigo, foliculitis, heridas infectadas).",
        "caracteristica": "Mupirocina tópica al 2% con inhibición específica de síntesis proteica bacteriana.",
        "beneficio": "Erradicación rápida de S. aureus y S. pyogenes sin resistencia cruzada con otros antibióticos.",
        "love_brand": "Seguridad dermatológica confiable que protege la piel de toda la familia."
    },
    "MR BICORPAN": {
        "producto": "Bicorpan", "peso": 2, "prioridad": 2, "categoria_mercado": "Prioridad 2 (Expansión)",
        "keywords": ["BICORPAN"],
        "paciente_meta": "Pacientes con dermatomicosis acompañadas de inflamación y prurito intenso.",
        "caracteristica": "Fórmula tópica combinada antimicótica y antiinflamatoria de alta penetración cutánea.",
        "beneficio": "Corta el prurito y el eritema desde el primer día mientras erradica el hongo causal.",
        "love_brand": "Alivio visible y rápido en infecciones dérmicas complejas."
    },
    "MR FEMGYL": {
        "producto": "Femgyl", "peso": 1, "prioridad": 3, "categoria_mercado": "Prioridad 3 (Complemento)",
        "keywords": ["FEMGYL"],
        "paciente_meta": "Pacientes ginecológicas con infecciones vaginales mixtas.",
        "caracteristica": "Terapia ginecológica de amplio espectro de acción local efectiva.",
        "beneficio": "Resolución clínica integral desde las primeras aplicaciones, restaurando el bienestar íntimo.",
        "love_brand": "Contribución fundamental de Gutis para el cuidado de la salud femenina."
    },
    "MR NORGYLEN": {
        "producto": "Norgylen", "peso": 1, "prioridad": 3, "categoria_mercado": "Prioridad 3 (Complemento)",
        "keywords": ["NORGYLEN"],
        "paciente_meta": "Pacientes en edad reproductiva que requieren planificación familiar hormonal segura.",
        "caracteristica": "Formulación anticonceptiva hormonal balanceada de alta eficacia clínica.",
        "beneficio": "Excelente control del ciclo menstrual con alta seguridad y tolerabilidad.",
        "love_brand": "Confianza y respaldo en cada etapa de la planificación familiar."
    },
    "MR ANSIOLIT": {
        "producto": "Ansiolit", "peso": 1, "prioridad": 3, "categoria_mercado": "Prioridad 3 (Complemento)",
        "keywords": ["ANSIOLIT"],
        "paciente_meta": "Pacientes adultos con trastornos de ansiedad generalizada o insomnio asociado.",
        "caracteristica": "Ansiolítico de perfil farmacocinético predecible y dosificación adaptable.",
        "beneficio": "Control efectivo de los síntomas somáticos y psíquicos de la ansiedad.",
        "love_brand": "Equilibrio emocional y paz mental respaldados por la calidad de Gutis."
    },
    "MR DEPAX": {
        "producto": "Depax", "peso": 1, "prioridad": 3, "categoria_mercado": "Prioridad 3 (Complemento)",
        "keywords": ["DEPAX"],
        "paciente_meta": "Pacientes con trastornos depresivos o de ansiedad que requieren bioequivalencia comprobada.",
        "caracteristica": "Antidepresivo con estudio de Bioequivalencia certificado.",
        "beneficio": "Estabilidad terapéutica continua a un costo accesible para el apego a largo plazo.",
        "love_brand": "Calidad bioequivalente comprobada para acompañar la recuperación emocional."
    },
    "MR FELICITAT": {
        "producto": "Felicitat", "peso": 1, "prioridad": 3, "categoria_mercado": "Prioridad 3 (Complemento)",
        "keywords": ["FELICITAT", "ESCITALOPRAM"],
        "paciente_meta": "Pacientes con depresión mayor o trastorno de ansiedad que buscan mejoría sostenida.",
        "caracteristica": "Escitalopram con interacción dual única en el transportador SERT.",
        "beneficio": "Inhibición más selectiva y eficaz de la recaptación de serotonina.",
        "love_brand": "Ayudar a miles de pacientes en su salud mental para que vuelvan a disfrutar de la vida."
    }
}

PRODUCTOS_GUTIS = [
    "GASTROALIVIO", "TALERDIN", "TALERDÍN", "DALIVIO", "DALIVIUM", "CONFLEXIL", "CONRELAX",
    "VALERPAN", "RENOVART PLATINUM", "BIOTOS", "CLEMBROXIL", "MOMETZONA",
    "VENTILAR", "FEMGYL", "NORGYLEN", "BICORPAN", "MUPIRAL", "ANSIOLIT",
    "DEPAX", "FELICITAT"
]

REGLAS_FARMA = """
REGLAS FARMACOLÓGICAS Y METODOLOGÍA OFICIAL TVP GUTIS (ESTRICTO):
1. CETRILER es CETIRIZINA. CARBUM es ESOMEPRAZOL.
2. TALERDÍN es CETIRIZINA (100% libre de alcohol, gotas exactas pediátricas).
3. GASTROALIVIO es ESOMEPRAZOL (Micropellets gastrorresistentes). PROHIBIDO en Pediatría.
4. VENTILAR es MONTELUKAST SÓDICO. MOMETZONA es FUROATO DE MOMETASONA (sin alcohol).
5. BIOTOS INMUNE es HEDERA HELIX + PELARGONIUM SIDOIDES.
6. METODOLOGÍA TVP GUTIS:
   - Escala de Adopción: 1. No Consciente, 2. Consciente, 3. Prueba (2-10 Pxs o <25% MS), 4. Adopción (25-50% MS), 5. Lealtad (>50% MS).
   - APERTURA: Prohibido nombrar marca; proponer Agenda centrada en el paciente, Valor de la agenda y Confirmar aceptación.
   - DESCUBRIR NECESIDADES: Técnica del Embudo (Circunstancias -> Necesidad -> Necesidad detrás de la Necesidad: Finanzas, Desempeño o Imagen) con Sondeos de Valor Mutuo.
   - APOYO/STORYTELLING: Comprensión + Característica/Beneficio + Love Brands + Confirmación.
   - CIERRE/PUENTE: Resumen + Compromiso bilateral + Puente natural a 2do y 3er producto.
"""

# --- ESTILOS CSS EJECUTIVOS (TICKER + CANVAS 4 CUADRANTES + 3 NÚCLEOS) ---
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
    h1, h2, h3, h4, h5 { color: #0f172a; font-weight: 700; letter-spacing: -0.3px; }
    .ticker-bar { background: #ffffff; border: 1px solid #e2e8f0; border-left: 6px solid #1e3a8a; border-radius: 8px; padding: 12px 18px; margin-bottom: 14px; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.03); }
    .ticker-item { flex: 1 1 200px; border-right: 1px solid #f1f5f9; padding-right: 12px; }
    .ticker-item:last-child { border-right: none; }
    .ticker-label { font-size: 0.68rem; text-transform: uppercase; color: #64748b; font-weight: 800; letter-spacing: 0.7px; }
    .ticker-val { font-size: 1.15rem; font-weight: 800; color: #0f172a; margin-top: 2px; }
    .ticker-sub { font-size: 0.76rem; color: #475569; font-weight: 600; }
    .canvas-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; margin-top: 10px; margin-bottom: 14px; }
    .quad-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 16px; box-shadow: 0 2px 5px rgba(0,0,0,0.02); }
    .quad-title { font-size: 0.76rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 8px; padding-bottom: 5px; border-bottom: 2px solid #f1f5f9; }
    .quad-body { font-size: 0.84rem; color: #1e293b; line-height: 1.45; }
    .elite-banner { background: linear-gradient(90deg, #0f172a 0%, #1e3a8a 100%); color: #f8fafc; padding: 10px 16px; border-radius: 7px; margin-bottom: 12px; border-left: 5px solid #eab308; font-weight: 700; font-size: 0.92rem; }
    .stTabs [data-baseweb="tab-list"] { border-bottom: 2px solid #cbd5e1; gap: 8px; }
    .stTabs [data-baseweb="tab"] { font-size: 0.9rem; font-weight: 800; color: #334155; padding: 11px 20px; border-radius: 8px 8px 0 0; background-color: #e2e8f0; border: none; }
    .stTabs [aria-selected="true"] { color: #ffffff; background-color: #0f172a; box-shadow: inset 0 -3px 0 #38bdf8; }
</style>
""", unsafe_allow_html=True)

# --- CARGA INTELIGENTE DE DATOS ---
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

LISTA_CIUDADES_REALES = sorted([c for c in df_panel["CIUDAD"].dropna().unique() if str(c).strip() not in ["", "NAN"]]) if not df_panel.empty and "CIUDAD" in df_panel.columns else []
LISTA_ESPECIALIDADES_REALES = sorted([e for e in df_panel["Especialidad"].dropna().unique() if str(e).strip() not in ["", "NAN"]]) if not df_panel.empty and "Especialidad" in df_panel.columns else []
LISTA_MERCADOS_REALES = sorted([m for m in df_productos["MERCADO"].dropna().unique() if str(m).strip() not in ["", "NAN", "TOTAL"]]) if not df_productos.empty and "MERCADO" in df_productos.columns else []
LISTA_RUTAS_VENTAS = sorted([r for r in df_ventas["DESCRIPCION_RUTA"].dropna().unique() if str(r).strip() not in ["", "NAN", "TOTAL"]]) if not df_ventas.empty and "DESCRIPCION_RUTA" in df_ventas.columns else []

# --- INICIALIZACIÓN DE SESIÓN ---
if "chira_history" not in st.session_state: st.session_state.chira_history = []
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "tvp_result" not in st.session_state: st.session_state.tvp_result = None
if "perfiles_memoria" not in st.session_state: st.session_state.perfiles_memoria = {}
if "bitacora_memoria" not in st.session_state: st.session_state.bitacora_memoria = []

# --- ENCABEZADO EJECUTIVO COMPACTO ---
st.markdown("""
<div style='background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); padding: 16px 22px; border-radius: 8px; margin-bottom: 14px; border-left: 6px solid #38bdf8; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;'>
    <div>
        <h2 style='color: #ffffff; margin: 0; font-size: 1.45rem; letter-spacing: 0.4px; font-weight: 800;'>⚜️ [GUTIS BI] — TERMINAL DE INTELIGENCIA COMERCIAL & ARQUITECTURA TVP</h2>
        <p style='color: #93c5fd; margin: 0; font-size: 0.76rem; text-transform: uppercase; font-weight: 600; margin-top: 3px; letter-spacing: 0.9px;'>Núcleo I: Radar Territorial  |  Núcleo II: Consultorio 360° & Canvas TVP  |  Núcleo III: Copiloto Chira & CRM</p>
    </div>
</div>
""", unsafe_allow_html=True)

# --- MENÚ LATERAL MULTIFILTRO ---
st.sidebar.markdown("### 🧭 [SELECTOR DE OBJETIVO]")
ciudades_sb = ["TODAS"] + LISTA_CIUDADES_REALES
ciudad_filtro = st.sidebar.selectbox("📍 1. Territorio / Ciudad:", ciudades_sb)

df_filtrado = df_panel if ciudad_filtro == "TODAS" else df_panel[df_panel["CIUDAD"] == ciudad_filtro]

esps_sb = ["TODAS"] + sorted([e for e in df_filtrado["Especialidad"].dropna().unique() if str(e).strip() not in ["", "NAN"]])
esp_filtro_sb = st.sidebar.selectbox("🧬 2. Especialidad:", esps_sb)
if esp_filtro_sb != "TODAS":
    df_filtrado = df_filtrado[df_filtrado["Especialidad"] == esp_filtro_sb]

cats_sb = ["TODAS"] + sorted([str(c) for c in df_filtrado["CATEGORIA"].dropna().unique() if str(c).strip() not in ["", "NAN"]]) if "CATEGORIA" in df_filtrado.columns else ["TODAS"]
cat_filtro_sb = st.sidebar.selectbox("💠 3. Categoría Médica:", cats_sb)
if cat_filtro_sb != "TODAS" and "CATEGORIA" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["CATEGORIA"].astype(str) == cat_filtro_sb]

lista_medicos = sorted(df_filtrado["Médico"].dropna().unique().tolist())

if not lista_medicos:
    st.warning("[SISTEMA] No existen registros para la combinación seleccionada.")
    st.stop()

medico_sel = st.sidebar.selectbox("⚗️ 4. Especialista Activo:", lista_medicos)

if "medico_chat" not in st.session_state or st.session_state.medico_chat != medico_sel:
    st.session_state.chat_history = []
    st.session_state.tvp_result = None
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
    if deporte and str(deporte) not in ["nan", ""]: partes_rapport.append(f"Afinidad: {deporte}")
    if estilo_visita and str(estilo_visita) not in ["nan", ""]: partes_rapport.append(f"Estilo: {estilo_visita}")
    if partes_rapport: contexto_rapport_str = " | ".join(partes_rapport)

# --- FUNCIONES DE CLASIFICACIÓN ---
def es_gutis(nombre_prod):
    n_norm = normalizar_txt(nombre_prod)
    return any(normalizar_txt(g) in n_norm for g in PRODUCTOS_GUTIS)

def obtener_meta_mercado(mercado_val):
    m_norm = normalizar_txt(mercado_val)
    for m_key, m_info in MERCADOS_PRIORITARIOS.items():
        base_key = normalizar_txt(m_key.replace("MR ", ""))
        if base_key in m_norm or any(normalizar_txt(k) in m_norm for k in m_info["keywords"]):
            return m_info
    return {
        "producto": str(mercado_val).replace("MR ", "").strip().title(),
        "peso": 1, "prioridad": 3, "categoria_mercado": "Prioridad 3 (Complemento)",
        "keywords": [m_norm.replace("MR ", "")],
        "paciente_meta": "Pacientes de consulta especializada que requieren eficacia y seguridad comprobada.",
        "caracteristica": "Formulación farmacéutica de calidad certificada Gutis.",
        "beneficio": "Respuesta clínica confiable, excelente tolerabilidad y apego al tratamiento.",
        "love_brand": "Innovación y tecnología farmacéutica pensada para mejorar la calidad de vida del paciente."
    }

def diagnosticar_escala_adopcion(pxs_gutis_m, pxs_tot_m, ms_gutis_m):
    if pxs_tot_m <= 0:
        return "1. No Consciente", "2. Consciente / 3. Prueba (2-5 Pxs)", "Crear conciencia del perfil de paciente y lograr las primeras 3 recetas de prueba."
    if pxs_gutis_m == 0:
        return "2. Consciente (0% MS)", "3. Prueba (2 a 10 Pxs)", f"Iniciar período de prueba en sus próximos 3 a 5 pacientes (hoy entrega {pxs_tot_m} Pxs a competencia)."
    if ms_gutis_m < 25.0 or pxs_gutis_m <= 10:
        return f"3. Prueba ({ms_gutis_m:.1f}% MS | {pxs_gutis_m} Pxs)", "4. Adopción (>25% a 50% MS)", "Explorar resultados de pacientes en prueba para expandir hacia el >25% de sus casos."
    if ms_gutis_m <= 50.0:
        return f"4. Adopción ({ms_gutis_m:.1f}% MS | {pxs_gutis_m} Pxs)", "5. Lealtad (>50% MS)", "Consolidar la marca como primera opción en más del 50% de sus pacientes meta."
    return f"5. Lealtad ({ms_gutis_m:.1f}% MS | {pxs_gutis_m} Pxs)", "5. Lealtad (Blindaje)", "Blindar lealtad y convertirlo en líder de opinión / promotor de la marca."

# --- MOTOR MACRO 1: MATRIZ DE PENETRACIÓN POR ESPECIALIDAD ---
@st.cache_data
def calcular_matriz_penetracion_panel(ciudad_sel="TODO MI PANEL"):
    df_p_sub = df_panel.copy()
    if ciudad_sel != "TODO MI PANEL" and "CIUDAD" in df_p_sub.columns:
        df_p_sub = df_p_sub[df_p_sub["CIUDAD"].astype(str).str.upper().str.contains(re.escape(ciudad_sel), na=False)].copy()

    if df_p_sub.empty or "Especialidad" not in df_p_sub.columns:
        return pd.DataFrame(), pd.DataFrame()

    usar_labs = not df_labs.empty and "FABRICANTE" in df_labs.columns and "Médico" in df_labs.columns
    if usar_labs:
        df_l_clean = df_labs[~df_labs["FABRICANTE"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])].copy()
        col_ytd_l = "Pxs-YTD" if "Pxs-YTD" in df_l_clean.columns else next((c for c in df_l_clean.columns if "YTD" in c.upper() and "PXS" in c.upper()), None)
        if not col_ytd_l:
            col_ytd_l = next((c for c in df_l_clean.columns if "PXS" in c.upper()), None)
        if col_ytd_l:
            df_l_clean[col_ytd_l] = pd.to_numeric(df_l_clean[col_ytd_l], errors='coerce').fillna(0)

    df_rx_c = df_productos[~df_productos["NOMBRE_PRODUCTO"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])].copy() if not df_productos.empty else pd.DataFrame()
    col_ytd_rx = next((c for c in df_rx_c.columns if c.upper() == "PXS-YTD"), None) if not df_rx_c.empty else None
    if not col_ytd_rx and not df_rx_c.empty:
        col_ytd_rx = next((c for c in df_rx_c.columns if "PXS" in c.upper()), None)
    if not df_rx_c.empty and col_ytd_rx:
        df_rx_c[col_ytd_rx] = pd.to_numeric(df_rx_c[col_ytd_rx], errors='coerce').fillna(0)
        df_rx_c["Es_G"] = df_rx_c["NOMBRE_PRODUCTO"].apply(es_gutis)

    filas_rendimiento, filas_competencia = [], []

    for esp_nom, grp_esp in df_p_sub.groupby("Especialidad"):
        meds_panel_esp = set(grp_esp["Médico"].dropna().unique())
        num_panel = len(meds_panel_esp)
        if num_panel == 0: continue

        if usar_labs and col_ytd_l:
            df_l_esp = df_l_clean[df_l_clean["Médico"].isin(meds_panel_esp)].copy()
            df_l_esp_act = df_l_esp[df_l_esp[col_ytd_l] > 0]
            meds_captados = set(df_l_esp_act["Médico"].unique())

            if not df_rx_c.empty and col_ytd_rx:
                meds_cap_rx = set(df_rx_c[(df_rx_c["Médico"].isin(meds_panel_esp)) & (df_rx_c[col_ytd_rx] > 0)]["Médico"].unique())
                meds_captados = meds_captados.union(meds_cap_rx)

            num_captados = len(meds_captados)
            recetan_gutis_count, top1_count, top3_count = 0, 0, 0

            for m_doc in meds_captados:
                sub_m = df_l_esp_act[df_l_esp_act["Médico"] == m_doc]
                if not sub_m.empty:
                    rk_m = sub_m.groupby("FABRICANTE")[col_ytd_l].sum().reset_index().sort_values(by=col_ytd_l, ascending=False).reset_index(drop=True)
                    rk_m["Rank"] = rk_m.index + 1
                    fila_g_m = rk_m[rk_m["FABRICANTE"].astype(str).str.upper().str.contains("GUTIS", na=False)]
                    if not fila_g_m.empty and fila_g_m.iloc[0][col_ytd_l] > 0:
                        recetan_gutis_count += 1
                        r_pos = int(fila_g_m.iloc[0]["Rank"])
                        if r_pos == 1: top1_count += 1
                        if r_pos <= 3: top3_count += 1
                elif not df_rx_c.empty and col_ytd_rx:
                    sub_rx_m = df_rx_c[(df_rx_c["Médico"] == m_doc) & (df_rx_c[col_ytd_rx] > 0)]
                    if not sub_rx_m.empty and sub_rx_m[sub_rx_m["Es_G"]][col_ytd_rx].sum() > 0:
                        recetan_gutis_count += 1

            penetracion_pct = (recetan_gutis_count / num_captados * 100) if num_captados > 0 else 0.0

            if not df_l_esp_act.empty:
                rk_esp_labs = df_l_esp_act.groupby("FABRICANTE")[col_ytd_l].sum().reset_index().sort_values(by=col_ytd_l, ascending=False).reset_index(drop=True)
                tot_pxs_esp_ytd = rk_esp_labs[col_ytd_l].sum()
                rk_esp_labs["MS_YTD"] = (rk_esp_labs[col_ytd_l] / tot_pxs_esp_ytd * 100) if tot_pxs_esp_ytd > 0 else 0.0
                
                fila_g_esp = rk_esp_labs[rk_esp_labs["FABRICANTE"].astype(str).str.upper().str.contains("GUTIS", na=False)]
                ms_gutis_ytd = float(fila_g_esp.iloc[0]["MS_YTD"]) if not fila_g_esp.empty else 0.0

                top5_strs = []
                for idx_c in range(5):
                    if idx_c < len(rk_esp_labs):
                        r_lab = rk_esp_labs.iloc[idx_c]
                        nom_f = str(r_lab["FABRICANTE"]).strip()
                        ms_f = float(r_lab["MS_YTD"])
                        marca_f = f"🔷 {nom_f} ({ms_f:.2f}%)" if "GUTIS" in nom_f.upper() else f"{nom_f} ({ms_f:.2f}%)"
                        top5_strs.append(marca_f)
                    else:
                        top5_strs.append("-")
            else:
                ms_gutis_ytd = 0.0
                top5_strs = ["-", "-", "-", "-", "-"]

            filas_rendimiento.append({
                "ESPECIALIDAD": esp_nom, "PANEL": num_panel, "CAPTADOS": num_captados,
                "RECETAN GUTIS": recetan_gutis_count, "PENETRACIÓN": round(penetracion_pct, 2),
                "TOP 1": top1_count, "TOP 3": top3_count, "%MS-YTD": round(ms_gutis_ytd, 2)
            })

            filas_competencia.append({
                "ESPECIALIDAD": esp_nom, "#1": top5_strs[0], "#2": top5_strs[1],
                "#3": top5_strs[2], "#4": top5_strs[3], "#5": top5_strs[4], "_orden": num_panel
            })

    df_rend = pd.DataFrame(filas_rendimiento).sort_values(by="PANEL", ascending=False) if filas_rendimiento else pd.DataFrame()
    df_comp = pd.DataFrame(filas_competencia).sort_values(by="_orden", ascending=False).drop(columns=["_orden"]) if filas_competencia else pd.DataFrame()
    return df_rend, df_comp

# --- MOTOR MACRO 2: SINCRONÍA TEMPORAL (RX MÉDICO VS. VENTA EN FARMACIA) ---
@st.cache_data
def calcular_sincronia_rx_vs_sellout(ciudad_sel="TODO MI PANEL"):
    df_p_sub = df_panel.copy()
    if ciudad_sel != "TODO MI PANEL" and "CIUDAD" in df_p_sub.columns:
        df_p_sub = df_p_sub[df_p_sub["CIUDAD"].astype(str).str.upper().str.contains(re.escape(ciudad_sel), na=False)].copy()
    meds_zona = set(df_p_sub["Médico"].dropna().unique())

    df_rx_sub = df_productos[df_productos["Médico"].isin(meds_zona)].copy() if not df_productos.empty else pd.DataFrame()
    if not df_rx_sub.empty:
        df_rx_sub = df_rx_sub[~df_rx_sub["NOMBRE_PRODUCTO"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]

    col_pxs_m = next((c for c in df_rx_sub.columns if c.upper() == "PXS-MES"), None) if not df_rx_sub.empty else None
    col_pxs_y = next((c for c in df_rx_sub.columns if c.upper() == "PXS-YTD"), None) if not df_rx_sub.empty else None
    if not df_rx_sub.empty and col_pxs_m: df_rx_sub[col_pxs_m] = pd.to_numeric(df_rx_sub[col_pxs_m], errors='coerce').fillna(0)
    if not df_rx_sub.empty and col_pxs_y: df_rx_sub[col_pxs_y] = pd.to_numeric(df_rx_sub[col_pxs_y], errors='coerce').fillna(0)

    df_v_sub = df_ventas.copy() if not df_ventas.empty else pd.DataFrame()
    if not df_v_sub.empty and ciudad_sel != "TODO MI PANEL" and "DESCRIPCION_RUTA" in df_v_sub.columns:
        df_v_sub = df_v_sub[df_v_sub["DESCRIPCION_RUTA"].str.contains(re.escape(ciudad_sel), na=False)].copy()
    if not df_v_sub.empty:
        df_v_sub = df_v_sub[~df_v_sub["NOMBRE_CLIENTE_1"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
    col_prod_v = "VM4" if (not df_v_sub.empty and "VM4" in df_v_sub.columns) else (next((c for c in df_v_sub.columns if "PRODUCTO" in c.upper()), None) if not df_v_sub.empty else None)

    filas_sincronia = []
    for m_key, m_info in MERCADOS_PRIORITARIOS.items():
        prod_nom = m_info["producto"]
        kw_merc = normalizar_txt(m_key.replace("MR ", ""))
        kw_venta = prod_nom.split()[0].upper()
        if kw_venta == "DALIVIO": patron_v = "DALIVIO|DALIVIUM"
        elif kw_venta in ["TALERDÍN", "TALERDIN"]: patron_v = "TALERDIN|TALERDÍN"
        elif kw_venta == "CONFLEXIL": patron_v = "CONFLEXIL|CONRELAX"
        else: patron_v = re.escape(kw_venta)

        pxs_ytd_tot, pxs_ytd_gut, pxs_mes_tot, pxs_mes_gut = 0, 0, 0, 0
        if not df_rx_sub.empty and "MERCADO" in df_rx_sub.columns:
            sub_m_rx = df_rx_sub[df_rx_sub["MERCADO"].apply(normalizar_txt).str.contains(re.escape(kw_merc), na=False)].copy()
            if not sub_m_rx.empty:
                sub_m_rx["Es_G"] = sub_m_rx["NOMBRE_PRODUCTO"].apply(es_gutis)
                if col_pxs_y:
                    pxs_ytd_tot = int(sub_m_rx[col_pxs_y].sum())
                    pxs_ytd_gut = int(sub_m_rx[sub_m_rx["Es_G"]][col_pxs_y].sum())
                if col_pxs_m:
                    pxs_mes_tot = int(sub_m_rx[col_pxs_m].sum())
                    pxs_mes_gut = int(sub_m_rx[sub_m_rx["Es_G"]][col_pxs_m].sum())

        ms_ytd_gut = (pxs_ytd_gut / pxs_ytd_tot * 100) if pxs_ytd_tot > 0 else 0.0
        ms_mes_gut = (pxs_mes_gut / pxs_mes_tot * 100) if pxs_mes_tot > 0 else 0.0
        delta_ms_rx = ms_mes_gut - ms_ytd_gut

        v_q1, v_q2, v_q3 = 0.0, 0.0, 0.0
        if not df_v_sub.empty and col_prod_v and "Trimestre" in df_v_sub.columns:
            sub_v = df_v_sub[df_v_sub[col_prod_v].astype(str).str.upper().str.contains(patron_v, na=False)]
            if not sub_v.empty:
                q_sums = sub_v.groupby("Trimestre")["Monto Real"].sum().to_dict()
                v_q1, v_q2, v_q3 = float(q_sums.get("Q1", 0.0)), float(q_sums.get("Q2", 0.0)), float(q_sums.get("Q3", 0.0))

        v_total = v_q1 + v_q2 + v_q3
        delta_so_pct = ((v_q3 - v_q2) / v_q2 * 100) if v_q2 > 0 else (100.0 if v_q3 > 0 else 0.0)

        if pxs_ytd_tot == 0 and pxs_mes_tot == 0 and v_total == 0: continue

        if delta_ms_rx >= 1.5 or (pxs_mes_gut > (pxs_ytd_gut / 8.0) and pxs_mes_gut > 0):
            tend_rx_str, rx_crece = f"⚡ Expande ({delta_ms_rx:+.1f}%)", True
        elif delta_ms_rx <= -1.5:
            tend_rx_str, rx_crece = f"🔻 Contrae ({delta_ms_rx:+.1f}%)", False
        else:
            tend_rx_str, rx_crece = f"⚖️ Estable ({delta_ms_rx:+.1f}%)", (ms_mes_gut >= 15.0 or pxs_mes_gut > 0)

        if delta_so_pct >= 5.0:
            tend_so_str, so_crece = f"🔷 +{delta_so_pct:.1f}%", True
        elif delta_so_pct <= -10.0:
            tend_so_str, so_crece = f"🔶 {delta_so_pct:.1f}%", False
        else:
            tend_so_str, so_crece = f"⚖️ {delta_so_pct:+.1f}%", (v_q3 > 0)

        if rx_crece and so_crece: diag_sinc = "⚡ SINCRONÍA ÓPTIMA (Médico + Farmacia)"
        elif rx_crece and not so_crece: diag_sinc = "🌪️ FUGA EN MOSTRADOR (Receta sube, PDV cae)"
        elif not rx_crece and so_crece: diag_sinc = "🛡️ TRACCIÓN PDV (Reforzar generador Rx)"
        else: diag_sinc = "🔻 ALERTA DOBLE (Activar plan TVP + Trade)"

        filas_sincronia.append({
            "Nivel": f"P{m_info['prioridad']}", "Marca Gutis": prod_nom,
            "Pxs (YTD/Mes)": f"{pxs_ytd_gut} / {pxs_mes_gut}", "% MS YTD": round(ms_ytd_gut, 2),
            "% MS MES": round(ms_mes_gut, 2), "Impulso Rx": tend_rx_str,
            "Q1": round(v_q1, 2), "Q2": round(v_q2, 2), "Q3": round(v_q3, 2),
            "Δ Farmacia": tend_so_str, "Veredicto de Sincronía": diag_sinc,
            "_orden_p": m_info["prioridad"], "_orden_v": v_total
        })

    df_sinc = pd.DataFrame(filas_sincronia)
    if not df_sinc.empty:
        df_sinc = df_sinc.sort_values(by=["_orden_p", "_orden_v"], ascending=[True, False]).drop(columns=["_orden_p", "_orden_v"])
    return df_sinc

# --- PROCESAMIENTO DEL MÉDICO ACTIVO ---
rx_raw = df_productos[df_productos["Médico"] == medico_sel].copy() if not df_productos.empty else pd.DataFrame()
rx_clean = rx_raw.dropna(subset=["NOMBRE_PRODUCTO"]) if not rx_raw.empty and "NOMBRE_PRODUCTO" in rx_raw.columns else pd.DataFrame()
if not rx_clean.empty: rx_clean = rx_clean[~rx_clean["NOMBRE_PRODUCTO"].str.upper().isin(["TOTAL", "NAN", ""])]

if not rx_clean.empty:
    rx_clean["Es_Gutis"] = rx_clean["NOMBRE_PRODUCTO"].apply(es_gutis)
    rx_clean["Meta_Mercado"] = rx_clean["MERCADO"].apply(obtener_meta_mercado)
    if es_pediatra: rx_clean = rx_clean[~rx_clean["MERCADO"].str.upper().str.contains("GASTROALIVIO", na=False)]

col_pxs = next((c for c in rx_clean.columns if c.upper() == "PXS-MES"), None) if not rx_clean.empty else None
if not col_pxs and not rx_clean.empty: col_pxs = next((c for c in rx_clean.columns if any(x in c.upper() for x in ["PXS-TRIM", "PXS-YTD", "PXS", "TRX", "RECETAS"])), None)
col_pxs_ytd_prod = next((c for c in rx_clean.columns if c.upper() == "PXS-YTD"), None) if not rx_clean.empty else None
col_mes = next((c for c in rx_clean.columns if c.upper() == "%MS-MES"), None) if not rx_clean.empty else None
if not col_mes and not rx_clean.empty: col_mes = next((c for c in rx_clean.columns if any(x in c.upper() for x in ["%MS-YTD", "%MS-TRIM", "%MS-TAM"])), None)

if not rx_clean.empty:
    if col_mes and col_mes in rx_clean.columns: rx_clean[col_mes] = pd.to_numeric(rx_clean[col_mes], errors='coerce').fillna(0)
    if col_pxs and col_pxs in rx_clean.columns: rx_clean[col_pxs] = pd.to_numeric(rx_clean[col_pxs], errors='coerce').fillna(0)
    if col_pxs_ytd_prod and col_pxs_ytd_prod in rx_clean.columns: rx_clean[col_pxs_ytd_prod] = pd.to_numeric(rx_clean[col_pxs_ytd_prod], errors='coerce').fillna(0)

total_pxs_medico = int(rx_clean[col_pxs].sum()) if not rx_clean.empty and col_pxs else 0
total_ytd_medico_global = int(rx_clean[col_pxs_ytd_prod].sum()) if not rx_clean.empty and col_pxs_ytd_prod else 0
gutis_pxs_medico = int(rx_clean[rx_clean["Es_Gutis"]][col_pxs].sum()) if total_pxs_medico > 0 else 0
comp_pxs_medico = total_pxs_medico - gutis_pxs_medico

cards_ataque_html, num_mercados, mercado_principal_str, producto_ataque_str, share_lider = "", 0, "[S/D]", "[N/D]", 0.0
prod_gutis_ataque_oficial = "Talerdín" if es_pediatra else "Gastroalivio"
opciones_mercados_medico = []

if not rx_clean.empty:
    for m_nom, df_m in rx_clean.groupby("MERCADO"):
        meta = obtener_meta_mercado(m_nom)
        prod_gutis_esperado = meta["producto"]
        prio_num = meta["prioridad"]
        cat_merc_txt = meta["categoria_mercado"]

        pxs_tot_m = int(df_m[col_pxs].sum()) if col_pxs else 0
        pxs_ytd_m = int(df_m[col_pxs_ytd_prod].sum()) if col_pxs_ytd_prod else 0
        pxs_gut_m = int(df_m[df_m["Es_Gutis"]][col_pxs].sum()) if col_pxs else 0
        pxs_comp_m = pxs_tot_m - pxs_gut_m
        ms_gut_m = (pxs_gut_m / pxs_tot_m * 100) if pxs_tot_m > 0 else 0.0

        df_m_ord = df_m.sort_values(by=[col_pxs, col_pxs_ytd_prod] if (col_pxs and col_pxs_ytd_prod) else ([col_pxs] if col_pxs else [col_mes]), ascending=False)
        lider = df_m_ord.iloc[0]
        lider_nombre = str(lider["NOMBRE_PRODUCTO"]).strip()
        lider_es_gutis = bool(lider["Es_Gutis"])
        lider_ms = (float(lider[col_mes]) * 100) if col_mes else 0.0

        escala_act, escala_meta, obj_escala = diagnosticar_escala_adopcion(pxs_gut_m, pxs_tot_m, ms_gut_m)

        if pxs_tot_m > 0 or pxs_ytd_m > 0 or lider_ms > 0:
            opciones_mercados_medico.append({
                "mercado": m_nom, "prioridad": prio_num, "categoria_mercado": cat_merc_txt,
                "lider_actual": lider_nombre, "lider_es_gutis": lider_es_gutis, "prod_gutis": prod_gutis_esperado,
                "pxs_totales": pxs_tot_m, "pxs_ytd": pxs_ytd_m, "pxs_gutis": pxs_gut_m, "pxs_comp": pxs_comp_m,
                "ms_lider": lider_ms, "ms_gutis": ms_gut_m, "escala_actual": escala_act,
                "escala_meta": escala_meta, "objetivo_escala": obj_escala, "meta_info": meta
            })

    opciones_mercados_medico = sorted(opciones_mercados_medico, key=lambda x: (-x["pxs_totales"], x["prioridad"], -x["pxs_ytd"]))
    num_mercados = len(opciones_mercados_medico)

    if opciones_mercados_medico:
        prim = opciones_mercados_medico[0]
        mercado_principal_str, producto_ataque_str, prod_gutis_ataque_oficial, share_lider = prim["mercado"], prim["lider_actual"], prim["prod_gutis"], prim["ms_lider"]

    for item_m in opciones_mercados_medico:
        m = item_m["mercado"]
        badge_p = f"P{item_m['prioridad']}"
        color_p = "#1e3a8a" if item_m["prioridad"] == 1 else ("#0284c7" if item_m["prioridad"] == 2 else "#64748b")
        if not item_m["lider_es_gutis"]:
            cards_ataque_html += f"""<div style="background: linear-gradient(180deg, #fff1f2 0%, #ffffff 100%); border: 1px solid #fecdd3; border-top: 4px solid #e11d48; border-radius: 6px; padding: 10px; min-width: 205px; flex: 1 1 calc(25% - 12px);"><div style="display:flex; justify-content:space-between; align-items:center;"><span style="font-size: 0.65rem; font-weight: 800; color: #9f1239;">{m.replace('MR ', '')}</span><span style="background:{color_p}; color:white; font-size:0.6rem; padding:2px 6px; border-radius:4px; font-weight:700;">{badge_p}</span></div><div style="font-size: 0.84rem; color: #0f172a; margin: 3px 0;">Líder: <b style="color:#be123c;">{item_m['lider_actual'][:15]}</b></div><div style="font-size: 0.72rem; color: #475569;">Mes: <b>{item_m['pxs_totales']}</b> (Comp: {item_m['pxs_comp']}) | YTD: {item_m['pxs_ytd']}</div><div style="font-size: 0.69rem; color: #334155; margin-top:2px;">Escala: <b>{item_m['escala_actual'].split('(')[0]}</b></div><div style="margin-top: 4px; font-size: 0.72rem; font-weight: 800; color: #047857; border-top: 1px dashed #cbd5e1; padding-top: 3px;">⚔️ Conquistar: {item_m['prod_gutis']}</div></div>"""
        else:
            cards_ataque_html += f"""<div style="background: linear-gradient(180deg, #ecfdf5 0%, #ffffff 100%); border: 1px solid #a7f3d0; border-top: 4px solid #059669; border-radius: 6px; padding: 10px; min-width: 205px; flex: 1 1 calc(25% - 12px);"><div style="display:flex; justify-content:space-between; align-items:center;"><span style="font-size: 0.65rem; font-weight: 800; color: #065f46;">{m.replace('MR ', '')}</span><span style="background:{color_p}; color:white; font-size:0.6rem; padding:2px 6px; border-radius:4px; font-weight:700;">{badge_p}</span></div><div style="font-size: 0.84rem; color: #0f172a; margin: 3px 0;">Dominio: <b style="color:#047857;">{item_m['prod_gutis']}</b></div><div style="font-size: 0.72rem; color: #475569;">Mes: <b>{item_m['pxs_totales']}</b> (Gutis: {item_m['pxs_gutis']}) | YTD: {item_m['pxs_ytd']}</div><div style="font-size: 0.69rem; color: #334155; margin-top:2px;">Escala: <b>{item_m['escala_actual'].split('(')[0]}</b></div><div style="margin-top: 4px; font-size: 0.72rem; font-weight: 800; color: #047857; border-top: 1px dashed #cbd5e1; padding-top: 3px;">🛡️ Blindar Recetario</div></div>"""

# DATOS DE SELL-OUT ZONAL
total_sellout_zona, total_puntos_venta = 0.0, 0
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

# --- LLAMADA API GEMINI ---
def llamar_gemini(prompt_text, max_tok=4096):
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key: return None
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt_text}]}], "generationConfig": {"maxOutputTokens": max_tok, "temperature": 0.2}}
    modelos_a_probar = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash"]
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

# --- TICKER SUPERIOR COMPACTO (4 INDICADORES EN UNA LÍNEA) ---
escala_ticker = opciones_mercados_medico[0]["escala_actual"].split("(")[0] if opciones_mercados_medico else "2. Consciente"
st.markdown(f"""
<div class='ticker-bar'>
    <div class='ticker-item'>
        <div class='ticker-label'>🧬 ESPECIALISTA EN FOCO</div>
        <div class='ticker-val'>{medico_sel[:24]}</div>
        <div class='ticker-sub'>{especialidad} | Cat {categoria} | {ciudad}</div>
    </div>
    <div class='ticker-item'>
        <div class='ticker-label'>⏳ AUDITORÍA DE RECETAS (RX)</div>
        <div class='ticker-val'>{total_pxs_medico} Pxs Mes <span style='font-size:0.85rem; color:#0284c7;'>({total_ytd_medico_global} YTD)</span></div>
        <div class='ticker-sub'>🔷 Gutis: {gutis_pxs_medico} | 🔶 Comp: {comp_pxs_medico}</div>
    </div>
    <div class='ticker-item'>
        <div class='ticker-label'>♟️ BLANCO PRIMARIO ({mercado_principal_str})</div>
        <div class='ticker-val'>{producto_ataque_str[:16]} ➔ {prod_gutis_ataque_oficial}</div>
        <div class='ticker-sub'>Escala TVP: <b>{escala_ticker}</b></div>
    </div>
    <div class='ticker-item'>
        <div class='ticker-label'>🏛️ SELL-OUT ZONAL ({ciudad} - {total_puntos_venta} PDV)</div>
        <div class='ticker-val'>${total_sellout_zona:,.2f}</div>
        <div class='ticker-sub'>Aliadas: {top_farmacias_ciudad_str[:32]}...</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# ARQUITECTURA EJECUTIVA DE 3 NÚCLEOS LÓGICOS
# ==============================================================================
nucleo_macro, nucleo_micro, nucleo_copiloto = st.tabs([
    "🛰️ Núcleo I: Radar Macro & Sincronía Territorial",
    "🧬 Núcleo II: Consultorio 360° & Canvas TVP",
    "♟️ Núcleo III: Copiloto Chira & Cierre Post-Visita"
])

# ==============================================================================
# NÚCLEO I: RADAR MACRO (PENETRACIÓN + SINCRONÍA RX/SELL-OUT + RUTA GEOTÁCTICA)
# ==============================================================================
with nucleo_macro:
    st.markdown("<div class='elite-banner'>🛰️ RADAR MACRO DE TERRITORIO: PENETRACIÓN POR ESPECIALIDAD, SINCRONÍA RX/PDV E ITINERARIO GEOTÁCTICO</div>", unsafe_allow_html=True)
    
    c_m1, c_m2 = st.columns([1.3, 2.7])
    with c_m1:
        zona_terreno_sel = st.selectbox("🗺️ Seleccionar Territorio Macro:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="terr_zona")
    with c_m2:
        vista_macro = st.radio(
            "🔭 Seleccionar Módulo de Inteligencia Territorial:",
            ["1. Matriz de Penetración & Top 5 Competencia", "2. Sincronía Rx vs. Sell-Out & Auditoría Farmacias", "3. Planificador Geotáctico de Ruta (P1, P2, P3)"],
            horizontal=True
        )

    # SUB-MÓDULO 1: PENETRACIÓN POR ESPECIALIDAD Y TOP 5 COMPETENCIA
    if vista_macro.startswith("1."):
        df_rend_interno, df_top_comp = calcular_matriz_penetracion_panel(zona_terreno_sel)
        if not df_rend_interno.empty:
            tot_pan = int(df_rend_interno["PANEL"].sum())
            tot_cap = int(df_rend_interno["CAPTADOS"].sum())
            tot_rec_g = int(df_rend_interno["RECETAN GUTIS"].sum())
            pen_global = (tot_rec_g / tot_cap * 100) if tot_cap > 0 else 0.0
            tot_t1 = int(df_rend_interno["TOP 1"].sum())
            tot_t3 = int(df_rend_interno["TOP 3"].sum())

            kt1, kt2, kt3, kt4, kt5 = st.columns(5)
            kt1.metric("Médicos en Panel", tot_pan)
            kt2.metric("Captados Close-Up", tot_cap, f"{(tot_cap/tot_pan*100):.1f}% Cobertura" if tot_pan > 0 else "")
            kt3.metric("Recetan Gutis", tot_rec_g)
            kt4.metric("Penetración Global", f"{pen_global:.2f}%")
            kt5.metric("Gutis Top 1 / Top 3", f"{tot_t1} / {tot_t3}")

            st.markdown(f"##### 💠 Rendimiento Interno YTD 2026 por Especialidad ({zona_terreno_sel})")
            st.dataframe(
                df_rend_interno, hide_index=True, use_container_width=True,
                column_config={
                    "PENETRACIÓN": st.column_config.ProgressColumn("PENETRACIÓN (%)", format="%.2f%%", min_value=0, max_value=100),
                    "%MS-YTD": st.column_config.ProgressColumn("%MS-YTD GUTIS", format="%.2f%%", min_value=0, max_value=100),
                }
            )
            st.markdown(f"##### ⚔️ Top Competencia Directa por Cuota de Mercado YTD ({zona_terreno_sel})")
            st.dataframe(df_top_comp, hide_index=True, use_container_width=True)
        else:
            st.warning("No se encontraron registros cruzados para la zona seleccionada.")

    # SUB-MÓDULO 2: SINCRONÍA RX VS SELL-OUT Y AUDITORÍA DETALLADA DE FARMACIAS
    elif vista_macro.startswith("2."):
        st.markdown(f"##### ⚖️ Matriz de Sincronía Temporal: Evolución de Receta (Rx) vs. Sell-Out Farmacéutico ({zona_terreno_sel})")
        df_sincronia = calcular_sincronia_rx_vs_sellout(zona_terreno_sel)
        if not df_sincronia.empty:
            st.dataframe(
                df_sincronia, hide_index=True, use_container_width=True,
                column_config={
                    "% MS YTD": st.column_config.NumberColumn("% MS YTD", format="%.2f%%"),
                    "% MS MES": st.column_config.NumberColumn("% MS MES", format="%.2f%%"),
                    "Q1": st.column_config.NumberColumn("Sell-Out Q1", format="$%.2f"),
                    "Q2": st.column_config.NumberColumn("Sell-Out Q2", format="$%.2f"),
                    "Q3": st.column_config.NumberColumn("Sell-Out Q3", format="$%.2f"),
                }
            )
            fugas_df = df_sincronia[df_sincronia["Veredicto de Sincronía"].str.contains("🌪️")]
            exitos_df = df_sincronia[df_sincronia["Veredicto de Sincronía"].str.contains("⚡")]
            ca1, ca2 = st.columns(2)
            with ca1:
                if not exitos_df.empty:
                    st.success(f"**⚡ Sincronía Óptima ({zona_terreno_sel}):** {', '.join(exitos_df['Marca Gutis'].tolist())}. La receta médica se convierte en facturación en mostrador.")
            with ca2:
                if not fugas_df.empty:
                    st.error(f"**🌪️ Alerta de Fuga en Mostrador ({zona_terreno_sel}):** {', '.join(fugas_df['Marca Gutis'].tolist())}. Crece o se sostiene la receta médica, pero cae la compra en farmacia en Q3.")

        st.divider()
        st.markdown("##### 🏛️ Desglose de Sell-Out por Sucursal Farmacéutica y Trimestre (Q1, Q2, Q3)")
        if not df_ventas.empty and "DESCRIPCION_RUTA" in df_ventas.columns:
            ventas_zona = df_ventas.copy() if zona_terreno_sel == "TODO MI PANEL" else df_ventas[df_ventas["DESCRIPCION_RUTA"].str.contains(re.escape(zona_terreno_sel), na=False)].copy()
            if not ventas_zona.empty:
                col_prod_v = "VM4" if "VM4" in ventas_zona.columns else next((c for c in ventas_zona.columns if "PRODUCTO" in c.upper()), None)
                if col_prod_v:
                    ventas_zona[col_prod_v] = ventas_zona[col_prod_v].astype(str).str.strip()
                    ventas_zona = ventas_zona[~ventas_zona[col_prod_v].str.upper().isin(["TOTAL", "NAN", ""])]
                ventas_zona = ventas_zona[~ventas_zona["NOMBRE_CLIENTE_1"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]

                cf_s1, cf_s2 = st.columns(2)
                with cf_s1:
                    farm_sel = st.multiselect("🏛️ Filtrar Farmacia(s):", sorted(ventas_zona["NOMBRE_CLIENTE_1"].dropna().unique().tolist()), placeholder="Todas las sucursales...")
                with cf_s2:
                    prod_v_sel = st.multiselect("⚗️ Filtrar Línea / Producto:", sorted(ventas_zona[col_prod_v].dropna().unique().tolist()) if col_prod_v else [], placeholder="Todas las líneas...")

                df_v_mostrar = ventas_zona.copy()
                if farm_sel: df_v_mostrar = df_v_mostrar[df_v_mostrar["NOMBRE_CLIENTE_1"].isin(farm_sel)]
                if prod_v_sel and col_prod_v: df_v_mostrar = df_v_mostrar[df_v_mostrar[col_prod_v].isin(prod_v_sel)]

                if col_prod_v and "Trimestre" in df_v_mostrar.columns and not df_v_mostrar.empty:
                    df_pivot = pd.pivot_table(df_v_mostrar, values="Monto Real", index=["NOMBRE_CLIENTE_1", col_prod_v], columns=["Trimestre"], aggfunc="sum", fill_value=0.0).reset_index()
                    for q_col in ["Q1", "Q2", "Q3"]:
                        if q_col not in df_pivot.columns: df_pivot[q_col] = 0.0
                        df_pivot[q_col] = df_pivot[q_col].round(2)
                    df_pivot["Venta Total"] = (df_pivot["Q1"] + df_pivot["Q2"] + df_pivot["Q3"]).round(2)

                    def evaluar_tendencia(row):
                        q2, q3 = row["Q2"], row["Q3"]
                        if q2 <= 0 and q3 > 0: return "⚡ Despegue (+100%)"
                        if q2 <= 0 and q3 <= 0: return "⚪ Inactivo"
                        var_pct = ((q3 - q2) / q2) * 100
                        if var_pct >= 10: return f"🔷 +{var_pct:.1f}%"
                        elif var_pct <= -15: return f"🌪️ {var_pct:.1f}%"
                        else: return f"⚖️ {var_pct:+.1f}%"

                    df_pivot["Δ Q3 vs Q2"] = df_pivot.apply(evaluar_tendencia, axis=1)
                    df_pivot = df_pivot.sort_values(by="Venta Total", ascending=False)

                    st.dataframe(
                        df_pivot[["NOMBRE_CLIENTE_1", col_prod_v, "Q1", "Q2", "Q3", "Venta Total", "Δ Q3 vs Q2"]].rename(columns={"NOMBRE_CLIENTE_1": "Punto de Venta / Farmacia", col_prod_v: "Línea Gutis"}),
                        hide_index=True, use_container_width=True,
                        column_config={
                            "Q1": st.column_config.NumberColumn("Q1", format="$%.2f"),
                            "Q2": st.column_config.NumberColumn("Q2", format="$%.2f"),
                            "Q3": st.column_config.NumberColumn("Q3", format="$%.2f"),
                            "Venta Total": st.column_config.NumberColumn("Venta Total", format="$%.2f"),
                        }
                    )

    # SUB-MÓDULO 3: PLANIFICADOR GEOTÁCTICO DE RUTA
    else:
        st.markdown("##### 🧭 Matriz Geotáctica de Ruta por Prioridad de Mercado (P1, P2, P3) y Oportunidad de Conquista")
        cr_p, cr1, cr2, cr3 = st.columns([1.2, 1.5, 1.2, 0.9])
        df_ruta_zona = df_panel.copy() if zona_terreno_sel == "TODO MI PANEL" else df_panel[df_panel["CIUDAD"].str.contains(re.escape(zona_terreno_sel), na=False)].copy()

        with cr_p:
            prio_ruta_sel = st.selectbox("💠 Nivel de Mercado:", ["Todos (P1, P2, P3)", "Solo Prioridad 1 (Core)", "Solo Prioridad 2 (Expansión)", "Solo Prioridad 3 (Complemento)"])
        mercados_disp_ruta = LISTA_MERCADOS_REALES
        if "Prioridad 1" in prio_ruta_sel: mercados_disp_ruta = [m for m in LISTA_MERCADOS_REALES if obtener_meta_mercado(m)["prioridad"] == 1]
        elif "Prioridad 2" in prio_ruta_sel: mercados_disp_ruta = [m for m in LISTA_MERCADOS_REALES if obtener_meta_mercado(m)["prioridad"] == 2]
        elif "Prioridad 3" in prio_ruta_sel: mercados_disp_ruta = [m for m in LISTA_MERCADOS_REALES if obtener_meta_mercado(m)["prioridad"] == 3]

        with cr1:
            mercados_ruta_sel = st.multiselect("⚗️ Mercados Específicos:", mercados_disp_ruta, placeholder="Todos los del nivel...")
        with cr2:
            esps_ruta_sel = st.multiselect("🧬 Especialidad:", sorted(df_ruta_zona["Especialidad"].dropna().unique().tolist()) if "Especialidad" in df_ruta_zona.columns else [], placeholder="Todas...")
        with cr3:
            cats_ruta_sel = st.multiselect("⚜️ Categoría:", sorted([str(c) for c in df_ruta_zona["CATEGORIA"].dropna().unique().tolist()]) if "CATEGORIA" in df_ruta_zona.columns else [], placeholder="Todas...")

        if esps_ruta_sel and "Especialidad" in df_ruta_zona.columns: df_ruta_zona = df_ruta_zona[df_ruta_zona["Especialidad"].isin(esps_ruta_sel)]
        if cats_ruta_sel and "CATEGORIA" in df_ruta_zona.columns: df_ruta_zona = df_ruta_zona[df_ruta_zona["CATEGORIA"].astype(str).isin(cats_ruta_sel)]

        columnas_deseadas = ["Médico", "Especialidad", "CATEGORIA", "DIRECCION", "Dirección", "CLINICA", "CIUDAD"]
        columnas_existentes = [col for col in columnas_deseadas if col in df_ruta_zona.columns]
        df_mostrar = df_ruta_zona[columnas_existentes].dropna(subset=["Médico"]).copy() if "Médico" in columnas_existentes else df_ruta_zona.copy()

        if not df_productos.empty and "Médico" in df_mostrar.columns:
            mercados_efectivos = mercados_ruta_sel if mercados_ruta_sel else mercados_disp_ruta
            rx_ruta = df_productos[df_productos["MERCADO"].isin(mercados_efectivos)].copy()
            rx_ruta = rx_ruta[~rx_ruta["NOMBRE_PRODUCTO"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
            col_pxs_ruta = next((c for c in rx_ruta.columns if c.upper() == "PXS-MES"), None)
            if not col_pxs_ruta: col_pxs_ruta = next((c for c in rx_ruta.columns if "PXS" in c.upper() or "TRX" in c.upper()), None)
            
            if col_pxs_ruta and not rx_ruta.empty:
                rx_ruta[col_pxs_ruta] = pd.to_numeric(rx_ruta[col_pxs_ruta], errors='coerce').fillna(0)
                rx_ruta["Es_G"] = rx_ruta["NOMBRE_PRODUCTO"].apply(es_gutis)
                tot_med = rx_ruta.groupby("Médico")[col_pxs_ruta].sum().reset_index().rename(columns={col_pxs_ruta: "Pxs Totales"})
                gut_med = rx_ruta[rx_ruta["Es_G"]].groupby("Médico")[col_pxs_ruta].sum().reset_index().rename(columns={col_pxs_ruta: "Pxs Gutis"})
                resumen_r = pd.merge(tot_med, gut_med, on="Médico", how="left").fillna(0)
                resumen_r["⚔️ Pxs Competencia (Conquista)"] = (resumen_r["Pxs Totales"] - resumen_r["Pxs Gutis"]).astype(int)
                resumen_r["Pxs Totales"] = resumen_r["Pxs Totales"].astype(int)
                resumen_r["Pxs Gutis"] = resumen_r["Pxs Gutis"].astype(int)

                how_merge = "inner" if (mercados_ruta_sel or "Solo" in prio_ruta_sel) else "left"
                df_mostrar = pd.merge(df_mostrar, resumen_r, on="Médico", how=how_merge).fillna(0)
                for c_int in ["Pxs Totales", "Pxs Gutis", "⚔️ Pxs Competencia (Conquista)"]:
                    if c_int in df_mostrar.columns: df_mostrar[c_int] = df_mostrar[c_int].astype(int)
                df_mostrar = df_mostrar.sort_values(by=["⚔️ Pxs Competencia (Conquista)", "Pxs Totales"], ascending=[False, False])

        st.dataframe(df_mostrar, hide_index=True, use_container_width=True)
        csv_ruta = df_mostrar.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Exportar Hoja de Ruta Geotáctica (CSV)", data=csv_ruta, file_name=f"Ruta_Gutis_{zona_terreno_sel}.csv", mime="text/csv")

# ==============================================================================
# NÚCLEO II: CONSULTORIO 360° & CANVAS TVP DE 4 CUADRANTES (VISTA UNIFICADA)
# ==============================================================================
with nucleo_micro:
    if cards_ataque_html:
        st.components.v1.html(f"""<div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-left: 5px solid #1e3a8a; padding: 12px; margin-bottom: 10px; border-radius: 8px;"><div style="font-size: 0.78rem; font-weight: 800; color: #0f172a; margin-bottom: 8px; letter-spacing: 0.5px;">💠 [MAPA DE MERCADOS ACTIVOS DEL ESPECIALISTA (P1, P2, P3) — {num_mercados} MERCADOS AUDITADOS]</div><div style="display: flex; flex-wrap: wrap; gap: 10px;">{cards_ataque_html}</div></div>""", height=190, scrolling=True)

    col_canvas, col_micro_datos = st.columns([1.35, 1.05])

    # COLUMNA IZQUIERDA: CANVAS TVP DE 4 CUADRANTES + DESPLEGABLES DE PROFUNDIZACIÓN
    with col_canvas:
        st.markdown("##### ♟️ [CANVAS TVP DE 4 CUADRANTES — LECTURA TÁCTICA EN 15 SEGUNDOS]")
        with st.container(border=True):
            if opciones_mercados_medico:
                etiquetas_m = [f"[P{o['prioridad']}] {o['mercado']} | Líder: {o['lider_actual'][:13]} ({o['pxs_totales']} Pxs) ➔ {o['prod_gutis']}" for o in opciones_mercados_medico]
                cm1, cm2, cm3 = st.columns(3)
                with cm1: idx_m1 = st.selectbox("🥇 1ra Posición (Foco):", range(len(etiquetas_m)), index=0, format_func=lambda i: etiquetas_m[i])
                with cm2: idx_m2 = st.selectbox("🥈 2da Posición (Puente):", range(len(etiquetas_m)), index=(1 if len(etiquetas_m)>1 else 0), format_func=lambda i: etiquetas_m[i])
                with cm3: idx_m3 = st.selectbox("🥉 3ra Posición (Cierre):", range(len(etiquetas_m)), index=(2 if len(etiquetas_m)>2 else (1 if len(etiquetas_m)>1 else 0)), format_func=lambda i: etiquetas_m[i])
                m_primario = opciones_mercados_medico[idx_m1]
                m_secundario = opciones_mercados_medico[idx_m2] if len(opciones_mercados_medico) > 1 else None
                m_terciario = opciones_mercados_medico[idx_m3] if len(opciones_mercados_medico) > 2 else None
            else:
                meta_def = obtener_meta_mercado("MR TALERDIN" if es_pediatra else "MR GASTROALIVIO")
                m_primario = {
                    "mercado": "MR TALERDIN" if es_pediatra else "MR GASTROALIVIO", "prioridad": 1, "categoria_mercado": "Prioridad 1 (Core)",
                    "lider_actual": producto_ataque_str, "lider_es_gutis": False, "prod_gutis": prod_gutis_ataque_oficial,
                    "pxs_totales": total_pxs_medico, "pxs_ytd": total_ytd_medico_global, "pxs_gutis": gutis_pxs_medico, "pxs_comp": comp_pxs_medico,
                    "ms_lider": share_lider, "ms_gutis": 0.0, "escala_actual": "2. Consciente (0% MS)", "escala_meta": "3. Prueba (2 a 10 Pxs)",
                    "objetivo_escala": "Iniciar período de prueba.", "meta_info": meta_def
                }
                m_secundario, m_terciario = None, None

            ct1, ct2 = st.columns(2)
            with ct1: tipo_cita_sel = st.selectbox("🚪 Contexto de Abordaje:", ["Visita con cita previa", "Visita sin cita (Improvisto)", "Encuentro casual (Pasillo)"])
            with ct2: nec_detras_sel = st.selectbox("🧠 Resorte Psicológico (NdN):", ["Desempeño (Eficacia y adherencia)", "Imagen (Prestigio clínico)", "Finanzas (Costo-beneficio)"])

        # Preparación de variables para el Canvas de 4 Cuadrantes
        meta1 = m_primario["meta_info"]
        prod1, comp1, merc1 = m_primario["prod_gutis"], m_primario["lider_actual"], m_primario["mercado"]
        prod2 = m_secundario["prod_gutis"] if m_secundario else "Conflexil / Valerpan"
        benef2 = m_secundario["meta_info"]["beneficio"] if m_secundario else "Recuperación funcional rápida"
        prod3 = m_terciario["prod_gutis"] if m_terciario else "Renovart Platinum"

        # Renderizado del Canvas TVP en 4 Cuadrantes de Alta Densidad Visual
        st.markdown(f"""
        <div class='canvas-grid'>
            <div class='quad-card' style='border-top: 4px solid #1e3a8a;'>
                <div class='quad-title' style='color:#1e3a8a;'>♟️ I. DIAGNÓSTICO & OBJETIVO SMART</div>
                <div class='quad-body'>
                    • <b>Escala Actual:</b> <span style='color:#be123c; font-weight:700;'>{m_primario['escala_actual']}</span><br>
                    • <b>Escalón Meta Hoy:</b> <span style='color:#047857; font-weight:700;'>{m_primario['escala_meta']}</span><br>
                    • <b>Meta SMART:</b> Capturar <b>3 a 5 pacientes</b> de <code>{comp1}</code> hacia <b>{prod1}</b> en los próximos 7 días.<br>
                    • <b>Plan B (Respaldo):</b> Prueba controlada en 2 casos clínicos con muestra inicial.
                </div>
            </div>
            <div class='quad-card' style='border-top: 4px solid #0284c7;'>
                <div class='quad-title' style='color:#0284c7;'>🗝️ II. APERTURA & PREGUNTA DISRUPTIVA</div>
                <div class='quad-body'>
                    • <b>Regla TVP:</b> Entrar con agenda centrada en el paciente (sin mencionar marca).<br>
                    • <b>Agenda ({tipo_cita_sel.split('(')[0].strip()}):</b> Revisar adherencia en <i>{meta1['paciente_meta'][:55]}...</i><br>
                    • <b>Disruptiva:</b> <i>«¿Qué impacto tendría en su consulta eliminar hoy el abandono al 2do día en estos pacientes?»</i><br>
                    • <b>Acuerdo:</b> <i>«¿Le parece bien revisarlo en 2 minutos?»</i>
                </div>
            </div>
            <div class='quad-card' style='border-top: 4px solid #059669;'>
                <div class='quad-title' style='color:#059669;'>⚗️ III. EMBUDO, APOYO & LOVE BRAND</div>
                <div class='quad-body'>
                    • <b>Sondeo Valor Mutuo:</b> <i>«Al <b>comparar</b> y <b>evaluar</b> la respuesta con {comp1}, ¿qué prioriza mejorar?»</i><br>
                    • <b>Ventaja ({prod1}):</b> {meta1['caracteristica']}<br>
                    • <b>Beneficio ({nec_detras_sel.split('(')[0].strip()}):</b> {meta1['beneficio']}<br>
                    • <b>Love Brand:</b> <i>«{meta1['love_brand']}»</i>
                </div>
            </div>
            <div class='quad-card' style='border-top: 4px solid #d97706;'>
                <div class='quad-title' style='color:#b45309;'>⛓️ IV. CIERRE BILATERAL & PUENTE P1➔P2➔P3</div>
                <div class='quad-body'>
                    • <b>Pido al Médico:</b> Iniciar <b>{prod1}</b> en los próximos 3-5 pacientes.<br>
                    • <b>Mi Compromiso:</b> Blindar stock hoy en <b>{top_farmacias_ciudad_str.split(',')[0]}</b>.<br>
                    • <b>Puente a 2da Posición ({prod2}):</b> <i>«Siguiendo con seguridad clínica, en estos casos cuenta con {prod2} ({benef2[:42]}...).»</i><br>
                    • <b>Recordación 3ra ({prod3}):</b> Respaldo activo en farmacias aledañas.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Desplegable 1: Guion Literal Completo para quien desee leer el diálogo extenso
        with st.expander("📜 [DESPLEGAR DIÁLOGO LITERAL EXTENDIDO PASO A PASO (UNIDADES 1 A 6 DEL MANUAL GUTIS)]"):
            if st.button("⚡ Personalizar Diálogo Extendido con IA", use_container_width=True):
                with st.spinner("Redactando guion conversacional..."):
                    prompt_ext = f"{REGLAS_FARMA}\nRedacta el diálogo exacto paso a paso (Apertura sin marca, Sondeos de Valor Mutuo, Apoyo Love Brand y Cierre con Puente de {prod1} hacia {prod2} y {prod3}) para el Dr(a). {medico_sel} ({especialidad} en {ciudad}), considerando que receta {comp1} ({m_primario['pxs_totales']} Pxs). Enfoque psicológico: {nec_detras_sel}. Farmacias aliadas: {top_farmacias_ciudad_str}."
                    res_ext = llamar_gemini(prompt_ext)
                    st.session_state.tvp_result = res_ext
            if st.session_state.tvp_result:
                st.markdown(st.session_state.tvp_result)
            else:
                st.markdown(f"""
* **1. Apertura Formal:** *«Doctor(a) {medico_sel}, gracias por estos minutos. {('Recordaba su interés en ' + contexto_rapport_str + '. ') if contexto_rapport_str else ''}Quería proponerle analizar cómo asegurar un alivio más rápido y sin abandono en {meta1['paciente_meta'].lower()}. ¿Le parece bien?»*
* **2. Sondeo del Embudo:** *«Al **evaluar** la evolución de sus pacientes tratados habitualmente con `{comp1}`, ¿qué aspecto de tolerabilidad o rapidez considera clave optimizar para proteger el prestigio de su consulta?»*
* **3. Apoyo & Storytelling:** *«Comprendo perfectamente su prioridad. Por ello en Gutis desarrollamos **{prod1}**, que aporta **{meta1['caracteristica'].lower()}**, traduciéndose en **{meta1['beneficio'].lower()}**. {meta1['love_brand']} ¿No es este el respaldo que busca para sus pacientes?»*
* **4. Cierre & Puente Multi-Mercado:** *«¿Consideraría iniciar con **{prod1}** a sus próximos 3 a 5 pacientes esta semana mientras yo verifico el inventario en **{top_farmacias_ciudad_str}**? Y conectando con la recuperación integral, recuerde que para sus casos complementarios cuenta con **{prod2}** y **{prod3}** disponibles en las mismas farmacias.»*
""")

        # Desplegable 2: Simulador de Indiferencia y Objeciones (Unidades 7 y 8)
        with st.expander("⚔️ [ENTRENADOR DE OBJECIONES TVP: ESCEPTICISMO, MALENTENDIDO, DESVENTAJA E INDIFERENCIA]"):
            st.caption("Escribe tu argumento frente a una objeción del médico y recibe feedback inmediato según las Unidades 7 y 8 del Manual Gutis.")
            chat_container = st.container(height=230)
            for msg in st.session_state.chat_history:
                with chat_container.chat_message(msg["role"]): st.write(msg["content"])
            if prompt_chat := st.chat_input(f"Rebate la objeción del Dr(a). {medico_sel} sobre {prod1}..."):
                st.session_state.chat_history.append({"role": "user", "content": prompt_chat})
                with chat_container.chat_message("user"): st.write(prompt_chat)
                with st.spinner("Evaluando técnica TVP..."):
                    prompt_sim = f"{REGLAS_FARMA}\nEntrena a Erick Calderón frente al Dr(a). {medico_sel}. Producto: {prod1} vs {comp1}. Erick dijo: '{prompt_chat}'. Responde en 2 bloques breves: 1) Respuesta realista del médico, 2) Coaching TVP (clasificando en Escepticismo, Malentendido o Desventaja)."
                    res_sim = llamar_gemini(prompt_sim)
                    if not res_sim:
                        res_sim = f"**🩺 Dr(a). {medico_sel}:** «Ya conozco `{comp1}` y me da resultados aceptables; además el paciente ya lo ubica.»\n\n**🛡️ Coaching TVP:** Clasificación: **Indiferencia / Hábito**. Aplica Unidad 7: 1) Demuestra comprensión sin ceder, 2) Pide permiso para 1 pregunta de agenda limitada sobre el beneficio exclusivo de **{prod1}** (*{meta1['caracteristica']}*)."
                st.session_state.chat_history.append({"role": "assistant", "content": res_sim})
                st.rerun()

    # COLUMNA DERECHA: AUDITORÍA RX (P1, P2, P3), RADAR DE LABS Y PERFIL 360 UNIFICADOS
    with col_micro_datos:
        sub_rx, sub_labs, sub_360 = st.tabs([
            "🧪 Recetario Rx (P1-P3)",
            "🏛️ Radar Fabricantes",
            "🪪 Ficha Omnicanal 360°"
        ])

        with sub_rx:
            if not rx_clean.empty:
                rx_clean["Nivel_Mercado"] = rx_clean["MERCADO"].apply(lambda x: f"P{obtener_meta_mercado(x)['prioridad']}")
                col_f_p, col_f_c = st.columns([1.8, 1.2])
                with col_f_p:
                    niv_rx_sel = st.multiselect("Filtrar Prioridad:", ["P1", "P2", "P3"], placeholder="Todas (P1, P2, P3)...")
                with col_f_c:
                    ocultar_ceros = st.checkbox("Solo Pxs > 0", value=True)

                rx_vista = rx_clean[rx_clean["Nivel_Mercado"].isin(niv_rx_sel)].copy() if niv_rx_sel else rx_clean.copy()
                cols_to_show = ["Nivel_Mercado", "MERCADO", "NOMBRE_PRODUCTO"]
                if col_pxs: cols_to_show.append(col_pxs)
                if col_pxs_ytd_prod and col_pxs_ytd_prod not in cols_to_show: cols_to_show.append(col_pxs_ytd_prod)
                if col_mes: cols_to_show.append(col_mes)

                df_rx_view = rx_vista[cols_to_show].copy()
                df_rx_view["Origen"] = df_rx_view["NOMBRE_PRODUCTO"].apply(lambda x: "🔷 GUTIS" if es_gutis(x) else "🔶 COMP")
                if col_mes: df_rx_view[col_mes] = (pd.to_numeric(df_rx_view[col_mes], errors='coerce').fillna(0) * 100).round(1)
                if col_pxs: df_rx_view[col_pxs] = pd.to_numeric(df_rx_view[col_pxs], errors='coerce').fillna(0).astype(int)
                if col_pxs_ytd_prod: df_rx_view[col_pxs_ytd_prod] = pd.to_numeric(df_rx_view[col_pxs_ytd_prod], errors='coerce').fillna(0).astype(int)

                if ocultar_ceros and col_pxs and col_pxs_ytd_prod:
                    df_rx_view = df_rx_view[(df_rx_view[col_pxs] > 0) | (df_rx_view[col_pxs_ytd_prod] > 0)]
                elif ocultar_ceros and col_pxs:
                    df_rx_view = df_rx_view[df_rx_view[col_pxs] > 0]

                sort_cols = [c for c in [col_pxs, col_pxs_ytd_prod] if c]
                if sort_cols: df_rx_view = df_rx_view.sort_values(by=sort_cols, ascending=[False]*len(sort_cols))

                renombrar = {"Nivel_Mercado": "P", "NOMBRE_PRODUCTO": "Marca", "MERCADO": "Mercado", col_pxs: "Mes", col_pxs_ytd_prod: "YTD", col_mes: "% MS"}
                st.dataframe(
                    df_rx_view.rename(columns=renombrar), hide_index=True, use_container_width=True, height=390,
                    column_config={"% MS": st.column_config.ProgressColumn("% MS", format="%.1f%%", min_value=0, max_value=100)}
                )
            else:
                st.info("Sin registros de prescripción para este especialista.")

        with sub_labs:
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
                        total_ytd_med = df_agrupado[col_pxs_ytd].sum()
                        df_agrupado["% MS YTD"] = ((df_agrupado[col_pxs_ytd] / total_ytd_med) * 100).round(2) if total_ytd_med > 0 else 0.0
                        df_agrupado = df_agrupado.sort_values(by=col_pxs_ytd, ascending=False).head(15)
                        df_agrupado["FABRICANTE"] = df_agrupado["FABRICANTE"].apply(lambda x: f"🔷 {x}" if "GUTIS" in str(x).upper() else str(x))
                        df_agrupado[col_pxs_ytd] = df_agrupado[col_pxs_ytd].astype(int)
                        if col_pxs_m_lab: df_agrupado[col_pxs_m_lab] = df_agrupado[col_pxs_m_lab].astype(int)
                        ren_labs = {"FABRICANTE": "Laboratorio", col_pxs_ytd: "Pxs YTD"}
                        if col_pxs_m_lab: ren_labs[col_pxs_m_lab] = "Pxs Mes"
                        st.dataframe(
                            df_agrupado.rename(columns=ren_labs), hide_index=True, use_container_width=True, height=390,
                            column_config={"% MS YTD": st.column_config.ProgressColumn("% MS YTD", format="%.2f%%", min_value=0, max_value=100)}
                        )
                else: st.info("Sin registros de fabricantes para este médico.")

        with sub_360:
            with st.form("form_perfil_360"):
                val_minsa = st.text_input("Código MINSA:", value=str(perfil_360_actual.get("MINSA", "")) if str(perfil_360_actual.get("MINSA", "")) != "nan" else "")
                val_cel = st.text_input("Celular / WhatsApp:", value=str(perfil_360_actual.get("Celular", "")) if str(perfil_360_actual.get("Celular", "")) != "nan" else "")
                val_cumple = st.text_input("Fecha de Cumpleaños:", value=str(perfil_360_actual.get("Cumpleaños", "")) if str(perfil_360_actual.get("Cumpleaños", "")) != "nan" else "")
                val_deporte = st.text_input("Afinidad / Hobby / Rapport:", value=str(perfil_360_actual.get("Deporte", "")) if str(perfil_360_actual.get("Deporte", "")) != "nan" else "")
                opc_visita = ["Ultra-ejecutiva", "Discusión científica", "Casos clínicos"]
                idx_vis = opc_visita.index(perfil_360_actual.get("Estilo_Visita", opc_visita[0])) if perfil_360_actual.get("Estilo_Visita") in opc_visita else 0
                val_estilo_visita = st.selectbox("Estilo de Visita:", opc_visita, index=idx_vis)

                if st.form_submit_button("💠 Guardar y Sincronizar con Canvas TVP", use_container_width=True, type="primary"):
                    nuevo_registro = {
                        "Médico": medico_sel, "MINSA": val_minsa, "Celular": val_cel,
                        "Cumpleaños": val_cumple, "Deporte": val_deporte,
                        "Estilo_Visita": val_estilo_visita, "Ultima_Actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }
                    st.session_state.perfiles_memoria[medico_sel] = nuevo_registro
                    try:
                        if os.path.exists(ARCHIVO_PERFIL_360):
                            df_p_save = pd.read_excel(ARCHIVO_PERFIL_360)
                            df_p_save = df_p_save[df_p_save["Médico"].astype(str).str.upper() != medico_sel]
                            df_p_save = pd.concat([df_p_save, pd.DataFrame([nuevo_registro])], ignore_index=True)
                        else: df_p_save = pd.DataFrame([nuevo_registro])
                        df_p_save.to_excel(ARCHIVO_PERFIL_360, index=False)
                    except: pass
                    st.success("Ficha 360° sincronizada.")

# ==============================================================================
# NÚCLEO III: COPILOTO CHIRA 2.0 & CIERRE POST-VISITA CRM (UNIDAD 9)
# ==============================================================================
with nucleo_copiloto:
    col_chira_main, col_crm_post = st.columns([1.45, 1.0])

    with col_chira_main:
        st.markdown("##### ♟️ [COPILOTO CHIRA 2.0 — CONSOLA MULTIDIMENSIONAL DE INTELIGENCIA COMERCIAL]")
        with st.container(border=True):
            p_c1, p_c2, p_c3, p_c4 = st.columns([1.2, 1.2, 1.2, 0.7])
            with p_c1: chira_ciu_sel = st.selectbox("📍 Territorio:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="ch_ciu")
            with p_c2: chira_esp_sel = st.selectbox("🧬 Especialidad:", ["TODAS LAS ESPECIALIDADES"] + LISTA_ESPECIALIDADES_REALES, key="ch_esp")
            with p_c3: chira_mer_sel = st.selectbox("⚗️ Mercado:", ["TODOS LOS MERCADOS"] + LISTA_MERCADOS_REALES, key="ch_mer")
            with p_c4: chira_top_sel = st.selectbox("🔢 Top:", [5, 10, 15, 20], index=0, key="ch_top")

            b_c1, b_c2, b_c3, b_c4, b_c5, b_c6 = st.columns(6)
            accion_consola = None
            if b_c1.button("⚜️ Penetración", use_container_width=True): accion_consola = "PENETRACION"
            if b_c2.button("⚖️ Sincronía", use_container_width=True): accion_consola = "SINCRONIA"
            if b_c3.button("🧪 Top Labs", use_container_width=True): accion_consola = "LABS"
            if b_c4.button("💠 Pareto 80/20", use_container_width=True): accion_consola = "MEDICOS_PARETO"
            if b_c5.button("⚔️ Conquista", use_container_width=True): accion_consola = "MEDICOS_CONQUISTA"
            if b_c6.button("🔭 No Visitados", use_container_width=True): accion_consola = "MEDICOS_NO_VISITADOS"

        chat_container_chira = st.container(height=340)
        for msg in st.session_state.chira_history:
            with chat_container_chira.chat_message(msg["role"]): st.write(msg["content"])
            
        input_chat_chira = st.chat_input("Consulta libre a Chira (ej: Top 5 laboratorios en Pediatría / Médicos no visitados en Rivas)...")

        if accion_consola or input_chat_chira:
            prio_target = None
            if accion_consola:
                top_n = chira_top_sel
                ciu_target = None if chira_ciu_sel == "TODO MI PANEL" else chira_ciu_sel
                esp_target = None if chira_esp_sel == "TODAS LAS ESPECIALIDADES" else chira_esp_sel
                mer_target = None if chira_mer_sel == "TODOS LOS MERCADOS" else chira_mer_sel
                modo_motor = accion_consola
                pregunta_mostrar = f"[Consola BI] {accion_consola} | Zona: {chira_ciu_sel} | Esp: {chira_esp_sel} | Mercado: {chira_mer_sel}"
            else:
                pregunta_mostrar = input_chat_chira
                texto_norm = normalizar_txt(input_chat_chira)
                match_num = re.search(r'\b(\d+)\b', texto_norm)
                top_n = int(match_num.group(1)) if match_num and 1 <= int(match_num.group(1)) <= 50 else 5

                if "PRIORIDAD 1" in texto_norm: prio_target = 1
                elif "PRIORIDAD 2" in texto_norm: prio_target = 2
                elif "PRIORIDAD 3" in texto_norm: prio_target = 3

                ciu_target = None
                alias_municipios = {"JINOTEPE": "CARAZO", "DIRIAMBA": "CARAZO", "SAN MARCOS": "CARAZO", "NANDAIME": "GRANADA", "NINDIRI": "MASAYA", "SAN JORGE": "RIVAS", "JUIGALPA": "CHONTALES"}
                for c_real in LISTA_CIUDADES_REALES:
                    if normalizar_txt(c_real) in texto_norm: ciu_target = c_real; break
                if not ciu_target:
                    for mun, dep in alias_municipios.items():
                        if mun in texto_norm: ciu_target = next((c for c in LISTA_CIUDADES_REALES if dep in normalizar_txt(c)), dep); break

                esp_target = None
                for e_real in LISTA_ESPECIALIDADES_REALES:
                    e_norm = normalizar_txt(e_real)
                    palabras_esp = [p for p in re.split(r'[\s/,-]+', e_norm) if len(p) >= 4]
                    if e_norm in texto_norm or any(p[:5] in texto_norm for p in palabras_esp): esp_target = e_real; break

                mer_target = None
                for m_real in LISTA_MERCADOS_REALES:
                    if normalizar_txt(m_real.replace("MR ", "")) in texto_norm: mer_target = m_real; break
                if not mer_target:
                    for m_key, m_val in MERCADOS_PRIORITARIOS.items():
                        if any(normalizar_txt(k) in texto_norm for k in m_val["keywords"]):
                            mer_target = next((m for m in LISTA_MERCADOS_REALES if normalizar_txt(m_key) in normalizar_txt(m)), m_key); break

                if any(k in texto_norm for k in ["PENETRACION", "REVISION DEL PANEL", "RENDIMIENTO INTERNO", "TOP 1", "TOP 3"]): modo_motor = "PENETRACION"
                elif any(k in texto_norm for k in ["SINCRONIA", "TENDENCIA", "FUGA", "RECETAS VS", "MEDICO VS"]): modo_motor = "SINCRONIA"
                elif any(k in texto_norm for k in ["NO VISITADO", "NO VISITADOS", "FUERA DE PANEL", "NO ESTA EN MI PANEL", "INCORPORAR", "NUEVOS MEDICOS"]): modo_motor = "MEDICOS_NO_VISITADOS"
                elif any(k in texto_norm for k in ["LABORATORIO", "FABRICANTE", "CASA", "INDUSTRIA"]): modo_motor = "LABS"
                elif any(k in texto_norm for k in ["FARMACIA", "SELL", "SUCURSAL", "PDV"]): modo_motor = "SELLOUT"
                elif any(k in texto_norm for k in ["CONQUISTA", "ROBAR", "ATAQUE", "COMPETENCIA", "OPORTUNIDAD"]): modo_motor = "MEDICOS_CONQUISTA"
                else: modo_motor = "MEDICOS_PARETO"

            st.session_state.chira_history.append({"role": "user", "content": pregunta_mostrar})
            with chat_container_chira.chat_message("user"): st.write(pregunta_mostrar)

            with st.spinner("[CHIRA EJECUTANDO CRUCE RELACIONAL...]"):
                df_panel_sub = df_panel.copy()
                etiqueta_z = ciu_target if ciu_target else "TODO MI PANEL"
                etiqueta_e = esp_target if esp_target else "Todas las Especialidades"
                etiqueta_m = mer_target if mer_target else "Todos los Mercados"

                if ciu_target and "CIUDAD" in df_panel_sub.columns:
                    df_panel_sub = df_panel_sub[df_panel_sub["CIUDAD"].astype(str).str.upper().str.contains(re.escape(ciu_target), na=False)]
                if esp_target and "Especialidad" in df_panel_sub.columns:
                    df_panel_sub = df_panel_sub[df_panel_sub["Especialidad"].astype(str).str.upper() == esp_target.upper()]

                medicos_segmento = set(df_panel_sub["Médico"].dropna().unique())
                num_meds_seg = len(medicos_segmento)

                if modo_motor == "PENETRACION":
                    df_r_ch, df_c_ch = calcular_matriz_penetracion_panel(etiqueta_z)
                    if not df_r_ch.empty:
                        resultado_final = f"### ⚜️ Penetración por Especialidad ({etiqueta_z})\n\n#### 1. Rendimiento Interno YTD:\n{df_a_markdown_nativo(df_r_ch)}\n\n#### 2. Top 5 Competencia Directa:\n{df_a_markdown_nativo(df_c_ch)}"
                    else: resultado_final = f"Sin datos de penetración para {etiqueta_z}."

                elif modo_motor == "SINCRONIA":
                    df_s_ch = calcular_sincronia_rx_vs_sellout(etiqueta_z)
                    if not df_s_ch.empty:
                        resultado_final = f"### ⚖️ Sincronía Temporal: Rx vs. Sell-Out ({etiqueta_z})\n\n{df_a_markdown_nativo(df_s_ch)}"
                    else: resultado_final = f"Sin datos de sincronía para {etiqueta_z}."

                elif modo_motor == "LABS":
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
                            df_rk = df_rk.sort_values(by=col_ord, ascending=False).reset_index(drop=True)
                            df_rk["Pos"] = df_rk.index + 1

                            lineas = [f"### 🧪 Top {top_n} Laboratorios | {etiqueta_e} ({etiqueta_z})"]
                            for _, r_l in df_rk.head(top_n).iterrows():
                                ic = "🔷 **[GUTIS]**" if "GUTIS" in str(r_l["FABRICANTE"]).upper() else "🏛️"
                                lineas.append(f"**{int(r_l['Pos'])}. {r_l['FABRICANTE']}** {ic} — `{int(r_l[col_ord]):,} Pxs YTD` (**{r_l['MS_YTD']:.2f}% MS**) | Prescriptores: {int(r_l['Meds_Activos'])}/{num_meds_seg}")
                            resultado_final = "\n".join(lineas)
                        else: resultado_final = "Sin registros en archivo de laboratorios para ese filtro."
                    else: resultado_final = "Archivo de laboratorios no detectado."

                elif modo_motor == "MEDICOS_NO_VISITADOS":
                    col_pxs_c = next((c for c in df_productos.columns if c.upper() == "PXS-MES"), None)
                    col_ytd_c = next((c for c in df_productos.columns if c.upper() == "PXS-YTD"), None)
                    todos_medicos_panel_erick = set(df_panel["Médico"].dropna().unique())
                    df_fuera = df_productos[~df_productos["Médico"].isin(todos_medicos_panel_erick)].copy()
                    df_fuera = df_fuera[~df_fuera["NOMBRE_PRODUCTO"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
                    if mer_target:
                        kw_m = normalizar_txt(mer_target.replace("MR ", ""))
                        df_fuera = df_fuera[df_fuera["MERCADO"].apply(normalizar_txt).str.contains(re.escape(kw_m), na=False)]
                    if not df_fuera.empty and col_pxs_c:
                        df_fuera[col_pxs_c] = pd.to_numeric(df_fuera[col_pxs_c], errors='coerce').fillna(0)
                        if col_ytd_c: df_fuera[col_ytd_c] = pd.to_numeric(df_fuera[col_ytd_c], errors='coerce').fillna(0)
                        df_fuera["Es_G"] = df_fuera["NOMBRE_PRODUCTO"].apply(es_gutis)
                        candidatos_fuera = []
                        for nom_doc, grp_f in df_fuera.groupby("Médico"):
                            pxs_m = int(grp_f[col_pxs_c].sum())
                            pxs_y = int(grp_f[col_ytd_c].sum()) if col_ytd_c else 0
                            if pxs_m <= 0 and pxs_y <= 0: continue
                            pxs_g = int(grp_f[grp_f["Es_G"]][col_pxs_c].sum())
                            grp_ord = grp_f.sort_values(by=[col_pxs_c], ascending=False)
                            candidatos_fuera.append({
                                "nombre": nom_doc, "pxs_mes": pxs_m, "pxs_ytd": pxs_y,
                                "pxs_comp": pxs_m - pxs_g, "lider_prod": str(grp_ord.iloc[0]["NOMBRE_PRODUCTO"]).strip(),
                                "lider_merc": str(grp_ord.iloc[0]["MERCADO"]).strip()
                            })
                        candidatos_fuera = sorted(candidatos_fuera, key=lambda x: (x["pxs_comp"], x["pxs_ytd"]), reverse=True)
                        lineas = [f"### 🔭 Top {top_n} Médicos Potenciales Fuera de Panel ({etiqueta_m})"]
                        for idx, cf in enumerate(candidatos_fuera[:top_n], 1):
                            lineas.append(f"**{idx}. Dr(a). {cf['nombre']}** — `{cf['pxs_mes']} Pxs-MES` (Comp: **{cf['pxs_comp']}** | YTD: `{cf['pxs_ytd']}`) | Líder: `{cf['lider_prod']}` ({cf['lider_merc']})")
                        resultado_final = "\n".join(lineas) if candidatos_fuera else "Sin candidatos fuera de panel para este filtro."
                    else: resultado_final = "Sin registros fuera de panel."

                else:
                    col_pxs_c = next((c for c in df_productos.columns if c.upper() == "PXS-MES"), None)
                    col_ytd_c = next((c for c in df_productos.columns if c.upper() == "PXS-YTD"), None)
                    df_rx_sub = df_productos[df_productos["Médico"].isin(medicos_segmento)].copy()
                    df_rx_sub = df_rx_sub[~df_rx_sub["NOMBRE_PRODUCTO"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
                    if mer_target:
                        kw_m = normalizar_txt(mer_target.replace("MR ", ""))
                        df_rx_sub = df_rx_sub[df_rx_sub["MERCADO"].apply(normalizar_txt).str.contains(re.escape(kw_m), na=False)]
                    ranking_medicos = []
                    if not df_rx_sub.empty and col_pxs_c:
                        df_rx_sub[col_pxs_c] = pd.to_numeric(df_rx_sub[col_pxs_c], errors='coerce').fillna(0)
                        if col_ytd_c: df_rx_sub[col_ytd_c] = pd.to_numeric(df_rx_sub[col_ytd_c], errors='coerce').fillna(0)
                        df_rx_sub["Es_G"] = df_rx_sub["NOMBRE_PRODUCTO"].apply(es_gutis)
                        info_panel_map = df_panel_sub.drop_duplicates(subset=["Médico"]).set_index("Médico").to_dict("index")
                        for nom_doc, grp_doc in df_rx_sub.groupby("Médico"):
                            pxs_mes_tot = int(grp_doc[col_pxs_c].sum())
                            pxs_ytd_tot = int(grp_doc[col_ytd_c].sum()) if col_ytd_c else 0
                            if pxs_mes_tot <= 0 and pxs_ytd_tot <= 0: continue
                            pxs_gut = int(grp_doc[grp_doc["Es_G"]][col_pxs_c].sum())
                            grp_ord = grp_doc.sort_values(by=[col_pxs_c], ascending=False)
                            meta_doc = info_panel_map.get(nom_doc, {})
                            ranking_medicos.append({
                                "nombre": nom_doc, "especialidad": str(meta_doc.get("Especialidad", "N/D")),
                                "ciudad": str(meta_doc.get("CIUDAD", "N/D")), "pxs_totales": pxs_mes_tot,
                                "pxs_ytd": pxs_ytd_tot, "gutis_pxs": pxs_gut, "comp_pxs": pxs_mes_tot - pxs_gut,
                                "lider_producto": str(grp_ord.iloc[0]["NOMBRE_PRODUCTO"]).strip()
                            })
                    criterio_orden = "comp_pxs" if modo_motor == "MEDICOS_CONQUISTA" else "pxs_totales"
                    ranking_medicos = sorted(ranking_medicos, key=lambda x: (x[criterio_orden], x["pxs_ytd"]), reverse=True)
                    if ranking_medicos:
                        lineas = [f"### 💠 Top {top_n} Especialistas | {etiqueta_z} ({etiqueta_m})"]
                        for idx, m_i in enumerate(ranking_medicos[:top_n], 1):
                            lineas.append(f"**{idx}. Dr(a). {m_i['nombre']}** ({m_i['especialidad']} | {m_i['ciudad']}) — Mes: `{m_i['pxs_totales']} Pxs` (🔷 Gutis: {m_i['gutis_pxs']} | ⚔️ Comp: **{m_i['comp_pxs']}**) | YTD: `{m_i['pxs_ytd']}` | Líder: `{m_i['lider_producto']}`")
                        resultado_final = "\n".join(lineas)
                    else: resultado_final = "Sin registros activos para la combinación seleccionada."

            st.session_state.chira_history.append({"role": "assistant", "content": resultado_final})
            st.rerun()

    # COLUMNA DERECHA: UNIDAD 9 POST-VISITA Y BITÁCORA CRM
    with col_crm_post:
        st.markdown(f"##### 📜 [UNIDAD 9: ANÁLISIS POST-VISITA & CRM — {medico_sel[:18]}]")
        with st.form("form_bitacora_crm"):
            cb1, cb2 = st.columns(2)
            with cb1: prod_promovido = st.selectbox("1. Producto Foco (P1):", [m["producto"] for m in MERCADOS_PRIORITARIOS.values()])
            with cb2: prod_puente = st.selectbox("2. Producto Puente (P2/P3):", ["Ninguno"] + [m["producto"] for m in MERCADOS_PRIORITARIOS.values()], index=2)
            cb3, cb4 = st.columns(2)
            with cb3: resultado_obj = st.selectbox("3. Resultado SMART:", ["Objetivo Principal Logrado", "Objetivo de Respaldo Logrado", "Seguimiento Pendiente"])
            with cb4: escala_post = st.selectbox("4. Escalón Alcanzado:", ["1. No Consciente", "2. Consciente", "3. Prueba (2-10 Pxs)", "4. Adopción (25-50%)", "5. Lealtad (>50%)"])
            compromiso_med = st.text_input("Compromiso del Médico:", value="Iniciar en próximos 3-5 pacientes")
            compromiso_vis = st.text_input("Compromiso Visitador:", value=f"Garantizar stock en {top_farmacias_ciudad_str.split(',')[0]}")
            notas_visita = st.text_area("Notas para Apertura de Próxima Visita:", height=68, placeholder="Necesidad detectada u objeción resuelta hoy...")

            if st.form_submit_button("⛓️ Registrar Cierre de Ciclo en Bitácora CRM", use_container_width=True, type="primary"):
                nueva_visita = {
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "Ciudad": ciudad, "Médico": medico_sel,
                    "Especialidad": especialidad, "Producto_Foco": prod_promovido, "Producto_Puente": prod_puente,
                    "Logro_SMART": resultado_obj, "Escala_TVP": escala_post,
                    "Acuerdo_Medico": compromiso_med, "Acuerdo_Visitador": compromiso_vis, "Notas": notas_visita
                }
                st.session_state.bitacora_memoria.append(nueva_visita)
                try:
                    if os.path.exists(ARCHIVO_BITACORA):
                        df_bit_old = pd.read_excel(ARCHIVO_BITACORA)
                        df_bit_new = pd.concat([df_bit_old, pd.DataFrame([nueva_visita])], ignore_index=True)
                    else: df_bit_new = pd.DataFrame([nueva_visita])
                    df_bit_new.to_excel(ARCHIVO_BITACORA, index=False)
                except: pass
                st.success("Visita registrada en CRM.")

        df_hist_crm = pd.DataFrame(st.session_state.bitacora_memoria)
        if os.path.exists(ARCHIVO_BITACORA):
            try: df_hist_crm = pd.read_excel(ARCHIVO_BITACORA)
            except: pass
        if not df_hist_crm.empty:
            st.dataframe(df_hist_crm.tail(8), hide_index=True, use_container_width=True, height=180)
            csv_crm = df_hist_crm.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 Exportar Bitácora CRM (CSV)", data=csv_crm, file_name=f"CRM_TVP_Gutis_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)
