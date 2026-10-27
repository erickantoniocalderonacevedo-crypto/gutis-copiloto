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

# --- CONVERSOR NATIVO DE TABLAS A MARKDOWN ---
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

# --- VADEMÉCUM OFICIAL GUTIS NICARAGUA 2026 (ADUANA ESTRICTA DE MARCAS Y PERFILES PEDIÁTRICO/ADULTO) ---
MERCADOS_PRIORITARIOS = {
    "MR TALERDIN": {
        "producto": "Talerdín", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Core)",
        "apto_pediatria": True,
        "keywords": ["TALERDIN", "CETIRIZINA", "CETRILER", "ALERCET", "DEGRALER"],
        "paciente_meta": "Pacientes con rinitis alérgica, conjuntivitis alérgica, urticaria o prurito que requieren control antihistamínico seguro.",
        "paciente_meta_ped": "Pacientes pediátricos y lactantes con rinitis alérgica, urticaria o prurito que requieren alivio seguro sin irritación gástrica.",
        "caracteristica": "Cetirizina en Tabletas (10 mg), Jarabe (60 ml 100% libre de alcohol) y Solución Gotas (10 ml: 1 gota por cada 2 kg de peso en menores de 2 años).",
        "beneficio": "Garantiza apego total al tratamiento sin rechazo por sabor ni efectos adversos gástricos por excipientes alcohólicos.",
        "nicho_flanqueo": "Lactantes y niños pequeños con reflujo o intolerancia al excipiente alcohólico de los jarabes tradicionales.",
        "love_brand": "Tranquilidad nocturna para el paciente y su familia desde la primera toma, libre de alcohol."
    },
    "MR BIOTOS": {
        "producto": "Biotos Inmune", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Core)",
        "apto_pediatria": True,
        "keywords": ["BIOTOS", "HEDERA", "PELARGONIUM", "ABRILAR", "TUSILEXIL"],
        "paciente_meta": "Pacientes con tos seca, tos con flemas y secreción nasal en resfriado común, bronquitis, rinosinusitis y faringitis viral.",
        "paciente_meta_ped": "Pacientes pediátricos (desde los 2 años) con IVRS virales, tos seca o con flemas y dificultad para expulsar secreciones.",
        "caracteristica": "Fórmula fitofarmacológica dual única: Hedera hélix (35 mg) + Pelargonium sidoides (12.5 mg) en presentación Pediátrica (120 ml) y Adulto (170 ml).",
        "beneficio": "Alivia la tos seca y con flemas mientras estimula los mecanismos defensivos antivirales y antibacterianos (efecto inmunorregulador).",
        "nicho_flanqueo": "Pacientes con cuadros respiratorios virales donde un mucolítico simple (solo Hedera) se queda corto sin inmunorregulación.",
        "love_brand": "Devolver la respiración libre y estimular las defensas naturales con respaldo científico."
    },
    "MR CLEMBROXIL": {
        "producto": "Clembroxil Compuesto", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Core)",
        "apto_pediatria": True,
        "keywords": ["CLEMBROXIL", "CLENBUTEROL", "AMBROXOL", "MUCOSOLVAN"],
        "paciente_meta": "Pacientes con patologías respiratorias agudas y crónicas que cursan con retención de secreciones y broncoespasmo.",
        "paciente_meta_ped": "Pacientes pediátricos y lactantes con broncoespasmo, sibilancias y retención severa de flemas (dosificación exacta a 2 gotas/kg).",
        "caracteristica": "Sinergia de Ambroxol (7.5 mg) + Clenbuterol (5 mcg) en Jarabe (120 ml) y Solución Gotas Pediátricas (20 ml), 100% libre de azúcar y alcohol.",
        "beneficio": "Abre el bronquio y fluidifica el moco simultáneamente, despejando las vías respiratorias sin irritación por azúcar o alcohol.",
        "nicho_flanqueo": "Pacientes con tos espástica y cierre bronquial donde un mucolítico aislado no resuelve el broncoespasmo.",
        "love_brand": "Respaldo respiratorio contundente y seguro cuando al paciente le falta el aire."
    },
    "MR MOMETZONA": {
        "producto": "Mometzona", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Core)",
        "apto_pediatria": True,
        "keywords": ["MOMETZONA", "MOMETASONA", "NASONEX", "GAMMAFLUX"],
        "paciente_meta": "Pacientes con rinitis alérgica u obstrucción nasal inflamatoria que requieren control local sin irritación.",
        "paciente_meta_ped": "Pacientes pediátricos (2 a 11 años: 1 pulsación al día) y adolescentes con rinitis alérgica y congestión nasal persistente.",
        "caracteristica": "Mometasona furoato al 0.05% en spray nasal acuoso (140 aplicaciones), suspensión 100% libre de alcohol.",
        "beneficio": "Desinflama la mucosa nasal desde la primera aplicación diaria sin causar ardor, resequedad ni sangrado nasal.",
        "nicho_flanqueo": "Pacientes con mucosa nasal sensible que abandonan otros sprays por ardor o presencia de alcohol.",
        "love_brand": "Descongestionar y devolver el descanso reparador con suavidad acuosa libre de alcohol."
    },
    "MR VENTILAR": {
        "producto": "Ventilar", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Core)",
        "apto_pediatria": True,
        "keywords": ["VENTILAR", "MONTELUKAST", "SINGULAIR", "AIRUM", "SUVIAR"],
        "paciente_meta": "Pacientes con asma bronquial o rinitis alérgica que requieren control preventivo nocturno.",
        "paciente_meta_ped": "Pacientes pediátricos desde los 6 meses hasta los 14 años con hiperreactividad bronquial, asma o rinitis alérgica.",
        "caracteristica": "Montelukast sódico en 3 presentaciones exactas: 4 mg masticable sabor naranja (6 meses a 5 años), 5 mg masticable sabor tutti-chicle (6 a 14 años) y 10 mg recubierto.",
        "beneficio": "Excelente adherencia pediátrica por su sabor agradable y control sostenido de leucotrienos con una sola toma nocturna.",
        "nicho_flanqueo": "Pacientes que requieren terapia continua de control sin abandonar el esquema por costo o mal sabor.",
        "love_brand": "Libertad para que el niño juegue y duerma toda la noche sin crisis respiratorias."
    },
    "MR GASTROALIVIO": {
        "producto": "Gastroalivio", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Core)",
        "apto_pediatria": False,
        "keywords": ["GASTROALIVIO", "ESOMEPRAZOL", "CARBUM", "NEXIUM"],
        "paciente_meta": "Pacientes adultos con ERGE, gastropatía por AINEs, hiperklorhidria o en erradicación de Helicobacter pylori.",
        "paciente_meta_ped": "Pacientes adolescentes mayores y adultos con ERGE o gastritis erosiva.",
        "caracteristica": "Esomeprazol 40 mg en cápsulas de liberación retardada con micropellets gastrorresistentes (libre de gluten y lactosa) + Plan Paciente 2+1.",
        "beneficio": "Protección gástrica y control ácido por 24 horas completas, sumado al Plan Paciente 2+1 (compra 2 cajas y recibe 1 gratis) que asegura el tratamiento completo.",
        "nicho_flanqueo": "Pacientes con ERGE rebelde donde el esomeprazol convencional no cubre las 24 horas o el paciente abandona el mes por costo.",
        "love_brand": "Tecnología de micropellets y respaldo 2+1 que protegen el estómago y la economía del paciente."
    },
    "MR DALIVIO": {
        "producto": "Dalivio / Dalivio Tramax", "peso": 3, "prioridad": 1, "categoria_mercado": "Prioridad 1 (Core)",
        "apto_pediatria": False,
        "keywords": ["DALIVIO", "DALIVIUM", "DEXKETOPROFENO", "ENANTYUM", "STADIUM", "CETIX", "DISFLAM"],
        "paciente_meta": "Pacientes adultos con dolor agudo de moderado a intenso (musculoesquelético, dismenorrea, odontalgia, cólico renal o dolor postoperatorio).",
        "paciente_meta_ped": "Pacientes adolescentes mayores con dolor agudo traumático, odontalgia o dismenorrea.",
        "caracteristica": "Dexketoprofeno en 3 vías (Tabletas 25 mg, Solución oral bebible 25 mg/10 ml e Inyectable 50 mg/2 ml) + Dalivio Tramax (Dexketoprofeno 25 mg + Tramadol 75 mg para analgesia multimodal).",
        "beneficio": "Alivio rápido y potente del dolor agudo en minutos (especialmente con el sobre bebible o ampolla) y analgesia multimodal en casos severos.",
        "nicho_flanqueo": "Pacientes con dolor agudo severo donde un AINE tradicional tarda demasiado en actuar o irrita la mucosa gástrica.",
        "love_brand": "Aliados del alivio rápido para devolverle la funcionalidad al paciente en minutos."
    },
    "MR CONFLEXIL": {
        "producto": "Conflexil / Conflexil Plus Shot", "peso": 2, "prioridad": 2, "categoria_mercado": "Prioridad 2 (Expansión)",
        "apto_pediatria": False,
        "keywords": ["CONFLEXIL", "CONRELAX", "TIZANIDINA", "MELOXICAM", "TIOCOLCHICOSIDO"],
        "paciente_meta": "Pacientes adultos y adolescentes (>16 años) con contracturas musculares, cervicalgia, dorsalgia o lumbalgia aguda.",
        "paciente_meta_ped": "Adolescentes a partir de los 16 años con contracturas musculares deportivas o posturales.",
        "caracteristica": "Portafolio integral: Conflexil (Tiocolchicósido 4 mg y Fuerte 8 mg que NO produce sueño) + Conflexil Plus Tabletas y Conflexil Plus Shot (bebible en stick pack con Tiocolchicósido 4 mg + Diclofenaco potásico 50 mg, aprobado por Guías ACP).",
        "beneficio": "Triple acción (analgésica, antiinflamatoria y miorrelajante) de rápida absorción en Shot bebible, recuperando la movilidad sin sedación diurna.",
        "nicho_flanqueo": "Pacientes laboralmente activos con lumbalgia o contractura que no pueden permitirse la somnolencia de otros relajantes.",
        "love_brand": "Liberar el movimiento del paciente sin adormecer su ritmo de vida."
    },
    "MR VALERPAN": {
        "producto": "Valerpan", "peso": 2, "prioridad": 2, "categoria_mercado": "Prioridad 2 (Expansión)",
        "apto_pediatria": True,
        "keywords": ["VALERPAN", "BETAMETASONA", "CELESTONE", "DIPROSPAN", "DEXAMETASONA"],
        "paciente_meta": "Pacientes con procesos inflamatorios severos, crisis alérgicas agudas o patologías articulares que requieren corticoterapia de doble acción.",
        "paciente_meta_ped": "Pacientes con cuadros alérgicos o inflamatorios agudos severos que requieren control inmediato y sostenido.",
        "caracteristica": "Fosfato sódico de Betametasona + Dipropionato de Betametasona en ampolla de 1 ml y 2 ml con viscosidad adecuada y óptima homogeneidad.",
        "beneficio": "Doble acción comprobada: inicio rápido a los 30 minutos (fosfato) y efecto prolongado hasta por 30 días (dipropionato) en una aplicación suave.",
        "nicho_flanqueo": "Cuadros inflamatorios o alérgicos agudos donde la dexametasona simple pierde efecto rápido y genera recaída.",
        "love_brand": "Calidad garantizada con acción inmediata en 30 minutos y respaldo prolongado."
    },
    "MR RENOVART": {
        "producto": "Renovart Platinum", "peso": 2, "prioridad": 2, "categoria_mercado": "Prioridad 2 (Expansión)",
        "apto_pediatria": False,
        "keywords": ["RENOVART", "COLAGENO", "GLUCOSAMINA", "CURCUMA"],
        "paciente_meta": "Pacientes adultos con dolor articular inflamatorio, desgaste de cartílago o enfermedades degenerativas articulares.",
        "paciente_meta_ped": "Adolescentes deportistas con sobrecarga articular.",
        "caracteristica": "Fórmula pentavalente en sticks sabor naranja: Colágeno 100% hidrolizado bioactivo (10 g) + Cúrcuma longa (400 mg) + N-AcetilGlucosamina (1000 mg) + Condroitina (800 mg) + Vitamina C (60 mg).",
        "beneficio": "No solo nutre el cartílago, sino que controla el dolor e inflamación articular gracias a los curcuminoides, sin azúcar, sin lactosa y bajo en sodio.",
        "nicho_flanqueo": "Pacientes con artrosis donde un colágeno simple sin cúrcuma ni glucosamina no alivia el dolor articular.",
        "love_brand": "Fortalecer las articulaciones y favorecer la movilidad diaria con la fórmula más completa."
    },
    "MR MUPIRAL": {
        "producto": "Mupiral", "peso": 2, "prioridad": 2, "categoria_mercado": "Prioridad 2 (Expansión)",
        "apto_pediatria": True,
        "keywords": ["MUPIRAL", "MUPIROCINA", "BACTROBAN"],
        "paciente_meta": "Pacientes con infecciones bacterianas primarias de la piel (impétigo, foliculitis, furunculosis) o secundarias (heridas, cortaduras, quemaduras).",
        "paciente_meta_ped": "Pacientes pediátricos (desde los 2 meses de edad) con impétigo, foliculitis o raspones y heridas sobreinfectadas.",
        "caracteristica": "Mupirocina al 2% en ungüento tópico (tubo de 15 g), seguro en adultos y niños desde los 2 meses de edad.",
        "beneficio": "Erradicación bacteriana localizada altamente eficaz con excelente tolerabilidad cutánea.",
        "nicho_flanqueo": "Infecciones cutáneas pediátricas o heridas donde los antibióticos tópicos combinados simples ya presentan resistencia.",
        "love_brand": "Seguridad antibiótica tópica de primera línea desde los 2 meses de edad."
    },
    "MR BICORPAN": {
        "producto": "Bicorpan", "peso": 2, "prioridad": 2, "categoria_mercado": "Prioridad 2 (Expansión)",
        "apto_pediatria": True,
        "keywords": ["BICORPAN"],
        "paciente_meta": "Pacientes (>12 años y adultos) con dermatitis inflamatorias complicadas con infecciones por bacterias y/o hongos (piodermias, tiñas).",
        "paciente_meta_ped": "Pacientes mayores de 12 años con dermatitis alérgica o por contacto sobreinfectada con hongos o bacterias.",
        "caracteristica": "Fórmula cuádruple en crema (15 g): Betametasona (0.5 mg) + Gentamicina (1 mg) + Tolnaftato (10 mg) + Yodoclorohidroxiquinoleína (10 mg).",
        "beneficio": "Controla simultáneamente la inflamación, el prurito, la infección bacteriana y la micosis en lesiones dérmicas mixtas.",
        "nicho_flanqueo": "Dermatitis mixtas rebeldes donde una crema simple no cubre hongos y bacterias a la vez.",
        "love_brand": "Resolución integral para afecciones complejas de la piel."
    },
    "MR FEMGYL": {
        "producto": "Femgyl", "peso": 1, "prioridad": 3, "categoria_mercado": "Prioridad 3 (Complemento)",
        "apto_pediatria": False,
        "keywords": ["FEMGYL"],
        "paciente_meta": "Pacientes en edad reproductiva que buscan anticoncepción hormonal mensual cómoda y segura.",
        "paciente_meta_ped": "Pacientes ginecológicas en control anticonceptivo.",
        "caracteristica": "Enantato de noretisterona (50 mg) + Valerato de estradiol (5 mg) en ampolla de 1 ml de aplicación mensual fecha calendario.",
        "beneficio": "Alta eficacia anticonceptiva en una sola aplicación mensual que evita olvidos diarios.",
        "nicho_flanqueo": "Usuarias que olvidan la toma diaria de tabletas orales.",
        "love_brand": "Tranquilidad y confianza mensual en salud femenina."
    },
    "MR NORGYLEN": {
        "producto": "Norgylen", "peso": 1, "prioridad": 3, "categoria_mercado": "Prioridad 3 (Complemento)",
        "apto_pediatria": False,
        "keywords": ["NORGYLEN"],
        "paciente_meta": "Pacientes que requieren anticoncepción oral hormonal combinada confiable.",
        "paciente_meta_ped": "Pacientes ginecológicas en regulación de ciclo o anticoncepción.",
        "caracteristica": "Levonorgestrel (0.15 mg) + Etinilestradiol (0.03 mg) en caja con 21 tabletas recubiertas.",
        "beneficio": "Control predecible del ciclo menstrual con alta eficacia y seguridad.",
        "nicho_flanqueo": "Pacientes que buscan estabilidad hormonal oral con respaldo farmacéutico.",
        "love_brand": "Cuidado confiable todos los días para la mujer."
    },
    "MR ANSIOLIT": {
        "producto": "Ansiolit", "peso": 1, "prioridad": 3, "categoria_mercado": "Prioridad 3 (Complemento)",
        "apto_pediatria": False,
        "keywords": ["ANSIOLIT", "ALPRAZOLAM"],
        "paciente_meta": "Pacientes adultos con ansiedad generalizada, ansiedad asociada a depresión o estados de pánico.",
        "paciente_meta_ped": "Pacientes adultos en manejo de ansiedad.",
        "caracteristica": "Alprazolam 0.5 mg en tabletas ranuradas para dosificación individualizada.",
        "beneficio": "Rápido control de las crisis de ansiedad y síntomas somáticos asociados.",
        "nicho_flanqueo": "Pacientes con crisis de angustia o insomnio por ansiedad aguda.",
        "love_brand": "Paz mental y control oportuno en trastornos de ansiedad."
    },
    "MR DEPAX": {
        "producto": "Depax", "peso": 1, "prioridad": 3, "categoria_mercado": "Prioridad 3 (Complemento)",
        "apto_pediatria": False,
        "keywords": ["DEPAX", "SERTRALINA"],
        "paciente_meta": "Pacientes adultos con depresión, TOC, trastorno de pánico, estrés postraumático o fobia social.",
        "paciente_meta_ped": "Pacientes en manejo por neurociencias.",
        "caracteristica": "Sertralina 50 mg en tabletas recubiertas con Sello de Bioequivalencia Comprobada.",
        "beneficio": "Garantiza idéntica biodisponibilidad y eficacia clínica que el innovador con un costo accesible para el apego a largo plazo.",
        "nicho_flanqueo": "Pacientes crónicos que necesitan seguridad bioequivalente certificada.",
        "love_brand": "Bioequivalencia comprobada para acompañar la recuperación emocional."
    },
    "MR FELICITAT": {
        "producto": "Felicitat", "peso": 1, "prioridad": 3, "categoria_mercado": "Prioridad 3 (Complemento)",
        "apto_pediatria": False,
        "keywords": ["FELICITAT", "ESCITALOPRAM"],
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

# Mercados de Close-Up que NO existen en el Vademécum Nicaragua 2026 y deben bloquearse o re-homologarse
MERCADOS_EXCLUIDOS_NICARAGUA = ["VALVIREX", "PRIMABELA", "BELEZA", "DESLER", " ZITRO", "FLUKIT"]

REGLAS_FARMA = """
REGLAS FARMACOLÓGICAS Y VADEMÉCUM OFICIAL GUTIS NICARAGUA 2026 (ESTRICTO):
1. PROHIBIDO mencionar marcas que NO existen en Nicaragua: JAMÁS menciones 'Disflam', 'Disflam Familia', 'Conrelax', 'Dalivium', 'Valvirex' ni 'Primabela' como marcas a promover. En Nicaragua las marcas oficiales son:
   - Línea Dolor: Conflexil (4mg y Fuerte 8mg), Conflexil Plus Tabletas y Conflexil Plus Shot (sobres bebibles Tiocolchicósido 4mg + Diclofenaco potásico 50mg, Guías ACP), Dalivio (Dexketoprofeno Tabletas 25mg, Bebible 25mg/10ml, Ampolla 50mg/2ml), Dalivio Tramax (Dexketoprofeno 25mg + Tramadol 75mg), Valerpan (Fosfato + Dipropionato de Betametasona ampolla 1ml y 2ml: acción en 30 min y por 30 días).
   - Salud Articular: Renovart Platinum con Cúrcuma (Colágeno hidrolizado 10g + Cúrcuma 400mg + N-AcetilGlucosamina 1000mg + Condroitina 800mg + Vitamina C 60mg).
   - Línea Respiratoria: Talerdín (Cetirizina Tabletas, Jarabe sin alcohol y Gotas: 1 gota/2kg en <2 años), Biotos Inmune (Hedera hélix + Pelargonium sidoides Pediátrico 120ml y Adulto 170ml), Clembroxil Compuesto (Ambroxol + Clenbuterol Jarabe 120ml y Gotas 20ml a 2 gotas/kg sin azúcar ni alcohol), Mometzona (Mometasona spray acuoso sin alcohol), Ventilar (Montelukast 4mg naranja, 5mg tutti-chicle y 10mg).
   - Línea Gastro: Gastroalivio (Esomeprazol 40mg micropellets + Plan Paciente 2+1). PROHIBIDO en Pediatría.
   - Línea Dermatológica, Salud Femenina y Neurociencias: Mupiral (Mupirocina 2% desde los 2 meses), Bicorpan (crema cuádruple >12 años), Femgyl, Norgylen, Ansiolit, Depax (Bioequivalencia comprobada) y Felicitat (10mg y 20mg).
2. COHERENCIA CON LA ESPECIALIDAD:
   - Si el médico es PEDIATRA, está PROHIBIDO hablar de 'adultos' en la agenda o promover líneas exclusivas de adultos (Gastroalivio, Conflexil, Dalivio Tramax, Renovart, Femgyl, Neurociencias). Enfócate 100% en lactantes, niños, gotas por kilo de peso y jarabes libres de alcohol/azúcar.
3. COHERENCIA TÁCTICA CON LA ESCALA DE ADOPCIÓN (MANUAL TVP GUTIS):
   - Si el médico ya está en LEALTAD (>50% MS) o ADOPCIÓN ALTA en una marca de Gutis: está PROHIBIDO pedirle 'probar en 3 a 5 pacientes' como si no nos conociera. Debes AGRADECER su lealtad como socio clave, BLINDAR la marca sutilmente y usar esa confianza para hacer el PUENTE hacia un segundo producto donde sí necesitamos crecer.
   - Si está en PRUEBA o ADOPCIÓN PARCIAL (comparte receta): agradece lo que ya nos da, indaga su experiencia con esos pacientes y migra sutilmente el nicho que aún entrega al competidor.
   - Si está en NO CONSCIENTE / CONSCIENTE (0 Pxs): aplica sondeo de descubrimiento y pide compromiso inicial de prueba (3 a 5 pacientes).
"""

# --- ESTILOS CSS EJECUTIVOS ---
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

# --- CARGA INTELIGENTE Y DEPURACIÓN DE DATOS ---
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
    if not df_rx.empty and "Médico" in df_rx.columns:
        df_rx["Médico"] = df_rx["Médico"].astype(str).str.strip().str.upper()
        if "NOMBRE_PRODUCTO" in df_rx.columns:
            df_rx = df_rx.dropna(subset=["NOMBRE_PRODUCTO"]).copy()
            df_rx["NOMBRE_PRODUCTO"] = df_rx["NOMBRE_PRODUCTO"].astype(str).str.strip()
            df_rx = df_rx[~df_rx["NOMBRE_PRODUCTO"].str.upper().isin(["TOTAL", "NAN", "NONE", ""])].copy()
        if "MERCADO" in df_rx.columns:
            # Filtrar mercados regionales que no pertenecen al portafolio activo de Nicaragua
            df_rx = df_rx[~df_rx["MERCADO"].apply(normalizar_txt).apply(lambda m: any(ex in m for ex in MERCADOS_EXCLUIDOS_NICARAGUA))].copy()
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
if "ultimo_medico_chira" not in st.session_state: st.session_state.ultimo_medico_chira = None

# --- ENCABEZADO EJECUTIVO COMPACTO ---
st.markdown("""
<div style='background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); padding: 16px 22px; border-radius: 8px; margin-bottom: 14px; border-left: 6px solid #38bdf8; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;'>
    <div>
        <h2 style='color: #ffffff; margin: 0; font-size: 1.45rem; letter-spacing: 0.4px; font-weight: 800;'>⚜️ [GUTIS BI] — TERMINAL DE INTELIGENCIA COMERCIAL & ARQUITECTURA TVP</h2>
        <p style='color: #93c5fd; margin: 0; font-size: 0.76rem; text-transform: uppercase; font-weight: 600; margin-top: 3px; letter-spacing: 0.9px;'>Núcleo I: Radar Territorial  |  Núcleo II: Consultorio 360° & Canvas TVP Adaptativo  |  Núcleo III: Copiloto Cognitivo Chira & CRM</p>
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
    if deporte and str(deporte) not in ["nan", ""]: partes_rapport.append(f"Afinidad/Contexto: {deporte}")
    if estilo_visita and str(estilo_visita) not in ["nan", ""]: partes_rapport.append(f"Estilo: {estilo_visita}")
    if partes_rapport: contexto_rapport_str = " | ".join(partes_rapport)

# --- ADUANA VADEMÉCUM NICARAGUA 2026: NUNCA RETORNA MARCAS INEXISTENTES COMO DISFLAM ---
def es_gutis(nombre_prod):
    n_norm = normalizar_txt(nombre_prod)
    return any(normalizar_txt(g) in n_norm for g in PRODUCTOS_GUTIS)

def obtener_meta_mercado(mercado_val, es_ped=False):
    m_norm = normalizar_txt(mercado_val)
    # Homologación explícita de nombres de mercados regionales Close-Up hacia Vademécum Nicaragua 2026
    if "DISFLAM" in m_norm or "DALIVIUM" in m_norm or "DALIVIO" in m_norm:
        return MERCADOS_PRIORITARIOS["MR TALERDIN"] if es_ped else MERCADOS_PRIORITARIOS["MR DALIVIO"]
    if "CONRELAX" in m_norm or "CONFLEXIL" in m_norm:
        return MERCADOS_PRIORITARIOS["MR BIOTOS"] if es_ped else MERCADOS_PRIORITARIOS["MR CONFLEXIL"]

    for m_key, m_info in MERCADOS_PRIORITARIOS.items():
        base_key = normalizar_txt(m_key.replace("MR ", ""))
        if base_key in m_norm or any(normalizar_txt(k) in m_norm for k in m_info["keywords"]):
            if es_ped and not m_info.get("apto_pediatria", True):
                return MERCADOS_PRIORITARIOS["MR TALERDIN"]
            return m_info

    # Fallback blindado al Vademécum Oficial según especialidad (jamás usa el nombre crudo si no es de Nicaragua)
    return MERCADOS_PRIORITARIOS["MR TALERDIN"] if es_ped else MERCADOS_PRIORITARIOS["MR DALIVIO"]

def diagnosticar_escala_adopcion(pxs_gutis_m, pxs_tot_m, ms_gutis_m):
    if pxs_tot_m <= 0:
        return "1. No Consciente", "2. Consciente / 3. Prueba (2-5 Pxs)", "CONQUISTA", "Crear conciencia del perfil de paciente y lograr las primeras 3 recetas de prueba."
    if pxs_gutis_m == 0:
        return "2. Consciente (0% MS)", "3. Prueba (2 a 10 Pxs)", "CONQUISTA", f"Iniciar período de prueba en sus próximos 3 a 5 pacientes (hoy entrega {pxs_tot_m} Pxs a competencia)."
    if ms_gutis_m < 25.0 or (pxs_gutis_m <= 4 and ms_gutis_m < 45.0):
        return f"3. Prueba ({ms_gutis_m:.1f}% MS | {pxs_gutis_m} Pxs)", "4. Adopción (>25% a 50% MS)", "EXPANSION", "Agradecer recetas iniciales, validar experiencia positiva y expandir hacia el >25% de sus casos."
    if ms_gutis_m < 50.0:
        return f"4. Adopción ({ms_gutis_m:.1f}% MS | {pxs_gutis_m} Pxs)", "5. Lealtad (>50% MS)", "EXPANSION", "Reconocer su respaldo activo y migrar sutilmente el nicho que aún comparte con otra marca."
    return f"5. Lealtad ({ms_gutis_m:.1f}% MS | {pxs_gutis_m} Pxs)", "5. Lealtad (Blindaje & Puente)", "LEALTAD", "Agradecer su lealtad como prescriptor socio de Gutis, blindar presentaciones y apalancar el Puente hacia la 2da marca."

# --- RECONOCIMIENTO COGNITIVO DE MÉDICOS EN TEXTO LIBRE ---
def detectar_medico_en_texto(texto_usuario):
    t_norm = normalizar_txt(texto_usuario)
    palabras_ignorar = {
        "DR", "DRA", "DOCTOR", "DOCTORA", "MEDICO", "MEDICOS", "ANALIZA", "ANALIZAR", "COMO", "PARA",
        "GRANADA", "MASAYA", "CARAZO", "RIVAS", "CHONTALES", "BOACO", "MANAGUA", "NUEVA", "GUINEA",
        "PEDIATRIA", "PEDIATRAS", "GINECOLOGIA", "INTERNA", "GENERAL", "OTORRINO", "ORTOPEDIA",
        "GUTIS", "TALERDIN", "BIOTOS", "GASTROALIVIO", "DALIVIO", "MOMETZONA", "VENTILAR", "CLEMBROXIL",
        "VALERPAN", "CONFLEXIL", "RENOVART", "LABORATORIO", "COMPETENCIA", "COMPRADA", "COMPRADO",
        "PANEL", "VISITA", "PLAN", "TVP", "CONGRESO", "MUESTRAS", "FARMACIA", "TOP", "LOS", "LAS", "DEL", "POR",
        "TIENE", "COMPROMISO", "NOSOTROS", "MARCAS", "PERO", "ESTA", "COMPARTIENDO", "MUCHO", "RECETA", "OTROS", "CREES", "PASE"
    }
    tokens_usr = [w for w in re.split(r'[^A-Z0-9Ñ]+', t_norm) if len(w) >= 3 and w not in palabras_ignorar]
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
        coincidencias = sum(1 for tu in tokens_usr if tu in tokens_med or any(tm.startswith(tu) for tm in tokens_med if len(tu) >= 4))
        if coincidencias > max_coincidencias:
            max_coincidencias = coincidencias
            mejor_medico = med

    if max_coincidencias >= 2:
        return mejor_medico
    if max_coincidencias == 1:
        indicadores_persona = ["DR ", "DRA ", "DRA.", "DR.", "DOCTOR", "DOCTORA", "ANALIZA A", "ABORDO A", "ABORDAR A", "COMPRAD", "CASAD", "AMARR", "PIDE", "OBJECION", "VISITAR A", "COMPROMISO"]
        if any(ind in t_norm for ind in indicadores_persona):
            return mejor_medico
    return None

# --- EXTRACTOR COMPLETO DE EXPEDIENTE DE CUALQUIER MÉDICO ---
def extraer_dossier_medico(nombre_med):
    en_panel = False
    esp_m, ciu_m, cat_m = "ESPECIALISTA", "NICARAGUA", "S/C"
    if not df_panel.empty and "Médico" in df_panel.columns:
        sub_p = df_panel[df_panel["Médico"] == nombre_med]
        if not sub_p.empty:
            en_panel = True
            fila_p = sub_p.iloc[0]
            esp_m = str(fila_p.get("Especialidad", "ESPECIALISTA")).strip().upper()
            ciu_m = str(fila_p.get("CIUDAD", "NICARAGUA")).strip().upper()
            cat_m = str(fila_p.get("CATEGORIA", "S/C")).strip()

    es_ped_doc = "PEDIAT" in esp_m
    rx_m = df_productos[df_productos["Médico"] == nombre_med].copy() if not df_productos.empty else pd.DataFrame()
    if not rx_m.empty:
        rx_m["Es_Gutis"] = rx_m["NOMBRE_PRODUCTO"].apply(es_gutis)
        if not en_panel:
            col_e = next((c for c in rx_m.columns if "ESPEC" in c.upper()), None)
            col_c = next((c for c in rx_m.columns if c.upper() in ["CIUDAD", "DEPARTAMENTO", "ZONA"]), None)
            if col_e: esp_m = str(rx_m.iloc[0][col_e]).strip().upper(); es_ped_doc = "PEDIAT" in esp_m
            if col_c: ciu_m = str(rx_m.iloc[0][col_c]).strip().upper()
        if es_ped_doc:
            rx_m = rx_m[~rx_m["MERCADO"].apply(normalizar_txt).str.contains("GASTROALIVIO|CONFLEXIL|CONRELAX|DISFLAM|RENOVART|FEMGYL|NORGYLEN|ANSIOLIT|DEPAX|FELICITAT", na=False)].copy()

    col_p_mes = next((c for c in rx_m.columns if c.upper() == "PXS-MES"), None) if not rx_m.empty else None
    if not col_p_mes and not rx_m.empty: col_p_mes = next((c for c in rx_m.columns if "PXS" in c.upper()), None)
    col_p_ytd = next((c for c in rx_m.columns if c.upper() == "PXS-YTD"), None) if not rx_m.empty else None

    if not rx_m.empty and col_p_mes: rx_m[col_p_mes] = pd.to_numeric(rx_m[col_p_mes], errors='coerce').fillna(0)
    if not rx_m.empty and col_p_ytd: rx_m[col_p_ytd] = pd.to_numeric(rx_m[col_p_ytd], errors='coerce').fillna(0)

    mercados_doc = []
    pxs_mes_tot_doc, pxs_ytd_tot_doc, pxs_gut_doc, pxs_comp_doc, pxs_gut_ytd_doc = 0, 0, 0, 0, 0

    if not rx_m.empty and col_p_mes:
        pxs_mes_tot_doc = int(rx_m[col_p_mes].sum())
        pxs_ytd_tot_doc = int(rx_m[col_p_ytd].sum()) if col_p_ytd else 0
        pxs_gut_doc = int(rx_m[rx_m["Es_Gutis"]][col_p_mes].sum())
        pxs_gut_ytd_doc = int(rx_m[rx_m["Es_Gutis"]][col_p_ytd].sum()) if col_p_ytd else 0
        pxs_comp_doc = pxs_mes_tot_doc - pxs_gut_doc

        for m_nom, df_g in rx_m.groupby("MERCADO"):
            meta_i = obtener_meta_mercado(m_nom, es_ped=es_ped_doc)
            p_m = int(df_g[col_p_mes].sum())
            p_y = int(df_g[col_p_ytd].sum()) if col_p_ytd else 0
            p_gut = int(df_g[df_g["Es_Gutis"]][col_p_mes].sum())
            p_gut_y = int(df_g[df_g["Es_Gutis"]][col_p_ytd].sum()) if col_p_ytd else 0
            p_cmp = p_m - p_gut
            ms_g = (p_gut / p_m * 100) if p_m > 0 else ((p_gut_y / p_y * 100) if p_y > 0 else 0.0)
            if p_m <= 0 and p_y <= 0:
                continue
            df_g_ord = df_g.sort_values(by=[col_p_mes, col_p_ytd] if col_p_ytd else [col_p_mes], ascending=False)
            lid_row = df_g_ord.iloc[0]
            lid_nom = str(lid_row["NOMBRE_PRODUCTO"]).strip()
            lid_px = int(lid_row[col_p_mes])
            lid_ytd = int(lid_row[col_p_ytd]) if col_p_ytd else 0

            df_no_g = df_g_ord[~df_g_ord["Es_Gutis"]]
            if not df_no_g.empty:
                comp_row = df_no_g.iloc[0]
                comp_nom_m = str(comp_row["NOMBRE_PRODUCTO"]).strip()
                comp_px_m = int(comp_row[col_p_mes])
                comp_ytd_m = int(comp_row[col_p_ytd]) if col_p_ytd else 0
            else:
                comp_nom_m, comp_px_m, comp_ytd_m = "Sin competidor activo", 0, 0

            esc_act, esc_meta, modo_tac, obj_esc = diagnosticar_escala_adopcion(p_gut, p_m, ms_g)

            mercados_doc.append({
                "mercado": m_nom, "prioridad": meta_i["prioridad"], "categoria_mercado": meta_i["categoria_mercado"],
                "prod_gutis": meta_i["producto"], "lider_actual": lid_nom, "lider_pxs_mes": lid_px, "lider_pxs_ytd": lid_ytd,
                "comp_principal": comp_nom_m, "comp_pxs_mes": comp_px_m, "comp_pxs_ytd": comp_ytd_m,
                "lider_es_gutis": bool(lid_row["Es_Gutis"]), "pxs_mes": p_m, "pxs_ytd": p_y,
                "pxs_gutis": p_gut, "pxs_gutis_ytd": p_gut_y, "pxs_comp": p_cmp, "ms_gutis": ms_g,
                "escala_actual": esc_act, "escala_meta": esc_meta, "modo_tactico": modo_tac, "meta_info": meta_i
            })
        mercados_doc = sorted(mercados_doc, key=lambda x: (-x["pxs_mes"], x["prioridad"], -x["pxs_ytd"]))

    labs_doc = []
    if not df_labs.empty and "Médico" in df_labs.columns and "FABRICANTE" in df_labs.columns:
        sub_l = df_labs[(df_labs["Médico"] == nombre_med) & (~df_labs["FABRICANTE"].astype(str).str.upper().isin(["TOTAL", "NAN", ""]))].copy()
        if not sub_l.empty:
            c_ly = "Pxs-YTD" if "Pxs-YTD" in sub_l.columns else next((c for c in sub_l.columns if "YTD" in c.upper() and "PXS" in c.upper()), None)
            c_lm = "Pxs-MES" if "Pxs-MES" in sub_l.columns else next((c for c in sub_l.columns if "MES" in c.upper() and "PXS" in c.upper()), None)
            if c_ly:
                sub_l[c_ly] = pd.to_numeric(sub_l[c_ly], errors='coerce').fillna(0)
                agg_d = {c_ly: 'sum'}
                if c_lm:
                    sub_l[c_lm] = pd.to_numeric(sub_l[c_lm], errors='coerce').fillna(0)
                    agg_d[c_lm] = 'sum'
                rk_l = sub_l.groupby("FABRICANTE").agg(agg_d).reset_index().sort_values(by=c_ly, ascending=False)
                tot_ly = rk_l[c_ly].sum()
                for _, rl in rk_l.head(6).iterrows():
                    ms_l = (rl[c_ly] / tot_ly * 100) if tot_ly > 0 else 0.0
                    labs_doc.append({
                        "fabricante": str(rl["FABRICANTE"]).strip(),
                        "pxs_ytd": int(rl[c_ly]),
                        "pxs_mes": int(rl[c_lm]) if c_lm else 0,
                        "ms_ytd": round(ms_l, 2)
                    })

    farmacias_doc_str = "principales farmacias de la zona"
    sellout_ciudad_doc = 0.0
    if not df_ventas.empty and "DESCRIPCION_RUTA" in df_ventas.columns and ciu_m != "NICARAGUA":
        vz = df_ventas[df_ventas["DESCRIPCION_RUTA"].str.contains(re.escape(ciu_m), na=False)].copy()
        if not vz.empty:
            vz = vz[~vz["NOMBRE_CLIENTE_1"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
            rk_f = vz.groupby("NOMBRE_CLIENTE_1")["Monto Real"].sum().reset_index().sort_values(by="Monto Real", ascending=False)
            sellout_ciudad_doc = float(rk_f["Monto Real"].sum())
            if not rk_f.empty:
                farmacias_doc_str = ", ".join(rk_f["NOMBRE_CLIENTE_1"].head(3).tolist())

    return {
        "nombre": nombre_med, "en_panel": en_panel, "especialidad": esp_m, "es_pediatra": es_ped_doc,
        "ciudad": ciu_m, "categoria": cat_m,
        "pxs_mes_total": pxs_mes_tot_doc, "pxs_ytd_total": pxs_ytd_tot_doc,
        "pxs_gutis_mes": pxs_gut_doc, "pxs_gutis_ytd": pxs_gut_ytd_doc, "pxs_comp_mes": pxs_comp_doc,
        "mercados": mercados_doc, "labs": labs_doc,
        "farmacias_aliadas": farmacias_doc_str, "sellout_zona": sellout_ciudad_doc
    }

# --- LLAMADA API GEMINI ---
def llamar_gemini(prompt_text, max_tok=4096):
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key: return None
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt_text}]}], "generationConfig": {"maxOutputTokens": max_tok, "temperature": 0.2}}
    modelos_a_probar = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.5-pro"]
    try:
        r_list = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}", timeout=4)
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
            res = requests.post(url_p, headers=headers, json=payload, timeout=18)
            if res.status_code == 200:
                cands = res.json().get('candidates', [])
                if cands and 'content' in cands[0] and 'parts' in cands[0]['content']:
                    return cands[0]['content']['parts'][0].get('text', '')
        except: continue
    return None

# --- MOTOR COGNITIVO CONVERSACIONAL DE CHIRA ---
def construir_respuesta_cognitiva_medico(dossier, pregunta_usuario):
    t_norm = normalizar_txt(pregunta_usuario)
    nom = dossier["nombre"]
    esp = dossier["especialidad"]
    es_ped_d = dossier["es_pediatra"]
    ciu = dossier["ciudad"]
    cat = dossier["categoria"]
    farmacias = dossier["farmacias_aliadas"]

    ms_global_mes = (dossier["pxs_gutis_mes"] / dossier["pxs_mes_total"] * 100) if dossier["pxs_mes_total"] > 0 else 0.0

    mercados_mencionados = []
    for m_item in dossier["mercados"]:
        p_norm = normalizar_txt(m_item["prod_gutis"].split()[0])
        m_clean = normalizar_txt(m_item["mercado"].replace("MR ", ""))
        if p_norm in t_norm or m_clean in t_norm or any(normalizar_txt(k) in t_norm for k in m_item["meta_info"]["keywords"]):
            mercados_mencionados.append(m_item)

    mercados_foco = mercados_mencionados if mercados_mencionados else dossier["mercados"][:5]

    if mercados_foco:
        m1 = mercados_foco[0]
        # Buscar como M2 un mercado donde la competencia tenga volumen (para un puente real)
        candidatos_puente = [m for m in dossier["mercados"] if m["prod_gutis"] != m1["prod_gutis"] and m["pxs_comp"] > 0]
        m2 = candidatos_puente[0] if candidatos_puente else (mercados_foco[1] if len(mercados_foco) > 1 else None)
    else:
        meta_fb = obtener_meta_mercado("MR TALERDIN" if es_ped_d else "MR GASTROALIVIO", es_ped=es_ped_d)
        m1 = {
            "mercado": "MR PRINCIPAL", "prioridad": 1, "categoria_mercado": "Prioridad 1 (Core)",
            "prod_gutis": meta_fb["producto"], "lider_actual": "Competencia",
            "lider_pxs_mes": 0, "lider_pxs_ytd": 0, "comp_principal": "Competencia", "comp_pxs_mes": 0, "comp_pxs_ytd": 0,
            "lider_es_gutis": False, "pxs_mes": 0, "pxs_ytd": 0, "pxs_gutis": 0, "pxs_gutis_ytd": 0,
            "pxs_comp": 0, "ms_gutis": 0.0, "escala_actual": "2. Consciente", "escala_meta": "3. Prueba", "modo_tactico": "CONQUISTA", "meta_info": meta_fb
        }
        m2 = None

    prod1, comp1, meta1 = m1["prod_gutis"], m1["comp_principal"], m1["meta_info"]
    paciente_perfil_1 = meta1.get("paciente_meta_ped", meta1["paciente_meta"]) if es_ped_d else meta1["paciente_meta"]
    prod2 = m2["prod_gutis"] if m2 else ("Biotos Inmune / Clembroxil Compuesto" if es_ped_d else "Conflexil Plus Shot / Dalivio")

    labs_txt = " | ".join([f"**#{i+1} {l['fabricante']}** (`{l['pxs_ytd']} Pxs YTD` - {l['ms_ytd']}%)" for i, l in enumerate(dossier["labs"][:5])]) if dossier["labs"] else "Sin desglose de fabricantes"
    
    desglose_mercados_foco = "\n".join([
        f"* **{m['prod_gutis']} (`{m['mercado']}` — Escalón: `{m['escala_actual']}`):** Mes `{m['pxs_mes']} Pxs` (🔷 **Gutis:** `{m['pxs_gutis']} Pxs` [{m['ms_gutis']:.1f}% MS] vs. ⚔️ **Rival No-Gutis:** **`{m['comp_principal']}`** con `{m['comp_pxs_mes']} Mes` / `{m['comp_pxs_ytd']} YTD`)."
        for m in mercados_foco
    ]) if mercados_foco else "* _Sin registros en los mercados consultados._"

    es_dilucion_compromiso_gutis = (
        any(k in t_norm for k in ["COMPARTIENDO", "COMPARTE", "DILUY", "DIVID", "CON NOSOTROS", "CON GUTIS", "QUE CREES QUE PASE", "QUE PASA", "POR QUE RECETA OTROS", "FUGA"])
        and not any(k in t_norm for k in ["COMPRADA POR", "COMPRADO POR", "CASADA CON MEGALABS"])
    )
    es_comprado_competencia = any(k in t_norm for k in ["COMPRAD", "AMARRAD", "CASAD", "FIDELIZAD", "NO SUELTA", "SOLO RECETA A"]) and not es_dilucion_compromiso_gutis
    es_pedido_quid_pro_quo = any(k in t_norm for k in ["PIDE", "PEDIR", "PIDIO", "A CAMBIO", "CONGRESO", "INSCRIPCION", "MUESTRA", "REGALO", "APOYO", "PATROCINIO", "CONDICION", "TRANSACCIONAL"])
    es_objecion_precio_esceptico = any(k in t_norm for k in ["PRECIO", "CARO", "COSTO", "ECONOMICO", "GENERICO", "ESCEPTIC", "BIOEQUIVALEN", "ESTUDIO", "DUDA", "NO CREE", "IGUALES", "OBJECION"])

    if es_dilucion_compromiso_gutis:
        return f"""### 🔍 Diagnóstico Consultivo: ¿Por qué el Dr(a). {nom} comparte la receta teniendo compromiso con Gutis?

En Close-Up, el/la **Dr(a). {nom}** ({esp}, Cat {cat}, {ciu}) genera **{dossier['pxs_mes_total']} Pxs-MES** (`{dossier['pxs_ytd_total']} Pxs-YTD`), de los cuales **Gutis recibe `{dossier['pxs_gutis_mes']} Pxs-MES` ({ms_global_mes:.1f}% MS)** y **`{dossier['pxs_comp_mes']} Pxs-MES` se desvían a otros laboratorios**.

#### 🧠 Las 3 Causas Tácticas de la Dilución:
1. **Cumplimiento Fraccionado:** Al tener compromiso en varias marcas simultáneamente, el médico siente que dándote **{dossier['pxs_gutis_mes']} recetas globales** ya cumplió su palabra, quedándose en **Adopción Parcial** en lugar de **Lealtad (>50%)**.
2. **Radiografía Marca por Marca (Con quién nos comparte la receta):**
{desglose_mercados_foco}
3. **Presión Competitiva en su Recetario:** Casas rivales activas: {labs_txt}.

#### ♟️ Abordaje Sutil TVP (Agradecer Primero $\rightarrow$ Aislar Nicho $\rightarrow$ Migrar):
* **1. Apertura de Reconocimiento (Nunca reclamar):**  
  > *«Doctor(a) {nom}, quiero iniciar agradeciéndole su respaldo constante a nuestro portafolio en {ciu}; gracias a su confianza decenas de pacientes están recibiendo formulaciones libres de alcohol y de alta pureza.»*
* **2. Sondeo Sutil de Segmentación (Unidad 4):**  
  > *«Precisamente dando seguimiento a la excelente respuesta que ha tenido con **{prod1}**, noté que para cierto grupo de pacientes a veces alterna el esquema con `{comp1}`. Al **comparar** ambos perfiles en su consulta de **{esp}**, ¿en qué cuadro específico siente que aún prefiere usar la otra opción?»*
* **3. Cierre de Consolidación de Lealtad:**  
  > *«Doctor(a), ya que usted conoce de primera mano la seguridad de **{prod1}** (*{meta1['caracteristica'].lower()}*), consolidemos también ese grupo de pacientes bajo un solo estándar de calidad, con disponibilidad total asegurada en **{farmacias}**. ¿Le parece bien?»*
"""
    elif es_comprado_competencia:
        return f"""### 🔒 Estrategia de Flanqueo TVP: Dr(a). {nom} ({esp} | {ciu})

#### 📊 Estado de Cartera ({dossier['pxs_mes_total']} Pxs-MES | {dossier['pxs_ytd_total']} YTD):
{desglose_mercados_foco}

#### 🗣️ Guion de Flanqueo por Nicho Clínico (Unidad 7 — Sin chocar con su laboratorio actual):
* **1. Desarme Psicológico:** *«Doctor(a) {nom}, conozco los buenos resultados que tiene con su esquema habitual y mi intención hoy no es cambiar lo que ya le funciona en su paciente general.»*
* **2. Sondeo de Grieta Clínica:** *«Solo quiero consultarle: cuando recibe ese subgrupo específico de **{meta1.get('nicho_flanqueo', paciente_perfil_1).lower()}**, ¿cómo evita que el paciente rechace o abandone el tratamiento?»*
* **3. Cierre de Rescate + Puente a `{prod2}`:** *«Para esos casos puntuales cuente con **{prod1}** (*{meta1['caracteristica'].lower()}*) en sus próximos **2 a 3 pacientes de rescate**, y apóyese también en **{prod2}** con inventario listo en **{farmacias}**.»*
"""
    elif es_pedido_quid_pro_quo:
        return f"""### 💼 Negociación Consultiva (Condicionalidad Invertida): Dr(a). {nom}

#### 📊 Auditoría de Retorno (ROI):
* **Volumen Actual:** `{dossier['pxs_mes_total']} Pxs-MES` (`{dossier['pxs_ytd_total']} YTD`) — **Gutis:** `{dossier['pxs_gutis_mes']} Pxs ({ms_global_mes:.1f}%)` | **Fuga a Competencia:** `{dossier['pxs_comp_mes']} Pxs`.
{desglose_mercados_foco}

#### 🗣️ Guion con Escudo de Dirección Médica:
> *«Doctor(a) {nom}, cuente conmigo para gestionar este apoyo; su consulta en {ciu} es prioritaria para Gutis. Para que Dirección Médica me apruebe formalmente el patrocinio este ciclo, el sistema me exige respaldarlo subiendo nuestra cuota actual de **{dossier['pxs_gutis_mes']} recetas mensuales** mediante la migración de al menos **12 a 15 pacientes** que hoy van a `{comp1}` hacia **{prod1}** y **{prod2}**, reflejados en **{farmacias}**. Si iniciamos esta semana con esos pacientes, yo presento su expediente con números en verde ante gerencia. ¿Arrancamos hoy?»*
"""
    else:
        # Adaptar según si el médico YA es Leal en su producto #1 o si es de Conquista
        if m1["modo_tactico"] == "LEALTAD":
            guion_adaptado = f"""#### 🛡️ Estrategia de Socio Leal (Escalón 5: `{m1['escala_actual']}` en `{prod1}`)
* **Análisis Táctico:** ¡Atención! El/La Dr(a). {nom} **ya es leal a `{prod1}` ({m1['ms_gutis']:.1f}% de cuota)**. Sería un error ir a venderle `{prod1}` desde cero. Hoy aplicamos **Agradecimiento + Blindaje Sutil + Puente Fuerte hacia `{prod2}`**.
* **1. Apertura de Agradecimiento y Valoración:**  
  > *«Doctor(a) {nom}, hoy quiero iniciar agradeciéndole su confianza y lealtad hacia **{prod1}**; usted es un referente clave para nuestro portafolio en {ciu} en el cuidado de **{paciente_perfil_1.lower()}**.»*
* **2. Sondeo de Validación y Blindaje Sutil:**  
  > *«En estos decenas de pacientes que ya trata con **{prod1}**, ¿qué comentarios le han compartido las familias sobre la tolerabilidad y dosificación de nuestras presentaciones (*{meta1['caracteristica'].lower()}*)? Recuerde que ya blindamos el stock completo en **{farmacias}** para que no le cambien ni una sola receta.»*
* **3. El Verdadero Objetivo de Hoy — Puente de Autoridad hacia `{prod2}`:**  
  > *«Y precisamente apoyándome en esa excelente experiencia que usted ya tiene con la calidad galénica de Gutis en **{prod1}**, quiero pedirle su respaldo para extender esa misma seguridad hacia **{prod2}** en sus pacientes donde aún se prescribe `{m2['comp_principal'] if m2 else 'la competencia'}`. ¿Iniciamos esta semana con sus próximos 3 a 5 casos en **{prod2}**?»*"""
        else:
            guion_adaptado = f"""#### ⚔️ Estrategia de {m1['modo_tactico'].title()} TVP (Escalón Actual: `{m1['escala_actual']}` $\rightarrow$ Meta: `{m1['escala_meta']}`)
* **1. Apertura Centrada en el Paciente ({esp}):**  
  > *«Doctor(a) {nom}, quería proponerle revisar brevemente cómo optimizar la adherencia y rapidez de respuesta en **{paciente_perfil_1.lower()}**. ¿Le parece bien?»*
* **2. Sondeo de Valor Mutuo:**  
  > *«En los casos donde actualmente se indica `{comp1}`, al **evaluar** la evolución en los primeros días, ¿qué considera prioritario mejorar en tolerabilidad y eficacia?»*
* **3. Apoyo Love Brand (`{prod1}`):**  
  > *«Con **{prod1}** usted cuenta con **{meta1['caracteristica'].lower()}**, logrando **{meta1['beneficio'].lower()}**.»*
* **4. Cierre Bilateral + Puente a `{prod2}`:**  
  > *«¿Lo ponemos en marcha en sus próximos 3 a 5 pacientes esta semana con stock garantizado en **{farmacias}**? Y como puente clínico para su consulta de **{esp}**, recuerde que también cuenta con **{prod2}**.»*"""

        return f"""### 🧬 Análisis Estratégico & Plan TVP: Dr(a). {nom}
**Especialidad:** `{esp}` | **Categoría:** `{cat}` | **Territorio:** `{ciu}` | **Volumen:** `{dossier['pxs_mes_total']} Pxs-MES` (`{dossier['pxs_ytd_total']} YTD`) — **Gutis:** `{dossier['pxs_gutis_mes']} Pxs ({ms_global_mes:.1f}%)` vs. **Competencia:** `{dossier['pxs_comp_mes']} Pxs`

#### 📊 1. Radiografía por Marca (Vademécum Nicaragua 2026):
{desglose_mercados_foco}
* **Ranking de Laboratorios en su Recetario:** {labs_txt}

{guion_adaptado}
"""

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

    df_rx_c = df_productos.copy() if not df_productos.empty else pd.DataFrame()
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

# --- PROCESAMIENTO DEL MÉDICO ACTIVO EN BARRA LATERAL (FILTRADO POR ESPECIALIDAD Y VADEMÉCUM) ---
rx_clean = df_productos[df_productos["Médico"] == medico_sel].copy() if not df_productos.empty else pd.DataFrame()
if not rx_clean.empty:
    rx_clean["Es_Gutis"] = rx_clean["NOMBRE_PRODUCTO"].apply(es_gutis)
    if es_pediatra:
        # Excluir mercados exclusivos de adultos en pediatría (Gastroalivio, Conflexil, Renovart, Salud Femenina, Neurociencias, Disflam)
        rx_clean = rx_clean[~rx_clean["MERCADO"].apply(normalizar_txt).str.contains("GASTROALIVIO|CONFLEXIL|CONRELAX|DISFLAM|RENOVART|FEMGYL|NORGYLEN|ANSIOLIT|DEPAX|FELICITAT", na=False)].copy()
    rx_clean["Meta_Mercado"] = rx_clean["MERCADO"].apply(lambda m: obtener_meta_mercado(m, es_ped=es_pediatra))

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
        meta = obtener_meta_mercado(m_nom, es_ped=es_pediatra)
        prod_gutis_esperado = meta["producto"]
        prio_num = meta["prioridad"]
        cat_merc_txt = meta["categoria_mercado"]

        pxs_tot_m = int(df_m[col_pxs].sum()) if col_pxs else 0
        pxs_ytd_m = int(df_m[col_pxs_ytd_prod].sum()) if col_pxs_ytd_prod else 0
        pxs_gut_m = int(df_m[df_m["Es_Gutis"]][col_pxs].sum()) if col_pxs else 0
        pxs_gut_ytd_m = int(df_m[df_m["Es_Gutis"]][col_pxs_ytd_prod].sum()) if col_pxs_ytd_prod else 0
        pxs_comp_m = pxs_tot_m - pxs_gut_m
        ms_gut_m = (pxs_gut_m / pxs_tot_m * 100) if pxs_tot_m > 0 else ((pxs_gut_ytd_m / pxs_ytd_m * 100) if pxs_ytd_m > 0 else 0.0)

        df_m_ord = df_m.sort_values(by=[col_pxs, col_pxs_ytd_prod] if (col_pxs and col_pxs_ytd_prod) else ([col_pxs] if col_pxs else [col_mes]), ascending=False)
        lider = df_m_ord.iloc[0]
        lider_nombre = str(lider["NOMBRE_PRODUCTO"]).strip()
        lider_es_gutis = bool(lider["Es_Gutis"])
        lider_ms = (float(lider[col_mes]) * 100) if col_mes else 0.0

        # Identificar SIEMPRE al rival No-Gutis número 1 del mercado para no atacar a nuestra propia marca
        df_rivales = df_m_ord[~df_m_ord["Es_Gutis"]]
        if not df_rivales.empty:
            rival_row = df_rivales.iloc[0]
            rival_nombre = str(rival_row["NOMBRE_PRODUCTO"]).strip()
            rival_pxs_mes = int(rival_row[col_pxs]) if col_pxs else 0
            rival_pxs_ytd = int(rival_row[col_pxs_ytd_prod]) if col_pxs_ytd_prod else 0
        else:
            rival_nombre, rival_pxs_mes, rival_pxs_ytd = "Competencia menor", 0, 0

        escala_act, escala_meta, modo_tactico_m, obj_escala = diagnosticar_escala_adopcion(pxs_gut_m, pxs_tot_m, ms_gut_m)

        if pxs_tot_m > 0 or pxs_ytd_m > 0 or lider_ms > 0:
            opciones_mercados_medico.append({
                "mercado": m_nom, "prioridad": prio_num, "categoria_mercado": cat_merc_txt,
                "lider_actual": lider_nombre, "lider_es_gutis": lider_es_gutis,
                "rival_principal": rival_nombre, "rival_pxs_mes": rival_pxs_mes, "rival_pxs_ytd": rival_pxs_ytd,
                "prod_gutis": prod_gutis_esperado,
                "pxs_totales": pxs_tot_m, "pxs_ytd": pxs_ytd_m, "pxs_gutis": pxs_gut_m, "pxs_gutis_ytd": pxs_gut_ytd_m, "pxs_comp": pxs_comp_m,
                "ms_lider": lider_ms, "ms_gutis": ms_gut_m, "escala_actual": escala_act,
                "escala_meta": escala_meta, "modo_tactico": modo_tactico_m, "objetivo_escala": obj_escala, "meta_info": meta
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
        if item_m["modo_tactico"] == "LEALTAD" or item_m["lider_es_gutis"]:
            cards_ataque_html += f"""<div style="background: linear-gradient(180deg, #ecfdf5 0%, #ffffff 100%); border: 1px solid #a7f3d0; border-top: 4px solid #059669; border-radius: 6px; padding: 10px; min-width: 205px; flex: 1 1 calc(25% - 12px);"><div style="display:flex; justify-content:space-between; align-items:center;"><span style="font-size: 0.65rem; font-weight: 800; color: #065f46;">{item_m['prod_gutis'].upper()}</span><span style="background:{color_p}; color:white; font-size:0.6rem; padding:2px 6px; border-radius:4px; font-weight:700;">{badge_p}</span></div><div style="font-size: 0.84rem; color: #0f172a; margin: 3px 0;">Líder: <b style="color:#047857;">{item_m['prod_gutis']} ({item_m['ms_gutis']:.0f}%)</b></div><div style="font-size: 0.72rem; color: #475569;">Mes: <b>{item_m['pxs_totales']}</b> (Gutis: {item_m['pxs_gutis']} | Comp: {item_m['pxs_comp']})</div><div style="font-size: 0.69rem; color: #334155; margin-top:2px;">Escala: <b>{item_m['escala_actual'].split('(')[0]}</b></div><div style="margin-top: 4px; font-size: 0.72rem; font-weight: 800; color: #047857; border-top: 1px dashed #cbd5e1; padding-top: 3px;">🛡️ Agradecer, Blindar & Puente</div></div>"""
        else:
            cards_ataque_html += f"""<div style="background: linear-gradient(180deg, #fff1f2 0%, #ffffff 100%); border: 1px solid #fecdd3; border-top: 4px solid #e11d48; border-radius: 6px; padding: 10px; min-width: 205px; flex: 1 1 calc(25% - 12px);"><div style="display:flex; justify-content:space-between; align-items:center;"><span style="font-size: 0.65rem; font-weight: 800; color: #9f1239;">{item_m['prod_gutis'].upper()}</span><span style="background:{color_p}; color:white; font-size:0.6rem; padding:2px 6px; border-radius:4px; font-weight:700;">{badge_p}</span></div><div style="font-size: 0.84rem; color: #0f172a; margin: 3px 0;">Rival: <b style="color:#be123c;">{item_m['rival_principal'][:15]}</b></div><div style="font-size: 0.72rem; color: #475569;">Mes: <b>{item_m['pxs_totales']}</b> (Comp: {item_m['pxs_comp']}) | YTD: {item_m['pxs_ytd']}</div><div style="font-size: 0.69rem; color: #334155; margin-top:2px;">Escala: <b>{item_m['escala_actual'].split('(')[0]}</b></div><div style="margin-top: 4px; font-size: 0.72rem; font-weight: 800; color: #047857; border-top: 1px dashed #cbd5e1; padding-top: 3px;">⚔️ Conquistar con {item_m['prod_gutis']}</div></div>"""

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

# --- TICKER SUPERIOR COMPACTO ---
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
        <div class='ticker-label'>♟️ FOCO PRIMARIO ({prod_gutis_ataque_oficial.upper()})</div>
        <div class='ticker-val'>{producto_ataque_str[:16]}</div>
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
    "♟️ Núcleo III: Copiloto Cognitivo Chira & CRM"
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
# NÚCLEO II: CONSULTORIO 360° & CANVAS TVP ADAPTATIVO SEGÚN ESCALA DE ADOPCIÓN
# ==============================================================================
with nucleo_micro:
    if cards_ataque_html:
        st.components.v1.html(f"""<div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-left: 5px solid #1e3a8a; padding: 12px; margin-bottom: 10px; border-radius: 8px;"><div style="font-size: 0.78rem; font-weight: 800; color: #0f172a; margin-bottom: 8px; letter-spacing: 0.5px;">💠 [MAPA DE MERCADOS ACTIVOS DEL ESPECIALISTA (VADEMÉCUM NICARAGUA 2026) — {num_mercados} MERCADOS AUDITADOS]</div><div style="display: flex; flex-wrap: wrap; gap: 10px;">{cards_ataque_html}</div></div>""", height=190, scrolling=True)

    col_canvas, col_micro_datos = st.columns([1.35, 1.05])

    with col_canvas:
        st.markdown("##### ♟️ [CANVAS TVP DE 4 CUADRANTES — INTELIGENCIA ADAPTATIVA SEGÚN ESCALA DE ADOPCIÓN]")
        with st.container(border=True):
            if opciones_mercados_medico:
                etiquetas_m = [
                    f"[{'🛡️ LEALTAD' if o['modo_tactico']=='LEALTAD' else ('🔍 EXPANSIÓN' if o['modo_tactico']=='EXPANSION' else '⚔️ CONQUISTA')}] {o['prod_gutis']} ({o['pxs_totales']} Pxs | Gutis: {o['ms_gutis']:.0f}%)"
                    for o in opciones_mercados_medico
                ]
                # Selección inteligente del índice de 2da Posición (Puente): buscar el primer mercado donde la competencia nos gane
                idx_puente_sugerido = 1 if len(opciones_mercados_medico) > 1 else 0
                for idx_cand, o_cand in enumerate(opciones_mercados_medico):
                    if idx_cand > 0 and o_cand["modo_tactico"] != "LEALTAD" and o_cand["pxs_comp"] > 0:
                        idx_puente_sugerido = idx_cand
                        break

                cm1, cm2, cm3 = st.columns(3)
                with cm1: idx_m1 = st.selectbox("🥇 1ra Posición (Foco / Ancla):", range(len(etiquetas_m)), index=0, format_func=lambda i: etiquetas_m[i])
                with cm2: idx_m2 = st.selectbox("🥈 2da Posición (Puente de Crecimiento):", range(len(etiquetas_m)), index=idx_puente_sugerido, format_func=lambda i: etiquetas_m[i])
                with cm3: idx_m3 = st.selectbox("🥉 3ra Posición (Recordación):", range(len(etiquetas_m)), index=(2 if len(etiquetas_m)>2 else idx_puente_sugerido), format_func=lambda i: etiquetas_m[i])
                m_primario = opciones_mercados_medico[idx_m1]
                m_secundario = opciones_mercados_medico[idx_m2] if len(opciones_mercados_medico) > 1 else None
                m_terciario = opciones_mercados_medico[idx_m3] if len(opciones_mercados_medico) > 2 else None
            else:
                meta_def = obtener_meta_mercado("MR TALERDIN" if es_pediatra else "MR GASTROALIVIO", es_ped=es_pediatra)
                m_primario = {
                    "mercado": "MR TALERDIN" if es_pediatra else "MR GASTROALIVIO", "prioridad": 1, "categoria_mercado": "Prioridad 1 (Core)",
                    "lider_actual": producto_ataque_str, "lider_es_gutis": False, "rival_principal": producto_ataque_str, "rival_pxs_mes": comp_pxs_medico, "rival_pxs_ytd": 0,
                    "prod_gutis": prod_gutis_ataque_oficial,
                    "pxs_totales": total_pxs_medico, "pxs_ytd": total_ytd_medico_global, "pxs_gutis": gutis_pxs_medico, "pxs_gutis_ytd": 0, "pxs_comp": comp_pxs_medico,
                    "ms_lider": share_lider, "ms_gutis": 0.0, "escala_actual": "2. Consciente (0% MS)", "escala_meta": "3. Prueba (2 a 10 Pxs)",
                    "modo_tactico": "CONQUISTA", "objetivo_escala": "Iniciar período de prueba.", "meta_info": meta_def
                }
                m_secundario, m_terciario = None, None

            ct1, ct2 = st.columns(2)
            with ct1: tipo_cita_sel = st.selectbox("🚪 Contexto de Abordaje:", ["Visita con cita previa", "Visita sin cita (Improvisto)", "Encuentro casual (Pasillo)"])
            with ct2: nec_detras_sel = st.selectbox("🧠 Resorte Psicológico (NdN):", ["Desempeño (Eficacia y adherencia)", "Imagen (Prestigio clínico)", "Finanzas (Costo-beneficio)"])

        meta1 = m_primario["meta_info"]
        prod1 = m_primario["prod_gutis"]
        rival1 = m_primario["rival_principal"] if m_primario["rival_principal"] != "Sin competidor activo" else "la competencia"
        modo_tac1 = m_primario["modo_tactico"]
        perfil_paciente_adaptado = meta1.get("paciente_meta_ped", meta1["paciente_meta"]) if es_pediatra else meta1["paciente_meta"]

        if m_secundario and m_secundario["prod_gutis"] != prod1:
            prod2 = m_secundario["prod_gutis"]
            benef2 = m_secundario["meta_info"]["beneficio"]
            rival2 = m_secundario["rival_principal"]
            pxs_comp2 = m_secundario["pxs_comp"]
        else:
            prod2 = "Biotos Inmune / Clembroxil Compuesto" if es_pediatra else "Conflexil Plus Shot / Dalivio"
            benef2 = "Cuádruple acción respiratoria sin alcohol" if es_pediatra else "Triple acción analgésica, antiinflamatoria y miorrelajante"
            rival2 = "marcas tradicionales"
            pxs_comp2 = 0

        if m_terciario and m_terciario["prod_gutis"] not in [prod1, prod2]:
            prod3 = m_terciario["prod_gutis"]
        else:
            prod3 = "Ventilar / Mometzona" if es_pediatra else "Valerpan / Renovart Platinum"

        # LÓGICA TÁCTICA DIFERENCIADA EN EL CANVAS DE 4 CUADRANTES SEGÚN ESCALA DE ADOPCIÓN
        if modo_tac1 == "LEALTAD":
            q1_html = f"""
                • <b>Escala Actual:</b> <span style='color:#047857; font-weight:800;'>{m_primario['escala_actual']} (Socio Leal)</span><br>
                • <b>Rol de {prod1}:</b> <b>Ancla de Reconocimiento y Blindaje</b>.<br>
                • <b>Meta SMART Hoy:</b> Blindar sus <b>{m_primario['pxs_gutis']} Pxs actuales</b> de <b>{prod1}</b> ({'capturando el remanente de ' + str(m_primario['pxs_comp']) + ' Pxs que va a ' + rival1 if m_primario['pxs_comp']>0 else '100% fidelizado'}) y usar su confianza para lograr <b>3-5 recetas nuevas en {prod2}</b>.<br>
                • <b>Plan B:</b> Asegurar rotación en <b>{top_farmacias_ciudad_str.split(',')[0]}</b>.
            """
            q2_html = f"""
                • <b>Regla TVP en Lealtad:</b> Prohibido vender de cero lo que ya receta; <b>agradecer y validar</b>.<br>
                • <b>Apertura de Reconocimiento:</b> Agradecer su liderazgo prescriptivo en <i>{perfil_paciente_adaptado[:58]}...</i><br>
                • <b>Pregunta de Validación:</b> <i>«¿Cómo han evolucionado sus pacientes tratados con nuestras presentaciones sin alcohol este mes?»</i><br>
                • <b>Acuerdo:</b> <i>«Permítame compartirle una actualización rápida y revisar un segundo grupo de pacientes.»</i>
            """
            q3_html = f"""
                • <b>Refuerzo Sutil ({prod1}):</b> Recordar dosificación y ventaja exclusiva ({meta1['caracteristica'][:75]}...).<br>
                • <b>Blindaje en {nec_detras_sel.split('(')[0].strip()}:</b> {meta1['beneficio']}<br>
                • <b>Love Brand de Socio:</b> <i>«Gracias a su confianza, decenas de pacientes en {ciudad} reciben tecnología limpia de Gutis.»</i>
            """
            q4_html = f"""
                • <b>Cierre en {prod1}:</b> Agradecer su preferencia #1 y garantizar stock total en <b>{top_farmacias_ciudad_str.split(',')[0]}</b>.<br>
                • <b>🔥 PUENTE PROTAGONISTA ({prod1} ➔ {prod2}):</b> <i>«Apoyándome en esa confianza que ya nos brinda con {prod1}, extendamos esa misma calidad hacia <b>{prod2}</b> ({benef2[:50]}...) en los casos donde aún usa {rival2}.»</i><br>
                • <b>Recordación 3ra ({prod3}):</b> Disponible en su farmacia aliada.
            """
        elif modo_tac1 == "EXPANSION":
            q1_html = f"""
                • <b>Escala Actual:</b> <span style='color:#0284c7; font-weight:800;'>{m_primario['escala_actual']} (Comparte Receta)</span><br>
                • <b>Escalón Meta Hoy:</b> <span style='color:#047857; font-weight:700;'>{m_primario['escala_meta']}</span><br>
                • <b>Meta SMART:</b> Agradecer sus <b>{m_primario['pxs_gutis']} Pxs actuales</b> en <b>{prod1}</b> y migrar <b>4 a 6 pacientes</b> de los <b>{m_primario['pxs_comp']} Pxs</b> que aún entrega a <code>{rival1}</code>.<br>
                • <b>Plan B:</b> Migrar el subgrupo de pacientes más sensibles hacia {prod1}.
            """
            q2_html = f"""
                • <b>Regla TVP en Expansión:</b> Abrir explorando su experiencia positiva con los pacientes que ya trató.<br>
                • <b>Agenda ({especialidad}):</b> Analizar evolución en <i>{perfil_paciente_adaptado[:58]}...</i><br>
                • <b>Pregunta Sutil:</b> <i>«En los casos donde ya prescribió nuestros esquemas frente a {rival1}, ¿qué diferencias notó en el apego al tratamiento?»</i><br>
                • <b>Acuerdo:</b> Confirmar agenda de 2 minutos.
            """
            q3_html = f"""
                • <b>Sondeo de Migración:</b> <i>«¿En qué perfil específico de paciente siente que aún alterna con {rival1}?»</i><br>
                • <b>Ventaja Diferencial ({prod1}):</b> {meta1['caracteristica']}<br>
                • <b>Beneficio ({nec_detras_sel.split('(')[0].strip()}):</b> {meta1['beneficio']}<br>
                • <b>Love Brand:</b> <i>«{meta1['love_brand']}»</i>
            """
            q4_html = f"""
                • <b>Pido al Médico:</b> Consolidar a <b>{prod1}</b> como primera elección en ese segmento que aún compartía con <code>{rival1}</code>.<br>
                • <b>Mi Compromiso:</b> Blindar stock hoy en <b>{top_farmacias_ciudad_str.split(',')[0]}</b>.<br>
                • <b>Puente a 2da Posición ({prod2}):</b> <i>«Y siguiendo con seguridad clínica, cuente con <b>{prod2}</b> ({benef2[:42]}...).»</i><br>
                • <b>Recordación 3ra ({prod3}):</b> Respaldo en farmacias aledañas.
            """
        else:
            q1_html = f"""
                • <b>Escala Actual:</b> <span style='color:#be123c; font-weight:700;'>{m_primario['escala_actual']}</span><br>
                • <b>Escalón Meta Hoy:</b> <span style='color:#047857; font-weight:700;'>{m_primario['escala_meta']}</span><br>
                • <b>Meta SMART:</b> Capturar los primeros <b>3 a 5 pacientes</b> de los <b>{m_primario['pxs_comp']} Pxs</b> que hoy entrega a <code>{rival1}</code> hacia <b>{prod1}</b> en 7 días.<br>
                • <b>Plan B (Respaldo):</b> Flanqueo en 2 pacientes de rescate con muestra de inicio.
            """
            q2_html = f"""
                • <b>Regla TVP:</b> Entrar con agenda centrada en el paciente de <b>{especialidad}</b> (sin mencionar marca).<br>
                • <b>Agenda ({tipo_cita_sel.split('(')[0].strip()}):</b> Revisar adherencia en <i>{perfil_paciente_adaptado[:58]}...</i><br>
                • <b>Disruptiva:</b> <i>«¿Qué impacto tendría en su consulta eliminar hoy el abandono al 2do día en estos pacientes?»</i><br>
                • <b>Acuerdo:</b> <i>«¿Le parece bien revisarlo en 2 minutos?»</i>
            """
            q3_html = f"""
                • <b>Sondeo Valor Mutuo:</b> <i>«Al <b>comparar</b> y <b>evaluar</b> la respuesta con {rival1}, ¿qué prioriza mejorar?»</i><br>
                • <b>Ventaja ({prod1}):</b> {meta1['caracteristica']}<br>
                • <b>Beneficio ({nec_detras_sel.split('(')[0].strip()}):</b> {meta1['beneficio']}<br>
                • <b>Love Brand:</b> <i>«{meta1['love_brand']}»</i>
            """
            q4_html = f"""
                • <b>Pido al Médico:</b> Iniciar <b>{prod1}</b> en sus próximos 3-5 pacientes con este cuadro.<br>
                • <b>Mi Compromiso:</b> Blindar stock hoy en <b>{top_farmacias_ciudad_str.split(',')[0]}</b>.<br>
                • <b>Puente a 2da Posición ({prod2}):</b> <i>«Siguiendo con eficacia comprobada, en estos casos cuenta con <b>{prod2}</b> ({benef2[:42]}...).»</i><br>
                • <b>Recordación 3ra ({prod3}):</b> Respaldo activo en farmacias aledañas.
            """

        st.markdown(f"""
        <div class='canvas-grid'>
            <div class='quad-card' style='border-top: 4px solid #1e3a8a;'>
                <div class='quad-title' style='color:#1e3a8a;'>♟️ I. DIAGNÓSTICO & OBJETIVO SMART ({modo_tac1})</div>
                <div class='quad-body'>{q1_html}</div>
            </div>
            <div class='quad-card' style='border-top: 4px solid #0284c7;'>
                <div class='quad-title' style='color:#0284c7;'>🗝️ II. APERTURA ADAPTADA ({especialidad})</div>
                <div class='quad-body'>{q2_html}</div>
            </div>
            <div class='quad-card' style='border-top: 4px solid #059669;'>
                <div class='quad-title' style='color:#059669;'>⚗️ III. EMBUDO, APOYO & LOVE BRAND</div>
                <div class='quad-body'>{q3_html}</div>
            </div>
            <div class='quad-card' style='border-top: 4px solid #d97706;'>
                <div class='quad-title' style='color:#b45309;'>⛓️ IV. CIERRE BILATERAL & PUENTE P1➔P2➔P3</div>
                <div class='quad-body'>{q4_html}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("📜 [DESPLEGAR DIÁLOGO LITERAL EXTENDIDO PASO A PASO (ADAPTADO A ESCALA DE ADOPCIÓN Y ESPECIALIDAD)]"):
            if st.button("⚡ Personalizar Diálogo Extendido con IA", use_container_width=True):
                with st.spinner("Redactando guion conversacional..."):
                    prompt_ext = f"""{REGLAS_FARMA}
Redacta el diálogo exacto paso a paso para el Dr(a). {medico_sel} (Especialidad: {especialidad} en {ciudad}).
- Producto 1: {prod1} | Estado en Escala de Adopción: {m_primario['escala_actual']} (Modo Táctico: {modo_tac1}) | Pacientes Gutis: {m_primario['pxs_gutis']} | Rival No-Gutis: {rival1} ({m_primario['pxs_comp']} Pxs).
- Producto 2 (Puente): {prod2} | Producto 3 (Recordación): {prod3}.
- Perfil de paciente: {perfil_paciente_adaptado}.
- Farmacias aliadas: {top_farmacias_ciudad_str}.
Recuerda: Si el Modo Táctico es LEALTAD, agradece su apoyo, blinda sutilmente {prod1} y enfoca el peso persuasivo en el Puente hacia {prod2}. Si es PEDIATRA, habla exclusivamente de pacientes pediátricos."""
                    res_ext = llamar_gemini(prompt_ext)
                    st.session_state.tvp_result = res_ext
            if st.session_state.tvp_result:
                st.markdown(st.session_state.tvp_result)
            else:
                if modo_tac1 == "LEALTAD":
                    st.markdown(f"""
* **1. Apertura de Reconocimiento y Gratitud (Socio Leal):** *«Doctor(a) {medico_sel}, qué gusto saludarlo(a). Antes que nada quiero agradecerle su respaldo y confianza sostenida en **{prod1}** ({m_primario['pxs_gutis']} recetas mensuales); para nosotros es un orgullo acompañarlo(a) en el cuidado de **{perfil_paciente_adaptado.lower()}**.»*
* **2. Sondeo de Validación y Blindaje Sutil:** *«En la experiencia que ha tenido este mes con nuestros esquemas, ¿cómo ha notado la satisfacción de las familias con nuestras presentaciones (*{meta1['caracteristica'].lower()}*)? Le confirmo además que en **{top_farmacias_ciudad_str}** tenemos inventario completo para que ningún paciente sufra cambios de receta.»*
* **3. Transición y Puente Fuerte hacia `{prod2}` (Unidad 6):** *«Y precisamente porque usted ya comprueba a diario la nobleza galénica de Gutis con **{prod1}**, quiero apoyarme en esa misma confianza para sus casos donde se requiere **{benef2.lower()}** (donde hoy todavía vemos prescripciones hacia `{rival2}`).»*
* **4. Cierre Bilateral en el Producto Puente:** *«¿Me permite que esta semana extendamos esa alianza iniciando con **{prod2}** en sus próximos 3 a 5 pacientes de este perfil, y manteniendo presente a **{prod3}** como complemento seguro?»*
""")
                else:
                    st.markdown(f"""
* **1. Apertura Formal ({especialidad}):** *«Doctor(a) {medico_sel}, gracias por estos minutos. {('Recordaba su interés en ' + contexto_rapport_str + '. ') if contexto_rapport_str else ''}Quería proponerle analizar cómo asegurar un alivio más rápido y sin abandono en **{perfil_paciente_adaptado.lower()}**. ¿Le parece bien?»*
* **2. Sondeo del Embudo:** *«Al **evaluar** la evolución de sus pacientes (donde en ocasiones se indica `{rival1}`), ¿qué aspecto de tolerabilidad o rapidez considera clave optimizar para proteger el éxito de su consulta?»*
* **3. Apoyo & Storytelling:** *«Comprendo perfectamente su prioridad. Por ello en Gutis contamos con **{prod1}**, que aporta **{meta1['caracteristica'].lower()}**, traduciéndose en **{meta1['beneficio'].lower()}**. {meta1['love_brand']} ¿No es este el respaldo que busca para sus pacientes?»*
* **4. Cierre & Puente Multi-Mercado:** *«¿Consideraría indicar **{prod1}** en sus próximos 3 a 5 pacientes esta semana mientras yo verifico el inventario en **{top_farmacias_ciudad_str}**? Y conectando con la recuperación integral en su consulta de **{especialidad}**, recuerde que también cuenta con **{prod2}** y **{prod3}** disponibles en las mismas farmacias.»*
""")

        with st.expander("⚔️ [ENTRENADOR DE OBJECIONES TVP: ESCEPTICISMO, MALENTENDIDO, DESVENTAJA E INDIFERENCIA]"):
            st.caption("Practica tu respuesta ante cualquier objeción clínica y recibe retroalimentación basada en el Manual TVP.")
            chat_container = st.container(height=230)
            for msg in st.session_state.chat_history:
                with chat_container.chat_message(msg["role"]): st.write(msg["content"])
            if prompt_chat := st.chat_input(f"Escribe tu argumento clínico para el Dr(a). {medico_sel}..."):
                st.session_state.chat_history.append({"role": "user", "content": prompt_chat})
                with chat_container.chat_message("user"): st.write(prompt_chat)
                with st.spinner("Evaluando técnica TVP..."):
                    prompt_sim = f"{REGLAS_FARMA}\nEntrena a Erick Calderón frente al Dr(a). {medico_sel} ({especialidad}). Producto: {prod1} vs {rival1}. Erick dijo: '{prompt_chat}'. Responde en 2 bloques breves: 1) Respuesta realista del médico, 2) Coaching TVP."
                    res_sim = llamar_gemini(prompt_sim)
                    if not res_sim:
                        res_sim = f"**🩺 Dr(a). {medico_sel}:** «Ya conozco `{rival1}` y me da resultados aceptables; además el paciente ya lo ubica.»\n\n**🛡️ Coaching TVP:** Clasificación: **Indiferencia / Hábito**. Aplica Unidad 7: 1) Demuestra comprensión sin ceder, 2) Pide permiso para 1 pregunta de agenda limitada sobre el beneficio exclusivo de **{prod1}** (*{meta1['caracteristica']}*)."
                st.session_state.chat_history.append({"role": "assistant", "content": res_sim})
                st.rerun()

    with col_micro_datos:
        sub_rx, sub_labs, sub_360 = st.tabs([
            "🧪 Recetario Rx (P1-P3)",
            "🏛️ Radar Fabricantes",
            "🪪 Ficha Omnicanal 360°"
        ])

        with sub_rx:
            if not rx_clean.empty:
                rx_clean["Nivel_Mercado"] = rx_clean["MERCADO"].apply(lambda x: f"P{obtener_meta_mercado(x, es_ped=es_pediatra)['prioridad']}")
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
                val_deporte = st.text_input("Contexto de Campo / Afinidad / Notas:", value=str(perfil_360_actual.get("Deporte", "")) if str(perfil_360_actual.get("Deporte", "")) != "nan" else "")
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
# NÚCLEO III: COPILOTO COGNITIVO CHIRA 3.0 & CIERRE POST-VISITA CRM (UNIDAD 9)
# ==============================================================================
with nucleo_copiloto:
    col_chira_main, col_crm_post = st.columns([1.48, 0.97])

    with col_chira_main:
        st.markdown("##### ♟️ [COPILOTO COGNITIVO CHIRA 3.0 — CONSULTORÍA DE ESPECIALISTAS, MERCADOS Y TERRITORIO]")
        st.caption("Consulta estrategias por médico, diagnóstico de mercados (P1, P2, P3), sincronía Rx vs. Sell-Out o planes tácticos TVP.")
        
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

        chat_container_chira = st.container(height=360)
        for msg in st.session_state.chira_history:
            with chat_container_chira.chat_message(msg["role"]): st.write(msg["content"])
            
        input_chat_chira = st.chat_input("Escribe tu consulta estratégica o análisis de caso...")

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
                top_n = int(match_num.group(1)) if match_num and 1 <= int(match_num.group(1)) <= 50 else 5

                medico_detectado_chat = detectar_medico_en_texto(input_chat_chira)
                es_pregunta_tactica_individual = any(k in texto_norm for k in [
                    "COMPRAD", "AMARRAD", "CASAD", "FIDELIZAD", "PIDE", "PEDIR", "PIDIO", "A CAMBIO",
                    "CONGRESO", "MUESTRA", "REGALO", "APOYO", "PATROCIN", "OBJECION", "ESCEPTIC",
                    "PRECIO", "CARO", "PASILLO", "ABORDO", "ABORDAR", "MANEJAR", "MANEJO", "ENTRARLE",
                    "ESTE MEDICO", "ESTA DOCTORA", "ESTE DOCTOR", "ELLA", "EL DOCTOR", "LA DOCTORA",
                    "COMPARTIENDO", "COMPARTE", "COMPROMISO", "QUE CREES QUE PASE"
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

            with st.spinner("[CHIRA ANALIZANDO CASO Y DATOS REALES...]"):
                if modo_motor == "CONSULTORIA_MEDICO_INDIVIDUAL":
                    dossier_doc = extraer_dossier_medico(medico_detectado_chat)
                    base_cognitiva = construir_respuesta_cognitiva_medico(dossier_doc, input_chat_chira)

                    prompt_cognitivo_ia = f"""{REGLAS_FARMA}
Eres CHIRA 3.0, Consultora Senior de Inteligencia Comercial y Master Coach TVP de Laboratorios Gutis en Nicaragua.
El usuario (Erick Calderón) te acaba de escribir exactamente esto:
"{input_chat_chira}"

Aquí tienes el análisis táctico previo y las cifras exactas extraídas de Close-Up y Sell-Out para el Dr(a). {dossier_doc['nombre']} (Especialidad: {dossier_doc['especialidad']}):
{base_cognitiva}

INSTRUCCIONES ESTRICTAS:
1. Empieza con un ANÁLISIS TÁCTICO directo respondiendo a la situación planteada por Erick antes de dar los pasos del guion.
2. Verifica la Escala de Adopción en cada marca: si el médico ya nos da muchas recetas en una marca (ej. está en Lealtad >50% MS o Adopción Alta), NO le propongas un guion forzado de 'probar en 3 pacientes'; sugiérele agradecerle como socio estratégico, blindar sutilmente la marca recordando su importancia en nuestro portafolio y usar esa confianza como PUENTE hacia las marcas donde tenemos brecha.
3. Respeta estrictamente el Vademécum Nicaragua 2026 (JAMÁS menciones Disflam, Conrelax ni Dalivium) y la especialidad del médico (si es PEDIATRA, habla solo de pacientes pediátricos)."""

                    res_ia_cog = llamar_gemini(prompt_cognitivo_ia)
                    resultado_final = res_ia_cog if (res_ia_cog and len(res_ia_cog.strip()) > 180) else base_cognitiva

                else:
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
                                grp_ord = grp_doc.sort_values(by=[col_pxs_c, col_ytd_c] if col_ytd_c else [col_pxs_c], ascending=False)
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
        med_crm_target = st.session_state.ultimo_medico_chira if st.session_state.ultimo_medico_chira else medico_sel
        st.markdown(f"##### 📜 [UNIDAD 9: ANÁLISIS POST-VISITA & CRM — {med_crm_target[:20]}]")
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

            if st.form_submit_button("⛓️ Registrar Cierre de Ciclo en Bitácora CRM", use_container_width=True, type="primary"):
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
                    else: df_bit_new = pd.DataFrame([nueva_visita])
                    df_bit_new.to_excel(ARCHIVO_BITACORA, index=False)
                except: pass
                st.success(f"Visita a {med_crm_target} registrada en CRM.")

        df_hist_crm = pd.DataFrame(st.session_state.bitacora_memoria)
        if os.path.exists(ARCHIVO_BITACORA):
            try: df_hist_crm = pd.read_excel(ARCHIVO_BITACORA)
            except: pass
        if not df_hist_crm.empty:
            st.dataframe(df_hist_crm.tail(8), hide_index=True, use_container_width=True, height=180)
            csv_crm = df_hist_crm.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 Exportar Bitácora CRM (CSV)", data=csv_crm, file_name=f"CRM_TVP_Gutis_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)
