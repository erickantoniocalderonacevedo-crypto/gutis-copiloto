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
    page_title="Gutis BI | Terminal Comercial TVP",
    page_icon="🏢",
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

# --- CONVERSOR NATIVO DE TABLAS A MARKDOWN (ELIMINA EL ERROR DE 'TABULATE') ---
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

# --- MATRIZ COMPLETA DE MERCADOS (PRIORIDAD 1, 2 Y 3 CON ATRIBUTOS CLÍNICOS Y STORYTELLING) ---
MERCADOS_PRIORITARIOS = {
    "MR TALERDIN": {
        "producto": "Talerdín", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Foco Core)",
        "keywords": ["TALERDIN", "CETIRIZINA", "CETRILER", "ALERCET", "DEGRALER"],
        "paciente_meta": "Pacientes pediátricos y adultos con rinitis alérgica o urticaria que requieren alivio rápido sin sedación ni irritación.",
        "caracteristica": "Cetirizina 100% libre de alcohol, libre de azúcar y con gotero de dosificación exacta pediátrica.",
        "beneficio": "Garantiza apego total al tratamiento pediátrico sin rechazo por sabor ni efectos adversos por excipientes alcohólicos.",
        "love_brand": "Tranquilidad nocturna para el niño y los padres desde la primera toma, protegiendo su desarrollo diario."
    },
    "MR BIOTOS": {
        "producto": "Biotos Inmune", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Foco Core)",
        "keywords": ["BIOTOS", "HEDERA", "PELARGONIUM", "ABRILAR", "TUSILEXIL"],
        "paciente_meta": "Pacientes desde los 2 años y adultos con IVRS virales, tos productiva y dificultad para manejar secreciones.",
        "caracteristica": "Combinación fitofarmacológica dual única de Hedera helix + Pelargonium sidoides.",
        "beneficio": "Cuádruple acción (mucolítica, broncodilatadora, expectorante e inmunomoduladora) que acorta el cuadro viral y previene sobreinfección bacteriana.",
        "love_brand": "En Gutis estamos orgullosos de devolverle la respiración libre a las familias con evidencia clínica natural."
    },
    "MR CLEMBROXIL": {
        "producto": "Clembroxil Compuesto", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Foco Core)",
        "keywords": ["CLEMBROXIL", "CLENBUTEROL", "AMBROXOL", "MUCOSOLVAN"],
        "paciente_meta": "Pacientes con broncoespasmo, bronquitis aguda o crónica y retención severa de moco en vías respiratorias.",
        "caracteristica": "Sinergia exacta de Ambroxol (mucolítico mucocinético) + Clenbuterol (broncodilatador selectivo B2).",
        "beneficio": "Despeja las vías aéreas dilatando el bronquio mientras fluidifica el moco espeso, facilitando la ventilación inmediata.",
        "love_brand": "Respaldo respiratorio contundente cuando el paciente siente que le falta el aire."
    },
    "MR MOMETZONA": {
        "producto": "Mometzona", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Foco Core)",
        "keywords": ["MOMETZONA", "MOMETASONA", "NASONEX", "GAMMAFLUX"],
        "paciente_meta": "Pacientes con rinitis alérgica estacional o perenne, congestión nasal persistente o pólipos nasales.",
        "caracteristica": "Furoato de Mometasona en suspensión acuosa nasal 100% libre de alcohol con válvula dosificadora de micro-nebulización.",
        "beneficio": "Potente control antiinflamatorio local sin resecar ni irritar la mucosa nasal y con biodisponibilidad sistémica insignificante (<0.1%).",
        "love_brand": "Descongestionar y devolver el descanso reparador sin ardor nasal."
    },
    "MR VENTILAR": {
        "producto": "Ventilar", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Foco Core)",
        "keywords": ["VENTILAR", "MONTELUKAST", "SINGULAIR", "AIRUM", "SUVIAR"],
        "paciente_meta": "Pacientes pediátricos y adultos con asma persistente, broncoespasmo inducido por ejercicio o rinitis alérgica.",
        "caracteristica": "Montelukast sódico de alta pureza galénica en tabletas masticables pediátricas y recubiertas de una toma diaria.",
        "beneficio": "Bloqueo selectivo de leucotrienos que previene las crisis respiratorias y reduce el uso de corticoides de rescate.",
        "love_brand": "Libertad para que el paciente pediátrico juegue y respire sin miedo a una crisis nocturna."
    },
    "MR GASTROALIVIO": {
        "producto": "Gastroalivio", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Foco Core)",
        "keywords": ["GASTROALIVIO", "ESOMEPRAZOL", "CARBUM", "NEXIUM"],
        "paciente_meta": "Pacientes adultos con ERGE, esofagitis erosiva, úlcera péptica o gastropatía por AINEs.",
        "caracteristica": "Esomeprazol con tecnología avanzada de micropellets gastrorresistentes.",
        "beneficio": "Mayor superficie de absorción en microvellosidades intestinales, ofreciendo inicio de acción más rápido y supresión ácida sostenida por 24 horas.",
        "love_brand": "Innovación galénica que protege el estómago del paciente desde la primera cápsula."
    },
    "MR DALIVIO": {
        "producto": "Dalivio", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Foco Core)",
        "keywords": ["DALIVIO", "DALIVIUM", "DEXKETOPROFENO", "ENANTYUM", "STADIUM", "CETIX"],
        "paciente_meta": "Pacientes con dolor agudo de moderado a severo (musculoesquelético, odontalgia, dismenorrea o postquirúrgico).",
        "caracteristica": "Dexketoprofeno trometamol (enantiómero activo S+) de rápida absorción disponible en bebible/sobre y tabletas.",
        "beneficio": "Alivio analgésico explosivo desde los primeros 10-15 minutos con la mitad de la carga metabólica y menor riesgo gástrico.",
        "love_brand": "Imagínese aliviar a su paciente del dolor agudo en solo 10 minutos para que recupere su día."
    },
    "MR VALERPAN": {
        "producto": "Valerpan", "peso": 2, "prioridad": 2, "categoria_mercado": "Prioridad 2 (Expansión)",
        "keywords": ["VALERPAN", "BETAMETASONA", "CELESTONE", "DIPROSPAN", "DEXAMETASONA"],
        "paciente_meta": "Pacientes con cuadros inflamatorios agudos, alérgicos severos o patologías osteomusculares que requieren corticoterapia de depósito.",
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
        "caracteristica": "Mupirocina tópica al 2% con mecanismo específico de inhibición de síntesis proteica bacteriana.",
        "beneficio": "Erradicación rápida de Staphylococcus aureus y Streptococcus pyogenes sin resistencia cruzada con otros antibióticos.",
        "love_brand": "Seguridad dermatológica confiable que protege la piel de toda la familia."
    },
    "MR BICORPAN": {
        "producto": "Bicorpan", "peso": 2, "prioridad": 2, "categoria_mercado": "Prioridad 2 (Expansión)",
        "keywords": ["BICORPAN"],
        "paciente_meta": "Pacientes con dermatomicosis acompañadas de inflamación y prurito intenso.",
        "caracteristica": "Fórmula tópica combinada antimicótica y antiinflamatoria de alta penetración cutánea.",
        "beneficio": "Corta el prurito y el eritema desde el primer día mientras erradica el hongo causal, evitando el rascado y sobreinfección.",
        "love_brand": "Alivio visible y rápido en infecciones dérmicas complejas."
    },
    "MR FEMGYL": {
        "producto": "Femgyl", "peso": 1, "prioridad": 3, "categoria_mercado": "Prioridad 3 (Especialidad / Complemento)",
        "keywords": ["FEMGYL"],
        "paciente_meta": "Pacientes ginecológicas con infecciones vaginales mixtas (candidiasis, vaginosis bacteriana o tricomoniasis).",
        "caracteristica": "Terapia ginecológica de amplio espectro de acción local efectiva.",
        "beneficio": "Resolución clínica integral desde las primeras aplicaciones, restaurando el bienestar íntimo de la paciente.",
        "love_brand": "Contribución fundamental de Gutis para el cuidado y bienestar de la salud femenina."
    },
    "MR NORGYLEN": {
        "producto": "Norgylen", "peso": 1, "prioridad": 3, "categoria_mercado": "Prioridad 3 (Especialidad / Complemento)",
        "keywords": ["NORGYLEN"],
        "paciente_meta": "Pacientes en edad reproductiva que requieren planificación familiar hormonal segura y confiable.",
        "caracteristica": "Formulación anticonceptiva hormonal balanceada de alta eficacia clínica.",
        "beneficio": "Excelente control del ciclo menstrual con alta seguridad y tolerabilidad.",
        "love_brand": "Confianza y respaldo en cada etapa de la planificación familiar."
    },
    "MR ANSIOLIT": {
        "producto": "Ansiolit", "peso": 1, "prioridad": 3, "categoria_mercado": "Prioridad 3 (Especialidad / Complemento)",
        "keywords": ["ANSIOLIT"],
        "paciente_meta": "Pacientes adultos con trastornos de ansiedad generalizada, tensión emocional o insomnio asociado a ansiedad.",
        "caracteristica": "Ansiolítico de perfil farmacocinético predecible y dosificación adaptable.",
        "beneficio": "Control efectivo de los síntomas somáticos y psíquicos de la ansiedad, estabilizando al paciente rápidamente.",
        "love_brand": "Equilibrio emocional y paz mental respaldados por la calidad farmacéutica de Gutis."
    },
    "MR DEPAX": {
        "producto": "Depax", "peso": 1, "prioridad": 3, "categoria_mercado": "Prioridad 3 (Especialidad / Complemento)",
        "keywords": ["DEPAX"],
        "paciente_meta": "Pacientes con trastornos depresivos o de ansiedad que requieren bioequivalencia comprobada.",
        "caracteristica": "Antidepresivo con estudio de Bioequivalencia certificado que garantiza eficacia idéntica al innovador.",
        "beneficio": "Estabilidad terapéutica continua a un costo accesible para el cumplimiento a largo plazo.",
        "love_brand": "Calidad bioequivalente comprobada para acompañar la recuperación emocional del paciente."
    },
    "MR FELICITAT": {
        "producto": "Felicitat", "peso": 1, "prioridad": 3, "categoria_mercado": "Prioridad 3 (Especialidad / Complemento)",
        "keywords": ["FELICITAT", "ESCITALOPRAM"],
        "paciente_meta": "Pacientes con depresión mayor o trastorno de ansiedad que buscan mejoría sostenida sin efectos secundarios molestos.",
        "caracteristica": "Escitalopram con interacción dual única en el transportador SERT (sitio primario y alostérico).",
        "beneficio": "Inhibición más selectiva y eficaz de la recaptación de serotonina, logrando una mejoría clínica sostenida.",
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
   - Escala de Adopción de la Marca: 1. No Consciente (0% MS), 2. Consciente (0% MS pero conoce), 3. Prueba (2 a 10 Pxs o >0% y <=25% MS), 4. Adopción (>25% a 50% MS), 5. Lealtad (>50% MS).
   - En la APERTURA está PROHIBIDO mencionar el nombre del producto y abusar del "Yo"; debe proponerse una Agenda centrada en el paciente, comunicar el Valor de la Agenda y Confirmar Aceptación.
   - En DESCUBRIR NECESIDADES se usa la Técnica del Embudo para explorar: Circunstancias -> Necesidad -> Necesidad detrás de la Necesidad (Finanzas, Desempeño o Imagen) usando Sondeos de Valor Mutuo.
   - En APOYO/STORYTELLING: 1) Demostrar comprensión de la necesidad, 2) Característica + Beneficio vinculado a la Necesidad detrás de la Necesidad + Love Brands, 3) Confirmar aceptación.
   - En CIERRE/PUENTE: 1) Resumir beneficios aceptados, 2) Pedir compromiso mutuo, 3) Confirmar aceptación, 4) Hacer PUENTE natural hacia el 2do y 3er producto.
"""

# --- ESTILOS CSS ELEGANTES Y PREMIUM ---
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
    h1, h2, h3, h4, h5 { color: #0f172a; font-weight: 700; letter-spacing: -0.3px; }
    .metric-card { background-color: #ffffff; border-radius: 8px; padding: 18px; border-left: 5px solid #1e3a8a; box-shadow: 0 2px 8px rgba(0,0,0,0.04); margin-bottom: 12px; }
    .metric-title { color: #64748b; font-size: 0.72rem; text-transform: uppercase; font-weight: 800; margin-bottom: 5px; letter-spacing: 0.8px; }
    .metric-value { color: #0f172a; font-size: 1.45rem; font-weight: 800; }
    .tvp-box { background-color: #ffffff; border: 1px solid #e2e8f0; border-left: 5px solid #0284c7; border-radius: 8px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.03); }
    .elite-header { background: linear-gradient(90deg, #0f172a 0%, #1e3a8a 100%); color: #f8fafc; padding: 12px 18px; border-radius: 8px; margin-bottom: 12px; border-left: 5px solid #eab308; font-weight: 800; }
    .stTabs [data-baseweb="tab-list"] { border-bottom: 2px solid #e2e8f0; gap: 5px; padding-bottom: 0; }
    .stTabs [data-baseweb="tab"] { font-size: 0.82rem; font-weight: 700; color: #475569; padding: 9px 14px; border-radius: 6px 6px 0 0; background-color: #f1f5f9; border: 1px solid transparent; border-bottom: none; }
    .stTabs [aria-selected="true"] { color: #ffffff; background-color: #1e3a8a; box-shadow: inset 0 -3px 0 #38bdf8; }
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
    <h2 style='color: #ffffff; margin: 0; font-size: 1.7rem; letter-spacing: 0.5px; font-weight: 800;'>[GUTIS BI] - TERMINAL DE INTELIGENCIA COMERCIAL & MODELO TVP</h2>
    <p style='color: #93c5fd; margin: 0; font-size: 0.82rem; text-transform: uppercase; font-weight: 600; margin-top: 5px; letter-spacing: 1px;'>Penetración por Especialidad, Sincronía Rx vs. Sell-Out y Técnica de Ventas Profesionales</p>
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

cats_sb = ["TODAS"] + sorted([str(c) for c in df_filtrado["CATEGORIA"].dropna().unique() if str(c).strip() not in ["", "NAN"]]) if "CATEGORIA" in df_filtrado.columns else ["TODAS"]
cat_filtro_sb = st.sidebar.selectbox("3. Categoría Médica:", cats_sb)
if cat_filtro_sb != "TODAS" and "CATEGORIA" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["CATEGORIA"].astype(str) == cat_filtro_sb]

lista_medicos = sorted(df_filtrado["Médico"].dropna().unique().tolist())

if not lista_medicos:
    st.warning("[SISTEMA] No existen registros para la combinación seleccionada.")
    st.stop()

medico_sel = st.sidebar.selectbox("4. Médico Objetivo:", lista_medicos)

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

# --- FUNCIONES DE CLASIFICACIÓN DE PRODUCTOS Y MERCADOS (SIN TILDES Y MULTI-FORMATO) ---
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
        "peso": 1, "prioridad": 3, "categoria_mercado": "Prioridad 3 (Complementario)",
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
        return "2. Consciente (0% MS Gutis)", "3. Prueba (2 a 10 nuevos pacientes)", f"Lograr que el médico inicie un período de prueba en sus próximos 3 a 5 pacientes (actualmente entrega {pxs_tot_m} Pxs a la competencia)."
    if ms_gutis_m < 25.0 or pxs_gutis_m <= 10:
        return f"3. Prueba ({ms_gutis_m:.1f}% MS | {pxs_gutis_m} Pxs)", "4. Adopción (>25% a 50% MS)", "Explorar los resultados positivos de los pacientes en prueba para expandir el uso hacia el >25% de sus casos."
    if ms_gutis_m <= 50.0:
        return f"4. Adopción ({ms_gutis_m:.1f}% MS | {pxs_gutis_m} Pxs)", "5. Lealtad (>50% MS)", "Consolidar la marca como primera elección en más del 50% de sus pacientes meta."
    return f"5. Lealtad ({ms_gutis_m:.1f}% MS | {pxs_gutis_m} Pxs)", "5. Lealtad (Blindaje y Promotor)", "Blindar su lealtad ante la competencia y convertirlo en médico promotor de la marca."

# --- FUNCIÓN MOTOR 1: MATRIZ DE PENETRACIÓN POR ESPECIALIDAD Y TOP 5 COMPETENCIA ---
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

    filas_rendimiento = []
    filas_competencia = []

    for esp_nom, grp_esp in df_p_sub.groupby("Especialidad"):
        meds_panel_esp = set(grp_esp["Médico"].dropna().unique())
        num_panel = len(meds_panel_esp)
        if num_panel == 0:
            continue

        if usar_labs and col_ytd_l:
            df_l_esp = df_l_clean[df_l_clean["Médico"].isin(meds_panel_esp)].copy()
            df_l_esp_act = df_l_esp[df_l_esp[col_ytd_l] > 0]
            meds_captados = set(df_l_esp_act["Médico"].unique())

            if not df_rx_c.empty and col_ytd_rx:
                meds_cap_rx = set(df_rx_c[(df_rx_c["Médico"].isin(meds_panel_esp)) & (df_rx_c[col_ytd_rx] > 0)]["Médico"].unique())
                meds_captados = meds_captados.union(meds_cap_rx)

            num_captados = len(meds_captados)
            recetan_gutis_count = 0
            top1_count = 0
            top3_count = 0

            for m_doc in meds_captados:
                sub_m = df_l_esp_act[df_l_esp_act["Médico"] == m_doc]
                if not sub_m.empty:
                    rk_m = sub_m.groupby("FABRICANTE")[col_ytd_l].sum().reset_index().sort_values(by=col_ytd_l, ascending=False).reset_index(drop=True)
                    rk_m["Rank"] = rk_m.index + 1
                    fila_g_m = rk_m[rk_m["FABRICANTE"].astype(str).str.upper().str.contains("GUTIS", na=False)]
                    if not fila_g_m.empty and fila_g_m.iloc[0][col_ytd_l] > 0:
                        recetan_gutis_count += 1
                        r_pos = int(fila_g_m.iloc[0]["Rank"])
                        if r_pos == 1:
                            top1_count += 1
                        if r_pos <= 3:
                            top3_count += 1
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
                        marca_f = f"🟢 {nom_f} ({ms_f:.2f}%)" if "GUTIS" in nom_f.upper() else f"{nom_f} ({ms_f:.2f}%)"
                        top5_strs.append(marca_f)
                    else:
                        top5_strs.append("-")
            else:
                ms_gutis_ytd = 0.0
                top5_strs = ["-", "-", "-", "-", "-"]

            filas_rendimiento.append({
                "ESPECIALIDAD": esp_nom,
                "PANEL": num_panel,
                "CAPTADOS": num_captados,
                "RECETAN GUTIS": recetan_gutis_count,
                "PENETRACIÓN": round(penetracion_pct, 2),
                "TOP 1": top1_count,
                "TOP 3": top3_count,
                "%MS-YTD": round(ms_gutis_ytd, 2)
            })

            filas_competencia.append({
                "ESPECIALIDAD": esp_nom,
                "#1": top5_strs[0],
                "#2": top5_strs[1],
                "#3": top5_strs[2],
                "#4": top5_strs[3],
                "#5": top5_strs[4],
                "_orden": num_panel
            })

    df_rend = pd.DataFrame(filas_rendimiento).sort_values(by="PANEL", ascending=False) if filas_rendimiento else pd.DataFrame()
    df_comp = pd.DataFrame(filas_competencia).sort_values(by="_orden", ascending=False).drop(columns=["_orden"]) if filas_competencia else pd.DataFrame()
    return df_rend, df_comp

# --- FUNCIÓN MOTOR 2: CRUCE DE TENDENCIAS EN EL TIEMPO (RX MÉDICO VS. VENTA EN FARMACIA) ---
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
    if not df_rx_sub.empty and col_pxs_m:
        df_rx_sub[col_pxs_m] = pd.to_numeric(df_rx_sub[col_pxs_m], errors='coerce').fillna(0)
    if not df_rx_sub.empty and col_pxs_y:
        df_rx_sub[col_pxs_y] = pd.to_numeric(df_rx_sub[col_pxs_y], errors='coerce').fillna(0)

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
        if kw_venta == "DALIVIO":
            patron_v = "DALIVIO|DALIVIUM"
        elif kw_venta in ["TALERDÍN", "TALERDIN"]:
            patron_v = "TALERDIN|TALERDÍN"
        elif kw_venta == "CONFLEXIL":
            patron_v = "CONFLEXIL|CONRELAX"
        else:
            patron_v = re.escape(kw_venta)

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
                v_q1 = float(q_sums.get("Q1", 0.0))
                v_q2 = float(q_sums.get("Q2", 0.0))
                v_q3 = float(q_sums.get("Q3", 0.0))

        v_total = v_q1 + v_q2 + v_q3
        delta_so_pct = ((v_q3 - v_q2) / v_q2 * 100) if v_q2 > 0 else (100.0 if v_q3 > 0 else 0.0)

        if pxs_ytd_tot == 0 and pxs_mes_tot == 0 and v_total == 0:
            continue

        if delta_ms_rx >= 1.5 or (pxs_mes_gut > (pxs_ytd_gut / 8.0) and pxs_mes_gut > 0):
            tend_rx_str = f"📈 Crece Rx ({delta_ms_rx:+.1f}% MS)"
            rx_crece = True
        elif delta_ms_rx <= -1.5:
            tend_rx_str = f"📉 Cae Rx ({delta_ms_rx:+.1f}% MS)"
            rx_crece = False
        else:
            tend_rx_str = f"➖ Estable ({delta_ms_rx:+.1f}% MS)"
            rx_crece = (ms_mes_gut >= 15.0 or pxs_mes_gut > 0)

        if delta_so_pct >= 5.0:
            tend_so_str = f"🟢 Sube +{delta_so_pct:.1f}%"
            so_crece = True
        elif delta_so_pct <= -10.0:
            tend_so_str = f"🔴 Cae {delta_so_pct:.1f}%"
            so_crece = False
        else:
            tend_so_str = f"🟡 Estable ({delta_so_pct:+.1f}%)"
            so_crece = True if v_q3 > 0 else False

        if rx_crece and so_crece:
            diag_sinc = "🟢 SINCRONÍA POSITIVA (Crece Médico y Crece Farmacia)"
        elif rx_crece and not so_crece:
            diag_sinc = "🚨 ALERTA DE FUGA EN MOSTRADOR (Médico receta más, pero cae Farmacia)"
        elif not rx_crece and so_crece:
            diag_sinc = "⚠️ EMPUJE COMERCIAL SIN TRACCIÓN RX (Sube Farmacia, reforzar visita médica)"
        else:
            diag_sinc = "🔴 CONTRACCIÓN DOBLE (Reactivar TVP en consultorio y PDV)"

        filas_sincronia.append({
            "Prioridad": f"P{m_info['prioridad']}",
            "Marca Gutis": prod_nom,
            "Pxs Gutis (YTD / Mes)": f"{pxs_ytd_gut} / {pxs_mes_gut}",
            "% MS YTD": round(ms_ytd_gut, 2),
            "% MS MES": round(ms_mes_gut, 2),
            "Evolución Receta (Rx)": tend_rx_str,
            "Sell-Out Q1": round(v_q1, 2),
            "Sell-Out Q2": round(v_q2, 2),
            "Sell-Out Q3": round(v_q3, 2),
            "Evolución Farmacia (Q3 vs Q2)": tend_so_str,
            "Diagnóstico de Sincronía (Rx vs. Farmacia)": diag_sinc,
            "_orden_p": m_info["prioridad"],
            "_orden_v": v_total
        })

    df_sinc = pd.DataFrame(filas_sincronia)
    if not df_sinc.empty:
        df_sinc = df_sinc.sort_values(by=["_orden_p", "_orden_v"], ascending=[True, False]).drop(columns=["_orden_p", "_orden_v"])
    return df_sinc

# --- PROCESAMIENTO MULTI-MERCADO DEL MÉDICO SELECCIONADO ---
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
        lider_pxs = int(lider[col_pxs]) if col_pxs else 0

        escala_act, escala_meta, obj_escala = diagnosticar_escala_adopcion(pxs_gut_m, pxs_tot_m, ms_gut_m)

        if pxs_tot_m > 0 or pxs_ytd_m > 0 or lider_ms > 0:
            opciones_mercados_medico.append({
                "mercado": m_nom, "prioridad": prio_num, "categoria_mercado": cat_merc_txt,
                "lider_actual": lider_nombre, "lider_es_gutis": lider_es_gutis, "prod_gutis": prod_gutis_esperado,
                "pxs_totales": pxs_tot_m, "pxs_ytd": pxs_ytd_m, "pxs_gutis": pxs_gut_m, "pxs_comp": pxs_comp_m,
                "ms_lider": lider_ms, "ms_gutis": ms_gut_m, "escala_actual": escala_act,
                "escala_meta": escala_meta, "objetivo_escala": obj_escala, "meta_info": meta
            })

    # Ordenar primero por los mercados con pacientes activos en el mes, luego Prioridad (P1->P2->P3) y luego YTD
    opciones_mercados_medico = sorted(opciones_mercados_medico, key=lambda x: (-x["pxs_totales"], x["prioridad"], -x["pxs_ytd"]))
    num_mercados = len(opciones_mercados_medico)

    if opciones_mercados_medico:
        prim = opciones_mercados_medico[0]
        mercado_principal_str = prim["mercado"]
        producto_ataque_str = prim["lider_actual"]
        prod_gutis_ataque_oficial = prim["prod_gutis"]
        share_lider = prim["ms_lider"]

    for item_m in opciones_mercados_medico:
        m = item_m["mercado"]
        badge_p = f"P{item_m['prioridad']}"
        color_p = "#1e3a8a" if item_m["prioridad"] == 1 else ("#0284c7" if item_m["prioridad"] == 2 else "#64748b")
        if not item_m["lider_es_gutis"]:
            cards_ataque_html += f"""<div style="background: linear-gradient(180deg, #fff1f2 0%, #ffffff 100%); border: 1px solid #fecdd3; border-top: 4px solid #e11d48; border-radius: 6px; padding: 11px; min-width: 215px; flex: 1 1 calc(25% - 15px);"><div style="display:flex; justify-content:space-between; align-items:center;"><span style="font-size: 0.65rem; font-weight: 800; color: #9f1239;">{m.replace('MR ', '')}</span><span style="background:{color_p}; color:white; font-size:0.6rem; padding:2px 6px; border-radius:4px; font-weight:700;">{badge_p}</span></div><div style="font-size: 0.85rem; color: #0f172a; margin: 4px 0;">Líder: <b style="color:#be123c;">{item_m['lider_actual'][:15]}</b></div><div style="font-size: 0.74rem; color: #475569;">Pxs Mes: <b>{item_m['pxs_totales']}</b> (Comp: {item_m['pxs_comp']}) | YTD: {item_m['pxs_ytd']}</div><div style="font-size: 0.7rem; color: #334155; margin-top:3px;">Escala: <b>{item_m['escala_actual'].split('(')[0]}</b></div><div style="margin-top: 5px; font-size: 0.73rem; font-weight: 800; color: #047857; border-top: 1px dashed #cbd5e1; padding-top: 4px;">➔ Atacar con {item_m['prod_gutis']}</div></div>"""
        else:
            cards_ataque_html += f"""<div style="background: linear-gradient(180deg, #ecfdf5 0%, #ffffff 100%); border: 1px solid #a7f3d0; border-top: 4px solid #059669; border-radius: 6px; padding: 11px; min-width: 215px; flex: 1 1 calc(25% - 15px);"><div style="display:flex; justify-content:space-between; align-items:center;"><span style="font-size: 0.65rem; font-weight: 800; color: #065f46;">{m.replace('MR ', '')}</span><span style="background:{color_p}; color:white; font-size:0.6rem; padding:2px 6px; border-radius:4px; font-weight:700;">{badge_p}</span></div><div style="font-size: 0.85rem; color: #0f172a; margin: 4px 0;">Dominio: <b style="color:#047857;">{item_m['prod_gutis']}</b></div><div style="font-size: 0.74rem; color: #475569;">Pxs Mes: <b>{item_m['pxs_totales']}</b> (Gutis: {item_m['pxs_gutis']}) | YTD: {item_m['pxs_ytd']}</div><div style="font-size: 0.7rem; color: #334155; margin-top:3px;">Escala: <b>{item_m['escala_actual'].split('(')[0]}</b></div><div style="margin-top: 5px; font-size: 0.73rem; font-weight: 800; color: #047857; border-top: 1px dashed #cbd5e1; padding-top: 4px;">[AVANZAR EN ADOPCIÓN]</div></div>"""

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

# --- CONSTRUCTOR DEL PLAN TVP OFICIAL GUTIS PASO A PASO ---
def construir_plan_tvp_gutis(med_nombre, esp_med, cat_med, ciu_med, m1, m2, m3, tipo_cita, necesidad_profunda, rapport_str, farmacias_str):
    meta1 = m1["meta_info"]
    prod1, comp1, merc1 = m1["prod_gutis"], m1["lider_actual"], m1["mercado"]
    escala_act1, escala_meta1 = m1["escala_actual"], m1["escala_meta"]

    if m2:
        prod2, comp2, merc2, cat_m2 = m2["prod_gutis"], m2["lider_actual"], m2["mercado"], m2["categoria_mercado"]
        caract2, benef2 = m2["meta_info"]["caracteristica"], m2["meta_info"]["beneficio"]
    else:
        prod2, comp2, merc2, cat_m2 = "Conflexil / Valerpan", "Competencia", "Mercado Secundario", "Prioridad 2 (Expansión)"
        caract2, benef2 = "Acción sinérgica antiinflamatoria y analgésica", "Rápida recuperación funcional del paciente"

    if m3:
        prod3, comp3, merc3, cat_m3 = m3["prod_gutis"], m3["lider_actual"], m3["mercado"], m3["categoria_mercado"]
        benef3 = m3["meta_info"]["beneficio"]
    else:
        prod3, comp3, merc3, cat_m3 = "Renovart Platinum / Felicitat", "Competencia", "Mercado Terciario", "Prioridad 3 (Complemento)"
        benef3 = "Mejora sostenida en la calidad de vida a largo plazo"

    if "Sin cita" in tipo_cita:
        frase_permiso = f"«Doctor(a) {med_nombre}, realmente le agradezco que me permita estos minutos; comprendo perfectamente que tiene pacientes en espera.»"
    elif "Encuentro casual" in tipo_cita:
        frase_permiso = f"«Doctor(a) {med_nombre}, veo que está sumamente ocupado(a), ¿me permitiría acompañarlo(a) exactamente tres minutos antes de que inicie su consulta? ¿Le parece bien?»"
    else:
        frase_permiso = f"«Doctor(a) {med_nombre}, un gusto saludarlo(a) nuevamente. {('Recordaba su afinidad por ' + rapport_str + '.') if rapport_str else 'Gracias por el espacio en su agenda de hoy.'}»"

    if "Desempeño" in necesidad_profunda:
        enfoque_ndn = "EL DESEMPEÑO CLÍNICO (asegurar máxima eficacia terapéutica, rapidez de acción y cero recaídas en sus pacientes)"
    elif "Imagen" in necesidad_profunda:
        enfoque_ndn = "LA IMAGEN Y PRESTIGIO MÉDICO (fortalecer la confianza de los pacientes y sus familias en el acierto diagnóstico y terapéutico de su consulta)"
    else:
        enfoque_ndn = "LAS FINANZAS / COSTO-BENEFICIO (garantizar un tratamiento que resuelva el cuadro en el primer ciclo sin gastos adicionales por falta de adherencia)"

    return f"""### 🎯 Hoja de Ruta Oficial: Técnica de Ventas Profesionales (TVP) - Gutis
**Médico:** Dr(a). {med_nombre} ({esp_med} | Categoría {cat_med} | {ciu_med})  
**Secuencia Multi-Mercado de Hoy:**  
1. **1ra Posición ({m1['categoria_mercado']}):** `{prod1}` en `{merc1}` *(Líder actual: {comp1} con {m1['pxs_totales']} Pxs-MES | YTD: {m1['pxs_ytd']} Pxs)*  
2. **2da Posición / Puente ({cat_m2}):** `{prod2}` en `{merc2}` *(Líder actual: {comp2})*  
3. **3ra Posición / Cierre de Portafolio ({cat_m3}):** `{prod3}` en `{merc3}`

---

#### 1️⃣ UNIDAD 2: PLANIFICACIÓN PREVIA A LA VISITA (Antes de entrar al consultorio)
* **Diagnóstico en la Escala de Adopción de la Marca:**
  * **Posición Actual:** `{escala_act1}` $\longrightarrow$ **Meta de Ascenso Hoy:** `{escala_meta1}`.
* **Perfil del Paciente Meta (¿A quién?):** {meta1['paciente_meta']}
* **Las 3 Preguntas de Perspectiva TVP:**
  * **¿A QUIÉN quiero que recomiende `{prod1}`?** A los {m1['pxs_totales']} pacientes mensuales (o {m1['pxs_ytd']} acumulados YTD) donde hoy prescribe `{comp1}`.
  * **¿POR QUÉ debería cambiar a `{prod1}`?** Por su ventaja exclusiva: *{meta1['caracteristica']}*.
  * **¿CÓMO debería prescribirlo?** En sus próximos casos de esta semana, sabiendo que cuenta con respaldo en **{farmacias_str}**.
* **Objetivos de Visita "SMART" (Específico, Medible, Alcanzable, Relevante y con Plazo):**
  * 🎯 **Objetivo Principal SMART:** Lograr que el Dr(a). {med_nombre} prescriba **{prod1}** a sus próximos **3 a 5 pacientes** con este perfil clínico durante los próximos **7 días**, avanzando hacia **{escala_meta1}**.
  * 🛡️ **Objetivo de Respaldo (Plan B si hay resistencia):** Acordar la prueba clínica en **2 pacientes específicos** utilizando las muestras médicas entregadas hoy y revisar su evolución en la próxima visita.

---

#### 2️⃣ UNIDAD 3: APERTURA FORMAL (Regla de Oro: NO mencionar el producto aún)
* **Paso A - Posicionamiento y Empatía ({tipo_cita}):**  
  > {frase_permiso}
* **Paso B - Proponer la Agenda (Centrada en el Paciente, sin usar el "Yo"):**  
  > *«En la consulta de **{esp_med}** aquí en {ciu_med}, se están presentando con mucha frecuencia **{meta1['paciente_meta'].lower()}**. Permítame proponerle que conversemos brevemente sobre los desafíos actuales en el cumplimiento y rapidez de respuesta en este grupo de pacientes.»*
* **Paso C - Comunicar el Valor de la Agenda para el Médico:**  
  > *«De esta forma, podremos analizar alternativas prácticas para que sus pacientes alcancen un alivio más rápido y sostenido, fortaleciendo **{enfoque_ndn.lower()}**.»*
* **Paso D - Pregunta Disruptiva (Sacar del "Piloto Automático"):**  
  > *«Doctor(a), si pudiera eliminar hoy mismo el principal motivo por el que estos pacientes abandonan o rechazan su tratamiento al segundo día, ¿qué impacto tendría en su consulta?»*
* **Paso E - Confirmar Aceptación de la Agenda:**  
  > *«¿Le parece bien que revisemos esto en dos minutos, o hay algún aspecto específico de estos pacientes que prefiera priorizar hoy?»*

---

#### 3️⃣ UNIDAD 4: DESCUBRIR NECESIDADES (Técnica del Embudo y Sondeos de Valor Mutuo)
* **1. Explorar las CIRCUNSTANCIAS (Sondeo Abierto y Neutro):**  
  > *«Doctor(a), cuando atiende a estos pacientes hoy en día (donde suele indicarse `{comp1}`), ¿qué esquema o pauta está utilizando actualmente y qué le comentan los pacientes sobre su evolución?»*
* **2. Descubrir la NECESIDAD (Sondeo de Valor Mutuo con Verbos de Reflexión):**  
  > *«Al **evaluar** y **comparar** la respuesta de sus pacientes en los primeros días, ¿qué es lo que considera más crítico mejorar en cuanto a tolerabilidad y velocidad de alivio?»*
* **3. Revelar la NECESIDAD DETRÁS DE LA NECESIDAD ({necesidad_profunda}):**  
  > *«Cuando logra que el paciente mejore desde las primeras tomas sin efectos indeseados, ¿qué significa eso para la confianza de la familia en su práctica médica y el éxito de su consulta?»*
* **4. Sondeo Cerrado de Confirmación (Lenguaje de las Necesidades):**  
  > *«Entonces Doctor(a), pareciera que para usted lo ideal en estos pacientes es contar con un tratamiento que combine **{meta1['beneficio'].lower()}**, ¿es así?»*

---

#### 4️⃣ UNIDAD 5: APOYO / STORYTELLING Y LOVE BRANDS (Cuando el médico confirma la necesidad)
* **Paso 1 - Demostrar Comprensión Genuina de la Necesidad:**  
  > *«Comprendo perfectamente su prioridad, Doctor(a); de hecho, los especialistas más destacados coinciden en que si esa necesidad no se cubre desde el inicio, el paciente abandona el esquema y se complica el cuadro.»*
* **Paso 2 - Característica + Beneficio Vinculado + Storytelling (Love Brands):**  
  > *«Precisamente para responder a esa exigencia contamos con **{prod1}**. Su característica diferencial es que posee **{meta1['caracteristica']}** (Característica), lo que para sus pacientes se traduce en **{meta1['beneficio']}** (Beneficio directo). En Laboratorios Gutis nos sentimos profundamente orgullosos de **{prod1}** porque brinda **{meta1['love_brand'].lower()}**, respaldando directamente **{enfoque_ndn.lower()}**.»*
* **Paso 3 - Confirmar que se ha Aceptado el Apoyo:**  
  > *«¿No son exactamente estos los resultados y la seguridad que usted busca garantizar en sus pacientes, Doctor(a)?»*

---

#### 5️⃣ UNIDAD 6: CIERRE / PUENTE MULTI-MERCADO (Categorías 1 $\rightarrow$ 2 $\rightarrow$ 3)
* **Paso 1 - Resumen de Beneficios Aceptados:**  
  > *«Como vimos hoy, Doctor(a), **{prod1}** le asegura a sus pacientes **{meta1['caracteristica'].lower()}**, logrando **{meta1['beneficio'].lower()}**.»*
* **Paso 2 - Pedir Compromiso Mutuo (Subir en la Escala de Adopción):**  
  > *«Cuando atienda esta semana a sus próximos **3 a 5 pacientes** con este cuadro, ¿consideraría iniciarlos con **{prod1}**? Por mi parte, yo me comprometo hoy mismo a verificar el stock completo en **{farmacias_str}** y a traerle literatura actualizada en mi próxima visita.»*
* **Paso 3 - Confirmar el Acuerdo:**  
  > *«¿Le parece un buen acuerdo, Doctor(a)? ¿Contamos con esas primeras recetas esta semana?»*
* **Paso 4 - EL PUENTE NATURAL HACIA EL 2DO Y 3ER MERCADO (Sin fricciones):**  
  * 🌉 **Puente a 2da Posición (`{prod2}` - {cat_m2}):**  
    > *«Y ya que hablamos de devolverle la calidad de vida rápidamente a sus pacientes con la tecnología de Gutis, otro grupo importante en su consulta es el de `{merc2.replace('MR ', '')}`. Siguiendo esa misma línea de seguridad, quiero recordarle que con **{prod2}** usted cuenta con **{caract2.lower()}**, ideal para lograr **{benef2.lower()}**. ¿Me permite dejarle este recordatorio para sus próximos casos?»*
  * 🌉 **Recordación de 3ra Posición (`{prod3}` - {cat_m3}):**  
    > *«Finalmente Doctor(a), para sus pacientes en `{merc3.replace('MR ', '')}`, recuerde que también tiene disponible en **{farmacias_str}** nuestro **{prod3}**, garantizando **{benef3.lower()}**.»*
"""

# --- TARJETAS KPI CORPORATIVAS ---
col1, col2, col3 = st.columns(3)
with col1: 
    st.markdown(f"""<div class='metric-card'><div class='metric-title'>MÉDICO OBJETIVO</div><div class='metric-value'>{medico_sel}</div><div style='color: #475569; font-size: 0.85rem; margin-top:5px; font-weight:600;'>{especialidad} | Categoría {categoria} | {ciudad}</div></div>""", unsafe_allow_html=True)
with col2: 
    sub_potencial = f"Pxs Mes: <b>{total_pxs_medico}</b> (Gutis: {gutis_pxs_medico} | Comp: {comp_pxs_medico})" if total_pxs_medico > 0 else f"Cuota: {share_lider:.1f}%"
    st.markdown(f"""<div class='metric-card' style='border-left-color: #0ea5e9;'><div class='metric-title'>FOCO PRIMARIO ({mercado_principal_str})</div><div class='metric-value'>{producto_ataque_str[:15]}</div><div style='color: #475569; font-size: 0.85rem; margin-top:5px; font-weight:600;'>{sub_potencial}</div></div>""", unsafe_allow_html=True)
with col3: 
    st.markdown(f"""<div class='metric-card' style='border-left-color: #8b5cf6;'><div class='metric-title'>SELL-OUT TERRITORIAL ({ciudad} - {total_puntos_venta} PDV)</div><div class='metric-value'>${total_sellout_zona:,.2f}</div><div style='color: #475569; font-size: 0.85rem; margin-top:5px; font-weight:600;'>Líderes: {top_farmacias_ciudad_str[:38]}...</div></div>""", unsafe_allow_html=True)

if cards_ataque_html:
    st.components.v1.html(f"""<div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-left: 5px solid #1e3a8a; padding: 14px; margin-bottom: 18px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.03);"><div style="font-size: 0.82rem; font-weight: 800; color: #0f172a; margin-bottom: 10px; letter-spacing: 0.5px;">[MATRIZ DE MERCADOS DEL MÉDICO POR PRIORIDAD (P1, P2, P3) Y ESCALA DE ADOPCIÓN - {num_mercados} MERCADOS ACTIVOS]</div><div style="display: flex; flex-wrap: wrap; gap: 10px;">{cards_ataque_html}</div></div>""", height=205, scrolling=True)

# --- PESTAÑAS DEL SISTEMA COMPLETAS (8 MÓDULOS INTEGRADOS) ---
tab_terreno, tab_chira, tab_estrategia, tab_perfil360, tab_rx, tab_sellout, tab_bitacora, tab_ruta = st.tabs([
    "📊 Inteligencia de Terreno", "[ASISTENTE CHIRA]", "Fase 1: Modelo TVP Gutis", "Perfil 360°", "Fase 2: Análisis Rx", "Fase 3: Sell-Out", "Fase 4: Post-Visita CRM", "Itinerario de Ruta"
])

# ==============================================================================
# PESTAÑA 1: INTELIGENCIA DE TERRENO (PENETRACIÓN POR ESPECIALIDAD + CRUCE RX VS SELL-OUT)
# ==============================================================================
with tab_terreno:
    st.markdown("<div class='elite-header'>🏆 INTELIGENCIA DE TERRENO: REVISIÓN DEL PANEL POR ESPECIALIDAD Y SINCRONÍA RX vs. SELL-OUT</div>", unsafe_allow_html=True)
    
    col_t_f1, col_t_f2 = st.columns([1.5, 2.5])
    with col_t_f1:
        zona_terreno_sel = st.selectbox("📍 Seleccionar Territorio a Auditar:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="terr_zona")
    with col_t_f2:
        st.info("💡 **Lectura Ejecutiva:** Arriba auditas la **Penetración y Top 5 Competencia por Especialidad** de tu panel; abajo auditas si el **crecimiento de recetas médicas (Rx)** se está reflejando en las **ventas de farmacia (Sell-Out)**.")

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
        kt2.metric("Captados en Close-Up", tot_cap, f"{(tot_cap/tot_pan*100):.1f}% Cobertura" if tot_pan > 0 else "")
        kt3.metric("Recetan Gutis", tot_rec_g)
        kt4.metric("Penetración Global", f"{pen_global:.2f}%")
        kt5.metric("Médicos Gutis Top 1 / Top 3", f"{tot_t1} / {tot_t3}")

        st.markdown(f"#### 1️⃣ Rendimiento Interno YTD 2026 ({zona_terreno_sel})")
        st.dataframe(
            df_rend_interno,
            hide_index=True,
            use_container_width=True,
            column_config={
                "PENETRACIÓN": st.column_config.ProgressColumn("PENETRACIÓN (%)", format="%.2f%%", min_value=0, max_value=100),
                "%MS-YTD": st.column_config.ProgressColumn("%MS-YTD GUTIS", format="%.2f%%", min_value=0, max_value=100),
                "TOP 1": st.column_config.NumberColumn("TOP 1 (Médicos)", help="Médicos donde Gutis es su laboratorio #1 en recetas YTD"),
                "TOP 3": st.column_config.NumberColumn("TOP 3 (Médicos)", help="Médicos donde Gutis está en su Top 3 de laboratorios YTD")
            }
        )

        st.markdown(f"#### 2️⃣ Top Competencia Directa por Cuota de Mercado YTD ({zona_terreno_sel})")
        st.dataframe(df_top_comp, hide_index=True, use_container_width=True)
    else:
        st.warning("No se encontraron datos de especialidades cruzados con el archivo de laboratorios.")

    st.divider()
    st.markdown(f"#### 3️⃣ Matriz de Sincronía en el Tiempo: Evolución de Recetas (Rx) vs. Sell-Out de Farmacias ({zona_terreno_sel})")
    st.caption("Compara si el impulso de prescripción del médico (% MS Mes vs % MS YTD) coincide con la tendencia de compra de las farmacias en Q3 vs Q2.")

    df_sincronia = calcular_sincronia_rx_vs_sellout(zona_terreno_sel)
    if not df_sincronia.empty:
        st.dataframe(
            df_sincronia,
            hide_index=True,
            use_container_width=True,
            column_config={
                "% MS YTD": st.column_config.NumberColumn("% MS YTD", format="%.2f%%"),
                "% MS MES": st.column_config.NumberColumn("% MS MES", format="%.2f%%"),
                "Sell-Out Q1": st.column_config.NumberColumn("Sell-Out Q1", format="$%.2f"),
                "Sell-Out Q2": st.column_config.NumberColumn("Sell-Out Q2", format="$%.2f"),
                "Sell-Out Q3": st.column_config.NumberColumn("Sell-Out Q3", format="$%.2f"),
            }
        )

        fugas_df = df_sincronia[df_sincronia["Diagnóstico de Sincronía (Rx vs. Farmacia)"].str.contains("🚨")]
        exitos_df = df_sincronia[df_sincronia["Diagnóstico de Sincronía (Rx vs. Farmacia)"].str.contains("🟢")]
        
        c_al1, c_al2 = st.columns(2)
        with c_al1:
            if not exitos_df.empty:
                marcas_ex = ", ".join(exitos_df["Marca Gutis"].tolist())
                st.success(f"**🟢 Mercados en Crecimiento Sincronizado ({zona_terreno_sel}):** {marcas_ex}. La receta médica impulsa directamente el Sell-Out en farmacias.")
        with c_al2:
            if not fugas_df.empty:
                marcas_fu = ", ".join(fugas_df["Marca Gutis"].tolist())
                st.error(f"**🚨 Alerta de Fuga en Mostrador ({zona_terreno_sel}):** {marcas_fu}. Los médicos de tu panel sostienen o suben la receta, pero el Sell-Out cayó en Q3. Auditar sustitución en farmacias o quiebre de inventario.")
    else:
        st.info("No hay suficientes datos combinados de Rx y Sell-Out para la zona seleccionada.")

# ==============================================================================
# PESTAÑA 2: CHIRA 2.0 - CONSOLA DINÁMICA MULTIDIMENSIONAL + FUERA DE PANEL
# ==============================================================================
with tab_chira:
    st.markdown("### [CHIRA 2.0] - Consultor de Inteligencia Comercial Senior")
    st.caption("Audita Penetración por Especialidad, Laboratorios, Pareto 80/20, Mercados (P1, P2, P3), Médicos No Visitados y Sincronía Rx vs. Sell-Out.")
    
    with st.container(border=True):
        st.markdown("**🎛️ Consola Dinámica de Cruce Territorial, Especialidades, Prioridad de Mercado y Médicos No Visitados:**")
        p_c1, p_c2, p_c3, p_c4, p_c5 = st.columns([1.2, 1.2, 1.1, 1.2, 0.6])
        with p_c1:
            chira_ciu_sel = st.selectbox("📍 Territorio / Ciudad:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="ch_ciu")
        with p_c2:
            chira_esp_sel = st.selectbox("🩺 Especialidad Médica:", ["TODAS LAS ESPECIALIDADES"] + LISTA_ESPECIALIDADES_REALES, key="ch_esp")
        with p_c3:
            chira_prio_sel = st.selectbox("🏅 Nivel de Mercado:", ["TODAS LAS PRIORIDADES", "Prioridad 1 (Foco Core)", "Prioridad 2 (Expansión)", "Prioridad 3 (Complemento)"], key="ch_prio")
        with p_c4:
            mercados_consola_disp = LISTA_MERCADOS_REALES
            if "Prioridad 1" in chira_prio_sel:
                mercados_consola_disp = [m for m in LISTA_MERCADOS_REALES if obtener_meta_mercado(m)["prioridad"] == 1]
            elif "Prioridad 2" in chira_prio_sel:
                mercados_consola_disp = [m for m in LISTA_MERCADOS_REALES if obtener_meta_mercado(m)["prioridad"] == 2]
            elif "Prioridad 3" in chira_prio_sel:
                mercados_consola_disp = [m for m in LISTA_MERCADOS_REALES if obtener_meta_mercado(m)["prioridad"] == 3]
            chira_mer_sel = st.selectbox("💊 Mercado / Producto:", ["TODOS LOS MERCADOS"] + mercados_consola_disp, key="ch_mer")
        with p_c5:
            chira_top_sel = st.selectbox("🔢 Top:", [5, 10, 15, 20], index=0, key="ch_top")

        b_c1, b_c2, b_c3, b_c4, b_c5, b_c6 = st.columns(6)
        accion_consola = None
        if b_c1.button("🏆 Penetración Panel", use_container_width=True): accion_consola = "PENETRACION"
        if b_c2.button("🔄 Rx vs Farmacia", use_container_width=True): accion_consola = "SINCRONIA"
        if b_c3.button("🔬 Auditar Labs", use_container_width=True): accion_consola = "LABS"
        if b_c4.button("📊 Pareto 80/20", use_container_width=True): accion_consola = "MEDICOS_PARETO"
        if b_c5.button("🎯 Conquista", use_container_width=True): accion_consola = "MEDICOS_CONQUISTA"
        if b_c6.button("🚀 Fuera de Panel", use_container_width=True): accion_consola = "MEDICOS_NO_VISITADOS"

    chat_container_chira = st.container(height=360)
    for msg in st.session_state.chira_history:
        with chat_container_chira.chat_message(msg["role"]): st.write(msg["content"])
        
    input_chat_chira = st.chat_input("Escribe cualquier consulta libre (ej: Dame la penetración por especialidad en Granada / Cruza recetas vs ventas en Carazo)...")

    if accion_consola or input_chat_chira:
        prio_target = None
        if accion_consola:
            top_n = chira_top_sel
            ciu_target = None if chira_ciu_sel == "TODO MI PANEL" else chira_ciu_sel
            esp_target = None if chira_esp_sel == "TODAS LAS ESPECIALIDADES" else chira_esp_sel
            mer_target = None if chira_mer_sel == "TODOS LOS MERCADOS" else chira_mer_sel
            if "Prioridad 1" in chira_prio_sel: prio_target = 1
            elif "Prioridad 2" in chira_prio_sel: prio_target = 2
            elif "Prioridad 3" in chira_prio_sel: prio_target = 3
            modo_motor = accion_consola
            pregunta_mostrar = f"[Consola BI] {accion_consola} | Zona: {chira_ciu_sel} | Esp: {chira_esp_sel} | {chira_prio_sel} | Mercado: {chira_mer_sel}"
        else:
            pregunta_mostrar = input_chat_chira
            texto_norm = normalizar_txt(input_chat_chira)
            
            match_num = re.search(r'\b(\d+)\b', texto_norm)
            top_n = int(match_num.group(1)) if match_num and 1 <= int(match_num.group(1)) <= 50 else 5

            if "PRIORIDAD 1" in texto_norm or "CATEGORIA 1 DE MERCADO" in texto_norm: prio_target = 1
            elif "PRIORIDAD 2" in texto_norm or "CATEGORIA 2 DE MERCADO" in texto_norm: prio_target = 2
            elif "PRIORIDAD 3" in texto_norm or "CATEGORIA 3 DE MERCADO" in texto_norm: prio_target = 3

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

            esp_target = None
            for e_real in LISTA_ESPECIALIDADES_REALES:
                e_norm = normalizar_txt(e_real)
                palabras_esp = [p for p in re.split(r'[\s/,-]+', e_norm) if len(p) >= 4]
                if e_norm in texto_norm or any(p[:5] in texto_norm for p in palabras_esp):
                    esp_target = e_real
                    break

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

            if any(k in texto_norm for k in ["PENETRACION", "REVISION DEL PANEL", "RENDIMIENTO INTERNO", "TOP 1", "TOP 3"]):
                modo_motor = "PENETRACION"
            elif any(k in texto_norm for k in ["SINCRONIA", "TENDENCIA", "FUGA", "RECETAS VS", "MEDICO VS"]):
                modo_motor = "SINCRONIA"
            elif any(k in texto_norm for k in [
                "NO VISITADO", "NO VISITADOS", "FUERA DE PANEL", "NO ESTA EN MI PANEL",
                "NO ESTAN EN MI PANEL", "NO ESTA SIENDO VISITADO", "NO SON VISITADOS",
                "POTENCIALES NO VISITADOS", "INCORPORAR", "NUEVOS MEDICOS", "SIN VISITA"
            ]):
                modo_motor = "MEDICOS_NO_VISITADOS"
            elif any(k in texto_norm for k in ["LABORATORIO", "FABRICANTE", "CASA", "INDUSTRIA"]):
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
            etiqueta_z = ciu_target if ciu_target else "TODO MI PANEL"
            etiqueta_e = esp_target if esp_target else "Todas las Especialidades"
            etiqueta_m = mer_target if mer_target else (f"Mercados Prioridad {prio_target}" if prio_target else "Todos los Mercados (P1, P2, P3)")

            if ciu_target and "CIUDAD" in df_panel_sub.columns:
                df_panel_sub = df_panel_sub[df_panel_sub["CIUDAD"].astype(str).str.upper().str.contains(re.escape(ciu_target), na=False)]
            if esp_target and "Especialidad" in df_panel_sub.columns:
                df_panel_sub = df_panel_sub[df_panel_sub["Especialidad"].astype(str).str.upper() == esp_target.upper()]

            medicos_segmento = set(df_panel_sub["Médico"].dropna().unique())
            num_meds_seg = len(medicos_segmento)

            if modo_motor == "PENETRACION":
                df_r_ch, df_c_ch = calcular_matriz_penetracion_panel(etiqueta_z)
                if not df_r_ch.empty:
                    lineas = [
                        f"### 🏆 Inteligencia de Terreno: Penetración por Especialidad ({etiqueta_z})\n",
                        "#### 1. Rendimiento Interno YTD 2026:",
                        df_a_markdown_nativo(df_r_ch),
                        "\n#### 2. Top Competencia Directa por Cuota de Mercado:",
                        df_a_markdown_nativo(df_c_ch)
                    ]
                    resultado_final = "\n".join(lineas)
                else:
                    resultado_final = f"No se encontraron datos de penetración para {etiqueta_z}."

            elif modo_motor == "SINCRONIA":
                df_s_ch = calcular_sincronia_rx_vs_sellout(etiqueta_z)
                if not df_s_ch.empty:
                    lineas = [
                        f"### 🔄 Sincronía en el Tiempo: Evolución Recetas (Rx) vs. Sell-Out Farmacias ({etiqueta_z})\n",
                        df_a_markdown_nativo(df_s_ch)
                    ]
                    resultado_final = "\n".join(lineas)
                else:
                    resultado_final = f"No se encontraron datos de sincronía Rx vs Sell-Out para {etiqueta_z}."

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

            elif modo_motor == "MEDICOS_NO_VISITADOS":
                if not df_productos.empty and "Médico" in df_productos.columns:
                    col_pxs_c = next((c for c in df_productos.columns if c.upper() == "PXS-MES"), None)
                    if not col_pxs_c: col_pxs_c = next((c for c in df_productos.columns if any(x in c.upper() for x in ["PXS-TRIM", "PXS-YTD", "PXS"])), None)
                    col_ytd_c = next((c for c in df_productos.columns if c.upper() == "PXS-YTD"), None)

                    todos_medicos_panel_erick = set(df_panel["Médico"].dropna().unique())
                    df_fuera = df_productos[~df_productos["Médico"].isin(todos_medicos_panel_erick)].copy()
                    df_fuera = df_fuera[~df_fuera["NOMBRE_PRODUCTO"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
                    df_fuera = df_fuera[~df_fuera["Médico"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]

                    if mer_target:
                        kw_m = normalizar_txt(mer_target.replace("MR ", ""))
                        df_fuera = df_fuera[df_fuera["MERCADO"].apply(normalizar_txt).str.contains(re.escape(kw_m), na=False)]
                    elif prio_target:
                        df_fuera = df_fuera[df_fuera["MERCADO"].apply(lambda x: obtener_meta_mercado(x)["prioridad"] == prio_target)]

                    col_ciu_rx = next((c for c in df_fuera.columns if c.upper() in ["CIUDAD", "DEPARTAMENTO", "ZONA", "REGION"]), None)
                    if ciu_target and col_ciu_rx:
                        df_fuera = df_fuera[df_fuera[col_ciu_rx].astype(str).str.upper().str.contains(re.escape(ciu_target), na=False)]

                    col_esp_rx = next((c for c in df_fuera.columns if "ESPEC" in c.upper()), None)
                    if esp_target and col_esp_rx:
                        raiz_e = normalizar_txt(esp_target)[:5]
                        df_fuera = df_fuera[df_fuera[col_esp_rx].apply(normalizar_txt).str.contains(raiz_e, na=False)]

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
                            pxs_comp = pxs_m - pxs_g

                            grp_ord = grp_f.sort_values(by=[col_pxs_c, col_ytd_c] if col_ytd_c else [col_pxs_c], ascending=False)
                            lider_r = grp_ord.iloc[0]
                            lider_nom = str(lider_r["NOMBRE_PRODUCTO"]).strip()
                            lider_merc = str(lider_r["MERCADO"]).strip()
                            lider_px = int(lider_r[col_pxs_c])

                            esp_val = str(lider_r[col_esp_rx]).strip() if col_esp_rx else "Especialidad en Close-Up"
                            ciu_val = str(lider_r[col_ciu_rx]).strip() if col_ciu_rx else (ciu_target if ciu_target else "Nicaragua")

                            candidatos_fuera.append({
                                "nombre": nom_doc, "especialidad": esp_val, "ciudad": ciu_val,
                                "pxs_mes": pxs_m, "pxs_ytd": pxs_y, "pxs_comp": pxs_comp,
                                "pxs_gutis": pxs_g, "lider_prod": lider_nom, "lider_merc": lider_merc, "lider_px": lider_px
                            })

                        candidatos_fuera = sorted(candidatos_fuera, key=lambda x: (x["pxs_comp"], x["pxs_mes"], x["pxs_ytd"]), reverse=True)

                        if candidatos_fuera:
                            lineas = [
                                f"### 🚀 Médicos Potenciales NO Visitados (Fuera de tu Panel Actual)",
                                f"**Filtros Aplicados:** Zona: `{etiqueta_z}` | Especialidad: `{etiqueta_e}` | Mercado: `{etiqueta_m}`",
                                f"**Hallazgo de Auditoría:** Se detectaron **{len(candidatos_fuera)} médicos fuera de tu panel** prescribiendo activamente.\n",
                                f"#### 🏆 Top {top_n} Candidatos Prioritarios para Incorporar:"
                            ]
                            for idx, cf in enumerate(candidatos_fuera[:top_n], 1):
                                meta_sug = obtener_meta_mercado(cf["lider_merc"])
                                prod_gutis_sug = meta_sug["producto"]
                                lineas.append(
                                    f"**{idx}. Dr(a). {cf['nombre']}** ({cf['especialidad']} | {cf['ciudad']})\n"
                                    f"- **Volumen en Mercados Gutis:** `{cf['pxs_mes']} Pxs-MES` (Competencia: **{cf['pxs_comp']} Pxs** | Gutis: {cf['pxs_gutis']} Pxs) | **Acumulado YTD:** `{cf['pxs_ytd']} Pxs`\n"
                                    f"- **Receta Dominante Actual:** `{cf['lider_prod']}` ({cf['lider_px']} Pxs en `{cf['lider_merc']}` - {meta_sug['categoria_mercado']})\n"
                                    f"- **Potencial de Captura:** Incorporar a ruta para iniciar en Escala de Adopción con **{prod_gutis_sug}**.\n"
                                )
                            resultado_final = "\n".join(lineas)
                        else:
                            resultado_final = f"No se detectaron médicos fuera de panel con prescripción activa para la combinación seleccionada."
                    else:
                        resultado_final = "No se encontraron registros fuera de panel para los filtros seleccionados."
                else:
                    resultado_final = "No se encontró el archivo de auditoría de productos Close-Up."

            else:
                ranking_medicos = []
                if not df_productos.empty and "Médico" in df_productos.columns:
                    col_pxs_c = next((c for c in df_productos.columns if c.upper() == "PXS-MES"), None)
                    if not col_pxs_c: col_pxs_c = next((c for c in df_productos.columns if any(x in c.upper() for x in ["PXS-TRIM", "PXS-YTD", "PXS"])), None)
                    col_ytd_c = next((c for c in df_productos.columns if c.upper() == "PXS-YTD"), None)

                    df_rx_sub = df_productos[df_productos["Médico"].isin(medicos_segmento)].copy()
                    df_rx_sub = df_rx_sub[~df_rx_sub["NOMBRE_PRODUCTO"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]

                    if mer_target:
                        kw_m = normalizar_txt(mer_target.replace("MR ", ""))
                        df_rx_sub = df_rx_sub[df_rx_sub["MERCADO"].apply(normalizar_txt).str.contains(re.escape(kw_m), na=False)]
                    elif prio_target:
                        df_rx_sub = df_rx_sub[df_rx_sub["MERCADO"].apply(lambda x: obtener_meta_mercado(x)["prioridad"] == prio_target)]

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
                            pxs_comp = pxs_mes_tot - pxs_gut
                            ms_gut = (pxs_gut / pxs_mes_tot * 100) if pxs_mes_tot > 0 else 0.0
                            esc_doc, _, _ = diagnosticar_escala_adopcion(pxs_gut, pxs_mes_tot, ms_gut)

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
                                "escala": esc_doc,
                                "es_gutis": es_gutis(lider_nom)
                            })

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
                            f"- **Volumen Mes:** `{m_i['pxs_totales']} Pxs-MES` (Gutis: {m_i['gutis_pxs']} | Comp: **{m_i['comp_pxs']}**) | **YTD:** `{m_i['pxs_ytd']} Pxs` | **Pareto Acum:** `{acum_p:.1f}%`\n"
                            f"- **Marca Dominante:** `{m_i['lider_producto']}` ({m_i['lider_pxs']} Pxs) | **Escala TVP:** `{m_i['escala']}` ➔ {est_str}\n"
                        )
                    resultado_final = "\n".join(lineas)
                else:
                    resultado_final = f"No se encontraron médicos con prescripción activa para la combinación seleccionada."

            prompt_ia = f"""{REGLAS_FARMA}
Eres CHIRA, Consultora Senior de BI de Laboratorios Gutis.
Respeta ÍNTEGRAMENTE todas las cifras y tablas del siguiente reporte y añade al final un bloque breve titulado '⚡ Recomendación Táctica TVP (Modo Argón)' con 2 acciones concretas para Erick Calderón:

{resultado_final}"""
            respuesta_ia = llamar_gemini(prompt_ia)
            if respuesta_ia and len(respuesta_ia.strip()) > 80:
                resultado_final = respuesta_ia

        st.session_state.chira_history.append({"role": "assistant", "content": resultado_final})
        st.rerun()

# ==============================================================================
# PESTAÑA 3: FASE 1 - MODELO OFICIAL TVP GUTIS PASO A PASO & MULTI-MERCADO
# ==============================================================================
with tab_estrategia:
    st.markdown("#### 📘 [PLANIFICADOR Y EJECUTOR DEL MODELO OFICIAL TVP GUTIS - MULTI-MERCADO (P1, P2, P3)]")
    st.caption("Estructura tu visita paso a paso siguiendo las Unidades del Manual TVP Gutis: Planificación SMART, Apertura con Agenda, Sondeos de Valor Mutuo, Storytelling Love Brands y Cierre con Puente entre Categorías de Mercado.")

    with st.container(border=True):
        st.markdown("**⚙️ 1. Configuración de la Secuencia Multi-Mercado (Prioridad 1, 2 y 3) y Contexto de Visita:**")
        if opciones_mercados_medico:
            etiquetas_m = [f"[P{o['prioridad']}] {o['mercado']} | Líder: {o['lider_actual'][:14]} (Mes: {o['pxs_totales']} | YTD: {o['pxs_ytd']}) ➔ {o['prod_gutis']}" for o in opciones_mercados_medico]
            cm1, cm2, cm3 = st.columns(3)
            with cm1:
                idx_m1 = st.selectbox("🥇 1ra Posición (Foco Principal):", range(len(etiquetas_m)), index=0, format_func=lambda i: etiquetas_m[i])
            with cm2:
                idx_def2 = 1 if len(etiquetas_m) > 1 else 0
                idx_m2 = st.selectbox("🥈 2da Posición (Puente Transicional):", range(len(etiquetas_m)), index=idx_def2, format_func=lambda i: etiquetas_m[i])
            with cm3:
                idx_def3 = 2 if len(etiquetas_m) > 2 else idx_def2
                idx_m3 = st.selectbox("🥉 3ra Posición (Recordación / Cierre):", range(len(etiquetas_m)), index=idx_def3, format_func=lambda i: etiquetas_m[i])
            
            m_primario = opciones_mercados_medico[idx_m1]
            m_secundario = opciones_mercados_medico[idx_m2] if len(opciones_mercados_medico) > 1 else None
            m_terciario = opciones_mercados_medico[idx_m3] if len(opciones_mercados_medico) > 2 else None
        else:
            meta_def = obtener_meta_mercado("MR TALERDIN" if es_pediatra else "MR GASTROALIVIO")
            m_primario = {
                "mercado": "MR TALERDIN" if es_pediatra else "MR GASTROALIVIO",
                "prioridad": 1, "categoria_mercado": "Prioridad 1 (Foco Core)",
                "lider_actual": producto_ataque_str, "lider_es_gutis": False,
                "prod_gutis": prod_gutis_ataque_oficial, "pxs_totales": total_pxs_medico,
                "pxs_ytd": total_pxs_medico, "pxs_gutis": gutis_pxs_medico, "pxs_comp": comp_pxs_medico,
                "ms_lider": share_lider, "ms_gutis": 0.0,
                "escala_actual": "2. Consciente (0% MS)", "escala_meta": "3. Prueba (2 a 10 Pxs)",
                "objetivo_escala": "Iniciar período de prueba.", "meta_info": meta_def
            }
            m_secundario, m_terciario = None, None

        ct1, ct2, ct3 = st.columns(3)
        with ct1:
            tipo_cita_sel = st.selectbox("🚪 Contexto de Acceso (Unidad 3):", ["Visita con cita previa", "Visita sin cita previa (Improvisto)", "Encuentro casual (Pasillo / Hospital)"])
        with ct2:
            nec_detras_sel = st.selectbox("🧠 Necesidad detrás de la Necesidad (Unidad 4):", ["Desempeño (Eficacia y adherencia clínica)", "Imagen (Prestigio y confianza del paciente)", "Finanzas (Costo-beneficio del tratamiento)"])
        with ct3:
            actitud_med_sel = st.selectbox("🎭 Actitud Inicial del Médico:", ["Receptivo / Consultivo", "Indiferente (Satisfecho con lo que receta)", "Con Objeción (Escepticismo / Malentendido / Desventaja)"])

    st.markdown(f"""
    <div class='tvp-box'>
        <div style='font-size:0.8rem; font-weight:800; color:#1e3a8a; text-transform:uppercase;'>📊 Diagnóstico Oficial en la Escala de Adopción de la Marca ({m_primario['prod_gutis']})</div>
        <div style='display:flex; flex-wrap:wrap; gap:18px; margin-top:8px; font-size:0.88rem;'>
            <div><b>Escalón Actual:</b> <span style='color:#be123c; font-weight:700;'>{m_primario['escala_actual']}</span></div>
            <div><b>Escalón Meta Hoy:</b> <span style='color:#047857; font-weight:700;'>{m_primario['escala_meta']}</span></div>
            <div><b>Acción TVP:</b> {m_primario['objetivo_escala']}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_izq_ia, col_der_ia = st.columns([1.35, 1.0])
    with col_izq_ia:
        st.markdown("#### 📋 [GUION PASO A PASO DE LA VISITA MÉDICA (UNIDADES 1 A 8)]")
        b_tvp1, b_tvp2 = st.columns(2)
        with b_tvp1:
            if st.button("📘 [GENERAR PLAN TVP COMPLETO PASO A PASO]", use_container_width=True, type="primary"):
                with st.spinner("[ESTRUCTURANDO VISITA BAJO EL MODELO TVP GUTIS...]"):
                    plan_base = construir_plan_tvp_gutis(
                        medico_sel, especialidad, categoria, ciudad,
                        m_primario, m_secundario, m_terciario,
                        tipo_cita_sel, nec_detras_sel, contexto_rapport_str, top_farmacias_ciudad_str
                    )
                    prompt_enriquecido = f"""{REGLAS_FARMA}
Actúa como Instructor Master del Modelo TVP de Laboratorios Gutis.
Respeta TODA la estructura, unidades y datos reales del siguiente plan paso a paso para el Dr(a). {medico_sel}, puliendo los diálogos para que suenen naturales, persuasivos y listos para decirlos en el consultorio.
Además, dado que la actitud seleccionada es '{actitud_med_sel}', añade al final un bloque específico de cómo aplicar la Unidad 7 (Manejo de la Indiferencia con agenda limitada y 4 pasos) o la Unidad 8 (Manejo de Objeciones: Escepticismo, Malentendido y Desventaja) para este médico:

{plan_base}"""
                    res_ia_tvp = llamar_gemini(prompt_enriquecido)
                    st.session_state.tvp_result = res_ia_tvp if (res_ia_tvp and len(res_ia_tvp) > 250) else plan_base

        with b_tvp2:
            if st.button("⚡ [MODO PASILLO / AGENDA LIMITADA 60s]", use_container_width=True):
                with st.spinner("[COMPILANDO ABORDAJE DE IMPACTO RÁPIDO...]"):
                    prod2_nom = m_secundario["prod_gutis"] if m_secundario else "nuestra línea complementaria"
                    pitch_base = f"""### ⚡ Abordaje de Pasillo con Agenda Limitada (60 Segundos)
1. **Permiso y Empatía (Unidad 3):** *«Doctor(a) {medico_sel}, sé que va entrando a consulta; regáleme exactamente 60 segundos mientras camina.»*
2. **Pregunta Disruptiva + Necesidad (Unidad 4):** *«Para los **{m_primario['pxs_totales']} pacientes mensuales** ({m_primario['pxs_ytd']} YTD) donde hoy indica `{m_primario['lider_actual']}`, si pudiera asegurarles **{m_primario['meta_info']['beneficio'].lower()}**, ¿no les daría mayor tranquilidad?»*
3. **Storytelling Flash (Unidad 5):** *«Con **{m_primario['prod_gutis']}** cuenta con **{m_primario['meta_info']['caracteristica'].lower()}**.»*
4. **Cierre + Puente Rápido (Unidad 6):** *«Póngalo a prueba en sus próximos 3 pacientes hoy; ya hay stock completo en **{top_farmacias_ciudad_str}** tanto de **{m_primario['prod_gutis']}** como de **{prod2_nom}**. ¿Contamos con ello, Doctor(a)?»*"""
                    st.session_state.pasillo_result = pitch_base

        if st.session_state.pasillo_result:
            st.info(st.session_state.pasillo_result)
        if st.session_state.tvp_result:
            st.markdown(st.session_state.tvp_result)

    with col_der_ia:
        st.markdown("#### 🥊 [SIMULADOR DE INDIFERENCIA Y OBJECIONES TVP (UNIDADES 7 Y 8)]")
        st.caption("Practica con el médico virtual. El simulador clasifica la objeción en **Escepticismo**, **Malentendido** o **Desventaja** (o **Indiferencia**) y evalúa si seguiste los 4 pasos del manual.")
        
        with st.expander("📖 Ver Chuleta Oficial TVP: Cómo responder Indiferencia y Objeciones"):
            st.markdown(f"""
**1. Si el médico está INDIFERENTE** (*"Ya estoy conforme con {m_primario['lider_actual']}"*):
* **Paso 1:** Demostrar que comprende su punto de vista sin darle la razón absoluta.
* **Paso 2:** Pedir permiso para realizar un sondeo con **agenda limitada** (1-2 minutos).
* **Paso 3:** Sondear para crear conciencia: *Explorar circunstancias $\rightarrow$ Identificar oportunidades $\rightarrow$ Examinar efectos $\rightarrow$ Confirmar necesidad*.
* **Paso 4:** Apoyar con Storytelling de **{m_primario['prod_gutis']}**.

**2. Si el médico plantea una OBJECIÓN (4 Pasos: Sondear para clarificar $\rightarrow$ Demostrar comprensión $\rightarrow$ Manejar $\rightarrow$ Confirmar aceptación):**
* 🧐 **Escepticismo** (*Duda que `{m_primario['prod_gutis']}` tenga el beneficio*): Aportar **pruebas y evidencias clínicas**.
* 💡 **Malentendido** (*Cree erróneamente que `{m_primario['prod_gutis']}` no tiene una ventaja*): Confirmar la **necesidad subyacente** y describir **característica + beneficio**.
* ⚖️ **Desventaja** (*Precio o presentación real*): **Reenfocar desde una perspectiva más amplia** y contraargumentar con los **beneficios exclusivos aceptados previamente**.
""")

        chat_container = st.container(height=340)
        for msg in st.session_state.chat_history:
            with chat_container.chat_message(msg["role"]): st.write(msg["content"])
            
        if prompt_chat := st.chat_input(f"Escribe cómo abordarías o rebatirías al Dr(a). {medico_sel}..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt_chat})
            with chat_container.chat_message("user"): st.write(prompt_chat)
            with st.spinner("[EVALUANDO BAJO EL MANUAL TVP GUTIS...]"):
                prompt_sim = f"""{REGLAS_FARMA}
Estás entrenando a Erick Calderón frente al Dr(a). {medico_sel} ({especialidad}).
Producto Gutis: {m_primario['prod_gutis']} vs Competidor: {m_primario['lider_actual']}.
Erick acaba de decirle al médico: "{prompt_chat}"

Responde en dos bloques cortos:
1. **🩺 Respuesta del Dr(a). {medico_sel}:** Actúa como el médico respondiendo de forma realista.
2. **📋 Coaching TVP Gutis:** Evalúa en 2 viñetas si Erick aplicó bien el manual y sugiérele la frase exacta para el siguiente paso."""
                res_sim = llamar_gemini(prompt_sim)
                if not res_sim:
                    res_sim = f"""**🩺 Respuesta del Dr(a). {medico_sel}:** «Entiendo lo que me comenta sobre **{m_primario['prod_gutis']}**, pero llevo tiempo usando `{m_primario['lider_actual']}` y algunos pacientes buscan opciones económicas. ¿Realmente vale la pena el cambio?»\n\n**📋 Coaching TVP Gutis (Unidad 8 - Desventaja/Escepticismo):**\n* **Diagnóstico:** El médico plantea una combinación de *Inercia/Indiferencia* y *Desventaja de precio*.\n* **Paso sugerido según el Manual:** 1) Demuestra comprensión (*"Comprendo que el costo total del tratamiento es importante para sus pacientes"*), 2) Reenfoca en una perspectiva amplia recordando que **{m_primario['prod_gutis']}** evita recaídas y gastos dobles gracias a *{m_primario['meta_info']['caracteristica']}*, y 3) Confirma aceptación (*"Teniendo en cuenta este beneficio, ¿le parece probarlo en sus próximos 3 pacientes?"*)."""
            st.session_state.chat_history.append({"role": "assistant", "content": res_sim})
            st.rerun()

# ==============================================================================
# PESTAÑA 4: PERFIL 360° (CON GUARDADO REAL EN EXCEL Y MEMORIA)
# ==============================================================================
with tab_perfil360:
    st.markdown(f"#### [ACTUALIZACIÓN DE PERFIL OMNICANAL - {medico_sel}]")
    st.caption("Los datos guardados aquí se inyectan automáticamente en la Unidad 2 (Planificación) y Unidad 3 (Apertura) del TVP.")
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
# PESTAÑA 5: FASE 2 - ANÁLISIS RX POR CATEGORÍAS DE MERCADO (P1, P2, P3)
# ==============================================================================
with tab_rx:
    st.markdown("#### [AUDITORÍA DE PRESCRIPCIÓN MULTI-MERCADO (PRIORIDAD 1, 2, 3) Y LABORATORIOS]")
    m_p1, m_p2, m_p3 = st.columns(3)
    with m_p1: st.metric("Pacientes Mes (Pxs-MES)", total_pxs_medico)
    with m_p2: st.metric("Pacientes Gutis (Mes)", gutis_pxs_medico)
    with m_p3: st.metric("Oportunidad Conquista (Competencia)", comp_pxs_medico)
    st.divider()

    if not rx_clean.empty:
        rx_clean["Prioridad_Num"] = rx_clean["MERCADO"].apply(lambda x: obtener_meta_mercado(x)["prioridad"])
        rx_clean["Nivel_Mercado"] = rx_clean["MERCADO"].apply(lambda x: obtener_meta_mercado(x)["categoria_mercado"])

        col_f0, col_f1, col_f2 = st.columns([1.3, 2.0, 0.9])
        with col_f0:
            niveles_disp = sorted(rx_clean["Nivel_Mercado"].dropna().unique().tolist())
            niveles_sel = st.multiselect("🏅 Filtrar Nivel de Mercado (P1, P2, P3):", niveles_disp, placeholder="Todos los niveles...")
        with col_f1:
            rx_temp_m = rx_clean[rx_clean["Nivel_Mercado"].isin(niveles_sel)] if niveles_sel else rx_clean
            mercados_disponibles = sorted(rx_temp_m["MERCADO"].dropna().unique().tolist())
            mercados_filtro = st.multiselect("🔍 Filtrar Mercado Específico:", mercados_disponibles, placeholder="Todos los mercados...")
        with col_f2:
            ocultar_ceros = st.checkbox("Ocultar 0 Pxs", value=False)
        
        rx_vista = rx_temp_m[rx_temp_m["MERCADO"].isin(mercados_filtro)].copy() if mercados_filtro else rx_temp_m.copy()

        col_r1, col_r2 = st.columns([2.25, 1.25])
        with col_r1:
            st.markdown("##### 📋 Auditoría por Nivel de Mercado (P1, P2, P3), Mes y Acumulado YTD")
            cols_to_show = ["Nivel_Mercado", "MERCADO", "NOMBRE_PRODUCTO"]
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

            sort_cols = ["Nivel_Mercado"] + [c for c in [col_pxs, col_pxs_ytd_prod, col_mes] if c]
            asc_flags = [True] + [False]*(len(sort_cols)-1)
            df_rx_view = df_rx_view.sort_values(by=sort_cols, ascending=asc_flags)
            
            renombrar = {
                "Nivel_Mercado": "Categoría Mercado",
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
# PESTAÑA 6: FASE 3 - SELL-OUT LIBRE POR TERRITORIO, SUCURSAL Y LÍNEA
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
                            top_crec = ", ".join([f"**{r[col_prod_v]}** en {r['NOMBRE_CLIENTE_1']} (${r['Q2']:,.2f} ➔ ${r['Q3']:,.2f})" for _, r in en_alza.head(3).iterrows()])
                            lineas_so.append(f"- **🟢 Motores de Crecimiento (Q3):** Excelente tracción en {top_crec}. Asegurar stock de seguridad.")
                        if not en_caida.empty:
                            top_fuga = ", ".join([f"**{r[col_prod_v]}** en {r['NOMBRE_CLIENTE_1']} (cayó de ${r['Q2']:,.2f} a ${r['Q3']:,.2f})" for _, r in en_caida.head(3).iterrows()])
                            lineas_so.append(f"- **🔴 Alerta de Fuga / Desabasto en Q3:** Revisar inventario y rotación en {top_fuga}. Cruzar con la receta de los médicos de la zona.")

                        reporte_base_so = "\n".join(lineas_so)
                        prompt_ventas = f"{REGLAS_FARMA}\nCon base en este diagnóstico exacto de Sell-Out, agrega 2 recomendaciones de Trade Marketing para Erick Calderón:\n{reporte_base_so}"
                        res_v = llamar_gemini(prompt_ventas)
                        st.info(res_v if (res_v and len(res_v) > 60) else reporte_base_so)
            else:
                st.info("No hay datos para la combinación de filtros seleccionada.")
    else: st.error("[SISTEMA] No hay cruce de rutas de venta.")

# ==============================================================================
# PESTAÑA 7: FASE 4 - ANÁLISIS POST-VISITA (UNIDAD 9 MANUAL TVP) & BITÁCORA CRM
# ==============================================================================
with tab_bitacora:
    st.markdown(f"#### [UNIDAD 9: ANÁLISIS POST-VISITA Y CONSOLA CRM - {medico_sel}]")
    st.caption("El Análisis Post-Visita alimenta la Planificación Previa de tu siguiente ciclo con este médico.")
    with st.form("form_bitacora_crm"):
        cb1, cb2, cb3, cb4 = st.columns(4)
        with cb1:
            prod_promovido = st.selectbox("1. Producto Primario (P1):", [m["producto"] for m in MERCADOS_PRIORITARIOS.values()])
        with cb2:
            prod_puente = st.selectbox("2. Producto Puente (P2/P3):", ["Ninguno"] + [m["producto"] for m in MERCADOS_PRIORITARIOS.values()], index=2)
        with cb3:
            resultado_obj = st.selectbox("3. ¿Alcanzó Objetivo SMART?:", ["Sí - Objetivo Principal Logrado", "Parcial - Se logró Objetivo de Respaldo", "Pendiente - Seguimiento en próxima visita"])
        with cb4:
            escala_post = st.selectbox("4. Nuevo Escalón de Adopción:", ["1. No Consciente", "2. Consciente", "3. Prueba (2-10 Pxs)", "4. Adopción (25-50%)", "5. Lealtad (>50%)"])
        
        cb5, cb6 = st.columns(2)
        with cb5:
            compromiso_med = st.text_input("Compromiso del Médico (¿A qué se comprometió?):", value="Recetar en los próximos 5 pacientes de la semana")
        with cb6:
            compromiso_vis = st.text_input("Compromiso Tuyo como Visitador:", value=f"Garantizar stock en {top_farmacias_ciudad_str.split(',')[0]} y traer estudio clínico")

        notas_visita = st.text_area("Necesidades descubiertas / Objeciones manejadas (Apertura para la próxima visita):", placeholder="Ej: Expresó preocupación por tolerabilidad gástrica; aceptó el beneficio de micropellets...")
        
        if st.form_submit_button("✅ [REGISTRAR ANÁLISIS POST-VISITA EN CRM]", use_container_width=True, type="primary"):
            nueva_visita = {
                "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Ciudad": ciudad,
                "Médico": medico_sel,
                "Especialidad": especialidad,
                "Categoría": categoria,
                "Producto_Primario": prod_promovido,
                "Producto_Puente": prod_puente,
                "Logro_SMART": resultado_obj,
                "Escala_Adopcion": escala_post,
                "Compromiso_Medico": compromiso_med,
                "Compromiso_Visitador": compromiso_vis,
                "Notas_Proxima_Apertura": notas_visita
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
            st.success(f"Análisis Post-Visita de {medico_sel} guardado exitosamente.")

    df_hist_crm = pd.DataFrame(st.session_state.bitacora_memoria)
    if os.path.exists(ARCHIVO_BITACORA):
        try: df_hist_crm = pd.read_excel(ARCHIVO_BITACORA)
        except: pass
    if not df_hist_crm.empty:
        st.markdown("##### 📂 Historial de Análisis Post-Visita Registradas")
        st.dataframe(df_hist_crm.tail(20), hide_index=True, use_container_width=True)
        csv_crm = df_hist_crm.to_csv(index=False).encode('utf-8-sig')
        st.download_button("⬇️ Descargar Historial Post-Visita CRM (CSV/Excel)", data=csv_crm, file_name=f"Bitacora_TVP_Gutis_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")

# ==============================================================================
# PESTAÑA 8: ITINERARIO DE RUTA MULTIDIMENSIONAL (CON FILTRO P1, P2, P3)
# ==============================================================================
with tab_ruta:
    st.markdown("#### [ITINERARIO INTELIGENTE POR TERRITORIO, NIVEL DE MERCADO (P1, P2, P3) Y POTENCIAL]")
    st.caption("Filtra por Prioridad de Mercado (Categoría 1, 2 o 3 de Mercado), Ciudad, Especialidad o Categoría del Médico.")
    
    cr0, cr_p, cr1, cr2, cr3 = st.columns([1.1, 1.2, 1.4, 1.1, 0.8])
    with cr0:
        ciudades_ruta_sel = st.multiselect("📍 1. Ciudad:", LISTA_CIUDADES_REALES, default=[ciudad] if ciudad in LISTA_CIUDADES_REALES else [], placeholder="Todo el panel...")
    with cr_p:
        prio_ruta_sel = st.selectbox("🏅 2. Nivel de Mercado:", ["Todos (P1, P2, P3)", "Solo Prioridad 1 (Foco Core)", "Solo Prioridad 2 (Expansión)", "Solo Prioridad 3 (Complemento)"])
    
    df_ruta_zona = df_panel[df_panel["CIUDAD"].isin(ciudades_ruta_sel)].copy() if ciudades_ruta_sel else df_panel.copy()

    mercados_disp_ruta = LISTA_MERCADOS_REALES
    if "Prioridad 1" in prio_ruta_sel:
        mercados_disp_ruta = [m for m in LISTA_MERCADOS_REALES if obtener_meta_mercado(m)["prioridad"] == 1]
    elif "Prioridad 2" in prio_ruta_sel:
        mercados_disp_ruta = [m for m in LISTA_MERCADOS_REALES if obtener_meta_mercado(m)["prioridad"] == 2]
    elif "Prioridad 3" in prio_ruta_sel:
        mercados_disp_ruta = [m for m in LISTA_MERCADOS_REALES if obtener_meta_mercado(m)["prioridad"] == 3]

    with cr1:
        mercados_ruta_sel = st.multiselect("🎯 3. Mercados Específicos:", mercados_disp_ruta, placeholder="Todos los del nivel...")
    with cr2:
        esps_ruta_disp = sorted(df_ruta_zona["Especialidad"].dropna().unique().tolist()) if "Especialidad" in df_ruta_zona.columns else []
        esps_ruta_sel = st.multiselect("🩺 4. Especialidad:", esps_ruta_disp, placeholder="Todas...")
    with cr3:
        cats_ruta_disp = sorted([str(c) for c in df_ruta_zona["CATEGORIA"].dropna().unique().tolist()]) if "CATEGORIA" in df_ruta_zona.columns else []
        cats_ruta_sel = st.multiselect("⭐ 5. Cat Médico:", cats_ruta_disp, placeholder="Todas...")

    if esps_ruta_sel and "Especialidad" in df_ruta_zona.columns:
        df_ruta_zona = df_ruta_zona[df_ruta_zona["Especialidad"].isin(esps_ruta_sel)]
    if cats_ruta_sel and "CATEGORIA" in df_ruta_zona.columns:
        df_ruta_zona = df_ruta_zona[df_ruta_zona["CATEGORIA"].astype(str).isin(cats_ruta_sel)]

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
            resumen_r["Pxs Competencia (Oportunidad)"] = (resumen_r["Pxs Totales"] - resumen_r["Pxs Gutis"]).astype(int)
            resumen_r["Pxs Totales"] = resumen_r["Pxs Totales"].astype(int)
            resumen_r["Pxs Gutis"] = resumen_r["Pxs Gutis"].astype(int)

            how_merge = "inner" if (mercados_ruta_sel or "Solo" in prio_ruta_sel) else "left"
            df_mostrar = pd.merge(df_mostrar, resumen_r, on="Médico", how=how_merge).fillna(0)
            for c_int in ["Pxs Totales", "Pxs Gutis", "Pxs Competencia (Oportunidad)"]:
                if c_int in df_mostrar.columns: df_mostrar[c_int] = df_mostrar[c_int].astype(int)
            df_mostrar = df_mostrar.sort_values(by=["Pxs Competencia (Oportunidad)", "Pxs Totales"], ascending=[False, False])

    st.dataframe(df_mostrar, hide_index=True, use_container_width=True)
    csv_ruta = df_mostrar.to_csv(index=False).encode('utf-8-sig')
    st.download_button("⬇️ Exportar Hoja de Ruta Filtrada (CSV/Excel)", data=csv_ruta, file_name="Hoja_De_Ruta_Gutis.csv", mime="text/csv")
