import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
import re
import unicodedata
import base64
from datetime import datetime

# --- CONFIGURACIÓN CORPORATIVA DE PÁGINA ---
st.set_page_config(
    page_title="Gutis BI | Análisis Close-Up & TVP",
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

# --- VADEMÉCUM OFICIAL GUTIS NICARAGUA 2026 Y MATRIZ DE CLASES TERAPÉUTICAS ---
MERCADOS_PRIORITARIOS = {
    "MR TALERDIN": {
        "producto": "Talerdín",
        "clase_terapeutica": "Antihistamínicos Sistémicos (R06A)",
        "prioridad": 1,
        "categoria_mercado": "Prioridad 1 (Core)",
        "apto_pediatria": True,
        "terminos_busqueda": [
            "TALERDIN", "ANTIHISTAMINICO", "ANTIHISTAMINICOS", "R06A", "CETIRIZINA",
            "CETRILER", "ALERCET", "DEGRALER", "LEVOCETIRIZINA", "DESLORATADINA",
            "LORATADINA", "FEXOFENADINA", "ALERFIN", "ZYRTEC", "AERIUS", "AVIANT"
        ],
        "paciente_meta": "Pacientes con rinitis alérgica, conjuntivitis alérgica, urticaria crónica o prurito que requieren control antihistamínico seguro.",
        "paciente_meta_ped": "Pacientes pediátricos y lactantes con rinitis alérgica, urticaria o prurito que requieren alivio seguro sin irritación gástrica.",
        "caracteristica": "Cetirizina en Tabletas (10 mg), Jarabe (60 ml 100% libre de alcohol) y Solución Gotas (10 ml: 1 gota por cada 2 kg de peso en menores de 2 años).",
        "beneficio": "Garantiza apego total al tratamiento sin rechazo por sabor ni efectos adversos gástricos asociados a excipientes alcohólicos.",
        "nicho_flanqueo": "Lactantes y niños pequeños con reflujo o intolerancia al excipiente alcohólico de otros jarabes antihistamínicos de la categoría.",
        "love_brand": "Tranquilidad nocturna para el paciente y su familia desde la primera toma, libre de alcohol."
    },
    "MR BIOTOS": {
        "producto": "Biotos Inmune",
        "clase_terapeutica": "Expectorantes, Antitusivos y Fitofármacos Respiratorios (R05C)",
        "prioridad": 1,
        "categoria_mercado": "Prioridad 1 (Core)",
        "apto_pediatria": True,
        "terminos_busqueda": [
            "BIOTOS", "EXPECTORANTE", "EXPECTORANTES", "FITOFARMACO", "ANTITUSIVO",
            "ANTITUSIVOS", "R05C", "HEDERA", "PELARGONIUM", "ABRILAR", "TUSILEXIL",
            "PROSPAN", "UMCKALOABO", "KALOBIN", "TOS"
        ],
        "paciente_meta": "Pacientes con tos seca, tos con flemas y secreción nasal en resfriado común, bronquitis, rinosinusitis y faringitis viral.",
        "paciente_meta_ped": "Pacientes pediátricos (desde los 2 años) con IVRS virales, tos seca o productiva y dificultad para expulsar secreciones.",
        "caracteristica": "Fórmula fitofarmacológica dual única: Hedera hélix (35 mg) + Pelargonium sidoides (12.5 mg) en presentación Pediátrica (120 ml) y Adulto (170 ml).",
        "beneficio": "Alivia la tos seca y con flemas mientras estimula los mecanismos defensivos antivirales y antibacterianos mediante su efecto inmunorregulador.",
        "nicho_flanqueo": "Pacientes con cuadros respiratorios virales donde un expectorante simple (solo Hedera o químico aislado) no aporta acción inmunorreguladora.",
        "love_brand": "Devolver la respiración libre y estimular las defensas naturales con respaldo científico."
    },
    "MR CLEMBROXIL": {
        "producto": "Clembroxil Compuesto",
        "clase_terapeutica": "Mucolíticos y Broncodilatadores Asociados (R05C / R03C)",
        "prioridad": 1,
        "categoria_mercado": "Prioridad 1 (Core)",
        "apto_pediatria": True,
        "terminos_busqueda": [
            "CLEMBROXIL", "CLENBUTEROL", "AMBROXOL", "MUCOLITICO", "MUCOLITICOS",
            "MUCOSOLVAN", "BROXOL", "SEKRETO", "BRONCODILATADOR"
        ],
        "paciente_meta": "Pacientes con patologías respiratorias agudas y crónicas que cursan con retención de secreciones y broncoespasmo.",
        "paciente_meta_ped": "Pacientes pediátricos y lactantes con broncoespasmo, sibilancias y retención severa de flemas (dosificación exacta a 2 gotas por kg de peso).",
        "caracteristica": "Sinergia de Ambroxol (7.5 mg) + Clenbuterol (5 mcg) en Jarabe (120 ml) y Solución Gotas Pediátricas (20 ml), 100% libre de azúcar y alcohol.",
        "beneficio": "Dilata el bronquio y fluidifica el moco simultáneamente, despejando la vía aérea sin irritación por azúcar o alcohol.",
        "nicho_flanqueo": "Pacientes con tos espástica y cierre bronquial donde un mucolítico simple no resuelve el broncoespasmo.",
        "love_brand": "Respaldo respiratorio contundente y seguro cuando al paciente le falta el aire."
    },
    "MR MOMETZONA": {
        "producto": "Mometzona",
        "clase_terapeutica": "Corticosteroides y Descongestivos Nasales Tópicos (R01A)",
        "prioridad": 1,
        "categoria_mercado": "Prioridad 1 (Core)",
        "apto_pediatria": True,
        "terminos_busqueda": [
            "MOMETZONA", "MOMETASONA", "NASAL", "NASALES", "R01A", "NASONEX",
            "GAMMAFLUX", "AVAMYS", "FLUTICASONA", "BUDESONIDA", "RINOCLENIL"
        ],
        "paciente_meta": "Pacientes con rinitis alérgica u obstrucción nasal inflamatoria que requieren control local sin irritación.",
        "paciente_meta_ped": "Pacientes pediátricos (2 a 11 años: 1 pulsación al día) y adolescentes con rinitis alérgica y congestión nasal persistente.",
        "caracteristica": "Mometasona furoato al 0.05% en spray nasal acuoso (140 aplicaciones), suspensión 100% libre de alcohol.",
        "beneficio": "Desinflama la mucosa nasal desde la primera aplicación diaria sin causar ardor, resequedad ni epistaxis.",
        "nicho_flanqueo": "Pacientes con mucosa nasal hipersensible que abandonan otros sprays de la categoría por ardor o excipientes alcohólicos.",
        "love_brand": "Descongestionar y devolver el descanso reparador con suavidad acuosa libre de alcohol."
    },
    "MR VENTILAR": {
        "producto": "Ventilar",
        "clase_terapeutica": "Antileucotrienos y Antiasmáticos Sistémicos (R03D)",
        "prioridad": 1,
        "categoria_mercado": "Prioridad 1 (Core)",
        "apto_pediatria": True,
        "terminos_busqueda": [
            "VENTILAR", "MONTELUKAST", "ANTILEUCOTRIENO", "LEUCOTRIENO", "R03D",
            "SINGULAIR", "AIRUM", "SUVIAR", "LUKAST", "ASMA"
        ],
        "paciente_meta": "Pacientes con asma bronquial o rinitis alérgica que requieren control preventivo nocturno.",
        "paciente_meta_ped": "Pacientes pediátricos desde los 6 meses hasta los 14 años con hiperreactividad bronquial, asma o rinitis alérgica.",
        "caracteristica": "Montelukast sódico en 3 presentaciones: 4 mg masticable sabor naranja (6 meses a 5 años), 5 mg masticable sabor tutti-chicle (6 a 14 años) y 10 mg recubierto.",
        "beneficio": "Excelente adherencia pediátrica por su sabor agradable y control sostenido de leucotrienos con una sola toma nocturna.",
        "nicho_flanqueo": "Pacientes en control preventivo continuo que abandonan otros esquemas por costo o rechazo al sabor.",
        "love_brand": "Libertad para que el paciente descanse toda la noche sin crisis respiratorias."
    },
    "MR GASTROALIVIO": {
        "producto": "Gastroalivio",
        "clase_terapeutica": "Inhibidores de la Bomba de Protones y Antiulcerosos (A02B)",
        "prioridad": 1,
        "categoria_mercado": "Prioridad 1 (Core)",
        "apto_pediatria": False,
        "terminos_busqueda": [
            "GASTROALIVIO", "ESOMEPRAZOL", "OMEPRAZOL", "PANTOPRAZOL", "LANSOPRAZOL",
            "DEXLANSOPRAZOL", "ANTIULCEROSO", "ANTIULCEROSOS", "IBP", "A02B", "NEXIUM",
            "CARBUM", "DEXIVANT", "ULCOZOL"
        ],
        "paciente_meta": "Pacientes adultos con ERGE, gastropatía por AINEs, hiperclorhidria o en erradicación de Helicobacter pylori.",
        "paciente_meta_ped": "Pacientes adolescentes mayores y adultos con ERGE o gastritis erosiva.",
        "caracteristica": "Esomeprazol 40 mg en cápsulas de liberación retardada con micropellets gastrorresistentes (libre de gluten y lactosa) + Plan Paciente 2+1.",
        "beneficio": "Protección gástrica y control ácido por 24 horas completas, respaldado por el Plan Paciente 2+1 (compra 2 cajas y recibe 1 gratis).",
        "nicho_flanqueo": "Pacientes con ERGE nocturno donde otros IBPs de la clase no sostienen las 24 horas o el paciente abandona el tratamiento por costo.",
        "love_brand": "Tecnología de micropellets y respaldo 2+1 que protegen el estómago y la economía del paciente."
    },
    "MR DALIVIO": {
        "producto": "Dalivio / Dalivio Tramax",
        "clase_terapeutica": "Analgésicos y Antiinflamatorios No Esteroideos - AINEs (M01A / N02B)",
        "prioridad": 1,
        "categoria_mercado": "Prioridad 1 (Core)",
        "apto_pediatria": False,
        "terminos_busqueda": [
            "DALIVIO", "DEXKETOPROFENO", "TRAMAX", "ANALGESICO", "ANALGESICOS",
            "AINE", "AINES", "ANTIINFLAMATORIO", "M01A", "N02B", "ENANTYUM",
            "STADIUM", "KETOROLACO", "DOLGENAL", "DICLOFENACO", "ETORICOXIB", "CELECOXIB"
        ],
        "paciente_meta": "Pacientes adultos con dolor agudo de moderado a intenso (musculoesquelético, dismenorrea, odontalgia, cólico renal o dolor postoperatorio).",
        "paciente_meta_ped": "Pacientes adolescentes mayores con dolor agudo traumático, odontalgia o dismenorrea.",
        "caracteristica": "Dexketoprofeno en 3 vías (Tabletas 25 mg, Solución oral bebible 25 mg/10 ml e Inyectable 50 mg/2 ml) + Dalivio Tramax (Dexketoprofeno 25 mg + Tramadol 75 mg para analgesia multimodal).",
        "beneficio": "Alivio rápido y potente del dolor agudo en minutos (sobre bebible o ampolla) y analgesia multimodal en dolor severo.",
        "nicho_flanqueo": "Pacientes con dolor agudo severo donde otros AINEs de la clase tardan más en actuar o irritan la mucosa gástrica.",
        "love_brand": "Aliados del alivio rápido para devolverle la funcionalidad al paciente en minutos."
    },
    "MR CONFLEXIL": {
        "producto": "Conflexil / Conflexil Plus Shot",
        "clase_terapeutica": "Miorrelajantes de Acción Central y Combinaciones (M03B)",
        "prioridad": 2,
        "categoria_mercado": "Prioridad 2 (Expansión)",
        "apto_pediatria": False,
        "terminos_busqueda": [
            "CONFLEXIL", "TIOCOLCHICOSIDO", "MIORRELAJANTE", "MIORRELAJANTES",
            "RELAJANTE MUSCULAR", "M03B", "TIZANIDINA", "CICLOBENZAPRINA", " SIRDALUD", "DORIXINA RELAX"
        ],
        "paciente_meta": "Pacientes adultos y adolescentes (>16 años) con contracturas musculares, cervicalgia, dorsalgia o lumbalgia aguda.",
        "paciente_meta_ped": "Adolescentes a partir de los 16 años con contracturas musculares deportivas o posturales.",
        "caracteristica": "Conflexil (Tiocolchicósido 4 mg y Fuerte 8 mg que NO produce sueño) + Conflexil Plus Tabletas y Conflexil Plus Shot (bebible en stick pack con Tiocolchicósido 4 mg + Diclofenaco potásico 50 mg, aprobado por Guías ACP).",
        "beneficio": "Triple acción (analgésica, antiinflamatoria y miorrelajante) de rápida absorción en Shot bebible, recuperando la movilidad sin sedación diurna.",
        "nicho_flanqueo": "Pacientes laboralmente activos con lumbalgia o contractura que no pueden permitirse la somnolencia de otros miorrelajantes.",
        "love_brand": "Liberar el movimiento del paciente sin adormecer su ritmo de vida."
    },
    "MR VALERPAN": {
        "producto": "Valerpan",
        "clase_terapeutica": "Corticosteroides Sistémicos Inyectables (H02A)",
        "prioridad": 2,
        "categoria_mercado": "Prioridad 2 (Expansión)",
        "apto_pediatria": True,
        "terminos_busqueda": [
            "VALERPAN", "BETAMETASONA", "CORTICOSTEROIDE", "CORTICOSTEROIDES",
            "H02A", "CELESTONE", "DIPROSPAN", "CRONODOSIS", "DEXAMETASONA"
        ],
        "paciente_meta": "Pacientes con procesos inflamatorios severos, crisis alérgicas agudas o patologías articulares que requieren corticoterapia de doble acción.",
        "paciente_meta_ped": "Pacientes con cuadros alérgicos o inflamatorios agudos severos que requieren control inmediato y sostenido.",
        "caracteristica": "Fosfato sódico de Betametasona + Dipropionato de Betametasona en ampolla de 1 ml y 2 ml con viscosidad adecuada y óptima homogeneidad.",
        "beneficio": "Doble acción comprobada: inicio rápido a los 30 minutos (fosfato) y efecto prolongado hasta por 30 días (dipropionato) en una aplicación suave.",
        "nicho_flanqueo": "Cuadros inflamatorios o alérgicos agudos donde un corticoide simple pierde efecto rápido y genera recaída.",
        "love_brand": "Calidad garantizada con acción inmediata en 30 minutos y respaldo prolongado."
    },
    "MR RENOVART": {
        "producto": "Renovart Platinum",
        "clase_terapeutica": "Condroprotectores y Salud Articular (M01C / M09A)",
        "prioridad": 2,
        "categoria_mercado": "Prioridad 2 (Expansión)",
        "apto_pediatria": False,
        "terminos_busqueda": [
            "RENOVART", "COLAGENO", "GLUCOSAMINA", "CONDROITINA", "CONDROPROTECTOR",
            "ARTICULAR", "CURCUMA", "M01C", "ARTROSIS"
        ],
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
        "terminos_busqueda": [
            "MUPIRAL", "MUPIROCINA", "ANTIBIOTICO TOPICO", "D06A", "BACTROBAN", "ACIDO FUSIDICO"
        ],
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
        "terminos_busqueda": [
            "BICORPAN", "D07C", "DERMATITIS", "TOLNAFTATO", "QUADRIDERM", "TRIDERM"
        ],
        "paciente_meta": "Pacientes (>12 años y adultos) con dermatitis inflamatorias complicadas con infecciones por bacterias y/o hongos (piodermias, tiñas).",
        "paciente_meta_ped": "Pacientes mayores de 12 años con dermatitis alérgica o por contacto sobreinfectada con hongos o bacterias.",
        "caracteristica": "Fórmula cuádruple en crema (15 g): Betametasona (0.5 mg) + Gentamicina (1 mg) + Tolnaftato (10 mg) + Yodoclorohidroxiquinoleína (10 mg).",
        "beneficio": "Controla simultáneamente la inflamación, el prurito, la infección bacteriana y la micosis en lesiones dérmicas mixtas.",
        "nicho_flanqueo": "Dermatitis mixtas rebeldes donde una crema simple no cubre hongos y bacterias a la vez.",
        "love_brand": "Resolución integral para afecciones complejas de la piel."
    },
    "MR FEMGYL": {
        "producto": "Femgyl",
        "clase_terapeutica": "Anticonceptivos Hormonales Inyectables (G03A)",
        "prioridad": 3,
        "categoria_mercado": "Prioridad 3 (Complemento)",
        "apto_pediatria": False,
        "terminos_busqueda": ["FEMGYL", "NORETISTERONA", "MESIGYNA", "ANTICONCEPTIVO INYECTABLE"],
        "paciente_meta": "Pacientes en edad reproductiva que buscan anticoncepción hormonal mensual cómoda y segura.",
        "paciente_meta_ped": "Pacientes ginecológicas en control anticonceptivo.",
        "caracteristica": "Enantato de noretisterona (50 mg) + Valerato de estradiol (5 mg) en ampolla de 1 ml de aplicación mensual fecha calendario.",
        "beneficio": "Alta eficacia anticonceptiva en una sola aplicación mensual que evita olvidos diarios.",
        "nicho_flanqueo": "Usuarias que olvidan la toma diaria de tabletas orales.",
        "love_brand": "Tranquilidad y confianza mensual en salud femenina."
    },
    "MR NORGYLEN": {
        "producto": "Norgylen",
        "clase_terapeutica": "Anticonceptivos Hormonales Orales (G03A)",
        "prioridad": 3,
        "categoria_mercado": "Prioridad 3 (Complemento)",
        "apto_pediatria": False,
        "terminos_busqueda": ["NORGYLEN", "LEVONORGESTREL", "ETINILESTRADIOL", "MICROGYNON", "ANTICONCEPTIVO ORAL"],
        "paciente_meta": "Pacientes que requieren anticoncepción oral hormonal combinada confiable.",
        "paciente_meta_ped": "Pacientes ginecológicas en regulación de ciclo o anticoncepción.",
        "caracteristica": "Levonorgestrel (0.15 mg) + Etinilestradiol (0.03 mg) en caja con 21 tabletas recubiertas.",
        "beneficio": "Control predecible del ciclo menstrual con alta eficacia y seguridad.",
        "nicho_flanqueo": "Pacientes que buscan estabilidad hormonal oral con respaldo farmacéutico.",
        "love_brand": "Cuidado confiable todos los días para la mujer."
    },
    "MR ANSIOLIT": {
        "producto": "Ansiolit",
        "clase_terapeutica": "Ansiolíticos Benzodiazepínicos (N05B)",
        "prioridad": 3,
        "categoria_mercado": "Prioridad 3 (Complemento)",
        "apto_pediatria": False,
        "terminos_busqueda": ["ANSIOLIT", "ALPRAZOLAM", "ANSIOLITICO", "ANSIOLITICOS", "N05B", "TAFIL"],
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
        "terminos_busqueda": ["DEPAX", "SERTRALINA", "ALTRULINE", "ZOLOFT"],
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
        "terminos_busqueda": ["FELICITAT", "ESCITALOPRAM", "LEXAPRO", "ANTIDEPRESIVO", "N06A"],
        "paciente_meta": "Pacientes adultos con episodios depresivos mayores, trastorno de angustia o ansiedad generalizada.",
        "paciente_meta_ped": "Pacientes en manejo de estado de ánimo.",
        "caracteristica": "Escitalopram en presentaciones de 10 mg y 20 mg (30 tabletas recubiertas) con acción dual en el receptor SERT.",
        "beneficio": "Inhibición altamente selectiva de la recaptación de serotonina para una mejoría emocional sostenida.",
        "nicho_flanqueo": "Pacientes que requieren ajustar dosis entre 10 mg y 20 mg con excelente tolerabilidad.",
        "love_brand": "Ayudar a miles de pacientes a volver a disfrutar de la vida."
    }
}

MARCAS_OFICIALES_GUTIS_NIC = [
    "GASTROALIVIO", "TALERDIN", "TALERDÍN", "DALIVIO", "CONFLEXIL",
    "VALERPAN", "RENOVART", "BIOTOS", "CLEMBROXIL", "MOMETZONA",
    "VENTILAR", "FEMGYL", "NORGYLEN", "BICORPAN", "MUPIRAL",
    "ANSIOLIT", "DEPAX", "FELICITAT"
]

REGLAS_FARMA = """
REGLAS ESTRICTAS DE NEGOCIO Y VADEMÉCUM OFICIAL GUTIS NICARAGUA 2026:
1. CERO EMOJIS: Prohibido utilizar emojis o iconos decorativos. Usa viñetas limpias, negritas y estructura ejecutiva.
2. CLASE TERAPÉUTICA COMPLETA: Cada marca de Gutis compite contra TODA LA CLASE TERAPÉUTICA (ej. Talerdín compite contra todos los antihistamínicos: Cetirizina, Desloratadina, Levocetirizina, Loratadina, Fexofenadina; Biotos y Clembroxil contra todos los expectorantes, mucolíticos y antitusivos; Gastroalivio contra todos los IBPs; Dalivio contra todos los AINEs/analgésicos).
3. ADUANA VADEMÉCUM NICARAGUA 2026: Jamás menciones marcas no comercializadas en Nicaragua como 'Disflam', 'Conrelax', 'Dalivium', 'Valvirex' o 'Primabela'.
4. ESCALA DE ADOPCIÓN Y ESPECIALIDAD:
   - Si el médico está en LEALTAD (>50% MS): prohibido pedirle 'probar en 3 a 5 pacientes'. Agradece su respaldo como socio estratégico, blinda sutilmente la marca y usa esa confianza como PUENTE hacia un segundo mercado donde tengamos brecha.
   - Si es PEDIATRA: habla exclusivamente de pacientes pediátricos y presentaciones infantiles (gotas/jarabes sin alcohol).
"""

# --- ESTILOS CORPORATIVOS INSPIRADOS EN EL PORTAL CLOSE-UP GUTIS (SIN EMOJIS) ---
st.markdown("""
<style>
    .stApp { background-color: #f4f6f9; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #0f172a; }
    .gutis-topbar {
        background: linear-gradient(90deg, #002b5c 0%, #003b7a 50%, #002b5c 100%);
        color: #ffffff;
        padding: 16px 28px;
        border-radius: 6px;
        margin-bottom: 18px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 4px 12px rgba(0, 43, 92, 0.18);
    }
    .gutis-brand { font-size: 1.45rem; font-weight: 800; letter-spacing: 0.5px; color: #ffffff; }
    .gutis-brand span { font-size: 0.72rem; font-weight: 600; color: #cbd5e1; display: block; letter-spacing: 1.1px; text-transform: uppercase; }
    .gutis-center-title { font-size: 1.25rem; font-weight: 700; color: #ffffff; letter-spacing: 0.4px; }
    .gutis-bi-badge { text-align: right; font-size: 0.85rem; font-weight: 700; color: #e2e8f0; }
    .gutis-bi-badge span { font-size: 0.68rem; color: #93c5fd; display: block; letter-spacing: 1px; text-transform: uppercase; }

    .kpi-strip {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
        gap: 12px;
        margin-bottom: 18px;
    }
    .kpi-card {
        background: #ffffff;
        border: 1px solid #dce3ec;
        border-left: 4px solid #002b5c;
        border-radius: 6px;
        padding: 12px 16px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.03);
    }
    .kpi-lbl { font-size: 0.68rem; text-transform: uppercase; color: #64748b; font-weight: 800; letter-spacing: 0.6px; }
    .kpi-num { font-size: 1.3rem; font-weight: 800; color: #002b5c; margin-top: 2px; }
    .kpi-sub { font-size: 0.74rem; color: #475569; margin-top: 2px; font-weight: 600; }

    div.stButton > button {
        border-radius: 6px;
        font-weight: 700;
        border: 1px solid #cbd5e1;
        border-left: 5px solid #002b5c;
        background-color: #ffffff;
        color: #002b5c;
        padding: 12px 16px;
        transition: all 0.15s ease-in-out;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
    }
    div.stButton > button:hover {
        background-color: #002b5c;
        color: #ffffff;
        border-color: #002b5c;
    }
    div.stButton > button[kind="primary"] {
        background-color: #002b5c;
        color: #ffffff;
        border: 1px solid #002b5c;
        border-left: 5px solid #38bdf8;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #003b7a;
        color: #ffffff;
    }

    .module-banner {
        background: #002b5c;
        color: #ffffff;
        padding: 10px 18px;
        border-radius: 5px;
        margin-bottom: 14px;
        border-left: 5px solid #38bdf8;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    .canvas-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin-top: 10px; margin-bottom: 16px; }
    .quad-card { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 16px; box-shadow: 0 2px 5px rgba(0,0,0,0.03); }
    .quad-title { font-size: 0.76rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; padding-bottom: 6px; border-bottom: 2px solid #f1f5f9; }
    .quad-body { font-size: 0.85rem; color: #1e293b; line-height: 1.5; }
    .script-box { background: #ffffff; border: 1px solid #93c5fd; border-left: 5px solid #002b5c; border-radius: 6px; padding: 18px 22px; margin-top: 10px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,43,92,0.06); }
    .drill-panel { background: #ffffff; border: 1px solid #cbd5e1; border-top: 4px solid #002b5c; border-radius: 6px; padding: 16px; margin-top: 14px; margin-bottom: 16px; }
</style>
""", unsafe_allow_html=True)

# --- CARGA Y HOMOLOGACIÓN DETERMINÍSTICA DE ARCHIVOS EXCEL ---
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

def es_marca_gutis_oficial(nombre_prod, fabricante=""):
    if fabricante and "GUTIS" in normalizar_txt(fabricante):
        return True
    n_norm = normalizar_txt(nombre_prod)
    # Validación por palabra completa o prefijo oficial para evitar falsos positivos
    for g in MARCAS_OFICIALES_GUTIS_NIC:
        g_norm = normalizar_txt(g)
        if re.search(rf'\b{re.escape(g_norm)}\b', n_norm) or n_norm.startswith(g_norm):
            return True
    return False

def resolver_clave_mercado_gutis(texto_mercado_o_clase, nombre_prod=""):
    t_norm = normalizar_txt(f"{texto_mercado_o_clase} {nombre_prod}")
    if not t_norm or t_norm in ["TOTAL", "NAN", "NONE"]:
        return None
    # Bloquear mercados ajenos a Nicaragua
    if any(ex in t_norm for ex in ["VALVIREX", "PRIMABELA", "BELEZA", "GESIMAX", "FLUKIT", "ZITRO"]):
        return None
    for m_key, m_info in MERCADOS_PRIORITARIOS.items():
        if any(normalizar_txt(term) in t_norm for term in m_info["terminos_busqueda"]):
            return m_key
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
        df_v1 = pd.read_excel("VENTA PRIMER TRIMESTRE 2026.xlsx"); df_v1["Trimestre"] = "Q1"
    except Exception:
        df_v1 = pd.DataFrame()
    try:
        df_v2 = pd.read_excel("VENTAS SEGUNDO TRIMESTRE 2026.xlsx"); df_v2["Trimestre"] = "Q2"
    except Exception:
        df_v2 = pd.DataFrame()
    try:
        df_v3 = pd.read_excel("VENTAS TERCER TRIMESTRE 2026.xlsx", sheet_name="Export"); df_v3["Trimestre"] = "Q3"
    except Exception:
        try:
            df_v3 = pd.read_excel("VENTAS TERCER TRIMESTRE 2026.xlsx"); df_v3["Trimestre"] = "Q3"
        except Exception:
            df_v3 = pd.DataFrame()

    dataframes_ventas = [df for df in [df_v1, df_v2, df_v3] if not df.empty]
    df_v = pd.concat(dataframes_ventas, ignore_index=True) if dataframes_ventas else pd.DataFrame()

    for d in [df_p, df_rx, df_v, df_labs_raw, df_clases_raw]:
        if not d.empty:
            d.columns = d.columns.astype(str).str.strip()

    if not df_p.empty:
        col_m_p = next((c for c in df_p.columns if normalizar_txt(c) == "MEDICO"), None)
        if col_m_p and col_m_p != "Médico":
            df_p = df_p.rename(columns={col_m_p: "Médico"})
        if "Médico" in df_p.columns:
            df_p["Médico"] = df_p["Médico"].astype(str).str.strip().str.upper()
        if "CIUDAD" in df_p.columns:
            df_p["CIUDAD"] = df_p["CIUDAD"].astype(str).str.strip().str.upper()
        if "Especialidad" in df_p.columns:
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

    # Vincular Clases Terapéuticas si existe columna de producto y clase
    if not df_clases_raw.empty and not df_rx.empty:
        col_prod_ct = next((c for c in df_clases_raw.columns if "PRODUCTO" in normalizar_txt(c)), None)
        col_clase_ct = next((c for c in df_clases_raw.columns if any(k in normalizar_txt(c) for k in ["CLASE", "TERAPEUTICA", "ATC", "CATEGORIA", "MERCADO"])), None)
        if col_prod_ct and col_clase_ct:
            mapa_ct = (
                df_clases_raw.dropna(subset=[col_prod_ct, col_clase_ct])
                .drop_duplicates(subset=[col_prod_ct])
                .set_index(df_clases_raw[col_prod_ct].astype(str).str.strip().str.upper())[col_clase_ct]
                .to_dict()
            )
            df_rx["CLASE_TERAPEUTICA_ARCHIVO"] = df_rx["NOMBRE_PRODUCTO"].str.upper().map(mapa_ct).fillna("")
        else:
            df_rx["CLASE_TERAPEUTICA_ARCHIVO"] = ""
    elif not df_rx.empty:
        df_rx["CLASE_TERAPEUTICA_ARCHIVO"] = ""

    # Si el archivo de Clases Terapéuticas trae directamente filas de prescripción por Médico y Clase Terapéutica,
    # unificar cualquier mercado/clase adicional que no esté en df_rx
    if not df_clases_raw.empty and "Médico" in df_clases_raw.columns and not df_rx.empty:
        col_clase_directa = next((c for c in df_clases_raw.columns if any(k in normalizar_txt(c) for k in ["CLASE", "TERAPEUTICA", "ATC", "MERCADO"])), None)
        if col_clase_directa and "MERCADO" in df_rx.columns:
            mapa_med_clase = (
                df_clases_raw.dropna(subset=["Médico", col_clase_directa])
                .groupby("Médico")[col_clase_directa]
                .apply(lambda s: " | ".join(set(s.astype(str))))
                .to_dict()
            )
            df_rx["CLASES_MEDICO_REF"] = df_rx["Médico"].map(mapa_med_clase).fillna("")

    if not df_v.empty and "DESCRIPCION_RUTA" in df_v.columns:
        df_v["DESCRIPCION_RUTA"] = df_v["DESCRIPCION_RUTA"].astype(str).str.strip().str.upper()

    archivos_cargados = {"panel": f_panel, "rx": f_rx, "labs": f_labs, "clases": f_clases}
    return df_p, df_rx, df_labs_raw, df_clases_raw, df_v, archivos_cargados

df_panel, df_productos, df_labs, df_clases, df_ventas, info_archivos = cargar_datos()

# Identificar columnas exactas de Mes y YTD (SIN MEZCLARLAS JAMÁS)
COL_PXS_MES = next((c for c in df_productos.columns if c.upper() == "PXS-MES"), None) if not df_productos.empty else None
if not COL_PXS_MES and not df_productos.empty:
    COL_PXS_MES = next((c for c in df_productos.columns if "MES" in c.upper() and "PXS" in c.upper()), None)

COL_PXS_YTD = next((c for c in df_productos.columns if c.upper() == "PXS-YTD"), None) if not df_productos.empty else None
if not COL_PXS_YTD and not df_productos.empty:
    COL_PXS_YTD = next((c for c in df_productos.columns if "YTD" in c.upper() and "PXS" in c.upper()), None)

if not df_productos.empty:
    if COL_PXS_MES and COL_PXS_MES in df_productos.columns:
        df_productos[COL_PXS_MES] = pd.to_numeric(df_productos[COL_PXS_MES], errors="coerce").fillna(0)
    if COL_PXS_YTD and COL_PXS_YTD in df_productos.columns:
        df_productos[COL_PXS_YTD] = pd.to_numeric(df_productos[COL_PXS_YTD], errors="coerce").fillna(0)

    col_fab_rx = next((c for c in df_productos.columns if "FABRICANTE" in c.upper() or "LAB" in c.upper()), None)
    df_productos["Es_Gutis"] = df_productos.apply(
        lambda r: es_marca_gutis_oficial(r.get("NOMBRE_PRODUCTO", ""), r.get(col_fab_rx, "") if col_fab_rx else ""),
        axis=1
    )
    df_productos["Clave_Gutis"] = df_productos.apply(
        lambda r: resolver_clave_mercado_gutis(
            f"{r.get('MERCADO', '')} {r.get('CLASE_TERAPEUTICA_ARCHIVO', '')}",
            r.get("NOMBRE_PRODUCTO", "")
        ),
        axis=1
    )
    # CÁLCULO MATEMÁTICO AUDITADO: Cuota de mercado (% MS) calculada estrictamente por ['Médico', 'MERCADO']
    if COL_PXS_MES:
        tot_cat_mes = df_productos.groupby(["Médico", "MERCADO"])[COL_PXS_MES].transform("sum")
        df_productos["MS_CAT_MES"] = np.where(tot_cat_mes > 0, (df_productos[COL_PXS_MES] / tot_cat_mes) * 100.0, 0.0)
    else:
        df_productos["MS_CAT_MES"] = 0.0

    if COL_PXS_YTD:
        tot_cat_ytd = df_productos.groupby(["Médico", "MERCADO"])[COL_PXS_YTD].transform("sum")
        df_productos["MS_CAT_YTD"] = np.where(tot_cat_ytd > 0, (df_productos[COL_PXS_YTD] / tot_cat_ytd) * 100.0, 0.0)
    else:
        df_productos["MS_CAT_YTD"] = 0.0

    # Enriquecer df_productos con CIUDAD y Especialidad desde df_panel para cruces directos
    if not df_panel.empty and "Médico" in df_panel.columns:
        mapa_ciu = df_panel.drop_duplicates(subset=["Médico"]).set_index("Médico")["CIUDAD"].to_dict() if "CIUDAD" in df_panel.columns else {}
        mapa_esp = df_panel.drop_duplicates(subset=["Médico"]).set_index("Médico")["Especialidad"].to_dict() if "Especialidad" in df_panel.columns else {}
        mapa_cat = df_panel.drop_duplicates(subset=["Médico"]).set_index("Médico")["CATEGORIA"].to_dict() if "CATEGORIA" in df_panel.columns else {}
        df_productos["CIUDAD_PANEL"] = df_productos["Médico"].map(mapa_ciu).fillna("FUERA DE PANEL")
        df_productos["ESP_PANEL"] = df_productos["Médico"].map(mapa_esp).fillna("ESPECIALISTA")
        df_productos["CAT_PANEL"] = df_productos["Médico"].map(mapa_cat).fillna("S/C")

LISTA_CIUDADES_REALES = sorted([c for c in df_panel["CIUDAD"].dropna().unique() if str(c).strip() not in ["", "NAN"]]) if not df_panel.empty and "CIUDAD" in df_panel.columns else []
LISTA_ESPECIALIDADES_REALES = sorted([e for e in df_panel["Especialidad"].dropna().unique() if str(e).strip() not in ["", "NAN"]]) if not df_panel.empty and "Especialidad" in df_panel.columns else []
LISTA_MERCADOS_GUTIS_KEYS = list(MERCADOS_PRIORITARIOS.keys())
LISTA_MERCADOS_EXCEL = sorted([m for m in df_productos["MERCADO"].dropna().unique() if str(m).strip() not in ["", "NAN", "TOTAL"] and resolver_clave_mercado_gutis(m) is not None]) if not df_productos.empty and "MERCADO" in df_productos.columns else []

def obtener_meta_por_mercado(mercado_o_clave):
    if mercado_o_clave in MERCADOS_PRIORITARIOS:
        return MERCADOS_PRIORITARIOS[mercado_o_clave]
    k = resolver_clave_mercado_gutis(mercado_o_clave)
    if k and k in MERCADOS_PRIORITARIOS:
        return MERCADOS_PRIORITARIOS[k]
    nom_limpio = str(mercado_o_clave).replace("MR ", "").strip()
    return {
        "producto": f"Portafolio {nom_limpio}",
        "clase_terapeutica": nom_limpio,
        "prioridad": 3,
        "categoria_mercado": "Otra Categoría",
        "apto_pediatria": True,
        "terminos_busqueda": [normalizar_txt(nom_limpio)],
        "paciente_meta": f"Pacientes dentro de la categoría {nom_limpio}.",
        "paciente_meta_ped": f"Pacientes pediátricos dentro de la categoría {nom_limpio}.",
        "caracteristica": "Calidad farmacéutica certificada Gutis.",
        "beneficio": "Eficacia y seguridad clínica comprobada.",
        "nicho_flanqueo": "Pacientes que requieren alta tolerabilidad.",
        "love_brand": "Innovación y tecnología para la vida."
    }

def diagnosticar_escala_adopcion(pxs_gutis_mes, pxs_tot_mes, ms_gutis_mes, pxs_gutis_ytd=0, pxs_tot_ytd=0, ms_gutis_ytd=0.0):
    # Evaluar primero sobre el período actual (Mes); si el médico no prescribió en el mes pero tiene historial YTD, indicarlo explícitamente sin mezclar cifras
    ms_eval = ms_gutis_mes if pxs_tot_mes > 0 else ms_gutis_ytd
    pxs_g_eval = pxs_gutis_mes if pxs_tot_mes > 0 else pxs_gutis_ytd
    pxs_t_eval = pxs_tot_mes if pxs_tot_mes > 0 else pxs_tot_ytd
    etiqueta_per = "Mes" if pxs_tot_mes > 0 else "Histórico YTD"

    if pxs_t_eval <= 0:
        return "1. No Consciente", "2. Consciente / 3. Prueba (2-5 Pxs)", "CONQUISTA", "Crear conciencia del perfil de paciente y lograr las primeras 3 recetas de prueba."
    if pxs_g_eval == 0:
        return f"2. Consciente (0% MS {etiqueta_per})", "3. Prueba (2 a 10 Pxs)", "CONQUISTA", f"Iniciar período de prueba en sus próximos 3 a 5 pacientes (prescribe {pxs_t_eval} Pxs en la categoría)."
    if ms_eval < 25.0:
        return f"3. Prueba ({ms_eval:.1f}% MS {etiqueta_per} | {pxs_g_eval} Pxs)", "4. Adopción (25% a 50% MS)", "EXPANSION", "Agradecer recetas iniciales, explorar experiencia clínica y expandir hacia más del 25% de la categoría."
    if ms_eval < 50.0:
        return f"4. Adopción ({ms_eval:.1f}% MS {etiqueta_per} | {pxs_g_eval} Pxs)", "5. Lealtad (>50% MS)", "EXPANSION", "Reconocer su respaldo activo y migrar sutilmente el segmento que aún comparte con otras marcas de la clase."
    return f"5. Lealtad ({ms_eval:.1f}% MS {etiqueta_per} | {pxs_g_eval} Pxs)", "5. Lealtad (Blindaje y Puente)", "LEALTAD", "Agradecer su lealtad como socio estratégico, blindar presentaciones y hacer el Puente hacia una segunda línea."

# --- ESTADO GLOBAL DE SESIÓN Y NAVEGACIÓN ---
if "modulo_activo" not in st.session_state:
    st.session_state.modulo_activo = "HUB"
if "medico_activo_global" not in st.session_state:
    st.session_state.medico_activo_global = sorted(df_panel["Médico"].dropna().unique().tolist())[0] if not df_panel.empty else ""
if "chira_history" not in st.session_state:
    st.session_state.chira_history = []
if "tvp_custom_script" not in st.session_state:
    st.session_state.tvp_custom_script = {}
if "ultimo_audio_hash" not in st.session_state:
    st.session_state.ultimo_audio_hash = None

def ir_a_modulo(nombre_mod, medico_destino=None):
    st.session_state.modulo_activo = nombre_mod
    if medico_destino:
        st.session_state.medico_activo_global = medico_destino

# --- FUNCIONES GEMINI (SOLO ESTRATEGIA, CERO ALTERACIÓN DE CIFRAS) ---
def llamar_gemini(prompt_text, max_tok=3500):
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt_text}]}], "generationConfig": {"maxOutputTokens": max_tok, "temperature": 0.2}}
    for mod in ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"]:
        try:
            url_p = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            res = requests.post(url_p, headers=headers, json=payload, timeout=16)
            if res.status_code == 200:
                cands = res.json().get("candidates", [])
                if cands and "content" in cands[0] and "parts" in cands[0]["content"]:
                    return cands[0]["content"]["parts"][0].get("text", "")
        except Exception:
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
                {"text": "Transcribe exactamente lo que dice este audio en español, sin añadir texto extra."},
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
        except Exception:
            continue
    return None

# --- MOTORES ANALÍTICOS DETERMINÍSTICOS (USADOS POR TODOS LOS MÓDULOS Y CHIRA) ---
def filtrar_df_por_mercado_o_clase(df_in, criterio_mercado=None, prio_num=None):
    if df_in.empty:
        return df_in
    df_out = df_in[df_in["Clave_Gutis"].notna()].copy()
    if prio_num:
        df_out = df_out[df_out["Clave_Gutis"].apply(lambda k: MERCADOS_PRIORITARIOS.get(k, {}).get("prioridad") == prio_num)].copy()
    if not criterio_mercado or criterio_mercado in ["TODOS", "TODOS LOS MERCADOS"]:
        return df_out

    criterios = criterio_mercado if isinstance(criterio_mercado, list) else [criterio_mercado]
    claves_buscadas = set()
    terminos_libres = []
    for c in criterios:
        c_norm = normalizar_txt(c)
        if c in MERCADOS_PRIORITARIOS:
            claves_buscadas.add(c)
        else:
            k_res = resolver_clave_mercado_gutis(c_norm)
            if k_res:
                claves_buscadas.add(k_res)
            terminos_libres.append(c_norm.replace("MR ", ""))

    mask = pd.Series(False, index=df_out.index)
    if claves_buscadas:
        mask = mask | df_out["Clave_Gutis"].isin(claves_buscadas)
    if terminos_libres:
        texto_fila = (
            df_out["MERCADO"].astype(str) + " " +
            df_out["CLASE_TERAPEUTICA_ARCHIVO"].astype(str) + " " +
            df_out["NOMBRE_PRODUCTO"].astype(str)
        ).apply(normalizar_txt)
        for tl in terminos_libres:
            if tl:
                mask = mask | texto_fila.str.contains(re.escape(tl), na=False)
    return df_out[mask].copy()

def obtener_desglose_productos_medico(nombre_medico, criterio_mercado=None):
    """
    Calcula la participación de cada marca individualmente por Médico, Mercado (Clase Terapéutica) y Período (Mes vs YTD separados).
    """
    if df_productos.empty or "Médico" not in df_productos.columns:
        return pd.DataFrame()
    sub = df_productos[df_productos["Médico"] == nombre_medico].copy()
    if sub.empty:
        return pd.DataFrame()
    if criterio_mercado:
        sub = filtrar_df_por_mercado_o_clase(sub, criterio_mercado=criterio_mercado)
    else:
        sub = sub[sub["Clave_Gutis"].notna()].copy()

    if sub.empty:
        return pd.DataFrame()

    c_m = COL_PXS_MES
    c_y = COL_PXS_YTD
    if c_m and c_y:
        sub = sub[(sub[c_m] > 0) | (sub[c_y] > 0)].copy()
    elif c_m:
        sub = sub[sub[c_m] > 0].copy()

    if sub.empty:
        return pd.DataFrame()

    sub["Origen"] = sub["Es_Gutis"].apply(lambda x: "GUTIS" if x else "COMPETENCIA")
    sub["Marca Gutis de la Clase"] = sub["Clave_Gutis"].apply(lambda k: MERCADOS_PRIORITARIOS.get(k, {}).get("producto", "Portafolio Gutis"))
    sub["Clase Terapéutica"] = sub["Clave_Gutis"].apply(lambda k: MERCADOS_PRIORITARIOS.get(k, {}).get("clase_terapeutica", ""))

    # Recalcular denominadores estrictamente por ['MERCADO'] dentro de este médico
    if c_m:
        tot_m = sub.groupby("MERCADO")[c_m].transform("sum")
        sub["% MS Mes (Categoría)"] = np.where(tot_m > 0, (sub[c_m] / tot_m * 100.0).round(1), 0.0)
        sub[c_m] = sub[c_m].astype(int)
    if c_y:
        tot_y = sub.groupby("MERCADO")[c_y].transform("sum")
        sub["% MS YTD (Categoría)"] = np.where(tot_y > 0, (sub[c_y] / tot_y * 100.0).round(1), 0.0)
        sub[c_y] = sub[c_y].astype(int)

    cols_sort = [c for c in ["MERCADO", c_m, c_y] if c]
    asc_sort = [True] + [False] * (len(cols_sort) - 1)
    sub = sub.sort_values(by=cols_sort, ascending=asc_sort)

    cols_out = ["MERCADO", "Clase Terapéutica", "NOMBRE_PRODUCTO", "Origen"]
    if c_m:
        cols_out += [c_m, "% MS Mes (Categoría)"]
    if c_y:
        cols_out += [c_y, "% MS YTD (Categoría)"]

    ren = {
        "MERCADO": "Mercado Close-Up",
        "NOMBRE_PRODUCTO": "Marca Prescrita",
        c_m: "Pxs Mes",
        c_y: "Pxs YTD"
    }
    return sub[cols_out].rename(columns=ren)

def obtener_ranking_medicos_mercado(ciudad_target=None, esp_target=None, mer_target=None, prio_target=None, modo_panel="PANEL"):
    """
    modo_panel: 'PANEL' (solo médicos en PANEL ERICK 2026), 'FUERA_PANEL' (no visitados), 'TODOS' (ambos).
    Mantiene Pxs Mes, % MS Mes, Pxs YTD y % MS YTD estrictamente separados.
    """
    if df_productos.empty:
        return pd.DataFrame()

    rx_sub = filtrar_df_por_mercado_o_clase(df_productos, criterio_mercado=mer_target, prio_num=prio_target)
    if rx_sub.empty:
        return pd.DataFrame()

    todos_panel_set = set(df_panel["Médico"].dropna().unique()) if not df_panel.empty else set()
    if modo_panel == "PANEL":
        rx_sub = rx_sub[rx_sub["Médico"].isin(todos_panel_set)].copy()
    elif modo_panel == "FUERA_PANEL":
        rx_sub = rx_sub[~rx_sub["Médico"].isin(todos_panel_set)].copy()

    if ciudad_target and ciudad_target not in ["TODAS", "TODO MI PANEL"]:
        col_c_doc = next((c for c in rx_sub.columns if c.upper() in ["CIUDAD", "DEPARTAMENTO", "ZONA", "CIUDAD_PANEL"]), "CIUDAD_PANEL")
        mask_ciu = rx_sub["CIUDAD_PANEL"].str.contains(re.escape(ciudad_target.upper()), na=False)
        if col_c_doc != "CIUDAD_PANEL":
            mask_ciu = mask_ciu | rx_sub[col_c_doc].astype(str).str.upper().str.contains(re.escape(ciudad_target.upper()), na=False)
        rx_sub = rx_sub[mask_ciu].copy()

    if esp_target and esp_target not in ["TODAS", "TODAS LAS ESPECIALIDADES"]:
        raiz_e = normalizar_txt(esp_target)[:5]
        col_e_doc = next((c for c in rx_sub.columns if "ESPEC" in c.upper()), "ESP_PANEL")
        mask_esp = rx_sub["ESP_PANEL"].apply(normalizar_txt).str.contains(raiz_e, na=False)
        if col_e_doc != "ESP_PANEL":
            mask_esp = mask_esp | rx_sub[col_e_doc].apply(normalizar_txt).str.contains(raiz_e, na=False)
        rx_sub = rx_sub[mask_esp].copy()

    if rx_sub.empty:
        return pd.DataFrame()

    c_m = COL_PXS_MES
    c_y = COL_PXS_YTD

    filas = []
    for nom_doc, grp in rx_sub.groupby("Médico"):
        p_mes_tot = int(grp[c_m].sum()) if c_m else 0
        p_ytd_tot = int(grp[c_y].sum()) if c_y else 0
        if p_mes_tot <= 0 and p_ytd_tot <= 0:
            continue

        p_gut_mes = int(grp[grp["Es_Gutis"]][c_m].sum()) if c_m else 0
        p_gut_ytd = int(grp[grp["Es_Gutis"]][c_y].sum()) if c_y else 0
        p_comp_mes = p_mes_tot - p_gut_mes
        p_comp_ytd = p_ytd_tot - p_gut_ytd

        ms_gut_mes = round((p_gut_mes / p_mes_tot * 100.0), 1) if p_mes_tot > 0 else 0.0
        ms_gut_ytd = round((p_gut_ytd / p_ytd_tot * 100.0), 1) if p_ytd_tot > 0 else 0.0

        grp_ord = grp.sort_values(by=[c_m, c_y] if (c_m and c_y) else [c_m or c_y], ascending=False)
        grp_no_g = grp_ord[~grp_ord["Es_Gutis"]]
        if not grp_no_g.empty:
            r_row = grp_no_g.iloc[0]
            rival_str = f"{r_row['NOMBRE_PRODUCTO']} ({int(r_row[c_m]) if c_m else 0} Mes / {int(r_row[c_y]) if c_y else 0} YTD)"
        else:
            rival_str = "Dominio 100% Gutis"

        top_marcas = []
        for _, r_p in grp_ord.head(3).iterrows():
            m_val = int(r_p[c_m]) if c_m else 0
            y_val = int(r_p[c_y]) if c_y else 0
            top_marcas.append(f"{r_p['NOMBRE_PRODUCTO']} [{m_val}M/{y_val}Y]")

        esc_act, _, modo_tac, _ = diagnosticar_escala_adopcion(p_gut_mes, p_mes_tot, ms_gut_mes, p_gut_ytd, p_ytd_tot, ms_gut_ytd)

        filas.append({
            "Médico": nom_doc,
            "Estatus Panel": "EN PANEL" if nom_doc in todos_panel_set else "FUERA DE PANEL",
            "Especialidad": str(grp.iloc[0].get("ESP_PANEL", "ESPECIALISTA")),
            "Cat": str(grp.iloc[0].get("CAT_PANEL", "S/C")),
            "Ciudad": str(grp.iloc[0].get("CIUDAD_PANEL", "NICARAGUA")),
            "Pxs Mes": p_mes_tot,
            "Gutis Mes": p_gut_mes,
            "Comp Mes": p_comp_mes,
            "% MS Mes": ms_gut_mes,
            "Pxs YTD": p_ytd_tot,
            "Gutis YTD": p_gut_ytd,
            "Comp YTD": p_comp_ytd,
            "% MS YTD": ms_gut_ytd,
            "Escala TVP": esc_act.split("(")[0].strip(),
            "Rival Principal en la Clase": rival_str,
            "Desglose Marcas [Mes/YTD]": " | ".join(top_marcas)
        })

    df_res = pd.DataFrame(filas)
    if not df_res.empty:
        df_res = df_res.sort_values(by=["Pxs Mes", "Pxs YTD", "Comp Mes"], ascending=[False, False, False]).reset_index(drop=True)
    return df_res

@st.cache_data
def calcular_crecimiento_mercados_mes_vs_ytd(ciudad_sel="TODO MI PANEL", incluir_fuera_panel=False):
    """
    Analiza qué mercados / clases terapéuticas están creciendo en el Mes respecto a su promedio histórico YTD.
    """
    if df_productos.empty:
        return pd.DataFrame()
    sub = df_productos[df_productos["Clave_Gutis"].notna()].copy()
    if not incluir_fuera_panel and not df_panel.empty:
        sub = sub[sub["Médico"].isin(set(df_panel["Médico"].dropna().unique()))].copy()
    if ciudad_sel not in ["TODO MI PANEL", "TODAS"]:
        sub = sub[sub["CIUDAD_PANEL"].str.contains(re.escape(ciudad_sel.upper()), na=False)].copy()

    if sub.empty:
        return pd.DataFrame()

    c_m = COL_PXS_MES
    c_y = COL_PXS_YTD
    filas = []
    for k_gut, grp in sub.groupby("Clave_Gutis"):
        meta = MERCADOS_PRIORITARIOS.get(k_gut, {})
        tot_m = int(grp[c_m].sum()) if c_m else 0
        tot_y = int(grp[c_y].sum()) if c_y else 0
        if tot_m == 0 and tot_y == 0:
            continue
        gut_m = int(grp[grp["Es_Gutis"]][c_m].sum()) if c_m else 0
        gut_y = int(grp[grp["Es_Gutis"]][c_y].sum()) if c_y else 0
        comp_m = tot_m - gut_m
        comp_y = tot_y - gut_y

        ms_m = round((gut_m / tot_m * 100.0), 2) if tot_m > 0 else 0.0
        ms_y = round((gut_y / tot_y * 100.0), 2) if tot_y > 0 else 0.0
        delta_ms = round(ms_m - ms_y, 2)

        if delta_ms >= 2.0:
            estado_crec = f"CRECE CUOTA (+{delta_ms:.1f} pts vs YTD)"
        elif delta_ms <= -2.0:
            estado_crec = f"PIERDE CUOTA ({delta_ms:.1f} pts vs YTD)"
        else:
            estado_crec = f"ESTABLE ({delta_ms:+.1f} pts vs YTD)"

        filas.append({
            "Prioridad": f"P{meta.get('prioridad', 3)}",
            "Marca Gutis": meta.get("producto", k_gut),
            "Clase Terapéutica": meta.get("clase_terapeutica", ""),
            "Mercado Total Mes": tot_m,
            "Gutis Mes": gut_m,
            "Comp Mes": comp_m,
            "% MS Mes": ms_m,
            "Mercado Total YTD": tot_y,
            "Gutis YTD": gut_y,
            "Comp YTD": comp_y,
            "% MS YTD": ms_y,
            "Delta % MS (Mes vs YTD)": delta_ms,
            "Diagnóstico de Evolución": estado_crec,
            "_p": meta.get("prioridad", 3)
        })
    df_out = pd.DataFrame(filas)
    if not df_out.empty:
        df_out = df_out.sort_values(by=["_p", "Mercado Total Mes", "Mercado Total YTD"], ascending=[True, False, False]).drop(columns=["_p"])
    return df_out

@st.cache_data
def calcular_matriz_penetracion_panel(ciudad_sel="TODO MI PANEL"):
    df_p_sub = df_panel.copy()
    if ciudad_sel not in ["TODO MI PANEL", "TODAS"] and "CIUDAD" in df_p_sub.columns:
        df_p_sub = df_p_sub[df_p_sub["CIUDAD"].astype(str).str.upper().str.contains(re.escape(ciudad_sel), na=False)].copy()
    if df_p_sub.empty or "Especialidad" not in df_p_sub.columns:
        return pd.DataFrame(), pd.DataFrame()

    usar_labs = not df_labs.empty and "FABRICANTE" in df_labs.columns and "Médico" in df_labs.columns
    if usar_labs:
        df_l_clean = df_labs[~df_labs["FABRICANTE"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])].copy()
        col_ytd_l = "Pxs-YTD" if "Pxs-YTD" in df_l_clean.columns else next((c for c in df_l_clean.columns if "YTD" in c.upper() and "PXS" in c.upper()), None)
        col_mes_l = "Pxs-MES" if "Pxs-MES" in df_l_clean.columns else next((c for c in df_l_clean.columns if "MES" in c.upper() and "PXS" in c.upper()), None)
        if col_ytd_l:
            df_l_clean[col_ytd_l] = pd.to_numeric(df_l_clean[col_ytd_l], errors="coerce").fillna(0)
        if col_mes_l:
            df_l_clean[col_mes_l] = pd.to_numeric(df_l_clean[col_mes_l], errors="coerce").fillna(0)

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

            penetracion_pct = (recetan_gutis_count / num_captados * 100.0) if num_captados > 0 else 0.0
            ms_gutis_ytd, ms_gutis_mes = 0.0, 0.0
            top5_strs = ["-", "-", "-", "-", "-"]

            if not df_l_esp_act.empty:
                agg_d = {col_ytd_l: "sum"}
                if col_mes_l:
                    agg_d[col_mes_l] = "sum"
                rk_esp_labs = df_l_esp_act.groupby("FABRICANTE").agg(agg_d).reset_index().sort_values(by=col_ytd_l, ascending=False).reset_index(drop=True)
                tot_y = rk_esp_labs[col_ytd_l].sum()
                tot_m = rk_esp_labs[col_mes_l].sum() if col_mes_l else 0
                rk_esp_labs["MS_YTD"] = np.where(tot_y > 0, rk_esp_labs[col_ytd_l] / tot_y * 100.0, 0.0)
                rk_esp_labs["MS_MES"] = np.where(tot_m > 0, rk_esp_labs[col_mes_l] / tot_m * 100.0, 0.0) if col_mes_l else 0.0

                fila_g_esp = rk_esp_labs[rk_esp_labs["FABRICANTE"].astype(str).str.upper().str.contains("GUTIS", na=False)]
                if not fila_g_esp.empty:
                    ms_gutis_ytd = float(fila_g_esp.iloc[0]["MS_YTD"])
                    ms_gutis_mes = float(fila_g_esp.iloc[0]["MS_MES"])

                top5_strs = []
                for idx_c in range(5):
                    if idx_c < len(rk_esp_labs):
                        r_lab = rk_esp_labs.iloc[idx_c]
                        nom_f = str(r_lab["FABRICANTE"]).strip()
                        ms_fy = float(r_lab["MS_YTD"])
                        ms_fm = float(r_lab["MS_MES"])
                        pref = "[GUTIS] " if "GUTIS" in nom_f.upper() else ""
                        top5_strs.append(f"{pref}{nom_f} ({ms_fm:.1f}% M | {ms_fy:.1f}% Y)")
                    else:
                        top5_strs.append("-")

            filas_rendimiento.append({
                "ESPECIALIDAD": esp_nom, "PANEL": num_panel, "CAPTADOS": num_captados,
                "RECETAN GUTIS": recetan_gutis_count, "PENETRACIÓN": round(penetracion_pct, 2),
                "TOP 1": top1_count, "TOP 3": top3_count,
                "% MS MES": round(ms_gutis_mes, 2), "% MS YTD": round(ms_gutis_ytd, 2)
            })
            filas_competencia.append({
                "ESPECIALIDAD": esp_nom, "#1": top5_strs[0], "#2": top5_strs[1],
                "#3": top5_strs[2], "#4": top5_strs[3], "#5": top5_strs[4], "_orden": num_panel
            })

    df_rend = pd.DataFrame(filas_rendimiento).sort_values(by="PANEL", ascending=False) if filas_rendimiento else pd.DataFrame()
    df_comp = pd.DataFrame(filas_competencia).sort_values(by="_orden", ascending=False).drop(columns=["_orden"]) if filas_competencia else pd.DataFrame()
    return df_rend, df_comp

def obtener_radar_laboratorios_doble_barra(ciudad_sel="TODO MI PANEL", esp_sel="TODAS", medico_especifico=None):
    """
    Calcula el Radar de Laboratorios con DOBLE BARRA SIMULTÁNEA: % MS Mes y % MS YTD.
    """
    if df_labs.empty or "FABRICANTE" not in df_labs.columns:
        return pd.DataFrame()
    sub_l = df_labs[~df_labs["FABRICANTE"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])].copy()
    if medico_especifico:
        sub_l = sub_l[sub_l["Médico"] == medico_especifico].copy()
    else:
        df_p_sub = df_panel.copy()
        if ciudad_sel not in ["TODO MI PANEL", "TODAS"] and "CIUDAD" in df_p_sub.columns:
            df_p_sub = df_p_sub[df_p_sub["CIUDAD"].str.contains(re.escape(ciudad_sel.upper()), na=False)]
        if esp_sel not in ["TODAS", "TODAS LAS ESPECIALIDADES"] and "Especialidad" in df_p_sub.columns:
            df_p_sub = df_p_sub[df_p_sub["Especialidad"].str.contains(re.escape(esp_sel[:5].upper()), na=False)]
        sub_l = sub_l[sub_l["Médico"].isin(set(df_p_sub["Médico"].dropna().unique()))].copy()

    if sub_l.empty:
        return pd.DataFrame()

    col_y = "Pxs-YTD" if "Pxs-YTD" in sub_l.columns else next((c for c in sub_l.columns if "YTD" in c.upper() and "PXS" in c.upper()), None)
    col_m = "Pxs-MES" if "Pxs-MES" in sub_l.columns else next((c for c in sub_l.columns if "MES" in c.upper() and "PXS" in c.upper()), None)

    if col_y: sub_l[col_y] = pd.to_numeric(sub_l[col_y], errors="coerce").fillna(0)
    if col_m: sub_l[col_m] = pd.to_numeric(sub_l[col_m], errors="coerce").fillna(0)

    agg_d = {}
    if col_m: agg_d[col_m] = "sum"
    if col_y: agg_d[col_y] = "sum"
    agg_d["Médico"] = lambda s: len(set(s))

    rk = sub_l.groupby("FABRICANTE").agg(agg_d).reset_index().rename(columns={"Médico": "Prescriptores"})
    tot_m = rk[col_m].sum() if col_m else 0
    tot_y = rk[col_y].sum() if col_y else 0

    rk["Pxs Mes"] = rk[col_m].astype(int) if col_m else 0
    rk["% MS Mes"] = np.where(tot_m > 0, (rk[col_m] / tot_m * 100.0).round(2), 0.0) if col_m else 0.0
    rk["Pxs YTD"] = rk[col_y].astype(int) if col_y else 0
    rk["% MS YTD"] = np.where(tot_y > 0, (rk[col_y] / tot_y * 100.0).round(2), 0.0) if col_y else 0.0
    rk["Delta MS (Mes vs YTD)"] = (rk["% MS Mes"] - rk["% MS YTD"]).round(2)
    rk["Laboratorio"] = rk["FABRICANTE"].apply(lambda x: f"[GUTIS] {x}" if "GUTIS" in str(x).upper() else str(x))

    rk = rk.sort_values(by=["Pxs Mes", "Pxs YTD"], ascending=[False, False]).reset_index(drop=True)
    return rk[["Laboratorio", "Prescriptores", "Pxs Mes", "% MS Mes", "Pxs YTD", "% MS YTD", "Delta MS (Mes vs YTD)"]]

# --- ENCABEZADO SUPERIOR ESTILO CLOSE-UP GUTIS BI ---
corte_nombre = info_archivos.get("rx") or "SEPTIEMBRE 2026"
st.markdown(f"""
<div class='gutis-topbar'>
    <div class='gutis-brand'>GUTIS <span>Innovación y Tecnología para la Vida</span></div>
    <div class='gutis-center-title'>Análisis Close-Up & Arquitectura TVP</div>
    <div class='gutis-bi-badge'>Inteligencia de Negocio <span>Centro de Competencias | {corte_nombre}</span></div>
</div>
""", unsafe_allow_html=True)

# --- MENÚ LATERAL DE NAVEGACIÓN RÁPIDA Y FILTRO DE ESPECIALISTA ---
st.sidebar.markdown("### NAVEGACIÓN DEL PORTAL")
opciones_nav = {
    "HUB": "Inicio | Menú Principal (5 Módulos)",
    "TOP_MEDICOS": "1. Top Médicos (inf.target)",
    "PREVISITA": "2. Previsita TVP (inf.target)",
    "ANALISIS_MERCADO": "3. Análisis Mercado (inf.market)",
    "EVOLUCION": "4. Evolución Rx vs. Sell-Out",
    "CHIRA": "5. CHIRA (Copiloto & CRM)"
}
nav_sel = st.sidebar.radio(
    "Módulo Activo:",
    list(opciones_nav.keys()),
    index=list(opciones_nav.keys()).index(st.session_state.modulo_activo),
    format_func=lambda k: opciones_nav[k]
)
if nav_sel != st.session_state.modulo_activo:
    st.session_state.modulo_activo = nav_sel
    st.rerun()

st.sidebar.divider()
st.sidebar.markdown("### ESPECIALISTA ACTIVO (PREVISITA)")
ciu_sb = st.sidebar.selectbox("Filtrar Ciudad del Panel:", ["TODAS"] + LISTA_CIUDADES_REALES)
df_pan_sb = df_panel if ciu_sb == "TODAS" else df_panel[df_panel["CIUDAD"] == ciu_sb]
esp_sb = st.sidebar.selectbox("Filtrar Especialidad:", ["TODAS"] + sorted(df_pan_sb["Especialidad"].dropna().unique().tolist()))
if esp_sb != "TODAS":
    df_pan_sb = df_pan_sb[df_pan_sb["Especialidad"] == esp_sb]

lista_meds_sb = sorted(df_pan_sb["Médico"].dropna().unique().tolist())
if not lista_meds_sb:
    lista_meds_sb = sorted(df_panel["Médico"].dropna().unique().tolist())

# Permitir también que si el usuario seleccionó un médico fuera de panel desde Top Médicos, aparezca en la lista
if st.session_state.medico_activo_global and st.session_state.medico_activo_global not in lista_meds_sb:
    lista_meds_sb = [st.session_state.medico_activo_global] + lista_meds_sb

idx_med_sb = lista_meds_sb.index(st.session_state.medico_activo_global) if st.session_state.medico_activo_global in lista_meds_sb else 0
med_elegido_sb = st.sidebar.selectbox("Especialista en Foco:", lista_meds_sb, index=idx_med_sb)
if med_elegido_sb != st.session_state.medico_activo_global:
    st.session_state.medico_activo_global = med_elegido_sb
    st.rerun()

medico_sel = st.session_state.medico_activo_global
fila_info_m = df_panel[df_panel["Médico"] == medico_sel]
if not fila_info_m.empty:
    ciudad = str(fila_info_m.iloc[0].get("CIUDAD", "NICARAGUA")).strip().upper()
    especialidad = str(fila_info_m.iloc[0].get("Especialidad", "ESPECIALISTA")).strip().upper()
    categoria = str(fila_info_m.iloc[0].get("CATEGORIA", "S/C")).strip()
else:
    ciudad, especialidad, categoria = "NICARAGUA", "ESPECIALISTA", "FUERA DE PANEL"
es_pediatra = "PEDIAT" in especialidad

# Indicadores ejecutivos globales para el Resumen Superior
tot_medicos_panel = len(df_panel["Médico"].dropna().unique()) if not df_panel.empty else 0
df_rx_panel_global = df_productos[df_productos["Médico"].isin(set(df_panel["Médico"].dropna().unique())) & df_productos["Clave_Gutis"].notna()] if not df_productos.empty else pd.DataFrame()
meds_activos_global = len(df_rx_panel_global[df_rx_panel_global[COL_PXS_YTD] > 0]["Médico"].unique()) if (not df_rx_panel_global.empty and COL_PXS_YTD) else 0
pxs_mes_global_tot = int(df_rx_panel_global[COL_PXS_MES].sum()) if (not df_rx_panel_global.empty and COL_PXS_MES) else 0
pxs_mes_global_gut = int(df_rx_panel_global[df_rx_panel_global["Es_Gutis"]][COL_PXS_MES].sum()) if pxs_mes_global_tot > 0 else 0
ms_mes_global_gut = (pxs_mes_global_gut / pxs_mes_global_tot * 100.0) if pxs_mes_global_tot > 0 else 0.0
pxs_ytd_global_tot = int(df_rx_panel_global[COL_PXS_YTD].sum()) if (not df_rx_panel_global.empty and COL_PXS_YTD) else 0
pxs_ytd_global_gut = int(df_rx_panel_global[df_rx_panel_global["Es_Gutis"]][COL_PXS_YTD].sum()) if pxs_ytd_global_tot > 0 else 0
ms_ytd_global_gut = (pxs_ytd_global_gut / pxs_ytd_global_tot * 100.0) if pxs_ytd_global_tot > 0 else 0.0

# ==============================================================================
# VISTA PRINCIPAL: LANDING HUB DE 5 BOTONES (ESTILO PORTAL CLOSE-UP GUTIS)
# ==============================================================================
if st.session_state.modulo_activo == "HUB":
    st.markdown(f"""
    <div class='kpi-strip'>
        <div class='kpi-card'>
            <div class='kpi-lbl'>PANEL MÉDICO REGISTRADO</div>
            <div class='kpi-num'>{tot_medicos_panel}</div>
            <div class='kpi-sub'>Prescriptores Activos Close-Up: {meds_activos_global}</div>
        </div>
        <div class='kpi-card'>
            <div class='kpi-lbl'>CUOTA GUTIS MES (CLASES ACTIVAS)</div>
            <div class='kpi-num'>{ms_mes_global_gut:.1f}%</div>
            <div class='kpi-sub'>{pxs_mes_global_gut:,} Gutis / {pxs_mes_global_tot:,} Total Mes</div>
        </div>
        <div class='kpi-card'>
            <div class='kpi-lbl'>CUOTA GUTIS YTD (ACUMULADO)</div>
            <div class='kpi-num'>{ms_ytd_global_gut:.1f}%</div>
            <div class='kpi-sub'>{pxs_ytd_global_gut:,} Gutis / {pxs_ytd_global_tot:,} Total YTD</div>
        </div>
        <div class='kpi-card'>
            <div class='kpi-lbl'>ESPECIALISTA EN PREPARACIÓN</div>
            <div class='kpi-num' style='font-size:1.02rem;'>{medico_sel[:24]}</div>
            <div class='kpi-sub'>{especialidad} | Cat {categoria} | {ciudad}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<h4 style='text-align:center; color:#002b5c; margin-top:10px; margin-bottom:22px;'>SELECCIONE EL MÓDULO DE INTELIGENCIA COMERCIAL</h4>", unsafe_allow_html=True)

    # Fila 1 de botones (Top Médicos | Previsita)
    sp1, col_b1, sp2, col_b2, sp3 = st.columns([0.4, 1.8, 0.4, 1.8, 0.4])
    with col_b1:
        if st.button("TOP MÉDICOS (inf.target)\nProspección Macro, Clases Terapéuticas y Fuera de Panel", use_container_width=True):
            ir_a_modulo("TOP_MEDICOS")
            st.rerun()
    with col_b2:
        if st.button("PREVISITA TVP (inf.target)\nCanvas TVP de 4 Cuadrantes y Guion Adaptativo en Primer Plano", use_container_width=True):
            ir_a_modulo("PREVISITA")
            st.rerun()

    st.write("")
    # Fila 2 de botones (Análisis Mercado | Evolución)
    sp4, col_b3, sp5, col_b4, sp6 = st.columns([0.4, 1.8, 0.4, 1.8, 0.4])
    with col_b3:
        if st.button("ANÁLISIS MERCADO (inf.market)\nPenetración por Especialidad y Radar Labs (Doble Barra Mes/YTD)", use_container_width=True):
            ir_a_modulo("ANALISIS_MERCADO")
            st.rerun()
    with col_b4:
        if st.button("EVOLUCIÓN (inf.target)\nSincronía Rx vs. Sell-Out Farmacias (Q1, Q2, Q3)", use_container_width=True):
            ir_a_modulo("EVOLUCION")
            st.rerun()

    st.write("")
    # Fila 3 central (CHIRA)
    sp7, col_b5, sp8 = st.columns([1.5, 1.8, 1.5])
    with col_b5:
        if st.button("CHIRA\nCopiloto Estratégico con Voz y Registro CRM Post-Visita", use_container_width=True, type="primary"):
            ir_a_modulo("CHIRA")
            st.rerun()

# ==============================================================================
# MÓDULO 1: TOP MÉDICOS (inf.target) — PROSPECCIÓN MACRO, CRECIMIENTO Y FUERA DE PANEL
# ==============================================================================
elif st.session_state.modulo_activo == "TOP_MEDICOS":
    c_back, c_tit = st.columns([0.8, 3.2])
    with c_back:
        if st.button("Volver al Menú Principal", use_container_width=True):
            ir_a_modulo("HUB"); st.rerun()
    with c_tit:
        st.markdown("<div class='module-banner'>MÓDULO 1: TOP MÉDICOS (inf.target) — AUDITORÍA DE TERRITORIO, CRECIMIENTO Y CONQUISTA</div>", unsafe_allow_html=True)

    f1, f2, f3, f4 = st.columns([1.1, 1.3, 1.1, 1.1])
    with f1:
        tm_ciu = st.selectbox("1. Territorio / Ciudad:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="tm_ciu")
    with f2:
        tm_mer = st.selectbox(
            "2. Clase Terapéutica / Mercado:",
            ["TODOS LOS MERCADOS"] + LISTA_MERCADOS_GUTIS_KEYS,
            format_func=lambda k: "TODOS LOS MERCADOS" if k == "TODOS LOS MERCADOS" else f"{MERCADOS_PRIORITARIOS[k]['producto']} — {MERCADOS_PRIORITARIOS[k]['clase_terapeutica']}",
            key="tm_mer"
        )
    with f3:
        tm_esp = st.selectbox("3. Especialidad:", ["TODAS"] + LISTA_ESPECIALIDADES_REALES, key="tm_esp")
    with f4:
        tm_universo = st.selectbox("4. Universo de Médicos:", ["Médicos en mi Panel", "Médicos Fuera de Panel (No Visitados)", "Todos (Panel + Fuera de Panel)"], key="tm_univ")

    modo_p_map = {
        "Médicos en mi Panel": "PANEL",
        "Médicos Fuera de Panel (No Visitados)": "FUERA_PANEL",
        "Todos (Panel + Fuera de Panel)": "TODOS"
    }[tm_universo]

    sub_tab_rk, sub_tab_crec = st.tabs([
        "1. Ranking de Médicos por Clase Terapéutica y Desglose de Marcas Rivales",
        "2. Qué Mercados Crecen en el Mes vs. Acumulado YTD"
    ])

    with sub_tab_rk:
        df_top_meds = obtener_ranking_medicos_mercado(
            ciudad_target=None if tm_ciu == "TODO MI PANEL" else tm_ciu,
            esp_target=None if tm_esp == "TODAS" else tm_esp,
            mer_target=None if tm_mer == "TODOS LOS MERCADOS" else tm_mer,
            modo_panel=modo_p_map
        )

        if not df_top_meds.empty:
            st.caption("Haz clic sobre cualquier fila de la tabla para inspeccionar debajo todas las marcas y moléculas que ese médico receta dentro de la categoría seleccionada:")
            ev_tm = st.dataframe(
                df_top_meds,
                hide_index=True,
                use_container_width=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    "% MS Mes": st.column_config.ProgressColumn("% MS Mes", format="%.1f%%", min_value=0, max_value=100),
                    "% MS YTD": st.column_config.ProgressColumn("% MS YTD", format="%.1f%%", min_value=0, max_value=100),
                }
            )

            filas_sel_tm = ev_tm.selection.rows if (ev_tm and hasattr(ev_tm, "selection")) else []
            idx_tm_doc = filas_sel_tm[0] if filas_sel_tm else 0
            lista_docs_tm = df_top_meds["Médico"].tolist()

            st.markdown("<div class='drill-panel'>", unsafe_allow_html=True)
            cd_1, cd_2 = st.columns([2.2, 1.2])
            with cd_1:
                doc_inspeccion_tm = st.selectbox(
                    "Especialista seleccionado para auditoría de marcas en la clase terapéutica:",
                    lista_docs_tm,
                    index=idx_tm_doc,
                    key="sel_doc_tm_drill"
                )
            with cd_2:
                st.write("")
                if st.button(f"Abrir a {doc_inspeccion_tm[:18]} en Previsita TVP", use_container_width=True, type="primary"):
                    ir_a_modulo("PREVISITA", medico_destino=doc_inspeccion_tm)
                    st.rerun()

            df_prods_doc_tm = obtener_desglose_productos_medico(
                doc_inspeccion_tm,
                criterio_mercado=None if tm_mer == "TODOS LOS MERCADOS" else tm_mer
            )
            if not df_prods_doc_tm.empty:
                st.dataframe(
                    df_prods_doc_tm,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "% MS Mes (Categoría)": st.column_config.ProgressColumn("% MS Mes (Categoría)", format="%.1f%%", min_value=0, max_value=100),
                        "% MS YTD (Categoría)": st.column_config.ProgressColumn("% MS YTD (Categoría)", format="%.1f%%", min_value=0, max_value=100),
                    }
                )
            st.markdown("</div>", unsafe_allow_html=True)

            csv_tm = df_top_meds.to_csv(index=False).encode("utf-8-sig")
            st.download_button("Exportar Ranking Top Médicos (CSV)", data=csv_tm, file_name=f"Top_Medicos_{tm_ciu}.csv", mime="text/csv")
        else:
            st.info("No se encontraron registros para ese filtro en el modo seleccionado. Prueba cambiar el Universo a 'Todos (Panel + Fuera de Panel)'.")

    with sub_tab_crec:
        st.markdown(f"##### Dinamismo de Clases Terapéuticas: Comparativa Mes Actual vs. Acumulado YTD ({tm_ciu})")
        df_crec = calcular_crecimiento_mercados_mes_vs_ytd(tm_ciu, incluir_fuera_panel=(modo_p_map != "PANEL"))
        if not df_crec.empty:
            st.dataframe(
                df_crec,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "% MS Mes": st.column_config.ProgressColumn("% MS Mes", format="%.2f%%", min_value=0, max_value=100),
                    "% MS YTD": st.column_config.ProgressColumn("% MS YTD", format="%.2f%%", min_value=0, max_value=100),
                }
            )
        else:
            st.info("Sin registros para calcular crecimiento en la zona seleccionada.")

# ==============================================================================
# MÓDULO 2: PREVISITA TVP (inf.target) — EL TVP EN PRIMER PLANO Y ADAPTATIVO
# ==============================================================================
elif st.session_state.modulo_activo == "PREVISITA":
    c_back, c_tit = st.columns([0.8, 3.2])
    with c_back:
        if st.button("Volver al Menú Principal", use_container_width=True):
            ir_a_modulo("HUB"); st.rerun()
    with c_tit:
        st.markdown(f"<div class='module-banner'>MÓDULO 2: PREVISITA TVP (inf.target) — DR(A). {medico_sel} ({especialidad} | CAT {categoria} | {ciudad})</div>", unsafe_allow_html=True)

    # Extraer mercados activos del médico en el portafolio oficial de Nicaragua
    rx_med = df_productos[(df_productos["Médico"] == medico_sel) & (df_productos["Clave_Gutis"].notna())].copy() if not df_productos.empty else pd.DataFrame()
    if es_pediatra and not rx_med.empty:
        rx_med = rx_med[rx_med["Clave_Gutis"].apply(lambda k: MERCADOS_PRIORITARIOS.get(k, {}).get("apto_pediatria", True))].copy()

    opciones_mercados_medico = []
    if not rx_med.empty:
        for k_gut, df_m in rx_med.groupby("Clave_Gutis"):
            meta = MERCADOS_PRIORITARIOS.get(k_gut)
            if not meta:
                continue
            p_m_tot = int(df_m[COL_PXS_MES].sum()) if COL_PXS_MES else 0
            p_y_tot = int(df_m[COL_PXS_YTD].sum()) if COL_PXS_YTD else 0
            if p_m_tot <= 0 and p_y_tot <= 0:
                continue
            p_m_gut = int(df_m[df_m["Es_Gutis"]][COL_PXS_MES].sum()) if COL_PXS_MES else 0
            p_y_gut = int(df_m[df_m["Es_Gutis"]][COL_PXS_YTD].sum()) if COL_PXS_YTD else 0
            p_m_comp = p_m_tot - p_m_gut
            p_y_comp = p_y_tot - p_y_gut

            ms_m = round((p_m_gut / p_m_tot * 100.0), 1) if p_m_tot > 0 else 0.0
            ms_y = round((p_y_gut / p_y_tot * 100.0), 1) if p_y_tot > 0 else 0.0

            df_m_ord = df_m.sort_values(by=[COL_PXS_MES, COL_PXS_YTD] if (COL_PXS_MES and COL_PXS_YTD) else [COL_PXS_MES or COL_PXS_YTD], ascending=False)
            df_riv = df_m_ord[~df_m_ord["Es_Gutis"]]
            if not df_riv.empty:
                r_row = df_riv.iloc[0]
                rival_nom = str(r_row["NOMBRE_PRODUCTO"]).strip()
                rival_m = int(r_row[COL_PXS_MES]) if COL_PXS_MES else 0
                rival_y = int(r_row[COL_PXS_YTD]) if COL_PXS_YTD else 0
            else:
                rival_nom, rival_m, rival_y = "Sin competidor activo en la clase", 0, 0

            esc_act, esc_meta, modo_tac, obj_esc = diagnosticar_escala_adopcion(p_m_gut, p_m_tot, ms_m, p_y_gut, p_y_tot, ms_y)
            opciones_mercados_medico.append({
                "clave_gutis": k_gut,
                "prod_gutis": meta["producto"],
                "clase_terapeutica": meta["clase_terapeutica"],
                "prioridad": meta["prioridad"],
                "pxs_mes": p_m_tot, "gutis_mes": p_m_gut, "comp_mes": p_m_comp, "ms_mes": ms_m,
                "pxs_ytd": p_y_tot, "gutis_ytd": p_y_gut, "comp_ytd": p_y_comp, "ms_ytd": ms_y,
                "rival_principal": rival_nom, "rival_mes": rival_m, "rival_ytd": rival_y,
                "escala_actual": esc_act, "escala_meta": esc_meta, "modo_tactico": modo_tac,
                "meta_info": meta
            })

    opciones_mercados_medico = sorted(opciones_mercados_medico, key=lambda x: (-x["pxs_mes"], -x["pxs_ytd"], x["prioridad"]))

    # Farmacias líderes de la ciudad del médico
    top_farmacias_ciudad_str = "principales farmacias de la zona"
    if not df_ventas.empty and "DESCRIPCION_RUTA" in df_ventas.columns:
        vz = df_ventas[df_ventas["DESCRIPCION_RUTA"].str.contains(re.escape(ciudad), na=False)].copy()
        if not vz.empty:
            vz = vz[~vz["NOMBRE_CLIENTE_1"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
            rk_f = vz.groupby("NOMBRE_CLIENTE_1")["Monto Real"].sum().reset_index().sort_values(by="Monto Real", ascending=False)
            if not rk_f.empty:
                top_farmacias_ciudad_str = ", ".join(rk_f["NOMBRE_CLIENTE_1"].head(3).tolist())

    # Selección de Posiciones de Visita (1ra, 2da y 3ra posición)
    with st.container(border=True):
        if opciones_mercados_medico:
            etiquetas_m = [
                f"[{o['modo_tactico']}] {o['prod_gutis']} | Mes: {o['pxs_mes']} ({o['ms_mes']}% MS) | YTD: {o['pxs_ytd']} ({o['ms_ytd']}% MS)"
                for o in opciones_mercados_medico
            ]
            idx_puente_def = 1 if len(opciones_mercados_medico) > 1 else 0
            for idx_c, o_c in enumerate(opciones_mercados_medico):
                if idx_c > 0 and o_c["modo_tactico"] != "LEALTAD" and (o_c["comp_mes"] > 0 or o_c["comp_ytd"] > 0):
                    idx_puente_def = idx_c
                    break
            cm1, cm2, cm3 = st.columns(3)
            with cm1: idx_m1 = st.selectbox("1ra Posición (Foco / Ancla):", range(len(etiquetas_m)), index=0, format_func=lambda i: etiquetas_m[i])
            with cm2: idx_m2 = st.selectbox("2da Posición (Puente Clínico):", range(len(etiquetas_m)), index=idx_puente_def, format_func=lambda i: etiquetas_m[i])
            with cm3: idx_m3 = st.selectbox("3ra Posición (Recordación):", range(len(etiquetas_m)), index=(2 if len(etiquetas_m) > 2 else idx_puente_def), format_func=lambda i: etiquetas_m[i])
            m_primario = opciones_mercados_medico[idx_m1]
            m_secundario = opciones_mercados_medico[idx_m2] if len(opciones_mercados_medico) > 1 else None
            m_terciario = opciones_mercados_medico[idx_m3] if len(opciones_mercados_medico) > 2 else None
        else:
            k_def = "MR TALERDIN" if es_pediatra else "MR GASTROALIVIO"
            meta_def = MERCADOS_PRIORITARIOS[k_def]
            m_primario = {
                "clave_gutis": k_def, "prod_gutis": meta_def["producto"], "clase_terapeutica": meta_def["clase_terapeutica"],
                "prioridad": 1, "pxs_mes": 0, "gutis_mes": 0, "comp_mes": 0, "ms_mes": 0.0,
                "pxs_ytd": 0, "gutis_ytd": 0, "comp_ytd": 0, "ms_ytd": 0.0,
                "rival_principal": "Competencia de la categoría", "rival_mes": 0, "rival_ytd": 0,
                "escala_actual": "1. No Consciente", "escala_meta": "3. Prueba (2-5 Pxs)", "modo_tactico": "CONQUISTA",
                "meta_info": meta_def
            }
            m_secundario, m_terciario = None, None

        ct1, ct2 = st.columns(2)
        with ct1: tipo_cita_sel = st.selectbox("Contexto de Visita:", ["Visita con cita previa", "Visita sin cita (Improvisto)", "Encuentro casual (Pasillo)"])
        with ct2: nec_detras_sel = st.selectbox("Necesidad detrás de la Necesidad (NdN):", ["Desempeño (Eficacia y adherencia clínica)", "Imagen (Prestigio clínico)", "Finanzas (Costo-beneficio)"])

    meta1 = m_primario["meta_info"]
    prod1 = m_primario["prod_gutis"]
    rival1 = m_primario["rival_principal"]
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

    # CANVAS TVP DE 4 CUADRANTES EN PRIMER PLANO
    if modo_tac1 == "LEALTAD":
        q1_html = f"""
            • <b>Escala Actual:</b> <span style='color:#047857; font-weight:800;'>{m_primario['escala_actual']} (Socio Leal)</span><br>
            • <b>Clase Terapéutica:</b> {m_primario['clase_terapeutica']}<br>
            • <b>Meta SMART Hoy:</b> Agradecer y blindar sus recetas de <b>{prod1}</b> (Mes: {m_primario['gutis_mes']} Pxs | YTD: {m_primario['gutis_ytd']} Pxs) y usar esa confianza como puente para iniciar <b>3 a 5 pacientes en {prod2}</b>.<br>
            • <b>Plan de Respaldo:</b> Asegurar rotación en <b>{top_farmacias_ciudad_str.split(',')[0]}</b>.
        """
        q2_html = f"""
            • <b>Postura Táctica:</b> Reconocimiento de lealtad (sin vender de cero lo que ya prescribe).<br>
            • <b>Apertura ({especialidad}):</b> Agradecer su preferencia sostenida en <i>{perfil_paciente_adaptado}</i><br>
            • <b>Pregunta de Validación:</b> <i>«¿Cómo ha notado la respuesta y adherencia de sus pacientes con nuestras presentaciones de {prod1} este mes?»</i>
        """
        q3_html = f"""
            • <b>Blindaje Sutil ({prod1}):</b> Recordar dosificación y ventaja diferencial ({meta1['caracteristica']}).<br>
            • <b>Enfoque ({nec_detras_sel.split('(')[0].strip()}):</b> {meta1['beneficio']}<br>
            • <b>Mensaje de Marca:</b> <i>«Gracias a su respaldo, decenas de pacientes en {ciudad} reciben un tratamiento seguro y libre de alcohol.»</i>
        """
        q4_html = f"""
            • <b>Cierre en {prod1}:</b> Agradecer su preferencia #1 y asegurar stock en <b>{top_farmacias_ciudad_str.split(',')[0]}</b>.<br>
            • <b>PUENTE PROTAGONISTA ({prod1} hacia {prod2}):</b> <i>«Apoyándome en su excelente experiencia con {prod1}, extendamos esa misma calidad hacia <b>{prod2}</b> ({benef2}) en los casos donde aún utiliza {rival2}.»</i><br>
            • <b>3ra Posición ({prod3}):</b> Recordación de disponibilidad zonal.
        """
        guion_base_visible = f"""
1. **Apertura de Reconocimiento y Gratitud (Escalón 5 - Lealtad):**
   > «Doctor(a) {medico_sel}, muchas gracias por recibirme. Hoy quiero iniciar agradeciéndole su confianza sostenida en **{prod1}** ({m_primario['gutis_mes']} Pxs en el mes y {m_primario['gutis_ytd']} en el año); usted es un referente clave para nuestro portafolio en {ciudad} en el cuidado de **{perfil_paciente_adaptado.lower()}**.»

2. **Sondeo de Validación y Blindaje Sutil:**
   > «En estos pacientes que ya trata regularmente con **{prod1}**, ¿qué comentarios le han compartido sobre la tolerabilidad y dosificación de nuestras presentaciones (*{meta1['caracteristica'].lower()}*)? Le confirmo que en **{top_farmacias_ciudad_str}** mantenemos inventario completo para evitar cualquier cambio de receta en mostrador.»

3. **El Puente de Autoridad hacia la 2da Marca (`{prod2}`):**
   > «Precisamente porque usted ya conoce de primera mano el respaldo galénico de Gutis con **{prod1}**, quiero apoyarme en esa misma confianza para sus pacientes donde requiere **{benef2.lower()}** (donde en la categoría aún se observan recetas hacia `{rival2}`).»

4. **Cierre Bilateral en el Producto Puente y Recordación (`{prod3}`):**
   > «¿Me permite que esta semana extendamos esa alianza iniciando con **{prod2}** en sus próximos 3 a 5 pacientes de este perfil, y manteniendo presente a **{prod3}** como complemento en las mismas farmacias?»
"""
    elif modo_tac1 == "EXPANSION":
        q1_html = f"""
            • <b>Escala Actual:</b> <span style='color:#0284c7; font-weight:800;'>{m_primario['escala_actual']} (Comparte Categoría)</span><br>
            • <b>Escalón Meta Hoy:</b> <span style='color:#047857; font-weight:700;'>{m_primario['escala_meta']}</span><br>
            • <b>Meta SMART:</b> Agradecer sus recetas actuales en <b>{prod1}</b> (Mes: {m_primario['gutis_mes']} | YTD: {m_primario['gutis_ytd']}) y migrar <b>4 a 6 pacientes</b> que aún van a <code>{rival1}</code>.<br>
            • <b>Plan de Respaldo:</b> Capturar el subgrupo de pacientes con mayor sensibilidad o riesgo de abandono.
        """
        q2_html = f"""
            • <b>Postura Táctica:</b> Explorar su experiencia positiva con los pacientes ya tratados.<br>
            • <b>Agenda ({especialidad}):</b> Analizar evolución en <i>{perfil_paciente_adaptado}</i><br>
            • <b>Pregunta Sutil:</b> <i>«En los casos donde ya prescribió nuestro esquema frente a {rival1}, ¿qué diferencias observó en tolerabilidad y apego?»</i>
        """
        q3_html = f"""
            • <b>Sondeo de Migración:</b> <i>«¿En qué perfil específico de paciente siente que todavía alterna con {rival1}?»</i><br>
            • <b>Ventaja Diferencial ({prod1}):</b> {meta1['caracteristica']}<br>
            • <b>Beneficio ({nec_detras_sel.split('(')[0].strip()}):</b> {meta1['beneficio']}
        """
        q4_html = f"""
            • <b>Pido al Médico:</b> Consolidar a <b>{prod1}</b> como primera elección en el segmento que compartía con <code>{rival1}</code>.<br>
            • <b>Mi Compromiso:</b> Garantizar inventario en <b>{top_farmacias_ciudad_str.split(',')[0]}</b>.<br>
            • <b>Puente a 2da Posición ({prod2}):</b> <i>«Y siguiendo con eficacia clínica, cuente con <b>{prod2}</b> ({benef2}).»</i>
        """
        guion_base_visible = f"""
1. **Apertura de Seguimiento Clínico (Escalón 3/4 - Expansión Sutil):**
   > «Doctor(a) {medico_sel}, qué gusto saludarlo(a). Quiero agradecerle los pacientes que ya está manejando con **{prod1}** y proponerle revisar en dos minutos la evolución de adherencia en **{perfil_paciente_adaptado.lower()}**. ¿Le parece bien?»

2. **Sondeo de Valor Mutuo (Aislar el Nicho Compartido):**
   > «Al **comparar** la respuesta de los pacientes en los que ya indicó **{prod1}** frente a aquellos donde aún alterna con `{rival1}`, ¿en qué perfil específico siente que todavía utiliza la otra opción?»

3. **Apoyo Galénico y Storytelling Love Brand:**
   > «Comprendo su punto, Doctor(a). Justamente para cubrir también a ese grupo de pacientes con total seguridad, **{prod1}** aporta **{meta1['caracteristica'].lower()}**, lo que garantiza **{meta1['beneficio'].lower()}**. *{meta1['love_brand']}*»

4. **Cierre de Consolidación y Puente hacia `{prod2}`:**
   > «Ya que usted mismo ha comprobado su respuesta, ¿consolidamos a **{prod1}** en esos próximos 4 a 6 pacientes que antes alternaba, mientras yo aseguro el stock en **{top_farmacias_ciudad_str}**? Y como puente clínico en su consulta de **{especialidad}**, recuerde que cuenta con **{prod2}** y **{prod3}**.»
"""
    else:
        q1_html = f"""
            • <b>Escala Actual:</b> <span style='color:#b91c1c; font-weight:700;'>{m_primario['escala_actual']}</span><br>
            • <b>Escalón Meta Hoy:</b> <span style='color:#047857; font-weight:700;'>{m_primario['escala_meta']}</span><br>
            • <b>Meta SMART:</b> Capturar los primeros <b>3 a 5 pacientes</b> que hoy prescribe en <code>{rival1}</code> (Comp Mes: {m_primario['comp_mes']} | Comp YTD: {m_primario['comp_ytd']}) hacia <b>{prod1}</b>.<br>
            • <b>Plan de Respaldo:</b> Iniciar prueba en 2 pacientes de rescate con muestra de arranque.
        """
        q2_html = f"""
            • <b>Postura Táctica:</b> Agenda centrada en el paciente de <b>{especialidad}</b> (sin mencionar marca en la apertura).<br>
            • <b>Agenda ({tipo_cita_sel.split('(')[0].strip()}):</b> Optimizar adherencia en <i>{perfil_paciente_adaptado}</i><br>
            • <b>Pregunta Disruptiva:</b> <i>«¿Qué impacto tendría en su consulta eliminar desde hoy el abandono terapéutico al segundo día en estos pacientes?»</i>
        """
        q3_html = f"""
            • <b>Sondeo de Valor Mutuo:</b> <i>«Al <b>evaluar</b> la respuesta actual con {rival1}, ¿qué considera prioritario optimizar en rapidez o tolerabilidad?»</i><br>
            • <b>Ventaja ({prod1}):</b> {meta1['caracteristica']}<br>
            • <b>Beneficio ({nec_detras_sel.split('(')[0].strip()}):</b> {meta1['beneficio']}
        """
        q4_html = f"""
            • <b>Pido al Médico:</b> Iniciar período de prueba con <b>{prod1}</b> en sus próximos 3 a 5 pacientes.<br>
            • <b>Mi Compromiso:</b> Asegurar disponibilidad hoy en <b>{top_farmacias_ciudad_str.split(',')[0]}</b>.<br>
            • <b>Puente a 2da Posición ({prod2}):</b> <i>«Siguiendo con seguridad clínica, cuenta también con <b>{prod2}</b> ({benef2}).»</i>
        """
        guion_base_visible = f"""
1. **Apertura Centrada en el Paciente (Sin nombrar marca - Unidad 3 TVP):**
   > «Doctor(a) {medico_sel}, gracias por estos minutos. Quería proponerle analizar brevemente cómo asegurar un alivio más rápido y sin abandono terapéutico en **{perfil_paciente_adaptado.lower()}**. ¿Le parece bien revisarlo?»

2. **Sondeo del Embudo (Unidad 4 TVP):**
   > «Actualmente, cuando maneja estos cuadros donde suele indicarse `{rival1}`, al **evaluar** la evolución en las primeras 48 horas, ¿qué aspecto de tolerabilidad o apego considera prioritario mejorar, especialmente en **{meta1['nicho_flanqueo'].lower()}**?»

3. **Apoyo y Storytelling de Marca (Unidad 5 TVP):**
   > «Coincido plenamente con usted. Por ello en Gutis desarrollamos **{prod1}**, que cuenta con **{meta1['caracteristica'].lower()}**, brindándole a su paciente **{meta1['beneficio'].lower()}**. *{meta1['love_brand']}* ¿No es este el estándar de seguridad que busca para ellos?»

4. **Cierre Bilateral y Puente hacia `{prod2}` (Unidad 6 TVP):**
   > «Cuando reciba esta semana a sus próximos 3 a 5 pacientes con este perfil, ¿consideraría iniciar la prueba con **{prod1}** mientras yo garantizo el inventario en **{top_farmacias_ciudad_str}**? Y conectando con el manejo integral, recuerde que cuenta también con **{prod2}** y **{prod3}**.»
"""

    st.markdown(f"""
    <div class='canvas-grid'>
        <div class='quad-card' style='border-top: 4px solid #002b5c;'>
            <div class='quad-title' style='color:#002b5c;'>I. DIAGNÓSTICO Y OBJETIVO SMART ({modo_tac1})</div>
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

    # GUION LITERAL PASO A PASO VISIBLE EN PRIMER PLANO (SIN ACORDEONES ESCONDIDOS)
    col_g_izq, col_g_der = st.columns([1.45, 1.0])
    with col_g_izq:
        st.markdown("##### GUION CONVERSACIONAL TVP EN PRIMER PLANO (ADAPTADO A ADOPCIÓN Y ESPECIALIDAD)")
        clave_cache_guion = f"{medico_sel}_{prod1}_{prod2}_{modo_tac1}_{nec_detras_sel}"
        if st.button("Generar / Refinar Variante Táctica de Guion (IA + Motor TVP)", use_container_width=True, type="primary"):
            with st.spinner("Estructurando variante táctica avanzada para el consultorio..."):
                prompt_g = f"""{REGLAS_FARMA}
Redacta una variante ejecutiva, persuasiva y natural del guion TVP paso a paso (1. Apertura, 2. Sondeo de Valor Mutuo, 3. Apoyo Galénico, 4. Cierre y Puente) para visitar al Dr(a). {medico_sel} ({especialidad} en {ciudad}).
Datos auditados que NO debes alterar:
- Producto 1: {prod1} | Escala actual: {m_primario['escala_actual']} (Modo: {modo_tac1}) | Gutis Mes: {m_primario['gutis_mes']} Pxs (YTD: {m_primario['gutis_ytd']}) | Rival en la clase: {rival1} (Comp Mes: {m_primario['comp_mes']} | Comp YTD: {m_primario['comp_ytd']}).
- Producto 2 (Puente): {prod2} | Producto 3: {prod3}.
- Enfoque psicológico: {nec_detras_sel} | Contexto: {tipo_cita_sel}.
- Farmacias aliadas: {top_farmacias_ciudad_str}."""
                res_g = llamar_gemini(prompt_g)
                if res_g and len(res_g.strip()) > 100:
                    st.session_state.tvp_custom_script[clave_cache_guion] = res_g
                else:
                    # Variante táctica determinística inmediata si la API no está disponible
                    st.session_state.tvp_custom_script[clave_cache_guion] = (
                        f"**[VARIANTE TÁCTICA EJECUTIVA — ENFOQUE {nec_detras_sel.upper()}]**\n\n" + guion_base_visible
                    )

        texto_guion_mostrar = st.session_state.tvp_custom_script.get(clave_cache_guion, guion_base_visible)
        st.markdown(f"<div class='script-box'>{texto_guion_mostrar}</div>", unsafe_allow_html=True)

    with col_g_der:
        st.markdown("##### RADIOGRAFÍA PRESCRIPTIVA DEL ESPECIALISTA")
        df_desg_pre = obtener_desglose_productos_medico(medico_sel)
        if not df_desg_pre.empty:
            st.dataframe(
                df_desg_pre,
                hide_index=True,
                use_container_width=True,
                height=340,
                column_config={
                    "% MS Mes (Categoría)": st.column_config.ProgressColumn("% MS Mes", format="%.1f%%", min_value=0, max_value=100),
                    "% MS YTD (Categoría)": st.column_config.ProgressColumn("% MS YTD", format="%.1f%%", min_value=0, max_value=100),
                }
            )
        else:
            st.info("El especialista no registra prescripciones activas en el corte actual.")

# ==============================================================================
# MÓDULO 3: ANÁLISIS MERCADO (inf.market) — PENETRACIÓN Y RADAR LABS DOBLE BARRA
# ==============================================================================
elif st.session_state.modulo_activo == "ANALISIS_MERCADO":
    c_back, c_tit = st.columns([0.8, 3.2])
    with c_back:
        if st.button("Volver al Menú Principal", use_container_width=True):
            ir_a_modulo("HUB"); st.rerun()
    with c_tit:
        st.markdown("<div class='module-banner'>MÓDULO 3: ANÁLISIS DE MERCADO (inf.market) — CLASES TERAPÉUTICAS Y DOBLE BARRA MES / YTD</div>", unsafe_allow_html=True)

    am1, am2, am3 = st.columns(3)
    with am1:
        am_ciu = st.selectbox("1. Territorio / Ciudad:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="am_ciu")
    with am2:
        am_esp = st.selectbox("2. Especialidad:", ["TODAS"] + LISTA_ESPECIALIDADES_REALES, key="am_esp")
    with am3:
        am_med_foco = st.selectbox("3. Nivel de Radar de Laboratorios:", ["Agregado Territorial / Especialidad", f"Solo Especialista Activo ({medico_sel[:20]})"])

    tab_labs_doble, tab_pen_esp = st.tabs([
        "1. Radar de Laboratorios con Doble Barra (% MS Mes vs. % MS YTD)",
        "2. Matriz de Penetración por Especialidad y Top 5 Competencia"
    ])

    with tab_labs_doble:
        med_param_l = medico_sel if am_med_foco.startswith("Solo") else None
        df_rk_labs = obtener_radar_laboratorios_doble_barra(ciudad_sel=am_ciu, esp_sel=am_esp, medico_especifico=med_param_l)
        if not df_rk_labs.empty:
            st.markdown(f"##### Participación Comparativa por Laboratorio: Mes Actual vs. Acumulado YTD ({med_param_l if med_param_l else am_ciu})")
            st.dataframe(
                df_rk_labs,
                hide_index=True,
                use_container_width=True,
                height=460,
                column_config={
                    "% MS Mes": st.column_config.ProgressColumn("% MS Mes (Actual)", format="%.2f%%", min_value=0, max_value=100),
                    "% MS YTD": st.column_config.ProgressColumn("% MS YTD (Acumulado)", format="%.2f%%", min_value=0, max_value=100),
                }
            )
        else:
            st.info("Sin registros de laboratorios para la combinación seleccionada.")

    with tab_pen_esp:
        df_rend_interno, df_top_comp = calcular_matriz_penetracion_panel(am_ciu)
        if not df_rend_interno.empty:
            st.markdown(f"##### 1. Cobertura y Penetración del Panel por Especialidad ({am_ciu})")
            st.dataframe(
                df_rend_interno,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "PENETRACIÓN": st.column_config.ProgressColumn("PENETRACIÓN (%)", format="%.2f%%", min_value=0, max_value=100),
                    "% MS MES": st.column_config.ProgressColumn("% MS MES GUTIS", format="%.2f%%", min_value=0, max_value=100),
                    "% MS YTD": st.column_config.ProgressColumn("% MS YTD GUTIS", format="%.2f%%", min_value=0, max_value=100),
                }
            )
            st.markdown(f"##### 2. Top 5 Laboratorios por Especialidad [Cuota Mes | Cuota YTD] ({am_ciu})")
            st.dataframe(df_top_comp, hide_index=True, use_container_width=True)
        else:
            st.info("Sin datos de penetración para el territorio seleccionado.")

# ==============================================================================
# MÓDULO 4: EVOLUCIÓN (inf.target) — SINCRONÍA RX VS. SELL-OUT FARMACIAS
# ==============================================================================
elif st.session_state.modulo_activo == "EVOLUCION":
    c_back, c_tit = st.columns([0.8, 3.2])
    with c_back:
        if st.button("Volver al Menú Principal", use_container_width=True):
            ir_a_modulo("HUB"); st.rerun()
    with c_tit:
        st.markdown("<div class='module-banner'>MÓDULO 4: EVOLUCIÓN (inf.target) — DESEMPEÑO DE RECETAS (MES / YTD) Y SELL-OUT EN FARMACIAS (Q1-Q3)</div>", unsafe_allow_html=True)

    ev_ciu = st.selectbox("Seleccionar Territorio:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="ev_ciu")

    # Tabla de Evolución de Clases Terapéuticas + Sell-Out Trimestral separando métricas verificadas
    df_ev_rx = calcular_crecimiento_mercados_mes_vs_ytd(ev_ciu, incluir_fuera_panel=False)
    df_v_sub = df_ventas.copy() if not df_ventas.empty else pd.DataFrame()
    if not df_v_sub.empty and ev_ciu != "TODO MI PANEL" and "DESCRIPCION_RUTA" in df_v_sub.columns:
        df_v_sub = df_v_sub[df_v_sub["DESCRIPCION_RUTA"].str.contains(re.escape(ev_ciu), na=False)].copy()
    if not df_v_sub.empty:
        df_v_sub = df_v_sub[~df_v_sub["NOMBRE_CLIENTE_1"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
    col_prod_v = "VM4" if (not df_v_sub.empty and "VM4" in df_v_sub.columns) else (next((c for c in df_v_sub.columns if "PRODUCTO" in c.upper()), None) if not df_v_sub.empty else None)

    if not df_ev_rx.empty:
        q1_list, q2_list, q3_list, var_so_list = [], [], [], []
        for _, r_ev in df_ev_rx.iterrows():
            kw_v = str(r_ev["Marca Gutis"]).split()[0].upper()
            patron_v = "DALIVIO|DALIVIUM" if kw_v == "DALIVIO" else ("TALERDIN|TALERDÍN" if kw_v in ["TALERDÍN", "TALERDIN"] else ("CONFLEXIL|CONRELAX" if kw_v == "CONFLEXIL" else re.escape(kw_v)))
            vq1, vq2, vq3 = 0.0, 0.0, 0.0
            if not df_v_sub.empty and col_prod_v and "Trimestre" in df_v_sub.columns:
                sv = df_v_sub[df_v_sub[col_prod_v].astype(str).str.upper().str.contains(patron_v, na=False)]
                if not sv.empty:
                    qs = sv.groupby("Trimestre")["Monto Real"].sum().to_dict()
                    vq1, vq2, vq3 = round(float(qs.get("Q1", 0.0)), 2), round(float(qs.get("Q2", 0.0)), 2), round(float(qs.get("Q3", 0.0)), 2)
            q1_list.append(vq1); q2_list.append(vq2); q3_list.append(vq3)
            var_pct = round(((vq3 - vq2) / vq2 * 100.0), 1) if vq2 > 0 else (100.0 if vq3 > 0 else 0.0)
            var_so_list.append(var_pct)

        df_ev_rx["Sell-Out Q1 ($)"] = q1_list
        df_ev_rx["Sell-Out Q2 ($)"] = q2_list
        df_ev_rx["Sell-Out Q3 ($)"] = q3_list
        df_ev_rx["Var % Q3 vs Q2"] = var_so_list

        st.markdown(f"##### 1. Comparativa Auditada por Marca: Cuota Prescriptiva (Mes vs. YTD) y Facturación Trimestral PDV ({ev_ciu})")
        st.dataframe(
            df_ev_rx,
            hide_index=True,
            use_container_width=True,
            column_config={
                "% MS Mes": st.column_config.ProgressColumn("% MS Mes", format="%.2f%%", min_value=0, max_value=100),
                "% MS YTD": st.column_config.ProgressColumn("% MS YTD", format="%.2f%%", min_value=0, max_value=100),
                "Sell-Out Q1 ($)": st.column_config.NumberColumn("Sell-Out Q1", format="$%.2f"),
                "Sell-Out Q2 ($)": st.column_config.NumberColumn("Sell-Out Q2", format="$%.2f"),
                "Sell-Out Q3 ($)": st.column_config.NumberColumn("Sell-Out Q3", format="$%.2f"),
                "Var % Q3 vs Q2": st.column_config.NumberColumn("Var Q3 vs Q2", format="%+.1f%%"),
            }
        )

    st.divider()
    st.markdown(f"##### 2. Auditoría Detallada de Sell-Out por Sucursal Farmacéutica ({ev_ciu})")
    if not df_v_sub.empty and col_prod_v:
        cf1, cf2 = st.columns(2)
        with cf1:
            f_sel = st.multiselect("Filtrar Farmacia(s):", sorted(df_v_sub["NOMBRE_CLIENTE_1"].dropna().unique().tolist()), placeholder="Todas las sucursales...")
        with cf2:
            p_sel = st.multiselect("Filtrar Producto:", sorted(df_v_sub[col_prod_v].dropna().unique().tolist()), placeholder="Todas las líneas...")
        df_vm = df_v_sub.copy()
        if f_sel: df_vm = df_vm[df_vm["NOMBRE_CLIENTE_1"].isin(f_sel)]
        if p_sel: df_vm = df_vm[df_vm[col_prod_v].isin(p_sel)]
        if not df_vm.empty and "Trimestre" in df_vm.columns:
            piv = pd.pivot_table(df_vm, values="Monto Real", index=["NOMBRE_CLIENTE_1", col_prod_v], columns=["Trimestre"], aggfunc="sum", fill_value=0.0).reset_index()
            for q in ["Q1", "Q2", "Q3"]:
                if q not in piv.columns: piv[q] = 0.0
                piv[q] = piv[q].round(2)
            piv["Total Acumulado"] = (piv["Q1"] + piv["Q2"] + piv["Q3"]).round(2)
            piv = piv.sort_values(by="Total Acumulado", ascending=False)
            st.dataframe(
                piv[["NOMBRE_CLIENTE_1", col_prod_v, "Q1", "Q2", "Q3", "Total Acumulado"]].rename(columns={"NOMBRE_CLIENTE_1": "Farmacia / Cliente", col_prod_v: "Producto Gutis"}),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Q1": st.column_config.NumberColumn("Q1", format="$%.2f"),
                    "Q2": st.column_config.NumberColumn("Q2", format="$%.2f"),
                    "Q3": st.column_config.NumberColumn("Q3", format="$%.2f"),
                    "Total Acumulado": st.column_config.NumberColumn("Total Acumulado", format="$%.2f"),
                }
            )

# ==============================================================================
# MÓDULO 5: CHIRA — COPILOTO COGNITIVO CON VOZ Y BITÁCORA CRM VERIFICADA
# ==============================================================================
elif st.session_state.modulo_activo == "CHIRA":
    c_back, c_tit = st.columns([0.8, 3.2])
    with c_back:
        if st.button("Volver al Menú Principal", use_container_width=True):
            ir_a_modulo("HUB"); st.rerun()
    with c_tit:
        st.markdown("<div class='module-banner'>MÓDULO 5: CHIRA — INTELIGENCIA COMERCIAL CONVERSACIONAL Y BITÁCORA CRM</div>", unsafe_allow_html=True)

    col_ch_izq, col_ch_der = st.columns([1.48, 0.97])

    with col_ch_izq:
        with st.container(border=True):
            p_c1, p_c2, p_c3, p_c4 = st.columns([1.1, 1.3, 1.1, 0.6])
            with p_c1: ch_ciu = st.selectbox("Territorio:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="ch_c")
            with p_c2:
                ch_mer = st.selectbox(
                    "Clase / Mercado:",
                    ["TODOS LOS MERCADOS"] + LISTA_MERCADOS_GUTIS_KEYS,
                    format_func=lambda k: "TODOS LOS MERCADOS" if k == "TODOS LOS MERCADOS" else f"{MERCADOS_PRIORITARIOS[k]['producto']} ({MERCADOS_PRIORITARIOS[k]['clase_terapeutica'][:22]}...)",
                    key="ch_m"
                )
            with p_c3: ch_esp = st.selectbox("Especialidad:", ["TODAS"] + LISTA_ESPECIALIDADES_REALES, key="ch_e")
            with p_c4: ch_top = st.selectbox("Top:", [5, 10, 15, 20], index=1, key="ch_t")

            b1, b2, b3, b4, b5 = st.columns(5)
            accion_rapida = None
            if b1.button("Top Prescriptores", use_container_width=True): accion_rapida = "PARETO"
            if b2.button("Oportunidad Conquista", use_container_width=True): accion_rapida = "CONQUISTA"
            if b3.button("Fuera de Panel", use_container_width=True): accion_rapida = "FUERA_PANEL"
            if b4.button("Crecimiento Mercados", use_container_width=True): accion_rapida = "CRECIMIENTO"
            if b5.button("Radar Laboratorios", use_container_width=True): accion_rapida = "LABS"

        # Micrófono nativo para dictar por voz
        texto_voz = None
        if hasattr(st, "audio_input"):
            aud = st.audio_input("Dictar consulta por voz a CHIRA (opcional):")
            if aud is not None:
                ab = aud.getvalue()
                h_aud = hash(ab)
                if st.session_state.ultimo_audio_hash != h_aud:
                    st.session_state.ultimo_audio_hash = h_aud
                    with st.spinner("Transcribiendo audio..."):
                        texto_voz = transcribir_audio_gemini(ab)

        chat_box = st.container(height=360)
        for msg in st.session_state.chira_history:
            with chat_box.chat_message(msg["role"]):
                st.markdown(msg["content"])

        txt_input = st.chat_input("Pregunta a CHIRA (ej: analiza el mercado de expectorantes en rivas / médicos más importantes para biotos o talerdin)...")
        consulta_activa = texto_voz if texto_voz else txt_input

        if accion_rapida or consulta_activa:
            if accion_rapida:
                ciu_q = None if ch_ciu == "TODO MI PANEL" else ch_ciu
                mer_q = None if ch_mer == "TODOS LOS MERCADOS" else ch_mer
                esp_q = None if ch_esp == "TODAS" else ch_esp
                top_q = ch_top
                modo_q = accion_rapida
                texto_mostrar = f"[Consulta Directa] {accion_rapida} | Zona: {ch_ciu} | Mercado: {ch_mer} | Esp: {ch_esp}"
            else:
                texto_mostrar = consulta_activa
                t_norm = normalizar_txt(consulta_activa)
                m_num = re.search(r'\b(\d+)\b', t_norm)
                top_q = int(m_num.group(1)) if m_num and 1 <= int(m_num.group(1)) <= 50 else ch_top

                # 1. Detectar Ciudad en el texto (o usar el selector si no especificó otra)
                ciu_q = None
                alias_mun = {"JINOTEPE": "CARAZO", "DIRIAMBA": "CARAZO", "SAN MARCOS": "CARAZO", "NANDAIME": "GRANADA", "NINDIRI": "MASAYA", "SAN JORGE": "RIVAS", "JUIGALPA": "CHONTALES"}
                for c_r in LISTA_CIUDADES_REALES:
                    if normalizar_txt(c_r) in t_norm:
                        ciu_q = c_r; break
                if not ciu_q:
                    for mun, dep in alias_mun.items():
                        if mun in t_norm:
                            ciu_q = next((c for c in LISTA_CIUDADES_REALES if dep in normalizar_txt(c)), dep); break
                if not ciu_q and ch_ciu != "TODO MI PANEL":
                    ciu_q = ch_ciu

                # 2. Detectar Clase Terapéutica o Marca en el texto (ej. "expectorantes", "biotos", "talerdin", "antihistaminicos")
                mer_q = resolver_clave_mercado_gutis(t_norm)
                if not mer_q and ch_mer != "TODOS LOS MERCADOS":
                    mer_q = ch_mer

                # 3. Detectar Especialidad
                esp_q = None
                for e_r in LISTA_ESPECIALIDADES_REALES:
                    e_n = normalizar_txt(e_r)
                    if e_n in t_norm or any(p[:5] in t_norm for p in re.split(r'[\s/,-]+', e_n) if len(p) >= 4):
                        esp_q = e_r; break
                if not esp_q and ch_esp != "TODAS":
                    esp_q = ch_esp

                # 4. Detectar si pregunta por un Médico específico (solo cuando no es una consulta plural de mercado/ciudad)
                es_plural = any(fp in t_norm for fp in ["CUALES SON", "QUIENES SON", "MEDICOS MAS IMPORTANTES", "ANALISA EL MERCADO", "ANALIZA EL MERCADO", "MERCADO DE", "TOP", "RANKING"])
                med_especifico_q = None
                if not es_plural:
                    universo_m = sorted(list(set(df_panel["Médico"].dropna().unique()).union(set(df_productos["Médico"].dropna().unique()))))
                    palabras_ign = {"PARA", "COMO", "RIVAS", "GRANADA", "MASAYA", "CARAZO", "CHONTALES", "BOACO", "MANAGUA", "TALERDIN", "BIOTOS", "DALIVIO", "GASTROALIVIO", "VENTILAR", "MOMETZONA", "CLEMBROXIL", "MEDICO", "DOCTOR", "DOCTORA", "COMPROMISO", "GUTIS"}
                    toks_u = [w for w in re.split(r'[^A-Z0-9Ñ]+', t_norm) if len(w) >= 4 and w not in palabras_ign]
                    mejor_m, max_c = None, 0
                    for m_cand in universo_m:
                        toks_m = [w for w in re.split(r'[^A-Z0-9Ñ]+', normalizar_txt(m_cand)) if len(w) >= 3]
                        c_hits = sum(1 for tu in toks_u if tu in toks_m)
                        if c_hits > max_c:
                            max_c = c_hits; mejor_m = m_cand
                    if max_c >= 2 or (max_c == 1 and any(ind in t_norm for ind in ["DR ", "DRA ", "DOCTOR", "DOCTORA"])):
                        med_especifico_q = mejor_m

                if med_especifico_q:
                    modo_q = "MEDICO_INDIVIDUAL"
                elif any(k in t_norm for k in ["CRECE", "CRECIMIENTO", "DINAMISMO", "EVOLUCION"]):
                    modo_q = "CRECIMIENTO"
                elif any(k in t_norm for k in ["LABORATORIO", "FABRICANTE", "CASA"]):
                    modo_q = "LABS"
                elif any(k in t_norm for k in ["FUERA DE PANEL", "NO VISITADO", "NO VISITADOS"]):
                    modo_q = "FUERA_PANEL"
                elif any(k in t_norm for k in ["CONQUISTA", "COMPETENCIA", "OPORTUNIDAD"]):
                    modo_q = "CONQUISTA"
                else:
                    modo_q = "PARETO"

            st.session_state.chira_history.append({"role": "user", "content": texto_mostrar})
            with chat_box.chat_message("user"):
                st.markdown(texto_mostrar)

            with st.spinner("Calculando indicadores verificados y estructurando análisis táctico..."):
                if modo_q == "MEDICO_INDIVIDUAL":
                    df_d_med = obtener_desglose_productos_medico(med_especifico_q)
                    md_tabla = df_a_markdown_nativo(df_d_med.head(15))
                    prompt_m = f"""{REGLAS_FARMA}
El usuario consulta sobre el Dr(a). {med_especifico_q}: "{consulta_activa}".
Basándote únicamente en esta tabla auditada, redacta un análisis táctico de 4 viñetas (identificando en qué mercados ya es leal para agradecer/blindar y en cuáles comparte receta con la competencia para hacer puente o migración):
{md_tabla}"""
                    analisis_ia = llamar_gemini(prompt_m) or "Revisa el desglose de cuotas por categoría terapéutica en la tabla superior para priorizar el puente clínico."
                    respuesta_chira = f"### Expediente Auditado: Dr(a). {med_especifico_q}\n\n{md_tabla}\n\n#### Análisis Táctico TVP:\n{analisis_ia}"

                elif modo_q == "CRECIMIENTO":
                    z_lbl = ciu_q or "TODO MI PANEL"
                    df_cr = calcular_crecimiento_mercados_mes_vs_ytd(z_lbl, incluir_fuera_panel=True)
                    respuesta_chira = f"### Evolución de Clases Terapéuticas (Mes vs. YTD) — {z_lbl}\n\n{df_a_markdown_nativo(df_cr)}"

                elif modo_q == "LABS":
                    z_lbl = ciu_q or "TODO MI PANEL"
                    df_lb = obtener_radar_laboratorios_doble_barra(ciudad_sel=z_lbl, esp_sel=esp_q or "TODAS")
                    respuesta_chira = f"### Radar de Laboratorios (Mes vs. YTD) — {z_lbl}\n\n{df_a_markdown_nativo(df_lb.head(top_q))}"

                else:
                    # Búsqueda unificada con expansión automática si el panel local tiene pocos datos
                    modo_p = "FUERA_PANEL" if modo_q == "FUERA_PANEL" else "PANEL"
                    df_rk_q = obtener_ranking_medicos_mercado(ciudad_target=ciu_q, esp_target=esp_q, mer_target=mer_q, modo_panel=modo_p)
                    nota_expansion = ""
                    if df_rk_q.empty and modo_p == "PANEL":
                        # Expandir automáticamente a TODOS (Panel + Fuera de Panel) para jamás dejar en blanco
                        df_rk_q = obtener_ranking_medicos_mercado(ciudad_target=ciu_q, esp_target=esp_q, mer_target=mer_q, modo_panel="TODOS")
                        if not df_rk_q.empty:
                            nota_expansion = "_Nota: Se incluyen prescriptores de toda la auditoría Close-Up para mostrar el universo completo de la categoría._\n\n"

                    if not df_rk_q.empty:
                        if modo_q == "CONQUISTA":
                            df_rk_q = df_rk_q.sort_values(by=["Comp Mes", "Comp YTD", "Pxs Mes"], ascending=[False, False, False])
                        z_lbl = ciu_q or "TODO MI PANEL"
                        m_lbl = f"{MERCADOS_PRIORITARIOS[mer_q]['producto']} ({MERCADOS_PRIORITARIOS[mer_q]['clase_terapeutica']})" if (mer_q and mer_q in MERCADOS_PRIORITARIOS) else (mer_q or "Todas las Clases Terapéuticas")
                        df_vista_q = df_rk_q.head(top_q)[["Médico", "Especialidad", "Cat", "Ciudad", "Pxs Mes", "Gutis Mes", "Comp Mes", "% MS Mes", "Pxs YTD", "% MS YTD", "Escala TVP", "Desglose Marcas [Mes/YTD]"]]
                        md_rk = df_a_markdown_nativo(df_vista_q)

                        prompt_rk = f"""{REGLAS_FARMA}
El usuario preguntó: "{texto_mostrar}".
Con base en esta tabla determinística de {m_lbl} en {z_lbl}, redacta únicamente 3 conclusiones ejecutivas breves indicando:
1) Quiénes son los prescriptores líderes a blindar/agradecer (Lealtad),
2) Quiénes concentran el mayor volumen en manos de la competencia (Oportunidad de Conquista/Expansión) y qué marcas rivales recetan,
3) Qué acción inmediata ejecutar en la ruta. No alteres ninguna cifra:
{md_rk}"""
                        analisis_rk = llamar_gemini(prompt_rk) or "Prioriza el blindaje y puente en los médicos en escalón de Lealtad y enfoca la conquista en los especialistas con mayor columna 'Comp Mes' y 'Comp YTD'."
                        respuesta_chira = f"### Análisis de Mercado y Prescriptores Clave | {m_lbl} — {z_lbl}\n{nota_expansion}{md_rk}\n\n#### Conclusiones y Plan de Acción Táctico:\n{analisis_rk}"
                    else:
                        # Mostrar el resumen general de los mercados activos de esa ciudad para nunca responder en blanco
                        df_cr_fallback = calcular_crecimiento_mercados_mes_vs_ytd(ciu_q or "TODO MI PANEL", incluir_fuera_panel=True)
                        respuesta_chira = f"### Radiografía de Clases Terapéuticas Activas en {ciu_q or 'TODO MI PANEL'}\n\n{df_a_markdown_nativo(df_cr_fallback)}"

            st.session_state.chira_history.append({"role": "assistant", "content": respuesta_chira})
            st.rerun()

    # COLUMNA DERECHA: BITÁCORA CRM CON GUARDADO VERIFICADO
    with col_ch_der:
        st.markdown(f"##### BITÁCORA CRM POST-VISITA (UNIDAD 9) — {medico_sel[:22]}")
        with st.form("form_crm_verificado"):
            c1, c2 = st.columns(2)
            with c1: p_foco = st.selectbox("1. Producto Foco (P1):", [m["producto"] for m in MERCADOS_PRIORITARIOS.values()])
            with c2: p_puente = st.selectbox("2. Producto Puente (P2):", ["Ninguno"] + [m["producto"] for m in MERCADOS_PRIORITARIOS.values()], index=2)
            c3, c4 = st.columns(2)
            with c3: res_smart = st.selectbox("3. Resultado SMART:", ["Objetivo Principal Logrado", "Objetivo de Respaldo Logrado", "Seguimiento Pendiente"])
            with c4: esc_alc = st.selectbox("4. Escalón Alcanzado:", ["1. No Consciente", "2. Consciente", "3. Prueba (2-10 Pxs)", "4. Adopción (25-50%)", "5. Lealtad (>50%)"])
            ac_med = st.text_input("Compromiso del Médico:", value="Consolidar prescripción y puente clínico")
            ac_vis = st.text_input("Compromiso del Visitador:", value="Garantizar inventario en farmacias aliadas")
            notas_crm = st.text_area("Observaciones Clínicas y Próxima Apertura:", height=70)

            if st.form_submit_button("Registrar Visita en Bitácora CRM", use_container_width=True, type="primary"):
                reg_visita = {
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Ciudad": ciudad,
                    "Médico": medico_sel,
                    "Especialidad": especialidad,
                    "Producto_Foco": p_foco,
                    "Producto_Puente": p_puente,
                    "Logro_SMART": res_smart,
                    "Escala_TVP": esc_alc,
                    "Acuerdo_Medico": ac_med,
                    "Acuerdo_Visitador": ac_vis,
                    "Notas": notas_crm
                }
                st.session_state.bitacora_memoria.append(reg_visita)
                try:
                    if os.path.exists(ARCHIVO_BITACORA):
                        df_old = pd.read_excel(ARCHIVO_BITACORA)
                        df_new = pd.concat([df_old, pd.DataFrame([reg_visita])], ignore_index=True)
                    else:
                        df_new = pd.DataFrame([reg_visita])
                    df_new.to_excel(ARCHIVO_BITACORA, index=False)
                    if os.path.exists(ARCHIVO_BITACORA) and os.path.getsize(ARCHIVO_BITACORA) > 0:
                        st.success(f"Visita a {medico_sel} guardada y verificada en {ARCHIVO_BITACORA}.")
                    else:
                        st.warning("La visita se guardó en la memoria de la sesión actual, pero no se pudo verificar el archivo en disco.")
                except Exception as e_save:
                    st.error(f"Error al escribir en disco ({e_save}). El registro se mantiene en la sesión para descarga CSV.")

        df_hist_crm = pd.DataFrame(st.session_state.bitacora_memoria)
        if os.path.exists(ARCHIVO_BITACORA):
            try:
                df_hist_crm = pd.read_excel(ARCHIVO_BITACORA)
            except Exception:
                pass
        if not df_hist_crm.empty:
            st.dataframe(df_hist_crm.tail(6), hide_index=True, use_container_width=True, height=190)
            csv_b = df_hist_crm.to_csv(index=False).encode("utf-8-sig")
            st.download_button("Descargar Bitácora CRM Completa (CSV)", data=csv_b, file_name=f"Bitacora_CRM_Gutis_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)
