import streamlit as st
import pandas as pd
import requests
import os
import json
import re
import unicodedata
from datetime import datetime
import numpy as np
import base64

# --- CONFIGURACIÓN CORPORATIVA DE PÁGINA ---
st.set_page_config(
    page_title="Gutis BI | Terminal de Inteligencia Comercial",
    layout="wide",
    initial_sidebar_state="expanded"
)

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
ARCHIVO_BITACORA = "HISTORIAL_VISITAS.xlsx"
ARCHIVO_PERFIL_360 = "PERFIL_360_MEDICOS.xlsx"

def normalizar_txt(texto):
    if pd.isna(texto):
        return ""
    t = str(texto).strip().upper()
    return ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')

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

# --- VADEMÉCUM OFICIAL GUTIS NICARAGUA 2026 Y CLASES TERAPÉUTICAS ---
MERCADOS_PRIORITARIOS = {
    "MR TALERDIN": {
        "producto": "Talerdín",
        "clase_terapeutica": "Antihistamínicos H1 Sistémicos (R06A)",
        "prioridad": 1,
        "categoria_mercado": "Prioridad 1 (Foco Core)",
        "apto_pediatria": True,
        "match_mercados": ["TALERDIN", "ANTIHISTAMINICO", "R06A", "CETIRIZINA"],
        "paciente_meta": "Pacientes con rinitis alérgica, conjuntivitis alérgica, urticaria o prurito que requieren control antihistamínico seguro.",
        "paciente_meta_ped": "Pacientes pediátricos y lactantes con rinitis alérgica, urticaria o prurito que requieren alivio seguro sin irritación gástrica.",
        "caracteristica": "Cetirizina en Tabletas (10 mg), Jarabe (60 ml 100% libre de alcohol) y Solución Gotas (10 ml: 1 gota por cada 2 kg de peso en menores de 2 años).",
        "beneficio": "Garantiza apego total al tratamiento sin rechazo por sabor ni efectos adversos gástricos por excipientes alcohólicos.",
        "nicho_flanqueo": "Lactantes y niños pequeños con reflujo o intolerancia al excipiente alcohólico de otros jarabes antihistamínicos.",
        "love_brand": "Tranquilidad nocturna para el paciente y su familia desde la primera toma, 100% libre de alcohol."
    },
    "MR BIOTOS": {
        "producto": "Biotos Inmune",
        "clase_terapeutica": "Expectorantes, Fitofármacos e Inmunomoduladores Respiratorios (R05C)",
        "prioridad": 1,
        "categoria_mercado": "Prioridad 1 (Foco Core)",
        "apto_pediatria": True,
        "match_mercados": ["BIOTOS", "HEDERA", "PELARGONIUM", "FITOFARMACO", "ANTITUSIVO", "EXPECTORANTE"],
        "paciente_meta": "Pacientes con tos seca, tos con flemas y secreción nasal en resfriado común, bronquitis, rinosinusitis y faringitis viral.",
        "paciente_meta_ped": "Pacientes pediátricos (desde los 2 años) con IVRS virales, tos seca o con flemas y dificultad para expulsar secreciones.",
        "caracteristica": "Fórmula fitofarmacológica dual única: Hedera hélix (35 mg) + Pelargonium sidoides (12.5 mg) en presentación Pediátrica (120 ml) y Adulto (170 ml).",
        "beneficio": "Alivia la tos seca y con flemas mientras estimula los mecanismos defensivos antivirales y antibacterianos (efecto inmunorregulador).",
        "nicho_flanqueo": "Pacientes con cuadros respiratorios virales donde un mucolítico simple (solo Hedera) no aporta actividad inmunorreguladora.",
        "love_brand": "Devolver la respiración libre y estimular las defensas naturales con respaldo científico."
    },
    "MR CLEMBROXIL": {
        "producto": "Clembroxil Compuesto",
        "clase_terapeutica": "Mucolíticos con Broncodilatador (R05C / R03C)",
        "prioridad": 1,
        "categoria_mercado": "Prioridad 1 (Foco Core)",
        "apto_pediatria": True,
        "match_mercados": ["CLEMBROXIL", "CLENBUTEROL", "AMBROXOL", "MUCOLITICO"],
        "paciente_meta": "Pacientes con patologías respiratorias agudas y crónicas que cursan con retención de secreciones y broncoespasmo.",
        "paciente_meta_ped": "Pacientes pediátricos y lactantes con broncoespasmo, sibilancias y retención severa de flemas (dosificación exacta a 2 gotas/kg).",
        "caracteristica": "Sinergia de Ambroxol (7.5 mg) + Clenbuterol (5 mcg) en Jarabe (120 ml) y Solución Gotas Pediátricas (20 ml), 100% libre de azúcar y alcohol.",
        "beneficio": "Abre el bronquio y fluidifica el moco simultáneamente, despejando las vías respiratorias sin irritación por azúcar o alcohol.",
        "nicho_flanqueo": "Pacientes con tos espástica y cierre bronquial donde un mucolítico aislado no resuelve el broncoespasmo.",
        "love_brand": "Respaldo respiratorio contundente y seguro cuando al paciente le falta el aire."
    },
    "MR MOMETZONA": {
        "producto": "Mometzona",
        "clase_terapeutica": "Corticosteroides Nasales Tópicos (R01A)",
        "prioridad": 1,
        "categoria_mercado": "Prioridad 1 (Foco Core)",
        "apto_pediatria": True,
        "match_mercados": ["MOMETZONA", "MOMETASONA", "NASAL", "R01A"],
        "paciente_meta": "Pacientes con rinitis alérgica u obstrucción nasal inflamatoria que requieren control local sin irritación.",
        "paciente_meta_ped": "Pacientes pediátricos (2 a 11 años: 1 pulsación al día) y adolescentes con rinitis alérgica y congestión nasal persistente.",
        "caracteristica": "Mometasona furoato al 0.05% en spray nasal acuoso (140 aplicaciones), suspensión 100% libre de alcohol.",
        "beneficio": "Desinflama la mucosa nasal desde la primera aplicación diaria sin causar ardor, resequedad ni sangrado nasal.",
        "nicho_flanqueo": "Pacientes con mucosa nasal sensible que abandonan otros sprays por ardor o presencia de alcohol.",
        "love_brand": "Descongestionar y devolver el descanso reparador con suavidad acuosa libre de alcohol."
    },
    "MR VENTILAR": {
        "producto": "Ventilar",
        "clase_terapeutica": "Antileucotrienos y Antiasmáticos Sistémicos (R03D)",
        "prioridad": 1,
        "categoria_mercado": "Prioridad 1 (Foco Core)",
        "apto_pediatria": True,
        "match_mercados": ["VENTILAR", "MONTELUKAST", "LEUCOTRIENO", "R03D"],
        "paciente_meta": "Pacientes con asma bronquial o rinitis alérgica que requieren control preventivo nocturno.",
        "paciente_meta_ped": "Pacientes pediátricos desde los 6 meses hasta los 14 años con hiperreactividad bronquial, asma o rinitis alérgica.",
        "caracteristica": "Montelukast sódico en 3 presentaciones exactas: 4 mg masticable sabor naranja (6 meses a 5 años), 5 mg masticable sabor tutti-chicle (6 a 14 años) y 10 mg recubierto.",
        "beneficio": "Excelente adherencia pediátrica por su sabor agradable y control sostenido de leucotrienos con una sola toma nocturna.",
        "nicho_flanqueo": "Pacientes que requieren terapia continua de control sin abandonar el esquema por costo o mal sabor.",
        "love_brand": "Libertad para que el paciente descanse toda la noche sin crisis respiratorias."
    },
    "MR GASTROALIVIO": {
        "producto": "Gastroalivio",
        "clase_terapeutica": "Inhibidores de la Bomba de Protones y Antiulcerosos (A02B)",
        "prioridad": 1,
        "categoria_mercado": "Prioridad 1 (Foco Core)",
        "apto_pediatria": False,
        "match_mercados": ["GASTROALIVIO", "ESOMEPRAZOL", "OMEPRAZOL", "PANTOPRAZOL", "LANSOPRAZOL", "DEXLANSOPRAZOL", "ANTIULCEROSO", "A02B"],
        "paciente_meta": "Pacientes adultos con ERGE, gastropatía por AINEs, hiperclorhidria o en erradicación de Helicobacter pylori.",
        "paciente_meta_ped": "Pacientes adolescentes mayores y adultos con ERGE o gastritis erosiva.",
        "caracteristica": "Esomeprazol 40 mg en cápsulas de liberación retardada con micropellets gastrorresistentes (libre de gluten y lactosa) + Plan Paciente 2+1.",
        "beneficio": "Protección gástrica y control ácido por 24 horas completas, sumado al Plan Paciente 2+1 (compra 2 cajas y recibe 1 gratis) que asegura el tratamiento completo.",
        "nicho_flanqueo": "Pacientes con ERGE rebelde donde los IBPs convencionales no cubren las 24 horas o el paciente abandona el tratamiento por costo.",
        "love_brand": "Tecnología de micropellets y respaldo 2+1 que protegen el estómago y la economía del paciente."
    },
    "MR DALIVIO": {
        "producto": "Dalivio / Dalivio Tramax",
        "clase_terapeutica": "Analgésicos y Antiinflamatorios No Esteroideos - AINEs (M01A / N02B)",
        "prioridad": 1,
        "categoria_mercado": "Prioridad 1 (Foco Core)",
        "apto_pediatria": False,
        "match_mercados": ["DALIVIO", "DALIVIUM", "DEXKETOPROFENO", "TRAMAX", "DISFLAM", "AINE", "ANALGESICO", "M01A"],
        "paciente_meta": "Pacientes adultos con dolor agudo de moderado a intenso (musculoesquelético, dismenorrea, odontalgia, cólico renal o dolor postoperatorio).",
        "paciente_meta_ped": "Pacientes adolescentes mayores con dolor agudo traumático, odontalgia o dismenorrea.",
        "caracteristica": "Dexketoprofeno en 3 vías (Tabletas 25 mg, Solución oral bebible 25 mg/10 ml e Inyectable 50 mg/2 ml) + Dalivio Tramax (Dexketoprofeno 25 mg + Tramadol 75 mg para analgesia multimodal).",
        "beneficio": "Alivio rápido y potente del dolor agudo en minutos (sobre bebible o ampolla) y analgesia multimodal en dolor severo.",
        "nicho_flanqueo": "Pacientes con dolor agudo severo donde otros AINEs de la categoría tardan demasiado en actuar o irritan la mucosa gástrica.",
        "love_brand": "Aliados del alivio rápido para devolverle la funcionalidad al paciente en minutos."
    },
    "MR CONFLEXIL": {
        "producto": "Conflexil / Conflexil Plus Shot",
        "clase_terapeutica": "Relajantes Musculares de Acción Central y Combinaciones (M03B)",
        "prioridad": 2,
        "categoria_mercado": "Prioridad 2 (Expansión)",
        "apto_pediatria": False,
        "match_mercados": ["CONFLEXIL", "CONRELAX", "TIOCOLCHICOSIDO", "MIORRELAJANTE", "RELAJANTE MUSCULAR", "M03B"],
        "paciente_meta": "Pacientes adultos y adolescentes (>16 años) con contracturas musculares, cervicalgia, dorsalgia o lumbalgia aguda.",
        "paciente_meta_ped": "Adolescentes a partir de los 16 años con contracturas musculares deportivas o posturales.",
        "caracteristica": "Conflexil (Tiocolchicósido 4 mg y Fuerte 8 mg que NO produce sueño) + Conflexil Plus Tabletas y Conflexil Plus Shot (bebible en stick pack con Tiocolchicósido 4 mg + Diclofenaco potásico 50 mg, aprobado por Guías ACP).",
        "beneficio": "Triple acción (analgésica, antiinflamatoria y miorrelajante) de rápida absorción en Shot bebible, recuperando la movilidad sin sedación diurna.",
        "nicho_flanqueo": "Pacientes laboralmente activos con lumbalgia o contractura que no pueden permitirse la somnolencia de otros relajantes.",
        "love_brand": "Liberar el movimiento del paciente sin adormecer su ritmo de vida."
    },
    "MR VALERPAN": {
        "producto": "Valerpan",
        "clase_terapeutica": "Corticosteroides Sistémicos Inyectables de Depósito (H02A)",
        "prioridad": 2,
        "categoria_mercado": "Prioridad 2 (Expansión)",
        "apto_pediatria": True,
        "match_mercados": ["VALERPAN", "BETAMETASONA", "CORTICOSTEROIDE", "H02A"],
        "paciente_meta": "Pacientes con procesos inflamatorios severos, crisis alérgicas agudas o patologías articulares que requieren corticoterapia de doble acción.",
        "paciente_meta_ped": "Pacientes con cuadros alérgicos o inflamatorios agudos severos que requieren control inmediato y sostenido.",
        "caracteristica": "Fosfato sódico de Betametasona + Dipropionato de Betametasona en ampolla de 1 ml y 2 ml con viscosidad adecuada y óptima homogeneidad.",
        "beneficio": "Doble acción comprobada: inicio rápido a los 30 minutos (fosfato) y efecto prolongado hasta por 30 días (dipropionato) en una aplicación suave.",
        "nicho_flanqueo": "Cuadros inflamatorios o alérgicos agudos donde un corticoide simple pierde efecto rápido y genera recaída.",
        "love_brand": "Calidad garantizada con acción inmediata en 30 minutos y respaldo prolongado."
    },
    "MR RENOVART": {
        "producto": "Renovart Platinum",
        "clase_terapeutica": "Condroprotectores y Antirreumáticos Específicos (M01C / M09A)",
        "prioridad": 2,
        "categoria_mercado": "Prioridad 2 (Expansión)",
        "apto_pediatria": False,
        "match_mercados": ["RENOVART", "COLAGENO", "GLUCOSAMINA", "ARTICULAR"],
        "paciente_meta": "Pacientes adultos con dolor articular inflamatorio, desgaste de cartílago o enfermedades degenerativas articulares.",
        "paciente_meta_ped": "Adolescentes deportistas con sobrecarga articular.",
        "caracteristica": "Fórmula pentavalente en sticks sabor naranja: Colágeno 100% hidrolizado bioactivo (10 g) + Cúrcuma longa (400 mg) + N-AcetilGlucosamina (1000 mg) + Condroitina (800 mg) + Vitamina C (60 mg).",
        "beneficio": "Nutre el cartílago y controla el dolor e inflamación articular gracias a los curcuminoides, sin azúcar, sin lactosa y bajo en sodio.",
        "nicho_flanqueo": "Pacientes con artrosis donde un colágeno simple sin cúrcuma ni glucosamina no alivia el dolor articular.",
        "love_brand": "Fortalecer las articulaciones y favorecer la movilidad diaria con la fórmula más completa."
    },
    "MR MUPIRAL": {
        "producto": "Mupiral",
        "clase_terapeutica": "Antibióticos Tópicos Dermatológicos (D06A)",
        "prioridad": 2,
        "categoria_mercado": "Prioridad 2 (Expansión)",
        "apto_pediatria": True,
        "match_mercados": ["MUPIRAL", "MUPIROCINA", "D06A"],
        "paciente_meta": "Pacientes con infecciones bacterianas primarias de la piel (impétigo, foliculitis, furunculosis) o secundarias (heridas, cortaduras, quemaduras).",
        "paciente_meta_ped": "Pacientes pediátricos (desde los 2 meses de edad) con impétigo, foliculitis o heridas sobreinfectadas.",
        "caracteristica": "Mupirocina al 2% en ungüento tópico (tubo de 15 g), seguro en adultos y niños desde los 2 meses de edad.",
        "beneficio": "Erradicación bacteriana localizada altamente eficaz con excelente tolerabilidad cutánea.",
        "nicho_flanqueo": "Infecciones cutáneas o heridas donde otros antibióticos tópicos ya presentan resistencia.",
        "love_brand": "Seguridad antibiótica tópica de primera línea desde los 2 meses de edad."
    },
    "MR BICORPAN": {
        "producto": "Bicorpan",
        "clase_terapeutica": "Corticosteroides Tópicos Combinados Polivalentes (D07C)",
        "prioridad": 2,
        "categoria_mercado": "Prioridad 2 (Expansión)",
        "apto_pediatria": True,
        "match_mercados": ["BICORPAN", "D07C"],
        "paciente_meta": "Pacientes (>12 años y adultos) con dermatitis inflamatorias complicadas con infecciones por bacterias y/o hongos (piodermias, tiñas).",
        "paciente_meta_ped": "Pacientes mayores de 12 años con dermatitis alérgica o por contacto sobreinfectada con hongos o bacterias.",
        "caracteristica": "Fórmula cuádruple en crema (15 g): Betametasona (0.5 mg) + Gentamicina (1 mg) + Tolnaftato (10 mg) + Yodoclorohidroxiquinoleína (10 mg).",
        "beneficio": "Controla simultáneamente la inflamación, el prurito, la infección bacteriana y la micosis en lesiones dérmicas mixtas.",
        "nicho_flanqueo": "Dermatitis mixtas rebeldes donde una crema simple no cubre hongos y bacterias a la vez.",
        "love_brand": "Resolución integral para afecciones complejas de la piel."
    },
    "MR FEMGYL": {
        "producto": "Femgyl",
        "clase_terapeutica": "Anticonceptivos Hormonales Sistémicos Inyectables (G03A)",
        "prioridad": 3,
        "categoria_mercado": "Prioridad 3 (Complemento)",
        "apto_pediatria": False,
        "match_mercados": ["FEMGYL"],
        "paciente_meta": "Pacientes en edad reproductiva que buscan anticoncepción hormonal mensual cómoda y segura.",
        "paciente_meta_ped": "Pacientes ginecológicas en control anticonceptivo.",
        "caracteristica": "Enantato de noretisterona (50 mg) + Valerato de estradiol (5 mg) en ampolla de 1 ml de aplicación mensual fecha calendario.",
        "beneficio": "Alta eficacia anticonceptiva en una sola aplicación mensual que evita olvidos diarios.",
        "nicho_flanqueo": "Usuarias que olvidan la toma diaria de tabletas orales.",
        "love_brand": "Tranquilidad y confianza mensual en salud femenina."
    },
    "MR NORGYLEN": {
        "producto": "Norgylen",
        "clase_terapeutica": "Anticonceptivos Hormonales Orales Combinados (G03A)",
        "prioridad": 3,
        "categoria_mercado": "Prioridad 3 (Complemento)",
        "apto_pediatria": False,
        "match_mercados": ["NORGYLEN"],
        "paciente_meta": "Pacientes que requieren anticoncepción oral hormonal combinada confiable.",
        "paciente_meta_ped": "Pacientes ginecológicas en regulación de ciclo o anticoncepción.",
        "caracteristica": "Levonorgestrel (0.15 mg) + Etinilestradiol (0.03 mg) en caja con 21 tabletas recubiertas.",
        "beneficio": "Control predecible del ciclo menstrual con alta eficacia y seguridad.",
        "nicho_flanqueo": "Pacientes que buscan estabilidad hormonal oral con respaldo farmacéutico.",
        "love_brand": "Cuidado confiable todos los días para la mujer."
    },
    "MR ANSIOLIT": {
        "producto": "Ansiolit",
        "clase_terapeutica": "Ansiolíticos Derivados de Benzodiazepinas (N05B)",
        "prioridad": 3,
        "categoria_mercado": "Prioridad 3 (Complemento)",
        "apto_pediatria": False,
        "match_mercados": ["ANSIOLIT", "ALPRAZOLAM", "ANSIOLITICO", "N05B"],
        "paciente_meta": "Pacientes adultos con ansiedad generalizada, ansiedad asociada a depresión o estados de pánico.",
        "paciente_meta_ped": "Pacientes adultos en manejo de ansiedad.",
        "caracteristica": "Alprazolam 0.5 mg en tabletas ranuradas para dosificación individualizada.",
        "beneficio": "Rápido control de las crisis de ansiedad y síntomas somáticos asociados.",
        "nicho_flanqueo": "Pacientes con crisis de angustia o insomnio por ansiedad aguda.",
        "love_brand": "Paz mental y control oportuno en trastornos de ansiedad."
    },
    "MR DEPAX": {
        "producto": "Depax",
        "clase_terapeutica": "Antidepresivos ISRS - Sertralina (N06A)",
        "prioridad": 3,
        "categoria_mercado": "Prioridad 3 (Complemento)",
        "apto_pediatria": False,
        "match_mercados": ["DEPAX", "SERTRALINA"],
        "paciente_meta": "Pacientes adultos con depresión, TOC, trastorno de pánico, estrés postraumático o fobia social.",
        "paciente_meta_ped": "Pacientes en manejo por neurociencias.",
        "caracteristica": "Sertralina 50 mg en tabletas recubiertas con Sello de Bioequivalencia Comprobada.",
        "beneficio": "Garantiza idéntica biodisponibilidad y eficacia clínica que el innovador con un costo accesible para el apego a largo plazo.",
        "nicho_flanqueo": "Pacientes crónicos que necesitan seguridad bioequivalente certificada.",
        "love_brand": "Bioequivalencia comprobada para acompañar la recuperación emocional."
    },
    "MR FELICITAT": {
        "producto": "Felicitat",
        "clase_terapeutica": "Antidepresivos ISRS - Escitalopram (N06A)",
        "prioridad": 3,
        "categoria_mercado": "Prioridad 3 (Complemento)",
        "apto_pediatria": False,
        "match_mercados": ["FELICITAT", "ESCITALOPRAM"],
        "paciente_meta": "Pacientes adultos con episodios depresivos mayores, trastorno de angustia o ansiedad generalizada.",
        "paciente_meta_ped": "Pacientes en manejo de estado de ánimo.",
        "caracteristica": "Escitalopram en presentaciones de 10 mg y 20 mg (30 tabletas recubiertas) con acción dual en el receptor SERT.",
        "beneficio": "Inhibición altamente selectiva de la recaptación de serotonina para una mejoría emocional sostenida.",
        "nicho_flanqueo": "Pacientes que requieren ajustar dosis entre 10 mg y 20 mg con excelente tolerabilidad.",
        "love_brand": "Ayudar a miles de pacientes a volver a disfrutar de la vida."
    }
}

PRODUCTOS_GUTIS = [
    "GASTROALIVIO", "TALERDIN", "TALERDÍN", "DALIVIO", "DALIVIUM", "CONFLEXIL", "CONRELAX",
    "VALERPAN", "RENOVART PLATINUM", "BIOTOS", "CLEMBROXIL", "MOMETZONA",
    "VENTILAR", "FEMGYL", "NORGYLEN", "BICORPAN", "MUPIRAL", "ANSIOLIT",
    "DEPAX", "FELICITAT"
]

REGLAS_FARMA = """
REGLAS ESTRICTAS DE NEGOCIO Y VADEMÉCUM OFICIAL GUTIS NICARAGUA 2026:
1. CERO EMOJIS: No utilices ningún emoji ni ícono decorativo en tu respuesta. Usa viñetas limpias, negritas y encabezados ejecutivos.
2. CONCEPTO DE MERCADO Y CLASE TERAPÉUTICA: Cada producto de Gutis compite contra TODA LA CLASE TERAPÉUTICA (no solo contra su mismo principio activo). Por ejemplo, Talerdín compite contra todos los antihistamínicos del mercado (Cetirizina, Desloratadina, Levocetirizina, Loratadina, Fexofenadina, etc.); Gastroalivio compite contra todos los IBPs (Esomeprazol, Omeprazol, Pantoprazol, Lansoprazol, Dexlansoprazol); Dalivio compite contra todos los AINEs/analgésicos de su categoría.
3. VADEMÉCUM NICARAGUA 2026: Jamás menciones marcas que no existen en Nicaragua como 'Disflam', 'Conrelax', 'Dalivium', 'Valvirex' o 'Primabela'. Usa siempre los nombres oficiales de Nicaragua: Conflexil (4mg y Fuerte 8mg), Conflexil Plus / Conflexil Plus Shot, Dalivio, Dalivio Tramax, Valerpan, Renovart Platinum, Biotos Inmune, Clembroxil Compuesto, Mometzona, Talerdín, Ventilar, Gastroalivio (Plan Paciente 2+1), Femgyl, Norgylen, Bicorpan, Mupiral, Ansiolit, Depax y Felicitat.
4. COHERENCIA CON LA ESCALA DE ADOPCIÓN (MANUAL TVP):
   - Si el médico está en LEALTAD (>50% MS) o ya nos da un volumen alto de la marca: NO uses un guion forzado pidiéndole 'probar en 3 a 5 pacientes'. Agradece su respaldo como socio estratégico, blinda sutilmente la marca y utiliza esa confianza para hacer el PUENTE hacia un segundo mercado donde tengamos brecha.
   - Si está en PRUEBA o ADOPCIÓN PARCIAL (comparte receta): agradece las recetas actuales, indaga su experiencia y migra sutilmente el nicho que aún entrega a la competencia.
   - Si está en NO CONSCIENTE / CONSCIENTE (0 Pxs): aplica sondeo de descubrimiento y pide compromiso inicial de 3 a 5 pacientes.
"""

# --- ESTILOS CSS EJECUTIVOS SIN EMOJIS ---
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; font-family: 'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #0f172a; }
    h1, h2, h3, h4, h5 { color: #0f172a; font-weight: 700; letter-spacing: -0.3px; }
    .header-box { background: #0f172a; padding: 18px 24px; border-radius: 6px; margin-bottom: 16px; border-left: 5px solid #2563eb; }
    .header-title { color: #ffffff; margin: 0; font-size: 1.35rem; font-weight: 800; letter-spacing: 0.3px; }
    .header-sub { color: #94a3b8; margin: 4px 0 0 0; font-size: 0.78rem; text-transform: uppercase; font-weight: 600; letter-spacing: 0.8px; }
    .ticker-bar { background: #ffffff; border: 1px solid #cbd5e1; border-left: 5px solid #1e3a8a; border-radius: 6px; padding: 14px 20px; margin-bottom: 16px; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
    .ticker-item { flex: 1 1 200px; border-right: 1px solid #e2e8f0; padding-right: 14px; }
    .ticker-item:last-child { border-right: none; }
    .ticker-label { font-size: 0.68rem; text-transform: uppercase; color: #64748b; font-weight: 700; letter-spacing: 0.6px; }
    .ticker-val { font-size: 1.15rem; font-weight: 800; color: #0f172a; margin-top: 3px; }
    .ticker-sub { font-size: 0.76rem; color: #475569; font-weight: 500; margin-top: 2px; }
    .canvas-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin-top: 10px; margin-bottom: 16px; }
    .quad-card { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }
    .quad-title { font-size: 0.75rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; padding-bottom: 6px; border-bottom: 2px solid #f1f5f9; }
    .quad-body { font-size: 0.84rem; color: #1e293b; line-height: 1.5; }
    .section-banner { background: #1e293b; color: #f8fafc; padding: 10px 16px; border-radius: 5px; margin-bottom: 14px; border-left: 4px solid #3b82f6; font-weight: 700; font-size: 0.88rem; text-transform: uppercase; letter-spacing: 0.5px; }
    .drill-box { background: #ffffff; border: 1px solid #93c5fd; border-left: 5px solid #2563eb; border-radius: 6px; padding: 16px; margin-top: 12px; margin-bottom: 16px; box-shadow: 0 2px 6px rgba(37,99,235,0.06); }
    .stTabs [data-baseweb="tab-list"] { border-bottom: 2px solid #cbd5e1; gap: 6px; }
    .stTabs [data-baseweb="tab"] { font-size: 0.85rem; font-weight: 700; color: #334155; padding: 10px 18px; border-radius: 6px 6px 0 0; background-color: #e2e8f0; border: none; }
    .stTabs [aria-selected="true"] { color: #ffffff; background-color: #0f172a; box-shadow: inset 0 -3px 0 #2563eb; }
</style>
""", unsafe_allow_html=True)

# --- BUSCADOR INTELIGENTE DE ARCHIVOS EXCEL (SEPTIEMBRE / AGOSTO / CLASES TERAPÉUTICAS) ---
def encontrar_archivo_local(palabras_clave_obligatorias, palabras_preferidas=None):
    archivos_dir = [f for f in os.listdir(".") if f.lower().endswith(".xlsx") and not f.startswith("~$")]
    candidatos = []
    for f in archivos_dir:
        f_norm = normalizar_txt(f)
        if all(normalizar_txt(k) in f_norm for k in palabras_clave_obligatorias):
            score = 0
            if palabras_preferidas:
                for p in palabras_preferidas:
                    if normalizar_txt(p) in f_norm:
                        score += 10
            candidatos.append((score, f))
    if candidatos:
        candidatos.sort(key=lambda x: (-x[0], x[1]))
        return candidatos[0][1]
    return None

@st.cache_data
def cargar_datos():
    f_panel = encontrar_archivo_local(["PANEL"]) or "PANEL ERICK 2026.xlsx"
    df_p = pd.read_excel(f_panel) if os.path.exists(f_panel) else pd.DataFrame()

    f_rx = encontrar_archivo_local(["PRODUCTOS"], ["SEPTIEMBRE", "2026"])
    df_rx = pd.read_excel(f_rx) if (f_rx and os.path.exists(f_rx)) else pd.DataFrame()

    f_labs = encontrar_archivo_local(["LABORATORIOS"], ["SEPTIEMBRE", "2026"])
    df_labs_raw = pd.read_excel(f_labs) if (f_labs and os.path.exists(f_labs)) else pd.DataFrame()

    f_clases = encontrar_archivo_local(["CLASES", "TERAPEUTICAS"], ["SEPTIEMBRE", "2026"])
    df_clases_raw = pd.read_excel(f_clases) if (f_clases and os.path.exists(f_clases)) else pd.DataFrame()

    try:
        df_v1 = pd.read_excel("VENTA PRIMER TRIMESTRE 2026.xlsx")
        df_v1["Trimestre"] = "Q1"
    except:
        df_v1 = pd.DataFrame()
    try:
        df_v2 = pd.read_excel("VENTAS SEGUNDO TRIMESTRE 2026.xlsx")
        df_v2["Trimestre"] = "Q2"
    except:
        df_v2 = pd.DataFrame()
    try:
        df_v3 = pd.read_excel("VENTAS TERCER TRIMESTRE 2026.xlsx", sheet_name="Export")
        df_v3["Trimestre"] = "Q3"
    except:
        try:
            df_v3 = pd.read_excel("VENTAS TERCER TRIMESTRE 2026.xlsx")
            df_v3["Trimestre"] = "Q3"
        except:
            df_v3 = pd.DataFrame()

    dataframes_ventas = [df for df in [df_v1, df_v2, df_v3] if not df.empty]
    df_v = pd.concat(dataframes_ventas, ignore_index=True) if dataframes_ventas else pd.DataFrame()

    for d in [df_p, df_rx, df_v, df_labs_raw, df_clases_raw]:
        if not d.empty:
            d.columns = d.columns.astype(str).str.strip()

    if not df_p.empty and "Médico" in df_p.columns:
        df_p["Médico"] = df_p["Médico"].astype(str).str.strip().str.upper()
    if not df_p.empty and "CIUDAD" in df_p.columns:
        df_p["CIUDAD"] = df_p["CIUDAD"].astype(str).str.strip().str.upper()
    if not df_p.empty and "Especialidad" in df_p.columns:
        df_p["Especialidad"] = df_p["Especialidad"].astype(str).str.strip().str.upper()

    if not df_rx.empty:
        col_m_rx = next((c for c in df_rx.columns if normalizar_txt(c) == "MEDICO"), None)
        if col_m_rx and col_m_rx != "Médico":
            df_rx = df_rx.rename(columns={col_m_rx: "Médico"})
        if "Médico" in df_rx.columns:
            df_rx["Médico"] = df_rx["Médico"].astype(str).str.strip().str.upper()
        if "NOMBRE_PRODUCTO" in df_rx.columns:
            df_rx = df_rx.dropna(subset=["NOMBRE_PRODUCTO"]).copy()
            df_rx["NOMBRE_PRODUCTO"] = df_rx["NOMBRE_PRODUCTO"].astype(str).str.strip()
            df_rx = df_rx[~df_rx["NOMBRE_PRODUCTO"].str.upper().isin(["TOTAL", "NAN", "NONE", ""])].copy()
        if "MERCADO" in df_rx.columns:
            df_rx["MERCADO"] = df_rx["MERCADO"].astype(str).str.strip()

    if not df_labs_raw.empty:
        col_m_l = next((c for c in df_labs_raw.columns if normalizar_txt(c) == "MEDICO"), None)
        if col_m_l and col_m_l != "Médico":
            df_labs_raw = df_labs_raw.rename(columns={col_m_l: "Médico"})
        if "Médico" in df_labs_raw.columns:
            df_labs_raw["Médico"] = df_labs_raw["Médico"].astype(str).str.strip().str.upper()

    if not df_clases_raw.empty:
        col_m_c = next((c for c in df_clases_raw.columns if normalizar_txt(c) == "MEDICO"), None)
        if col_m_c and col_m_c != "Médico":
            df_clases_raw = df_clases_raw.rename(columns={col_m_c: "Médico"})
        if "Médico" in df_clases_raw.columns:
            df_clases_raw["Médico"] = df_clases_raw["Médico"].astype(str).str.strip().str.upper()

    # Si el archivo de Clases Terapéuticas trae un mapeo de Producto -> Clase Terapéutica, enriquecer df_rx
    if not df_clases_raw.empty and not df_rx.empty:
        col_prod_ct = next((c for c in df_clases_raw.columns if "PRODUCTO" in normalizar_txt(c)), None)
        col_clase_ct = next((c for c in df_clases_raw.columns if any(k in normalizar_txt(c) for k in ["CLASE", "TERAPEUTICA", "ATC", "CATEGORIA"])), None)
        if col_prod_ct and col_clase_ct and "CLASE_TERAPEUTICA" not in df_rx.columns:
            mapa_ct = df_clases_raw.dropna(subset=[col_prod_ct, col_clase_ct]).drop_duplicates(subset=[col_prod_ct]).set_index(df_clases_raw[col_prod_ct].astype(str).str.strip().str.upper())[col_clase_ct].to_dict()
            df_rx["CLASE_TERAPEUTICA"] = df_rx["NOMBRE_PRODUCTO"].str.upper().map(mapa_ct).fillna("")

    if not df_v.empty and "DESCRIPCION_RUTA" in df_v.columns:
        df_v["DESCRIPCION_RUTA"] = df_v["DESCRIPCION_RUTA"].astype(str).str.strip().str.upper()

    archivos_cargados = {"panel": f_panel, "rx": f_rx, "labs": f_labs, "clases": f_clases}
    return df_p, df_rx, df_labs_raw, df_clases_raw, df_v, archivos_cargados

df_panel, df_productos, df_labs, df_clases, df_ventas, info_archivos = cargar_datos()

# --- IDENTIFICADOR ESTRICTO DE MERCADOS GUTIS NICARAGUA 2026 (SIN FALSOS POSITIVOS) ---
def es_gutis(nombre_prod):
    n_norm = normalizar_txt(nombre_prod)
    return any(normalizar_txt(g) in n_norm for g in PRODUCTOS_GUTIS)

def clasificar_mercado_gutis(mercado_val):
    """
    Vincula el nombre del MERCADO o CLASE TERAPÉUTICA de Close-Up con el portafolio oficial de Gutis Nicaragua 2026.
    IMPORTANTE: Si el mercado del Excel NO pertenece a las líneas de Nicaragua (ej. Gesimax, Valvirex, etc.),
    retorna None en 'clave_gutis' para que NUNCA se etiquete falsamente como Talerdín o Dalivio.
    """
    m_norm = normalizar_txt(mercado_val)
    if not m_norm or m_norm in ["TOTAL", "NAN", "NONE"]:
        return None

    # Exclusiones explícitas de mercados de otros países o moléculas donde Gutis Nicaragua no participa
    if any(ex in m_norm for ex in ["VALVIREX", "PRIMABELA", "BELEZA", "GESIMAX", "FLUKIT", "ZITRO"]):
        return None

    for m_key, m_info in MERCADOS_PRIORITARIOS.items():
        if any(normalizar_txt(pat) in m_norm for pat in m_info["match_mercados"]):
            return m_info
    return None

def obtener_meta_mercado_seguro(mercado_val):
    info = clasificar_mercado_gutis(mercado_val)
    if info:
        return info
    # Si es un mercado no mapeado pero se consulta en una tabla general, mantener su nombre real sin inventarle Talerdín
    nombre_limpio = str(mercado_val).replace("MR ", "").strip()
    return {
        "producto": f"Mercado {nombre_limpio}",
        "clase_terapeutica": nombre_limpio,
        "prioridad": 3,
        "categoria_mercado": "Otra Categoría Auditada",
        "apto_pediatria": True,
        "match_mercados": [],
        "paciente_meta": f"Pacientes tratados dentro de la categoría {nombre_limpio}.",
        "paciente_meta_ped": f"Pacientes pediátricos dentro de la categoría {nombre_limpio}.",
        "caracteristica": "Portafolio con calidad certificada Gutis.",
        "beneficio": "Eficacia y seguridad clínica comprobada.",
        "nicho_flanqueo": "Pacientes que requieren alta tolerabilidad.",
        "love_brand": "Innovación y tecnología para la vida."
    }

def diagnosticar_escala_adopcion(pxs_gutis_m, pxs_tot_m, ms_gutis_m):
    if pxs_tot_m <= 0:
        return "1. No Consciente", "2. Consciente / 3. Prueba (2-5 Pxs)", "CONQUISTA", "Crear conciencia del perfil de paciente y lograr las primeras 3 recetas de prueba."
    if pxs_gutis_m == 0:
        return "2. Consciente (0% MS)", "3. Prueba (2 a 10 Pxs)", "CONQUISTA", f"Iniciar período de prueba en sus próximos 3 a 5 pacientes (actualmente prescribe {pxs_tot_m} Pxs en otras marcas de la categoría)."
    if ms_gutis_m < 25.0 or (pxs_gutis_m <= 4 and ms_gutis_m < 45.0):
        return f"3. Prueba ({ms_gutis_m:.1f}% MS | {pxs_gutis_m} Pxs)", "4. Adopción (>25% a 50% MS)", "EXPANSION", "Agradecer recetas iniciales, validar experiencia positiva y expandir hacia más del 25% de la categoría."
    if ms_gutis_m < 50.0:
        return f"4. Adopción ({ms_gutis_m:.1f}% MS | {pxs_gutis_m} Pxs)", "5. Lealtad (>50% MS)", "EXPANSION", "Reconocer su respaldo activo y migrar sutilmente el segmento que aún comparte con otras moléculas de la clase terapéutica."
    return f"5. Lealtad ({ms_gutis_m:.1f}% MS | {pxs_gutis_m} Pxs)", "5. Lealtad (Blindaje y Puente)", "LEALTAD", "Agradecer su lealtad como socio clave, blindar presentaciones y utilizar esa confianza como puente hacia una segunda línea."

# Filtrar LISTA_MERCADOS_REALES para mostrar prioritariamente los mercados válidos de Gutis Nicaragua
LISTA_CIUDADES_REALES = sorted([c for c in df_panel["CIUDAD"].dropna().unique() if str(c).strip() not in ["", "NAN"]]) if not df_panel.empty and "CIUDAD" in df_panel.columns else []
LISTA_ESPECIALIDADES_REALES = sorted([e for e in df_panel["Especialidad"].dropna().unique() if str(e).strip() not in ["", "NAN"]]) if not df_panel.empty and "Especialidad" in df_panel.columns else []
LISTA_MERCADOS_TODOS = sorted([m for m in df_productos["MERCADO"].dropna().unique() if str(m).strip() not in ["", "NAN", "TOTAL"]]) if not df_productos.empty and "MERCADO" in df_productos.columns else []
LISTA_MERCADOS_GUTIS = [m for m in LISTA_MERCADOS_TODOS if clasificar_mercado_gutis(m) is not None]
LISTA_MERCADOS_REALES = LISTA_MERCADOS_GUTIS if LISTA_MERCADOS_GUTIS else LISTA_MERCADOS_TODOS

# Columnas dinámicas de prescripción (Mes y YTD)
COL_PXS_MES = next((c for c in df_productos.columns if c.upper() == "PXS-MES"), None) if not df_productos.empty else None
if not COL_PXS_MES and not df_productos.empty:
    COL_PXS_MES = next((c for c in df_productos.columns if "MES" in c.upper() and "PXS" in c.upper()), None)
COL_PXS_YTD = next((c for c in df_productos.columns if c.upper() == "PXS-YTD"), None) if not df_productos.empty else None
if not COL_PXS_YTD and not df_productos.empty:
    COL_PXS_YTD = next((c for c in df_productos.columns if "YTD" in c.upper() and "PXS" in c.upper()), None)
if not COL_PXS_MES and COL_PXS_YTD:
    COL_PXS_MES = COL_PXS_YTD

# Asegurar tipos numéricos en df_productos
if not df_productos.empty:
    if COL_PXS_MES and COL_PXS_MES in df_productos.columns:
        df_productos[COL_PXS_MES] = pd.to_numeric(df_productos[COL_PXS_MES], errors="coerce").fillna(0)
    if COL_PXS_YTD and COL_PXS_YTD in df_productos.columns:
        df_productos[COL_PXS_YTD] = pd.to_numeric(df_productos[COL_PXS_YTD], errors="coerce").fillna(0)
    df_productos["Es_Gutis"] = df_productos["NOMBRE_PRODUCTO"].apply(es_gutis)

# --- INICIALIZACIÓN DE SESIÓN ---
if "chira_history" not in st.session_state: st.session_state.chira_history = []
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "tvp_result" not in st.session_state: st.session_state.tvp_result = None
if "perfiles_memoria" not in st.session_state: st.session_state.perfiles_memoria = {}
if "bitacora_memoria" not in st.session_state: st.session_state.bitacora_memoria = []
if "ultimo_medico_chira" not in st.session_state: st.session_state.ultimo_medico_chira = None
if "ultimo_audio_hash" not in st.session_state: st.session_state.ultimo_audio_hash = None

# --- ENCABEZADO CORPORATIVO LIMPIO ---
corte_activo_txt = info_archivos.get("rx") or "Close-Up Activo"
st.markdown(f"""
<div class='header-box'>
    <div class='header-title'>GUTIS BI — TERMINAL DE INTELIGENCIA COMERCIAL Y MODELO TVP</div>
    <div class='header-sub'>Núcleo I: Inteligencia Territorial y Ruta  |  Núcleo II: Consultorio 360 y Canvas TVP  |  Núcleo III: Copiloto Chira y CRM  |  Fuente: {corte_activo_txt}</div>
</div>
""", unsafe_allow_html=True)

# --- MENÚ LATERAL MULTIFILTRO ---
st.sidebar.markdown("### SELECTOR DE ESPECIALISTA")
ciudades_sb = ["TODAS"] + LISTA_CIUDADES_REALES
ciudad_filtro = st.sidebar.selectbox("1. Territorio / Ciudad:", ciudades_sb)

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
    st.warning("No existen registros para la combinación seleccionada en el menú lateral.")
    st.stop()

idx_med_default = 0
if "medico_forzado_ruta" in st.session_state and st.session_state.medico_forzado_ruta in lista_medicos:
    idx_med_default = lista_medicos.index(st.session_state.medico_forzado_ruta)

medico_sel = st.sidebar.selectbox("4. Especialista Activo:", lista_medicos, index=idx_med_default)

if "medico_chat" not in st.session_state or st.session_state.medico_chat != medico_sel:
    st.session_state.chat_history = []
    st.session_state.tvp_result = None
    st.session_state.medico_chat = medico_sel

info_medico = df_filtrado[df_filtrado["Médico"] == medico_sel].iloc[0]
ciudad = str(info_medico.get("CIUDAD", "N/D")).strip().upper()
especialidad = str(info_medico.get("Especialidad", "N/D")).strip().upper()
categoria = str(info_medico.get("CATEGORIA", "N/D")).strip()
es_pediatra = "PEDIAT" in especialidad

st.sidebar.divider()
st.sidebar.caption(f"Archivos sincronizados:\n- Rx: {info_archivos.get('rx')}\n- Labs: {info_archivos.get('labs')}\n- Clases: {info_archivos.get('clases')}")

# --- PERFIL OMNICANAL 360 ---
perfil_360_actual = st.session_state.perfiles_memoria.get(medico_sel, {})
if not perfil_360_actual and os.path.exists(ARCHIVO_PERFIL_360):
    try:
        df_p360 = pd.read_excel(ARCHIVO_PERFIL_360)
        coincidencias = df_p360[df_p360["Médico"].astype(str).str.upper() == medico_sel]
        if not coincidencias.empty:
            perfil_360_actual = coincidencias.iloc[0].to_dict()
    except:
        pass

contexto_rapport_str = ""
if perfil_360_actual:
    cumple = perfil_360_actual.get("Cumpleaños", "")
    deporte = perfil_360_actual.get("Deporte", "")
    estilo_visita = perfil_360_actual.get("Estilo_Visita", "")
    partes_rapport = []
    if cumple and str(cumple) not in ["nan", ""]: partes_rapport.append(f"Cumpleaños: {cumple}")
    if deporte and str(deporte) not in ["nan", ""]: partes_rapport.append(f"Notas: {deporte}")
    if estilo_visita and str(estilo_visita) not in ["nan", ""]: partes_rapport.append(f"Estilo: {estilo_visita}")
    if partes_rapport: contexto_rapport_str = " | ".join(partes_rapport)

# ==============================================================================
# MOTOR UNIFICADO DE CRUCE MÉDICO-MERCADO (USADO POR RUTA, CONSULTORIO Y CHIRA)
# ==============================================================================
def obtener_desglose_productos_medico(nombre_medico, lista_mercados_filtro=None):
    """
    Devuelve el dataframe detallado de todas las marcas (Gutis y Competencia de la misma clase terapéutica)
    que receta un médico dentro del mercado o mercados seleccionados.
    """
    if df_productos.empty or "Médico" not in df_productos.columns:
        return pd.DataFrame()
    sub = df_productos[df_productos["Médico"] == nombre_medico].copy()
    if sub.empty:
        return pd.DataFrame()
    if lista_mercados_filtro:
        patrones = [normalizar_txt(m.replace("MR ", "")) for m in lista_mercados_filtro]
        sub = sub[sub["MERCADO"].apply(normalizar_txt).apply(lambda x: any(p in x for p in patrones))].copy()
    if sub.empty:
        return pd.DataFrame()

    c_m = COL_PXS_MES if COL_PXS_MES in sub.columns else None
    c_y = COL_PXS_YTD if COL_PXS_YTD in sub.columns else None

    if c_m and c_y:
        sub = sub[(sub[c_m] > 0) | (sub[c_y] > 0)].copy()
    elif c_m:
        sub = sub[sub[c_m] > 0].copy()

    if sub.empty:
        return pd.DataFrame()

    sub["Origen"] = sub["Es_Gutis"].apply(lambda x: "GUTIS" if x else "COMPETENCIA")
    sub["Marca Gutis Objetivo"] = sub["MERCADO"].apply(lambda m: obtener_meta_mercado_seguro(m)["producto"])
    sub["Clase Terapéutica"] = sub["MERCADO"].apply(lambda m: obtener_meta_mercado_seguro(m)["clase_terapeutica"])

    tot_mes_m = sub[c_m].sum() if c_m else 0
    tot_ytd_m = sub[c_y].sum() if c_y else 0
    if c_m and tot_mes_m > 0:
        sub["% Cuota Categoría"] = (sub[c_m] / tot_mes_m * 100).round(1)
    elif c_y and tot_ytd_m > 0:
        sub["% Cuota Categoría"] = (sub[c_y] / tot_ytd_m * 100).round(1)
    else:
        sub["% Cuota Categoría"] = 0.0

    cols_orden = [c for c in [c_m, c_y] if c]
    if cols_orden:
        sub = sub.sort_values(by=cols_orden, ascending=[False] * len(cols_orden))

    cols_out = ["MERCADO", "Clase Terapéutica", "NOMBRE_PRODUCTO", "Origen"]
    if c_m:
        sub[c_m] = sub[c_m].astype(int)
        cols_out.append(c_m)
    if c_y and c_y != c_m:
        sub[c_y] = sub[c_y].astype(int)
        cols_out.append(c_y)
    cols_out.append("% Cuota Categoría")

    ren = {
        "MERCADO": "Mercado Close-Up",
        "NOMBRE_PRODUCTO": "Producto Prescrito (Categoría)",
        c_m: "Pxs Mes",
        c_y: "Pxs YTD"
    }
    return sub[cols_out].rename(columns=ren)

def obtener_ranking_medicos_mercado(ciudad_target=None, esp_target=None, mer_target=None, prio_target=None, incluir_fuera_panel=False):
    """
    Motor único y consistente para la tabla de Ruta y para el asistente Chira.
    Evalúa tanto Pxs-MES como Pxs-YTD para que ningún médico importante (como en Rivas) quede oculto.
    """
    if df_productos.empty:
        return pd.DataFrame()

    df_p_base = df_panel.copy()
    if ciudad_target and "CIUDAD" in df_p_base.columns:
        df_p_base = df_p_base[df_p_base["CIUDAD"].astype(str).str.upper().str.contains(re.escape(ciudad_target.upper()), na=False)].copy()
    if esp_target and "Especialidad" in df_p_base.columns:
        raiz_e = normalizar_txt(esp_target)[:5]
        df_p_base = df_p_base[df_p_base["Especialidad"].apply(normalizar_txt).str.contains(raiz_e, na=False)].copy()

    medicos_panel_set = set(df_p_base["Médico"].dropna().unique())
    info_panel_map = df_p_base.drop_duplicates(subset=["Médico"]).set_index("Médico").to_dict("index")

    if incluir_fuera_panel:
        todos_panel = set(df_panel["Médico"].dropna().unique())
        rx_sub = df_productos[~df_productos["Médico"].isin(todos_panel)].copy()
    else:
        rx_sub = df_productos[df_productos["Médico"].isin(medicos_panel_set)].copy()

    if mer_target:
        if isinstance(mer_target, list):
            pats = [normalizar_txt(m.replace("MR ", "")) for m in mer_target]
            rx_sub = rx_sub[rx_sub["MERCADO"].apply(normalizar_txt).apply(lambda x: any(p in x for p in pats))].copy()
        else:
            kw_m = normalizar_txt(str(mer_target).replace("MR ", ""))
            rx_sub = rx_sub[rx_sub["MERCADO"].apply(normalizar_txt).str.contains(re.escape(kw_m), na=False)].copy()
    elif prio_target:
        rx_sub = rx_sub[rx_sub["MERCADO"].apply(lambda m: (clasificar_mercado_gutis(m) or {}).get("prioridad") == prio_target)].copy()
    else:
        # Por defecto evaluar mercados válidos de Gutis Nicaragua
        rx_sub = rx_sub[rx_sub["MERCADO"].apply(lambda m: clasificar_mercado_gutis(m) is not None)].copy()

    if rx_sub.empty:
        return pd.DataFrame()

    c_m = COL_PXS_MES
    c_y = COL_PXS_YTD

    filas = []
    for nom_doc, grp in rx_sub.groupby("Médico"):
        p_mes_tot = int(grp[c_m].sum()) if c_m else 0
        p_ytd_tot = int(grp[c_y].sum()) if c_y else 0
        p_gut_mes = int(grp[grp["Es_Gutis"]][c_m].sum()) if c_m else 0
        p_gut_ytd = int(grp[grp["Es_Gutis"]][c_y].sum()) if c_y else 0
        p_comp_mes = p_mes_tot - p_gut_mes
        p_comp_ytd = p_ytd_tot - p_gut_ytd

        # Usar la métrica activa (si Mes es 0 pero YTD tiene datos, mostrar volumen efectivo además de desglose)
        vol_efectivo_tot = p_mes_tot if p_mes_tot > 0 else p_ytd_tot
        vol_efectivo_gut = p_gut_mes if p_mes_tot > 0 else p_gut_ytd
        vol_efectivo_comp = p_comp_mes if p_mes_tot > 0 else p_comp_ytd

        if p_mes_tot <= 0 and p_ytd_tot <= 0:
            continue

        grp_ord = grp.sort_values(by=[c_m, c_y] if (c_m and c_y) else [c_m or c_y], ascending=False)
        top_prods_lista = []
        for _, r_p in grp_ord.head(4).iterrows():
            v_p = int(r_p[c_m]) if (c_m and int(r_p[c_m]) > 0) else (int(r_p[c_y]) if c_y else 0)
            if v_p > 0:
                top_prods_lista.append(f"{r_p['NOMBRE_PRODUCTO']} ({v_p})")
        resumen_prods_str = ", ".join(top_prods_lista) if top_prods_lista else str(grp_ord.iloc[0]["NOMBRE_PRODUCTO"])

        grp_no_g = grp_ord[~grp_ord["Es_Gutis"]]
        rival_principal = str(grp_no_g.iloc[0]["NOMBRE_PRODUCTO"]).strip() if not grp_no_g.empty else "Sin competidor activo"

        meta_d = info_panel_map.get(nom_doc, {})
        filas.append({
            "Médico": nom_doc,
            "Especialidad": str(meta_d.get("Especialidad", "ESPECIALISTA")),
            "CATEGORIA": str(meta_d.get("CATEGORIA", "S/C")),
            "CIUDAD": str(meta_d.get("CIUDAD", ciudad_target or "NICARAGUA")),
            "Pxs Mes": p_mes_tot,
            "Pxs YTD": p_ytd_tot,
            "Pxs Totales (Activo)": vol_efectivo_tot,
            "Pxs Gutis": vol_efectivo_gut,
            "Pxs Competencia (Conquista)": vol_efectivo_comp,
            "Rival Principal": rival_principal,
            "Productos que Receta en la Categoría": resumen_prods_str
        })

    df_res = pd.DataFrame(filas)
    if not df_res.empty:
        df_res = df_res.sort_values(
            by=["Pxs Totales (Activo)", "Pxs Competencia (Conquista)", "Pxs YTD"],
            ascending=[False, False, False]
        ).reset_index(drop=True)
    return df_res

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
            df_l_clean[col_ytd_l] = pd.to_numeric(df_l_clean[col_ytd_l], errors="coerce").fillna(0)

    df_rx_c = df_productos.copy() if not df_productos.empty else pd.DataFrame()
    col_ytd_rx = COL_PXS_YTD or COL_PXS_MES

    filas_rendimiento, filas_competencia = [], []

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
                    if not sub_rx_m.empty and sub_rx_m[sub_rx_m["Es_Gutis"]][col_ytd_rx].sum() > 0:
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
                        marca_f = f"[GUTIS] {nom_f} ({ms_f:.2f}%)" if "GUTIS" in nom_f.upper() else f"{nom_f} ({ms_f:.2f}%)"
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
                if COL_PXS_YTD:
                    pxs_ytd_tot = int(sub_m_rx[COL_PXS_YTD].sum())
                    pxs_ytd_gut = int(sub_m_rx[sub_m_rx["Es_Gutis"]][COL_PXS_YTD].sum())
                if COL_PXS_MES:
                    pxs_mes_tot = int(sub_m_rx[COL_PXS_MES].sum())
                    pxs_mes_gut = int(sub_m_rx[sub_m_rx["Es_Gutis"]][COL_PXS_MES].sum())

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

        if pxs_ytd_tot == 0 and pxs_mes_tot == 0 and v_total == 0:
            continue

        if delta_ms_rx >= 1.5 or (pxs_mes_gut > (pxs_ytd_gut / 9.0) and pxs_mes_gut > 0):
            tend_rx_str, rx_crece = f"CRECE ({delta_ms_rx:+.1f}%)", True
        elif delta_ms_rx <= -1.5:
            tend_rx_str, rx_crece = f"CAE ({delta_ms_rx:+.1f}%)", False
        else:
            tend_rx_str, rx_crece = f"ESTABLE ({delta_ms_rx:+.1f}%)", (ms_mes_gut >= 15.0 or pxs_mes_gut > 0)

        if delta_so_pct >= 5.0:
            tend_so_str, so_crece = f"SUBE +{delta_so_pct:.1f}%", True
        elif delta_so_pct <= -10.0:
            tend_so_str, so_crece = f"CAE {delta_so_pct:.1f}%", False
        else:
            tend_so_str, so_crece = f"ESTABLE ({delta_so_pct:+.1f}%)", (v_q3 > 0)

        if rx_crece and so_crece:
            diag_sinc = "[SINCRONIA POSITIVA] Crece receta y crece farmacia"
        elif rx_crece and not so_crece:
            diag_sinc = "[ALERTA FUGA MOSTRADOR] Receta activa pero cae farmacia"
        elif not rx_crece and so_crece:
            diag_sinc = "[TRACCION PDV] Sube farmacia, reforzar consultorio"
        else:
            diag_sinc = "[CONTRACCION DOBLE] Activar plan TVP y Trade"

        filas_sincronia.append({
            "Prioridad": f"P{m_info['prioridad']}",
            "Marca Gutis": prod_nom,
            "Pxs Gutis (YTD / Mes)": f"{pxs_ytd_gut} / {pxs_mes_gut}",
            "% MS YTD": round(ms_ytd_gut, 2),
            "% MS MES": round(ms_mes_gut, 2),
            "Tendencia Rx": tend_rx_str,
            "Sell-Out Q1": round(v_q1, 2),
            "Sell-Out Q2": round(v_q2, 2),
            "Sell-Out Q3": round(v_q3, 2),
            "Var Q3 vs Q2": tend_so_str,
            "Diagnóstico de Sincronía": diag_sinc,
            "_orden_p": m_info["prioridad"],
            "_orden_v": v_total
        })

    df_sinc = pd.DataFrame(filas_sincronia)
    if not df_sinc.empty:
        df_sinc = df_sinc.sort_values(by=["_orden_p", "_orden_v"], ascending=[True, False]).drop(columns=["_orden_p", "_orden_v"])
    return df_sinc

# --- PROCESAMIENTO DE MERCADOS DEL ESPECIALISTA SELECCIONADO EN EL SIDEBAR ---
rx_clean = df_productos[df_productos["Médico"] == medico_sel].copy() if not df_productos.empty else pd.DataFrame()
if not rx_clean.empty:
    # Filtrar únicamente los mercados donde Gutis Nicaragua participa (evita que Gesimax/Dolgenal se disfracen de Talerdín)
    rx_clean["Info_Gutis"] = rx_clean["MERCADO"].apply(clasificar_mercado_gutis)
    rx_gutis_validos = rx_clean[rx_clean["Info_Gutis"].notna()].copy()
    if es_pediatra and not rx_gutis_validos.empty:
        rx_gutis_validos = rx_gutis_validos[rx_gutis_validos["Info_Gutis"].apply(lambda d: d.get("apto_pediatria", True))].copy()
else:
    rx_gutis_validos = pd.DataFrame()

total_pxs_medico = int(rx_gutis_validos[COL_PXS_MES].sum()) if not rx_gutis_validos.empty and COL_PXS_MES else 0
total_ytd_medico_global = int(rx_gutis_validos[COL_PXS_YTD].sum()) if not rx_gutis_validos.empty and COL_PXS_YTD else 0
gutis_pxs_medico = int(rx_gutis_validos[rx_gutis_validos["Es_Gutis"]][COL_PXS_MES].sum()) if total_pxs_medico > 0 else 0
gutis_ytd_medico = int(rx_gutis_validos[rx_gutis_validos["Es_Gutis"]][COL_PXS_YTD].sum()) if total_ytd_medico_global > 0 else 0
comp_pxs_medico = total_pxs_medico - gutis_pxs_medico

cards_ataque_html, num_mercados, mercado_principal_str, producto_ataque_str, share_lider = "", 0, "S/D", "N/D", 0.0
prod_gutis_ataque_oficial = "Talerdín" if es_pediatra else "Gastroalivio"
opciones_mercados_medico = []

if not rx_gutis_validos.empty:
    for m_nom, df_m in rx_gutis_validos.groupby("MERCADO"):
        meta = clasificar_mercado_gutis(m_nom)
        if not meta:
            continue
        prod_gutis_esperado = meta["producto"]
        prio_num = meta["prioridad"]
        cat_merc_txt = meta["categoria_mercado"]

        pxs_tot_m = int(df_m[COL_PXS_MES].sum()) if COL_PXS_MES else 0
        pxs_ytd_m = int(df_m[COL_PXS_YTD].sum()) if COL_PXS_YTD else 0
        pxs_gut_m = int(df_m[df_m["Es_Gutis"]][COL_PXS_MES].sum()) if COL_PXS_MES else 0
        pxs_gut_ytd_m = int(df_m[df_m["Es_Gutis"]][COL_PXS_YTD].sum()) if COL_PXS_YTD else 0
        pxs_comp_m = pxs_tot_m - pxs_gut_m
        pxs_comp_ytd_m = pxs_ytd_m - pxs_gut_ytd_m

        vol_eval_tot = pxs_tot_m if pxs_tot_m > 0 else pxs_ytd_m
        vol_eval_gut = pxs_gut_m if pxs_tot_m > 0 else pxs_gut_ytd_m
        ms_gut_m = (vol_eval_gut / vol_eval_tot * 100) if vol_eval_tot > 0 else 0.0

        df_m_ord = df_m.sort_values(by=[COL_PXS_MES, COL_PXS_YTD] if (COL_PXS_MES and COL_PXS_YTD) else [COL_PXS_MES or COL_PXS_YTD], ascending=False)
        lider = df_m_ord.iloc[0]
        lider_nombre = str(lider["NOMBRE_PRODUCTO"]).strip()
        lider_es_gutis = bool(lider["Es_Gutis"])

        df_rivales = df_m_ord[~df_m_ord["Es_Gutis"]]
        if not df_rivales.empty:
            rival_row = df_rivales.iloc[0]
            rival_nombre = str(rival_row["NOMBRE_PRODUCTO"]).strip()
            rival_pxs_mes = int(rival_row[COL_PXS_MES]) if COL_PXS_MES else 0
            rival_pxs_ytd = int(rival_row[COL_PXS_YTD]) if COL_PXS_YTD else 0
        else:
            rival_nombre, rival_pxs_mes, rival_pxs_ytd = "Sin competidor en categoría", 0, 0

        escala_act, escala_meta, modo_tactico_m, obj_escala = diagnosticar_escala_adopcion(vol_eval_gut, vol_eval_tot, ms_gut_m)

        if pxs_tot_m > 0 or pxs_ytd_m > 0:
            opciones_mercados_medico.append({
                "mercado": m_nom,
                "clase_terapeutica": meta["clase_terapeutica"],
                "prioridad": prio_num,
                "categoria_mercado": cat_merc_txt,
                "lider_actual": lider_nombre,
                "lider_es_gutis": lider_es_gutis,
                "rival_principal": rival_nombre,
                "rival_pxs_mes": rival_pxs_mes,
                "rival_pxs_ytd": rival_pxs_ytd,
                "prod_gutis": prod_gutis_esperado,
                "pxs_totales": pxs_tot_m,
                "pxs_ytd": pxs_ytd_m,
                "pxs_gutis": pxs_gut_m,
                "pxs_gutis_ytd": pxs_gut_ytd_m,
                "pxs_comp": pxs_comp_m,
                "pxs_comp_ytd": pxs_comp_ytd_m,
                "ms_gutis": ms_gut_m,
                "escala_actual": escala_act,
                "escala_meta": escala_meta,
                "modo_tactico": modo_tactico_m,
                "objetivo_escala": obj_escala,
                "meta_info": meta
            })

    opciones_mercados_medico = sorted(opciones_mercados_medico, key=lambda x: (-x["pxs_totales"], -x["pxs_ytd"], x["prioridad"]))
    num_mercados = len(opciones_mercados_medico)

    if opciones_mercados_medico:
        prim = opciones_mercados_medico[0]
        mercado_principal_str = prim["mercado"]
        producto_ataque_str = prim["lider_actual"]
        prod_gutis_ataque_oficial = prim["prod_gutis"]

    for item_m in opciones_mercados_medico:
        m_label = item_m["mercado"].replace("MR ", "").upper()
        badge_p = f"P{item_m['prioridad']}"
        color_p = "#1e3a8a" if item_m["prioridad"] == 1 else ("#0284c7" if item_m["prioridad"] == 2 else "#64748b")
        if item_m["modo_tactico"] == "LEALTAD" or item_m["lider_es_gutis"]:
            cards_ataque_html += f"""
            <div style="background:#f8fafc; border:1px solid #cbd5e1; border-top:4px solid #059669; border-radius:6px; padding:11px; min-width:210px; flex:1 1 calc(25% - 12px); font-family:sans-serif;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:0.68rem; font-weight:800; color:#065f46;">MERCADO: {m_label}</span>
                    <span style="background:{color_p}; color:white; font-size:0.62rem; padding:2px 6px; border-radius:3px; font-weight:700;">{badge_p}</span>
                </div>
                <div style="font-size:0.84rem; color:#0f172a; margin:4px 0;">Dominio: <b style="color:#047857;">{item_m['prod_gutis']} ({item_m['ms_gutis']:.0f}%)</b></div>
                <div style="font-size:0.73rem; color:#334155;">Mes: <b>{item_m['pxs_totales']}</b> (Gutis: {item_m['pxs_gutis']}) | YTD: <b>{item_m['pxs_ytd']}</b></div>
                <div style="font-size:0.7rem; color:#475569; margin-top:2px;">Rival en Clase: {item_m['rival_principal'][:18]}</div>
                <div style="margin-top:5px; font-size:0.7rem; font-weight:800; color:#047857; border-top:1px solid #e2e8f0; padding-top:4px;">[LEALTAD: AGRADECER Y PUENTE]</div>
            </div>"""
        else:
            cards_ataque_html += f"""
            <div style="background:#f8fafc; border:1px solid #cbd5e1; border-top:4px solid #dc2626; border-radius:6px; padding:11px; min-width:210px; flex:1 1 calc(25% - 12px); font-family:sans-serif;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:0.68rem; font-weight:800; color:#991b1b;">MERCADO: {m_label}</span>
                    <span style="background:{color_p}; color:white; font-size:0.62rem; padding:2px 6px; border-radius:3px; font-weight:700;">{badge_p}</span>
                </div>
                <div style="font-size:0.84rem; color:#0f172a; margin:4px 0;">Rival #1: <b style="color:#b91c1c;">{item_m['rival_principal'][:16]}</b></div>
                <div style="font-size:0.73rem; color:#334155;">Mes: <b>{item_m['pxs_totales']}</b> (Comp: {item_m['pxs_comp']}) | YTD: <b>{item_m['pxs_ytd']}</b></div>
                <div style="font-size:0.7rem; color:#475569; margin-top:2px;">Escala: <b>{item_m['escala_actual'].split('(')[0]}</b></div>
                <div style="margin-top:5px; font-size:0.7rem; font-weight:800; color:#1e3a8a; border-top:1px solid #e2e8f0; padding-top:4px;">[ATACAR CON {item_m['prod_gutis'].upper()}]</div>
            </div>"""

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

# --- FUNCIONES DE LLAMADA A GEMINI (TEXTO Y AUDIO DE MICRÓFONO) ---
def llamar_gemini(prompt_text, max_tok=4096):
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt_text}]}], "generationConfig": {"maxOutputTokens": max_tok, "temperature": 0.2}}
    modelos_a_probar = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.5-pro"]
    for mod in modelos_a_probar:
        try:
            url_p = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            res = requests.post(url_p, headers=headers, json=payload, timeout=18)
            if res.status_code == 200:
                cands = res.json().get("candidates", [])
                if cands and "content" in cands[0] and "parts" in cands[0]["content"]:
                    return cands[0]["content"]["parts"][0].get("text", "")
        except:
            continue
    return None

def transcribir_audio_gemini(audio_bytes):
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key or not audio_bytes:
        return None
    b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [
                {"text": "Transcribe exactamente lo que dice este audio en español, sin agregar comentarios adicionales."},
                {"inline_data": {"mime_type": "audio/wav", "data": b64_audio}}
            ]
        }]
    }
    for mod in ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"]:
        try:
            url_p = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            res = requests.post(url_p, headers=headers, json=payload, timeout=15)
            if res.status_code == 200:
                cands = res.json().get("candidates", [])
                if cands and "content" in cands[0] and "parts" in cands[0]["content"]:
                    return cands[0]["content"]["parts"][0].get("text", "").strip()
        except:
            continue
    return None

# --- RECONOCIMIENTO PRECISO DE MÉDICO INDIVIDUAL VS CONSULTA DE MERCADO/RANKING ---
def detectar_medico_en_texto(texto_usuario):
    t_norm = normalizar_txt(texto_usuario)
    # Si la consulta pide una lista o ranking plural ("cuales son los medicos", "quienes son", "top", "mas importantes"), NO es un médico individual
    frases_plurales = [
        "CUALES SON LOS MEDICOS", "QUIENES SON LOS MEDICOS", "MEDICOS MAS IMPORTANTES",
        "TOP MEDICOS", "RANKING DE MEDICOS", "LISTA DE MEDICOS", "QUE MEDICOS RECETAN",
        "MEDICOS DE RIVAS", "MEDICOS DE GRANADA", "MEDICOS DE MASAYA", "MEDICOS DE CARAZO",
        "MEDICOS DE CHONTALES", "MEDICOS DE BOACO", "MEDICOS EN RIVAS", "MEDICOS EN GRANADA"
    ]
    if any(fp in t_norm for fp in frases_plurales):
        return None

    palabras_ignorar = {
        "DR", "DRA", "DOCTOR", "DOCTORA", "MEDICO", "MEDICOS", "ANALIZA", "ANALIZAR", "COMO", "PARA",
        "GRANADA", "MASAYA", "CARAZO", "RIVAS", "CHONTALES", "BOACO", "MANAGUA", "NUEVA", "GUINEA",
        "PEDIATRIA", "PEDIATRAS", "GINECOLOGIA", "INTERNA", "GENERAL", "OTORRINO", "ORTOPEDIA",
        "GUTIS", "TALERDIN", "BIOTOS", "GASTROALIVIO", "DALIVIO", "MOMETZONA", "VENTILAR", "CLEMBROXIL",
        "VALERPAN", "CONFLEXIL", "RENOVART", "LABORATORIO", "COMPETENCIA", "COMPRADA", "COMPRADO",
        "PANEL", "VISITA", "PLAN", "TVP", "CONGRESO", "MUESTRAS", "FARMACIA", "TOP", "LOS", "LAS", "DEL", "POR",
        "TIENE", "COMPROMISO", "NOSOTROS", "MARCAS", "PERO", "ESTA", "COMPARTIENDO", "MUCHO", "RECETA",
        "OTROS", "CREES", "PASE", "CUALES", "SON", "MAS", "IMPORTANTES", "MERCADO", "QUIENES", "QUE"
    }
    tokens_usr = [w for w in re.split(r'[^A-Z0-9Ñ]+', t_norm) if len(w) >= 4 and w not in palabras_ignorar]
    if not tokens_usr:
        return None

    universo_meds = sorted(list(set(df_panel["Médico"].dropna().unique()).union(set(df_productos["Médico"].dropna().unique() if not df_productos.empty else []))))
    mejor_medico = None
    max_coincidencias = 0
    for med in universo_meds:
        med_norm = normalizar_txt(med)
        tokens_med = [w for w in re.split(r'[^A-Z0-9Ñ]+', med_norm) if len(w) >= 3]
        if not tokens_med:
            continue
        coincidencias = sum(1 for tu in tokens_usr if tu in tokens_med)
        if coincidencias > max_coincidencias:
            max_coincidencias = coincidencias
            mejor_medico = med

    if max_coincidencias >= 2:
        return mejor_medico
    if max_coincidencias == 1:
        indicadores_persona = ["DR ", "DRA ", "DRA.", "DR.", "DOCTOR", "DOCTORA", "ANALIZA A", "ABORDO A", "ABORDAR A", "COMPRAD", "CASAD", "AMARR", "PIDE", "OBJECION", "VISITAR A"]
        if any(ind in t_norm for ind in indicadores_persona):
            return mejor_medico
    return None

# --- TICKER SUPERIOR COMPACTO SIN EMOJIS ---
escala_ticker = opciones_mercados_medico[0]["escala_actual"].split("(")[0] if opciones_mercados_medico else "2. Consciente"
st.markdown(f"""
<div class='ticker-bar'>
    <div class='ticker-item'>
        <div class='ticker-label'>ESPECIALISTA EN FOCO</div>
        <div class='ticker-val'>{medico_sel[:26]}</div>
        <div class='ticker-sub'>{especialidad} | Categoría {categoria} | {ciudad}</div>
    </div>
    <div class='ticker-item'>
        <div class='ticker-label'>AUDITORÍA DE RECETAS (PORTAFOLIO GUTIS)</div>
        <div class='ticker-val'>{total_pxs_medico} Pxs Mes <span style='font-size:0.85rem; color:#1d4ed8;'>({total_ytd_medico_global} YTD)</span></div>
        <div class='ticker-sub'>Gutis Mes: {gutis_pxs_medico} ({gutis_ytd_medico} YTD) | Competencia Mes: {comp_pxs_medico}</div>
    </div>
    <div class='ticker-item'>
        <div class='ticker-label'>MERCADO PRIMARIO ({prod_gutis_ataque_oficial.upper()})</div>
        <div class='ticker-val'>{producto_ataque_str[:18]}</div>
        <div class='ticker-sub'>Escala TVP: <b>{escala_ticker}</b></div>
    </div>
    <div class='ticker-item'>
        <div class='ticker-label'>SELL-OUT ZONAL ({ciudad} - {total_puntos_venta} PDV)</div>
        <div class='ticker-val'>${total_sellout_zona:,.2f}</div>
        <div class='ticker-sub'>Farmacias Líderes: {top_farmacias_ciudad_str[:34]}...</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# ARQUITECTURA EJECUTIVA DE 3 NÚCLEOS LÓGICOS (SIN EMOJIS)
# ==============================================================================
nucleo_macro, nucleo_micro, nucleo_copiloto = st.tabs([
    "NÚCLEO I: RADAR TERRITORIAL Y RUTA POR MERCADO",
    "NÚCLEO II: CONSULTORIO 360 Y CANVAS TVP",
    "NÚCLEO III: COPILOTO CHIRA Y BITÁCORA CRM"
])

# ==============================================================================
# NÚCLEO I: RADAR TERRITORIAL + INTERACCIÓN CLIC EN MÉDICO -> PRODUCTOS QUE RECETA
# ==============================================================================
with nucleo_macro:
    st.markdown("<div class='section-banner'>RADAR TERRITORIAL: PENETRACIÓN POR ESPECIALIDAD, SINCRONÍA RX VS. SELL-OUT Y DESGLOSE POR MERCADO</div>", unsafe_allow_html=True)

    c_m1, c_m2 = st.columns([1.2, 2.8])
    with c_m1:
        zona_terreno_sel = st.selectbox("Seleccionar Territorio:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="terr_zona")
    with c_m2:
        vista_macro = st.radio(
            "Seleccionar Módulo de Análisis:",
            [
                "1. Médicos por Mercado y Desglose de Recetas (Interactivo)",
                "2. Matriz de Penetración por Especialidad y Top 5 Competencia",
                "3. Sincronía Rx vs. Sell-Out y Auditoría de Farmacias"
            ],
            horizontal=True
        )

    # SUB-MÓDULO 1: RUTA POR MERCADO + CLIC EN MÉDICO PARA VER QUÉ PRODUCTOS RECETA EN ESE MERCADO
    if vista_macro.startswith("1."):
        st.markdown("##### Análisis de Prescriptores por Mercado / Clase Terapéutica (Haz clic en cualquier médico de la tabla para ver las marcas exactas que receta)")
        cr_p, cr1, cr2, cr3 = st.columns([1.1, 1.5, 1.1, 0.9])

        with cr_p:
            prio_ruta_sel = st.selectbox("Nivel de Mercado:", ["Todos (P1, P2, P3)", "Solo Prioridad 1 (Core)", "Solo Prioridad 2 (Expansión)", "Solo Prioridad 3 (Complemento)"])
        p_num_r = 1 if "Prioridad 1" in prio_ruta_sel else (2 if "Prioridad 2" in prio_ruta_sel else (3 if "Prioridad 3" in prio_ruta_sel else None))

        mercados_disp_ruta = [m for m in LISTA_MERCADOS_REALES if (clasificar_mercado_gutis(m) or {}).get("prioridad") == p_num_r] if p_num_r else LISTA_MERCADOS_REALES

        with cr1:
            mercados_ruta_sel = st.multiselect("Seleccionar Mercado(s) (ej. MR Talerdin):", mercados_disp_ruta, placeholder="Todos los mercados del nivel...")
        with cr2:
            esps_ruta_sel = st.selectbox("Especialidad:", ["TODAS"] + LISTA_ESPECIALIDADES_REALES)
        with cr3:
            incluir_no_vis = st.checkbox("Ver Fuera de Panel", value=False)

        ciu_r_param = None if zona_terreno_sel == "TODO MI PANEL" else zona_terreno_sel
        esp_r_param = None if esps_ruta_sel == "TODAS" else esps_ruta_sel
        mer_r_param = mercados_ruta_sel if mercados_ruta_sel else None

        df_ranking_ruta = obtener_ranking_medicos_mercado(
            ciudad_target=ciu_r_param,
            esp_target=esp_r_param,
            mer_target=mer_r_param,
            prio_target=p_num_r,
            incluir_fuera_panel=incluir_no_vis
        )

        if not df_ranking_ruta.empty:
            st.caption("Haz clic sobre cualquier fila de la tabla para abrir abajo la radiografía de productos y moléculas que ese médico receta en el mercado seleccionado:")
            evento_sel = st.dataframe(
                df_ranking_ruta,
                hide_index=True,
                use_container_width=True,
                on_select="rerun",
                selection_mode="single-row"
            )

            # Determinar qué médico inspeccionar (por clic en la fila o selector rápido)
            filas_seleccionadas = evento_sel.selection.rows if (evento_sel and hasattr(evento_sel, "selection")) else []
            idx_doc_inspeccion = filas_seleccionadas[0] if filas_seleccionadas else 0
            lista_docs_tabla = df_ranking_ruta["Médico"].tolist()

            st.markdown("<div class='drill-box'>", unsafe_allow_html=True)
            cd1, cd2 = st.columns([2.2, 1.0])
            with cd1:
                med_drill_sel = st.selectbox(
                    "Especialista seleccionado para desglose de productos en el mercado:",
                    lista_docs_tabla,
                    index=idx_doc_inspeccion,
                    key="drill_med_sel"
                )
            with cd2:
                st.write("")
                if st.button("Cargar Especialista en Consultorio 360 y Canvas TVP", use_container_width=True, type="primary"):
                    st.session_state.medico_forzado_ruta = med_drill_sel
                    st.rerun()

            df_detalle_prods = obtener_desglose_productos_medico(med_drill_sel, mer_r_param)
            if not df_detalle_prods.empty:
                st.markdown(f"**Productos y Marcas prescritas por {med_drill_sel} ({' | '.join(mer_r_param) if mer_r_param else 'Portafolio Seleccionado'}):**")
                st.dataframe(
                    df_detalle_prods,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "% Cuota Categoría": st.column_config.ProgressColumn("% Cuota Categoría", format="%.1f%%", min_value=0, max_value=100)
                    }
                )
            else:
                st.info("Selecciona un mercado con prescripción activa para visualizar el desglose de marcas.")
            st.markdown("</div>", unsafe_allow_html=True)

            csv_ruta = df_ranking_ruta.to_csv(index=False).encode("utf-8-sig")
            st.download_button("Exportar Tabla de Médicos y Mercados (CSV)", data=csv_ruta, file_name=f"Ranking_Mercado_{zona_terreno_sel}.csv", mime="text/csv")
        else:
            st.info("No se encontraron registros activos para los filtros seleccionados.")

    # SUB-MÓDULO 2: MATRIZ DE PENETRACIÓN POR ESPECIALIDAD
    elif vista_macro.startswith("2."):
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

            st.markdown(f"##### 1. Rendimiento Interno YTD 2026 por Especialidad ({zona_terreno_sel})")
            st.dataframe(
                df_rend_interno, hide_index=True, use_container_width=True,
                column_config={
                    "PENETRACIÓN": st.column_config.ProgressColumn("PENETRACIÓN (%)", format="%.2f%%", min_value=0, max_value=100),
                    "%MS-YTD": st.column_config.ProgressColumn("%MS-YTD GUTIS", format="%.2f%%", min_value=0, max_value=100),
                }
            )
            st.markdown(f"##### 2. Top 5 Competencia Directa por Cuota de Mercado YTD ({zona_terreno_sel})")
            st.dataframe(df_top_comp, hide_index=True, use_container_width=True)
        else:
            st.warning("No se encontraron registros cruzados para la zona seleccionada.")

    # SUB-MÓDULO 3: SINCRONÍA RX VS SELL-OUT
    else:
        st.markdown(f"##### Matriz de Sincronía Temporal: Evolución de Receta (Rx) vs. Sell-Out Farmacéutico ({zona_terreno_sel})")
        df_sincronia = calcular_sincronia_rx_vs_sellout(zona_terreno_sel)
        if not df_sincronia.empty:
            st.dataframe(
                df_sincronia, hide_index=True, use_container_width=True,
                column_config={
                    "% MS YTD": st.column_config.NumberColumn("% MS YTD", format="%.2f%%"),
                    "% MS MES": st.column_config.NumberColumn("% MS MES", format="%.2f%%"),
                    "Sell-Out Q1": st.column_config.NumberColumn("Sell-Out Q1", format="$%.2f"),
                    "Sell-Out Q2": st.column_config.NumberColumn("Sell-Out Q2", format="$%.2f"),
                    "Sell-Out Q3": st.column_config.NumberColumn("Sell-Out Q3", format="$%.2f"),
                }
            )
        st.divider()
        st.markdown("##### Desglose de Sell-Out por Sucursal Farmacéutica y Trimestre (Q1, Q2, Q3)")
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
                    farm_sel = st.multiselect("Filtrar Farmacia(s):", sorted(ventas_zona["NOMBRE_CLIENTE_1"].dropna().unique().tolist()), placeholder="Todas las sucursales...")
                with cf_s2:
                    prod_v_sel = st.multiselect("Filtrar Línea / Producto:", sorted(ventas_zona[col_prod_v].dropna().unique().tolist()) if col_prod_v else [], placeholder="Todas las líneas...")

                df_v_mostrar = ventas_zona.copy()
                if farm_sel: df_v_mostrar = df_v_mostrar[df_v_mostrar["NOMBRE_CLIENTE_1"].isin(farm_sel)]
                if prod_v_sel and col_prod_v: df_v_mostrar = df_v_mostrar[df_v_mostrar[col_prod_v].isin(prod_v_sel)]

                if col_prod_v and "Trimestre" in df_v_mostrar.columns and not df_v_mostrar.empty:
                    df_pivot = pd.pivot_table(df_v_mostrar, values="Monto Real", index=["NOMBRE_CLIENTE_1", col_prod_v], columns=["Trimestre"], aggfunc="sum", fill_value=0.0).reset_index()
                    for q_col in ["Q1", "Q2", "Q3"]:
                        if q_col not in df_pivot.columns: df_pivot[q_col] = 0.0
                        df_pivot[q_col] = df_pivot[q_col].round(2)
                    df_pivot["Venta Total"] = (df_pivot["Q1"] + df_pivot["Q2"] + df_pivot["Q3"]).round(2)
                    df_pivot = df_pivot.sort_values(by="Venta Total", ascending=False)

                    st.dataframe(
                        df_pivot[["NOMBRE_CLIENTE_1", col_prod_v, "Q1", "Q2", "Q3", "Venta Total"]].rename(columns={"NOMBRE_CLIENTE_1": "Punto de Venta / Farmacia", col_prod_v: "Línea Gutis"}),
                        hide_index=True, use_container_width=True,
                        column_config={
                            "Q1": st.column_config.NumberColumn("Q1", format="$%.2f"),
                            "Q2": st.column_config.NumberColumn("Q2", format="$%.2f"),
                            "Q3": st.column_config.NumberColumn("Q3", format="$%.2f"),
                            "Venta Total": st.column_config.NumberColumn("Venta Total", format="$%.2f"),
                        }
                    )

# ==============================================================================
# NÚCLEO II: CONSULTORIO 360 Y CANVAS TVP ADAPTATIVO (SIN EMOJIS)
# ==============================================================================
with nucleo_micro:
    if cards_ataque_html:
        st.components.v1.html(f"""
        <div style="background-color:#ffffff; border:1px solid #cbd5e1; border-left:5px solid #1e3a8a; padding:12px; margin-bottom:10px; border-radius:6px; font-family:sans-serif;">
            <div style="font-size:0.76rem; font-weight:800; color:#0f172a; margin-bottom:8px; letter-spacing:0.5px;">
                MERCADOS AUDITADOS DEL ESPECIALISTA EN EL VADEMÉCUM NICARAGUA 2026 ({num_mercados} CATEGORÍAS TERAPÉUTICAS ACTIVAS)
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:10px;">{cards_ataque_html}</div>
        </div>""", height=195, scrolling=True)

    col_canvas, col_micro_datos = st.columns([1.32, 1.08])

    with col_canvas:
        st.markdown("##### CANVAS TVP DE 4 CUADRANTES — ESTRUCTURA TÁCTICA DE VISITA")
        with st.container(border=True):
            if opciones_mercados_medico:
                etiquetas_m = [
                    f"[{o['modo_tactico']}] {o['prod_gutis']} ({o['mercado'].replace('MR ','')}) — Mes: {o['pxs_totales']} | YTD: {o['pxs_ytd']} | Gutis: {o['ms_gutis']:.0f}%"
                    for o in opciones_mercados_medico
                ]
                idx_puente_sugerido = 1 if len(opciones_mercados_medico) > 1 else 0
                for idx_cand, o_cand in enumerate(opciones_mercados_medico):
                    if idx_cand > 0 and o_cand["modo_tactico"] != "LEALTAD" and (o_cand["pxs_comp"] > 0 or o_cand["pxs_comp_ytd"] > 0):
                        idx_puente_sugerido = idx_cand
                        break

                cm1, cm2, cm3 = st.columns(3)
                with cm1: idx_m1 = st.selectbox("1ra Posición (Foco / Ancla):", range(len(etiquetas_m)), index=0, format_func=lambda i: etiquetas_m[i])
                with cm2: idx_m2 = st.selectbox("2da Posición (Puente):", range(len(etiquetas_m)), index=idx_puente_sugerido, format_func=lambda i: etiquetas_m[i])
                with cm3: idx_m3 = st.selectbox("3ra Posición (Recordación):", range(len(etiquetas_m)), index=(2 if len(etiquetas_m) > 2 else idx_puente_sugerido), format_func=lambda i: etiquetas_m[i])
                m_primario = opciones_mercados_medico[idx_m1]
                m_secundario = opciones_mercados_medico[idx_m2] if len(opciones_mercados_medico) > 1 else None
                m_terciario = opciones_mercados_medico[idx_m3] if len(opciones_mercados_medico) > 2 else None
            else:
                meta_def = MERCADOS_PRIORITARIOS["MR TALERDIN"] if es_pediatra else MERCADOS_PRIORITARIOS["MR GASTROALIVIO"]
                m_primario = {
                    "mercado": "MR TALERDIN" if es_pediatra else "MR GASTROALIVIO",
                    "clase_terapeutica": meta_def["clase_terapeutica"],
                    "prioridad": 1, "categoria_mercado": "Prioridad 1 (Foco Core)",
                    "lider_actual": producto_ataque_str, "lider_es_gutis": False,
                    "rival_principal": "Competencia de la categoría", "rival_pxs_mes": 0, "rival_pxs_ytd": 0,
                    "prod_gutis": prod_gutis_ataque_oficial,
                    "pxs_totales": total_pxs_medico, "pxs_ytd": total_ytd_medico_global,
                    "pxs_gutis": gutis_pxs_medico, "pxs_gutis_ytd": 0, "pxs_comp": comp_pxs_medico, "pxs_comp_ytd": 0,
                    "ms_gutis": 0.0, "escala_actual": "2. Consciente (0% MS)", "escala_meta": "3. Prueba (2 a 10 Pxs)",
                    "modo_tactico": "CONQUISTA", "objetivo_escala": "Iniciar período de prueba.", "meta_info": meta_def
                }
                m_secundario, m_terciario = None, None

            ct1, ct2 = st.columns(2)
            with ct1: tipo_cita_sel = st.selectbox("Contexto de Acceso:", ["Visita con cita previa", "Visita sin cita (Improvisto)", "Encuentro casual (Pasillo)"])
            with ct2: nec_detras_sel = st.selectbox("Necesidad detrás de la Necesidad (NdN):", ["Desempeño (Eficacia y adherencia clínica)", "Imagen (Prestigio clínico)", "Finanzas (Costo-beneficio)"])

        meta1 = m_primario["meta_info"]
        prod1 = m_primario["prod_gutis"]
        rival1 = m_primario["rival_principal"] if m_primario["rival_principal"] != "Sin competidor en categoría" else "otras marcas de la clase terapéutica"
        modo_tac1 = m_primario["modo_tactico"]
        perfil_paciente_adaptado = meta1.get("paciente_meta_ped", meta1["paciente_meta"]) if es_pediatra else meta1["paciente_meta"]

        if m_secundario and m_secundario["prod_gutis"] != prod1:
            prod2 = m_secundario["prod_gutis"]
            benef2 = m_secundario["meta_info"]["beneficio"]
            rival2 = m_secundario["rival_principal"]
        else:
            prod2 = "Biotos Inmune / Clembroxil Compuesto" if es_pediatra else "Conflexil Plus Shot / Dalivio"
            benef2 = "Cuádruple acción respiratoria libre de alcohol" if es_pediatra else "Triple acción analgésica, antiinflamatoria y miorrelajante"
            rival2 = "la competencia"

        prod3 = m_terciario["prod_gutis"] if (m_terciario and m_terciario["prod_gutis"] not in [prod1, prod2]) else ("Ventilar / Mometzona" if es_pediatra else "Valerpan / Renovart Platinum")

        if modo_tac1 == "LEALTAD":
            q1_html = f"""
                • <b>Escala Actual:</b> <span style='color:#047857; font-weight:800;'>{m_primario['escala_actual']} (Socio Leal)</span><br>
                • <b>Clase Terapéutica:</b> {m_primario['clase_terapeutica']}<br>
                • <b>Meta SMART Hoy:</b> Agradecer y blindar sus recetas de <b>{prod1}</b> (Mes: {m_primario['pxs_gutis']} | YTD: {m_primario['pxs_gutis_ytd']}) y apalancar esa confianza para iniciar <b>3 a 5 pacientes en {prod2}</b>.<br>
                • <b>Plan de Respaldo:</b> Confirmar inventario en <b>{top_farmacias_ciudad_str.split(',')[0]}</b>.
            """
            q2_html = f"""
                • <b>Postura Táctica:</b> Reconocimiento de lealtad (sin vender de cero lo que ya prescribe).<br>
                • <b>Apertura ({especialidad}):</b> Agradecer su preferencia sostenida en <i>{perfil_paciente_adaptado[:60]}...</i><br>
                • <b>Pregunta de Validación:</b> <i>«¿Cómo ha notado la respuesta y adherencia de sus pacientes con nuestras presentaciones de {prod1} este mes?»</i><br>
                • <b>Acuerdo:</b> Revisar brevemente una segunda línea complementaria.
            """
            q3_html = f"""
                • <b>Blindaje Sutil ({prod1}):</b> Recordar dosificación y ventaja diferencial ({meta1['caracteristica'][:75]}...).<br>
                • <b>Enfoque ({nec_detras_sel.split('(')[0].strip()}):</b> {meta1['beneficio']}<br>
                • <b>Mensaje de Marca:</b> <i>«Gracias a su respaldo, decenas de pacientes en {ciudad} reciben un tratamiento seguro y libre de alcohol.»</i>
            """
            q4_html = f"""
                • <b>Cierre en {prod1}:</b> Agradecer su preferencia #1 y asegurar stock en <b>{top_farmacias_ciudad_str.split(',')[0]}</b>.<br>
                • <b>PUENTE PRINCIPAL ({prod1} hacia {prod2}):</b> <i>«Apoyándome en su excelente experiencia con {prod1}, extendamos esa misma calidad hacia <b>{prod2}</b> ({benef2[:50]}...) en los casos donde aún utiliza {rival2}.»</i><br>
                • <b>3ra Posición ({prod3}):</b> Recordación de disponibilidad zonal.
            """
        elif modo_tac1 == "EXPANSION":
            q1_html = f"""
                • <b>Escala Actual:</b> <span style='color:#0284c7; font-weight:800;'>{m_primario['escala_actual']} (Comparte Categoría)</span><br>
                • <b>Escalón Meta Hoy:</b> <span style='color:#047857; font-weight:700;'>{m_primario['escala_meta']}</span><br>
                • <b>Meta SMART:</b> Agradecer sus recetas actuales en <b>{prod1}</b> y migrar <b>4 a 6 pacientes</b> que aún van hacia <code>{rival1}</code> dentro de la clase terapéutica.<br>
                • <b>Plan de Respaldo:</b> Capturar el subgrupo de pacientes más sensibles hacia {prod1}.
            """
            q2_html = f"""
                • <b>Postura Táctica:</b> Explorar su experiencia positiva con los pacientes ya tratados.<br>
                • <b>Agenda ({especialidad}):</b> Analizar evolución en <i>{perfil_paciente_adaptado[:60]}...</i><br>
                • <b>Pregunta Sutil:</b> <i>«En los casos donde ya prescribió nuestro esquema frente a {rival1}, ¿qué diferencias observó en tolerabilidad y apego?»</i><br>
                • <b>Acuerdo:</b> Confirmar agenda de 2 minutos.
            """
            q3_html = f"""
                • <b>Sondeo de Migración:</b> <i>«¿En qué perfil específico de paciente siente que todavía alterna con {rival1}?»</i><br>
                • <b>Ventaja Diferencial ({prod1}):</b> {meta1['caracteristica']}<br>
                • <b>Beneficio ({nec_detras_sel.split('(')[0].strip()}):</b> {meta1['beneficio']}<br>
                • <b>Mensaje de Marca:</b> <i>«{meta1['love_brand']}»</i>
            """
            q4_html = f"""
                • <b>Pido al Médico:</b> Consolidar a <b>{prod1}</b> como primera elección en el segmento que compartía con <code>{rival1}</code>.<br>
                • <b>Mi Compromiso:</b> Garantizar inventario en <b>{top_farmacias_ciudad_str.split(',')[0]}</b>.<br>
                • <b>Puente a 2da Posición ({prod2}):</b> <i>«Y siguiendo con eficacia clínica, cuente con <b>{prod2}</b> ({benef2[:42]}...).»</i><br>
                • <b>3ra Posición ({prod3}):</b> Respaldo en farmacias aledañas.
            """
        else:
            q1_html = f"""
                • <b>Escala Actual:</b> <span style='color:#b91c1c; font-weight:700;'>{m_primario['escala_actual']}</span><br>
                • <b>Escalón Meta Hoy:</b> <span style='color:#047857; font-weight:700;'>{m_primario['escala_meta']}</span><br>
                • <b>Meta SMART:</b> Capturar los primeros <b>3 a 5 pacientes</b> que hoy prescribe en <code>{rival1}</code> (Mes: {m_primario['pxs_comp']} | YTD: {m_primario['pxs_comp_ytd']}) hacia <b>{prod1}</b>.<br>
                • <b>Plan de Respaldo:</b> Iniciar prueba en 2 pacientes específicos con muestra de arranque.
            """
            q2_html = f"""
                • <b>Postura Táctica:</b> Agenda centrada en el paciente de <b>{especialidad}</b> (sin mencionar marca en apertura).<br>
                • <b>Agenda ({tipo_cita_sel.split('(')[0].strip()}):</b> Revisar adherencia en <i>{perfil_paciente_adaptado[:60]}...</i><br>
                • <b>Pregunta Disruptiva:</b> <i>«¿Qué impacto tendría en su consulta eliminar desde hoy el abandono terapéutico al segundo día en estos pacientes?»</i><br>
                • <b>Acuerdo:</b> <i>«¿Le parece bien revisarlo en 2 minutos?»</i>
            """
            q3_html = f"""
                • <b>Sondeo de Valor Mutuo:</b> <i>«Al <b>comparar</b> y <b>evaluar</b> la respuesta con {rival1}, ¿qué considera prioritario optimizar?»</i><br>
                • <b>Ventaja ({prod1}):</b> {meta1['caracteristica']}<br>
                • <b>Beneficio ({nec_detras_sel.split('(')[0].strip()}):</b> {meta1['beneficio']}<br>
                • <b>Mensaje de Marca:</b> <i>«{meta1['love_brand']}»</i>
            """
            q4_html = f"""
                • <b>Pido al Médico:</b> Iniciar <b>{prod1}</b> en sus próximos 3 a 5 pacientes con este cuadro.<br>
                • <b>Mi Compromiso:</b> Asegurar disponibilidad hoy en <b>{top_farmacias_ciudad_str.split(',')[0]}</b>.<br>
                • <b>Puente a 2da Posición ({prod2}):</b> <i>«Siguiendo con seguridad clínica, en estos casos cuenta con <b>{prod2}</b> ({benef2[:42]}...).»</i><br>
                • <b>3ra Posición ({prod3}):</b> Disponibilidad en farmacias de su ruta.
            """

        st.markdown(f"""
        <div class='canvas-grid'>
            <div class='quad-card' style='border-top: 4px solid #1e3a8a;'>
                <div class='quad-title' style='color:#1e3a8a;'>I. DIAGNÓSTICO Y OBJETIVO SMART ({modo_tac1})</div>
                <div class='quad-body'>{q1_html}</div>
            </div>
            <div class='quad-card' style='border-top: 4px solid #0284c7;'>
                <div class='quad-title' style='color:#0284c7;'>II. APERTURA ADAPTADA ({especialidad})</div>
                <div class='quad-body'>{q2_html}</div>
            </div>
            <div class='quad-card' style='border-top: 4px solid #059669;'>
                <div class='quad-title' style='color:#059669;'>III. EMBUDO, APOYO Y MENSAJE DE MARCA</div>
                <div class='quad-body'>{q3_html}</div>
            </div>
            <div class='quad-card' style='border-top: 4px solid #d97706;'>
                <div class='quad-title' style='color:#b45309;'>IV. CIERRE BILATERAL Y PUENTE P1 - P2 - P3</div>
                <div class='quad-body'>{q4_html}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("VER GUION CONVERSACIONAL EXTENDIDO PASO A PASO"):
            if st.button("Generar Guion Personalizado con IA", use_container_width=True):
                with st.spinner("Generando guion táctico..."):
                    prompt_ext = f"""{REGLAS_FARMA}
Redacta el guion exacto paso a paso para el Dr(a). {medico_sel} (Especialidad: {especialidad} en {ciudad}).
- Producto 1: {prod1} | Escala de Adopción: {m_primario['escala_actual']} (Modo Táctico: {modo_tac1}) | Pacientes Gutis Mes: {m_primario['pxs_gutis']} (YTD: {m_primario['pxs_gutis_ytd']}) | Rival en la Clase Terapéutica: {rival1} (Mes: {m_primario['pxs_comp']} | YTD: {m_primario['pxs_comp_ytd']}).
- Producto 2 (Puente): {prod2} | Producto 3 (Recordación): {prod3}.
- Perfil de paciente: {perfil_paciente_adaptado}.
- Farmacias aliadas: {top_farmacias_ciudad_str}."""
                    res_ext = llamar_gemini(prompt_ext)
                    st.session_state.tvp_result = res_ext
            if st.session_state.tvp_result:
                st.markdown(st.session_state.tvp_result)

    with col_micro_datos:
        sub_rx, sub_labs, sub_360 = st.tabs([
            "Recetario por Categoría Terapéutica",
            "Radar de Laboratorios",
            "Ficha Omnicanal 360"
        ])

        with sub_rx:
            st.caption(f"Desglose de todas las marcas que prescribe {medico_sel} dentro de las clases terapéuticas auditadas:")
            mercados_disp_med = sorted(rx_clean["MERCADO"].dropna().unique().tolist()) if not rx_clean.empty else []
            merc_med_filtro = st.multiselect("Filtrar Mercado / Clase:", mercados_disp_med, placeholder="Todos los mercados del médico...")
            df_desglose_med = obtener_desglose_productos_medico(medico_sel, merc_med_filtro if merc_med_filtro else None)
            if not df_desglose_med.empty:
                st.dataframe(
                    df_desglose_med,
                    hide_index=True,
                    use_container_width=True,
                    height=410,
                    column_config={
                        "% Cuota Categoría": st.column_config.ProgressColumn("% Cuota Categoría", format="%.1f%%", min_value=0, max_value=100)
                    }
                )
            else:
                st.info("Sin prescripciones activas en el corte actual para este especialista.")

        with sub_labs:
            if not df_labs.empty and "FABRICANTE" in df_labs.columns and "Médico" in df_labs.columns:
                df_labs_medico = df_labs[df_labs["Médico"] == medico_sel].copy()
                df_labs_medico = df_labs_medico[~df_labs_medico["FABRICANTE"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
                if not df_labs_medico.empty:
                    col_pxs_ytd = "Pxs-YTD" if "Pxs-YTD" in df_labs_medico.columns else next((c for c in df_labs_medico.columns if "YTD" in c.upper() and "PXS" in c.upper()), None)
                    col_pxs_m_lab = "Pxs-MES" if "Pxs-MES" in df_labs_medico.columns else next((c for c in df_labs_medico.columns if "MES" in c.upper() and "PXS" in c.upper()), None)
                    if col_pxs_ytd:
                        df_labs_medico[col_pxs_ytd] = pd.to_numeric(df_labs_medico[col_pxs_ytd], errors="coerce").fillna(0)
                        agg_l = {col_pxs_ytd: "sum"}
                        if col_pxs_m_lab:
                            df_labs_medico[col_pxs_m_lab] = pd.to_numeric(df_labs_medico[col_pxs_m_lab], errors="coerce").fillna(0)
                            agg_l[col_pxs_m_lab] = "sum"
                        df_agrupado = df_labs_medico.groupby("FABRICANTE").agg(agg_l).reset_index()
                        total_ytd_med = df_agrupado[col_pxs_ytd].sum()
                        df_agrupado["% MS YTD"] = ((df_agrupado[col_pxs_ytd] / total_ytd_med) * 100).round(2) if total_ytd_med > 0 else 0.0
                        df_agrupado = df_agrupado.sort_values(by=col_pxs_ytd, ascending=False).head(15)
                        df_agrupado["FABRICANTE"] = df_agrupado["FABRICANTE"].apply(lambda x: f"[GUTIS] {x}" if "GUTIS" in str(x).upper() else str(x))
                        df_agrupado[col_pxs_ytd] = df_agrupado[col_pxs_ytd].astype(int)
                        if col_pxs_m_lab: df_agrupado[col_pxs_m_lab] = df_agrupado[col_pxs_m_lab].astype(int)
                        ren_labs = {"FABRICANTE": "Laboratorio", col_pxs_ytd: "Pxs YTD"}
                        if col_pxs_m_lab: ren_labs[col_pxs_m_lab] = "Pxs Mes"
                        st.dataframe(
                            df_agrupado.rename(columns=ren_labs), hide_index=True, use_container_width=True, height=410,
                            column_config={"% MS YTD": st.column_config.ProgressColumn("% MS YTD", format="%.2f%%", min_value=0, max_value=100)}
                        )
                else:
                    st.info("Sin registros de fabricantes para este médico.")

        with sub_360:
            with st.form("form_perfil_360"):
                val_minsa = st.text_input("Código MINSA:", value=str(perfil_360_actual.get("MINSA", "")) if str(perfil_360_actual.get("MINSA", "")) != "nan" else "")
                val_cel = st.text_input("Celular / WhatsApp:", value=str(perfil_360_actual.get("Celular", "")) if str(perfil_360_actual.get("Celular", "")) != "nan" else "")
                val_cumple = st.text_input("Fecha de Cumpleaños:", value=str(perfil_360_actual.get("Cumpleaños", "")) if str(perfil_360_actual.get("Cumpleaños", "")) != "nan" else "")
                val_deporte = st.text_input("Contexto de Campo / Afinidad / Notas:", value=str(perfil_360_actual.get("Deporte", "")) if str(perfil_360_actual.get("Deporte", "")) != "nan" else "")
                opc_visita = ["Ultra-ejecutiva", "Discusión científica", "Casos clínicos"]
                idx_vis = opc_visita.index(perfil_360_actual.get("Estilo_Visita", opc_visita[0])) if perfil_360_actual.get("Estilo_Visita") in opc_visita else 0
                val_estilo_visita = st.selectbox("Estilo de Visita:", opc_visita, index=idx_vis)

                if st.form_submit_button("Guardar y Sincronizar Ficha 360", use_container_width=True, type="primary"):
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
                        else:
                            df_p_save = pd.DataFrame([nuevo_registro])
                        df_p_save.to_excel(ARCHIVO_PERFIL_360, index=False)
                    except:
                        pass
                    st.success("Ficha 360 sincronizada correctamente.")

# ==============================================================================
# NÚCLEO III: COPILOTO CHIRA (CON MICRÓFONO INTEGRADO Y MOTOR DE RUTA UNIFICADO)
# ==============================================================================
with nucleo_copiloto:
    col_chira_main, col_crm_post = st.columns([1.48, 0.97])

    with col_chira_main:
        st.markdown("##### COPILOTO CHIRA — CONSULTORÍA DE ESPECIALISTAS, CLASES TERAPÉUTICAS Y TERRITORIO")

        with st.container(border=True):
            p_c1, p_c2, p_c3, p_c4 = st.columns([1.2, 1.2, 1.2, 0.6])
            with p_c1: chira_ciu_sel = st.selectbox("Territorio:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="ch_ciu")
            with p_c2: chira_esp_sel = st.selectbox("Especialidad:", ["TODAS LAS ESPECIALIDADES"] + LISTA_ESPECIALIDADES_REALES, key="ch_esp")
            with p_c3: chira_mer_sel = st.selectbox("Mercado:", ["TODOS LOS MERCADOS"] + LISTA_MERCADOS_REALES, key="ch_mer")
            with p_c4: chira_top_sel = st.selectbox("Top:", [5, 10, 15, 20], index=1, key="ch_top")

            b_c1, b_c2, b_c3, b_c4, b_c5, b_c6 = st.columns(6)
            accion_consola = None
            if b_c1.button("Penetración", use_container_width=True): accion_consola = "PENETRACION"
            if b_c2.button("Sincronía", use_container_width=True): accion_consola = "SINCRONIA"
            if b_c3.button("Top Labs", use_container_width=True): accion_consola = "LABS"
            if b_c4.button("Pareto 80/20", use_container_width=True): accion_consola = "MEDICOS_PARETO"
            if b_c5.button("Conquista", use_container_width=True): accion_consola = "MEDICOS_CONQUISTA"
            if b_c6.button("No Visitados", use_container_width=True): accion_consola = "MEDICOS_NO_VISITADOS"

        # Barra de Micrófono para dictado por voz + Chat escrito
        texto_voz_transcrito = None
        if hasattr(st, "audio_input"):
            audio_val = st.audio_input("Dictar consulta por micrófono a Chira (opcional):")
            if audio_val is not None:
                audio_bytes = audio_val.getvalue()
                hash_actual = hash(audio_bytes)
                if st.session_state.ultimo_audio_hash != hash_actual:
                    st.session_state.ultimo_audio_hash = hash_actual
                    with st.spinner("Transcribiendo mensaje de voz..."):
                        texto_voz_transcrito = transcribir_audio_gemini(audio_bytes)

        chat_container_chira = st.container(height=350)
        for msg in st.session_state.chira_history:
            with chat_container_chira.chat_message(msg["role"]):
                st.write(msg["content"])

        input_chat_texto = st.chat_input("Escribe tu consulta estratégica o análisis de caso...")
        input_chat_chira = texto_voz_transcrito if texto_voz_transcrito else input_chat_texto

        if accion_consola or input_chat_chira:
            prio_target = None
            medico_detectado_chat = None

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
                top_n = int(match_num.group(1)) if match_num and 1 <= int(match_num.group(1)) <= 50 else 10

                medico_detectado_chat = detectar_medico_en_texto(input_chat_chira)
                es_pregunta_tactica_individual = any(k in texto_norm for k in [
                    "COMPRAD", "AMARRAD", "CASAD", "FIDELIZAD", "PIDE", "PEDIR", "PIDIO", "A CAMBIO",
                    "CONGRESO", "MUESTRA", "REGALO", "APOYO", "PATROCIN", "OBJECION", "ESCEPTIC",
                    "PRECIO", "CARO", "PASILLO", "ABORDO", "ABORDAR", "MANEJAR", "MANEJO", "ENTRARLE",
                    "ESTE MEDICO", "ESTA DOCTORA", "ESTE DOCTOR", "COMPARTIENDO", "COMPARTE", "QUE CREES QUE PASE"
                ])

                if not medico_detectado_chat and es_pregunta_tactica_individual:
                    medico_detectado_chat = st.session_state.ultimo_medico_chira if st.session_state.ultimo_medico_chira else medico_sel

                if medico_detectado_chat:
                    st.session_state.ultimo_medico_chira = medico_detectado_chat
                    modo_motor = "CONSULTORIA_MEDICO_INDIVIDUAL"
                    ciu_target, esp_target, mer_target = None, None, None
                else:
                    if "PRIORIDAD 1" in texto_norm: prio_target = 1
                    elif "PRIORIDAD 2" in texto_norm: prio_target = 2
                    elif "PRIORIDAD 3" in texto_norm: prio_target = 3

                    ciu_target = None
                    alias_municipios = {"JINOTEPE": "CARAZO", "DIRIAMBA": "CARAZO", "SAN MARCOS": "CARAZO", "NANDAIME": "GRANADA", "NINDIRI": "MASAYA", "SAN JORGE": "RIVAS", "JUIGALPA": "CHONTALES"}
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
                        if normalizar_txt(m_real.replace("MR ", "")) in texto_norm:
                            mer_target = m_real
                            break
                    if not mer_target:
                        for m_key, m_val in MERCADOS_PRIORITARIOS.items():
                            if any(normalizar_txt(k) in texto_norm for k in m_val["match_mercados"]):
                                mer_target = m_key
                                break

                    if any(k in texto_norm for k in ["PENETRACION", "REVISION DEL PANEL", "RENDIMIENTO INTERNO", "TOP 1", "TOP 3"]):
                        modo_motor = "PENETRACION"
                    elif any(k in texto_norm for k in ["SINCRONIA", "TENDENCIA", "FUGA", "RECETAS VS", "MEDICO VS"]):
                        modo_motor = "SINCRONIA"
                    elif any(k in texto_norm for k in ["NO VISITADO", "NO VISITADOS", "FUERA DE PANEL", "NO ESTA EN MI PANEL", "INCORPORAR", "NUEVOS MEDICOS"]):
                        modo_motor = "MEDICOS_NO_VISITADOS"
                    elif any(k in texto_norm for k in ["LABORATORIO", "FABRICANTE", "CASA", "INDUSTRIA"]):
                        modo_motor = "LABS"
                    elif any(k in texto_norm for k in ["CONQUISTA", "ROBAR", "ATAQUE", "COMPETENCIA", "OPORTUNIDAD"]):
                        modo_motor = "MEDICOS_CONQUISTA"
                    else:
                        modo_motor = "MEDICOS_PARETO"

            st.session_state.chira_history.append({"role": "user", "content": pregunta_mostrar})
            with chat_container_chira.chat_message("user"):
                st.write(pregunta_mostrar)

            with st.spinner("Procesando análisis estratégico y cruzando bases de datos..."):
                if modo_motor == "CONSULTORIA_MEDICO_INDIVIDUAL":
                    df_desg_doc = obtener_desglose_productos_medico(medico_detectado_chat)
                    tabla_md_doc = df_a_markdown_nativo(df_desg_doc.head(15)) if not df_desg_doc.empty else "Sin prescripciones registradas en el corte actual."

                    sub_p_d = df_panel[df_panel["Médico"] == medico_detectado_chat]
                    esp_d = str(sub_p_d.iloc[0].get("Especialidad", "ESPECIALISTA")) if not sub_p_d.empty else "ESPECIALISTA"
                    ciu_d = str(sub_p_d.iloc[0].get("CIUDAD", "NICARAGUA")) if not sub_p_d.empty else "NICARAGUA"
                    cat_d = str(sub_p_d.iloc[0].get("CATEGORIA", "S/C")) if not sub_p_d.empty else "S/C"

                    resumen_base_doc = f"""### Análisis Táctico y Expediente Prescriptivo: Dr(a). {medico_detectado_chat}
**Especialidad:** {esp_d} | **Categoría:** {cat_d} | **Ciudad:** {ciu_d}

#### Desglose de Productos Prescritos por Clase Terapéutica:
{tabla_md_doc}
"""
                    prompt_cog = f"""{REGLAS_FARMA}
Actúa como CHIRA, Consultora Senior de Inteligencia Comercial de Laboratorios Gutis en Nicaragua.
Erick Calderón te plantea la siguiente consulta:
"{input_chat_chira}"

Aquí están los datos reales de prescripción del Dr(a). {medico_detectado_chat}:
{resumen_base_doc}

INSTRUCCIONES:
1. Inicia con un ANÁLISIS TÁCTICO directo respondiendo a la pregunta de Erick usando las cifras exactas de cada marca y su competencia dentro de la clase terapéutica.
2. Verifica la Escala de Adopción en cada mercado: si el médico ya tiene una cuota alta con Gutis (>50% MS), indica agradecer su lealtad, blindar sutilmente la marca y hacer el puente hacia otra línea donde tengamos brecha. Si comparte la receta o está en cero, estructura la estrategia de expansión o conquista paso a paso."""
                    res_ia = llamar_gemini(prompt_cog)
                    resultado_final = res_ia if (res_ia and len(res_ia.strip()) > 150) else resumen_base_doc

                elif modo_motor == "PENETRACION":
                    etiqueta_z = ciu_target if ciu_target else "TODO MI PANEL"
                    df_r_ch, df_c_ch = calcular_matriz_penetracion_panel(etiqueta_z)
                    if not df_r_ch.empty:
                        resultado_final = f"### Matriz de Penetración por Especialidad ({etiqueta_z})\n\n#### 1. Rendimiento Interno YTD:\n{df_a_markdown_nativo(df_r_ch)}\n\n#### 2. Top 5 Competencia Directa:\n{df_a_markdown_nativo(df_c_ch)}"
                    else:
                        resultado_final = f"No se encontraron datos de penetración para {etiqueta_z}."

                elif modo_motor == "SINCRONIA":
                    etiqueta_z = ciu_target if ciu_target else "TODO MI PANEL"
                    df_s_ch = calcular_sincronia_rx_vs_sellout(etiqueta_z)
                    if not df_s_ch.empty:
                        resultado_final = f"### Sincronía Temporal: Rx vs. Sell-Out ({etiqueta_z})\n\n{df_a_markdown_nativo(df_s_ch)}"
                    else:
                        resultado_final = f"No se encontraron datos de sincronía para {etiqueta_z}."

                elif modo_motor == "LABS":
                    etiqueta_z = ciu_target if ciu_target else "TODO MI PANEL"
                    etiqueta_e = esp_target if esp_target else "Todas las Especialidades"
                    df_p_sub = df_panel.copy()
                    if ciu_target: df_p_sub = df_p_sub[df_p_sub["CIUDAD"].str.contains(re.escape(ciu_target), na=False)]
                    if esp_target: df_p_sub = df_p_sub[df_p_sub["Especialidad"].str.contains(re.escape(esp_target[:5]), na=False)]
                    meds_seg = set(df_p_sub["Médico"].dropna().unique())
                    df_l_seg = df_labs[df_labs["Médico"].isin(meds_seg)].copy() if not df_labs.empty else pd.DataFrame()
                    df_l_seg = df_l_seg[~df_l_seg["FABRICANTE"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
                    col_ytd = "Pxs-YTD" if "Pxs-YTD" in df_l_seg.columns else next((c for c in df_l_seg.columns if "PXS" in c.upper()), None)
                    if not df_l_seg.empty and col_ytd:
                        df_l_seg[col_ytd] = pd.to_numeric(df_l_seg[col_ytd], errors="coerce").fillna(0)
                        df_rk = df_l_seg.groupby("FABRICANTE").agg({col_ytd: "sum", "Médico": lambda x: len(set(x))}).reset_index().rename(columns={"Médico": "Médicos Prescriptores"})
                        univ = df_rk[col_ytd].sum()
                        df_rk["% MS YTD"] = (df_rk[col_ytd] / univ * 100).round(2) if univ > 0 else 0.0
                        df_rk = df_rk.sort_values(by=col_ytd, ascending=False).head(top_n)
                        resultado_final = f"### Top {top_n} Laboratorios | {etiqueta_e} ({etiqueta_z})\n\n{df_a_markdown_nativo(df_rk)}"
                    else:
                        resultado_final = "Sin registros en el archivo de laboratorios para ese filtro."

                else:
                    # USA EXACTAMENTE EL MISMO MOTOR UNIFICADO DE LA TABLA DE RUTA (NUNCA MÁS DARÁ FALSO VACÍO EN RIVAS)
                    fuera_flag = (modo_motor == "MEDICOS_NO_VISITADOS")
                    df_rk_meds = obtener_ranking_medicos_mercado(
                        ciudad_target=ciu_target,
                        esp_target=esp_target,
                        mer_target=mer_target,
                        prio_target=prio_target,
                        incluir_fuera_panel=fuera_flag
                    )
                    if not df_rk_meds.empty:
                        if modo_motor == "MEDICOS_CONQUISTA":
                            df_rk_meds = df_rk_meds.sort_values(by=["Pxs Competencia (Conquista)", "Pxs Totales (Activo)"], ascending=[False, False])
                        etiqueta_z = ciu_target if ciu_target else "TODO MI PANEL"
                        etiqueta_m = mer_target if mer_target else "Portafolio Gutis"
                        df_top_view = df_rk_meds.head(top_n)[["Médico", "Especialidad", "CATEGORIA", "CIUDAD", "Pxs Totales (Activo)", "Pxs Gutis", "Pxs Competencia (Conquista)", "Productos que Receta en la Categoría"]]
                        base_tabla = f"### Médicos Más Importantes | Territorio: {etiqueta_z} | Mercado: {etiqueta_m}\n\n{df_a_markdown_nativo(df_top_view)}"
                        prompt_rk = f"""{REGLAS_FARMA}
Presenta esta tabla exacta de los médicos más importantes para {etiqueta_m} en {etiqueta_z} y añade debajo un breve análisis táctico de 3 puntos sobre a quién abordar primero (diferenciando quién ya es leal a Gutis para blindar/hacer puente y quién tiene volumen en la competencia para conquistar):
{base_tabla}"""
                        res_ia_rk = llamar_gemini(prompt_rk)
                        resultado_final = res_ia_rk if (res_ia_rk and len(res_ia_rk.strip()) > 120) else base_tabla
                    else:
                        resultado_final = "No se encontraron médicos con prescripciones registradas para esa combinación."

            st.session_state.chira_history.append({"role": "assistant", "content": resultado_final})
            st.rerun()

    # COLUMNA DERECHA: UNIDAD 9 POST-VISITA Y BITÁCORA CRM
    with col_crm_post:
        med_crm_target = st.session_state.ultimo_medico_chira if st.session_state.ultimo_medico_chira else medico_sel
        st.markdown(f"##### UNIDAD 9: ANÁLISIS POST-VISITA Y BITÁCORA CRM — {med_crm_target[:22]}")
        with st.form("form_bitacora_crm"):
            cb1, cb2 = st.columns(2)
            with cb1: prod_promovido = st.selectbox("1. Producto Foco (P1):", [m["producto"] for m in MERCADOS_PRIORITARIOS.values()])
            with cb2: prod_puente = st.selectbox("2. Producto Puente (P2/P3):", ["Ninguno"] + [m["producto"] for m in MERCADOS_PRIORITARIOS.values()], index=2)
            cb3, cb4 = st.columns(2)
            with cb3: resultado_obj = st.selectbox("3. Resultado SMART:", ["Objetivo Principal Logrado", "Objetivo de Respaldo Logrado", "Seguimiento Pendiente"])
            with cb4: escala_post = st.selectbox("4. Escalón Alcanzado:", ["1. No Consciente", "2. Consciente", "3. Prueba (2-10 Pxs)", "4. Adopción (25-50%)", "5. Lealtad (>50%)"])
            compromiso_med = st.text_input("Compromiso del Médico:", value="Consolidar prescripción y puente clínico")
            compromiso_vis = st.text_input("Compromiso Visitador:", value=f"Garantizar stock en {top_farmacias_ciudad_str.split(',')[0]}")
            notas_visita = st.text_area("Acuerdos Clínicos y Observaciones Post-Visita:", height=68, placeholder="Registra hallazgos clínicos o seguimiento para la próxima apertura...")

            if st.form_submit_button("Registrar Cierre de Ciclo en Bitácora CRM", use_container_width=True, type="primary"):
                nueva_visita = {
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "Ciudad": ciudad, "Médico": med_crm_target,
                    "Especialidad": especialidad, "Producto_Foco": prod_promovido, "Producto_Puente": prod_puente,
                    "Logro_SMART": resultado_obj, "Escala_TVP": escala_post,
                    "Acuerdo_Medico": compromiso_med, "Acuerdo_Visitador": compromiso_vis, "Notas": notas_visita
                }
                st.session_state.bitacora_memoria.append(nueva_visita)
                try:
                    if os.path.exists(ARCHIVO_BITACORA):
                        df_bit_old = pd.read_excel(ARCHIVO_BITACORA)
                        df_bit_new = pd.concat([df_bit_old, pd.DataFrame([nueva_visita])], ignore_index=True)
                    else:
                        df_bit_new = pd.DataFrame([nueva_visita])
                    df_bit_new.to_excel(ARCHIVO_BITACORA, index=False)
                except:
                    pass
                st.success(f"Visita a {med_crm_target} registrada en CRM.")

        df_hist_crm = pd.DataFrame(st.session_state.bitacora_memoria)
        if os.path.exists(ARCHIVO_BITACORA):
            try:
                df_hist_crm = pd.read_excel(ARCHIVO_BITACORA)
            except:
                pass
        if not df_hist_crm.empty:
            st.dataframe(df_hist_crm.tail(8), hide_index=True, use_container_width=True, height=180)
            csv_crm = df_hist_crm.to_csv(index=False).encode("utf-8-sig")
            st.download_button("Exportar Bitácora CRM (CSV)", data=csv_crm, file_name=f"CRM_TVP_Gutis_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)
