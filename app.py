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

# --- MOTOR DE NORMALIZACIÓN VECTORIZADA EN C (ULTRARRÁPIDO) ---
TABLA_SIN_ACENTOS = str.maketrans(
    "ÁÉÍÓÚÜÀÈÌÒÙÂÊÎÔÛáéíóúüàèìòùâêîôû",
    "AEIOUUAEIOUAEIOUaeiouuaeiouaeiou"
)

def normalizar_txt(texto):
    if pd.isna(texto):
        return ""
    return str(texto).strip().upper().translate(TABLA_SIN_ACENTOS)

def normalizar_serie_rapida(serie):
    return serie.fillna("").astype(str).str.strip().str.upper().str.translate(TABLA_SIN_ACENTOS)

def df_a_markdown_nativo(df):
    if df is None or df.empty:
        return "_Sin registros disponibles._"
    cols = [str(c) for c in df.columns]
    encabezado = "| " + " | ".join(cols) + " |"
    separador = "| " + " | ".join(["---"] * len(cols)) + " |"
    filas = [encabezado, separador]
    for row in df.itertuples(index=False):
        valores = [str(val).replace("|", "/") for val in row]
        filas.append("| " + " | ".join(valores) + " |")
    return "\n".join(filas)

# --- FORMATEADORES INTELIGENTES DE NOMBRES MÉDICOS Y SKUS DE CLOSE-UP ---
def formatear_nombre_medico(nombre_raw):
    if not nombre_raw or pd.isna(nombre_raw):
        return "Especialista"
    partes = [p.capitalize() for p in str(nombre_raw).replace("#", "ñ").strip().split() if len(p) > 1]
    if len(partes) >= 4:
        return f"{partes[2]} {partes[0]}"
    elif len(partes) == 3:
        return f"{partes[2]} {partes[0]}"
    elif len(partes) == 2:
        return f"{partes[1]} {partes[0]}"
    return str(nombre_raw).title()

def limpiar_sku_competencia(sku_raw):
    if not sku_raw or pd.isna(sku_raw) or "SIN COMPETIDOR" in str(sku_raw).upper():
        return "la marca tradicional", "presentación convencional", "la competencia de la categoría"
    s = str(sku_raw).strip()
    s_up = s.upper()

    forma_f = "presentación habitual"
    if any(k in s_up for k in ["GOT", "GTS", "DROP"]):
        forma_f = "Solución Gotas"
    elif any(k in s_up for k in ["JAR", "JBE", "SUSP", "SOL OR", "SYR", "LIQ"]):
        forma_f = "Jarabe / Suspensión oral"
    elif any(k in s_up for k in ["SPRAY", "NAS", "AER", " INH"]):
        forma_f = "Spray nasal"
    elif any(k in s_up for k in ["AMP", "INY", "VIAL", "JGA"]):
        forma_f = "Ampolla inyectable"
    elif any(k in s_up for k in ["SOB", "STICK", "GRAN", "POLV"]):
        forma_f = "Sobres / Granulado"
    elif any(k in s_up for k in ["CREM", "UNG", "POM", "GEL", "TOP"]):
        forma_f = "Crema / Ungüento tópico"
    elif any(k in s_up for k in ["TAB", "COMP", "CAP", "GRAG"]):
        forma_f = "Tabletas / Cápsulas"

    partes_guion = s.split("-")
    izquierda = partes_guion[0].strip()
    tokens_izq = izquierda.split()
    if len(tokens_izq) > 1 and len(tokens_izq[-1]) in [2, 3, 4]:
        marca_limpia = " ".join(tokens_izq[:-1]).title()
    else:
        marca_limpia = izquierda.title()

    if not marca_limpia:
        marca_limpia = s.split()[0].title()

    return marca_limpia, forma_f, f"{marca_limpia} ({forma_f})"

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
        "paciente_meta": "Pacientes con rinitis alérgica, conjuntivitis alérgica, urticaria crónica o prurito que requieren control antihistamínico seguro",
        "paciente_meta_ped": "Pacientes pediátricos y lactantes con rinitis alérgica, urticaria o prurito que requieren alivio seguro sin irritación gástrica",
        "caracteristica": "Cetirizina en Tabletas (10 mg), Jarabe (60 ml 100% libre de alcohol) y Solución Gotas (10 ml: 1 gota por cada 2 kg de peso en menores de 2 años)",
        "beneficio": "garantiza apego total al tratamiento sin rechazo por sabor ni efectos adversos gástricos asociados a excipientes alcohólicos",
        "arg_imagen": "proyecta ante los padres y el paciente una prescripción de alta pureza galénica que evita molestias gástricas y asegura noches tranquilas desde la primera dosis",
        "arg_finanzas": "optimiza la economía familiar gracias a su concentración exacta (1 gota por cada 2 kg en lactantes y jarabe de alto rendimiento) que evita desperdicios o recompras por rechazo",
        "nicho_flanqueo": "lactantes y pacientes con mucosa gástrica sensible o intolerancia al excipiente alcohólico de otros antihistamínicos",
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
        "paciente_meta": "Pacientes con tos seca, tos con flemas y secreción nasal en resfriado común, bronquitis, rinosinusitis y faringitis viral",
        "paciente_meta_ped": "Pacientes pediátricos (desde los 2 años) con IVRS virales, tos seca o productiva y dificultad para expulsar secreciones",
        "caracteristica": "Fórmula fitofarmacológica dual única: Hedera hélix (35 mg) + Pelargonium sidoides (12.5 mg) en presentación Pediátrica (120 ml) y Adulto (170 ml)",
        "beneficio": "alivia la tos seca y con flemas mientras estimula los mecanismos defensivos antivirales y antibacterianos mediante su efecto inmunorregulador",
        "arg_imagen": "posiciona su receta un paso adelante del mucolítico tradicional, resolviendo tanto el síntoma de la tos como la respuesta inmune local para evitar recaídas",
        "arg_finanzas": "integra en un solo frasco (120 ml pediátrico o 170 ml adulto) la acción expectorante, antitusiva e inmunomoduladora, evitando que el paciente gaste en dos jarabes por separado",
        "nicho_flanqueo": "pacientes con cuadros respiratorios virales donde un expectorante simple (solo Hedera o químico aislado) no aporta acción inmunorreguladora",
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
        "paciente_meta": "Pacientes con patologías respiratorias agudas y crónicas que cursan con retención de secreciones y broncoespasmo",
        "paciente_meta_ped": "Pacientes pediátricos y lactantes con broncoespasmo, sibilancias y retención severa de flemas (dosificación exacta a 2 gotas por kg de peso)",
        "caracteristica": "Sinergia de Ambroxol (7.5 mg) + Clenbuterol (5 mcg) en Jarabe (120 ml) y Solución Gotas Pediátricas (20 ml), 100% libre de azúcar y alcohol",
        "beneficio": "dilata el bronquio y fluidifica el moco simultáneamente, despejando la vía aérea sin irritación por azúcar o alcohol",
        "arg_imagen": "respalda su diagnóstico en cuadros obstructivos complejos con un alivio respiratorio rápido que la familia percibe desde las primeras tomas",
        "arg_finanzas": "ofrece un frasco gotero de 20 ml (el doble de volumen habitual) o jarabe de 120 ml libre de azúcar y alcohol que cubre el esquema completo con un solo envase",
        "nicho_flanqueo": "pacientes con tos espástica y cierre bronquial donde un mucolítico simple no resuelve el broncoespasmo",
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
        "paciente_meta": "Pacientes con rinitis alérgica u obstrucción nasal inflamatoria que requieren control local sin irritación",
        "paciente_meta_ped": "Pacientes pediátricos (2 a 11 años: 1 pulsación al día) y adolescentes con rinitis alérgica y congestión nasal persistente",
        "caracteristica": "Mometasona furoato al 0.05% en spray nasal acuoso (140 aplicaciones), suspensión 100% libre de alcohol",
        "beneficio": "desinflama la mucosa nasal desde la primera aplicación diaria sin causar ardor, resequedad ni epistaxis",
        "arg_imagen": "asegura que el paciente cumpla el tratamiento nasal sin quejarse de ardor o sangrado gracias a su vehículo acuoso libre de alcohol",
        "arg_finanzas": "entrega 140 dosis exactas de alta estabilidad que garantizan más de un mes completo de control continuo a un costo altamente competitivo",
        "nicho_flanqueo": "pacientes con mucosa nasal hipersensible que abandonan otros sprays de la categoría por ardor o excipientes alcohólicos",
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
        "paciente_meta": "Pacientes con asma bronquial o rinitis alérgica que requieren control preventivo nocturno",
        "paciente_meta_ped": "Pacientes pediátricos desde los 6 meses hasta los 14 años con hiperreactividad bronquial, asma o rinitis alérgica",
        "caracteristica": "Montelukast sódico en 3 presentaciones: 4 mg masticable sabor naranja (6 meses a 5 años), 5 mg masticable sabor tutti-chicle (6 a 14 años) y 10 mg recubierto",
        "beneficio": "logra excelente adherencia pediátrica por su sabor agradable y control sostenido de leucotrienos con una sola toma nocturna",
        "arg_imagen": "consolida el control preventivo a largo plazo evitando crisis nocturnas y visitas de urgencia",
        "arg_finanzas": "permite sostener terapias preventivas prolongadas mes a mes con accesibilidad económica real para la familia",
        "nicho_flanqueo": "pacientes en control preventivo continuo que abandonan otros esquemas por costo o rechazo al sabor",
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
        "paciente_meta": "Pacientes adultos con ERGE, gastropatía por AINEs, hiperclorhidria o en erradicación de Helicobacter pylori",
        "paciente_meta_ped": "Pacientes adolescentes mayores y adultos con ERGE o gastritis erosiva",
        "caracteristica": "Esomeprazol 40 mg en cápsulas de liberación retardada con micropellets gastrorresistentes (libre de gluten y lactosa) + Plan Paciente 2+1",
        "beneficio": "brinda protección gástrica y control ácido por 24 horas completas, respaldado por el Plan Paciente 2+1 (compra 2 cajas y recibe 1 gratis)",
        "arg_imagen": "asegura la remisión sintomática desde los primeros días evitando el reflujo nocturno gracias a la tecnología de micropellets",
        "arg_finanzas": "otorga un ahorro directo del 33% mediante el Plan Paciente 2+1 en farmacia, logrando que el paciente complete las 4 a 8 semanas sin abandonar por precio",
        "nicho_flanqueo": "pacientes con ERGE nocturno donde otros IBPs de la clase no sostienen las 24 horas o el paciente abandona el tratamiento al segundo mes por costo",
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
        "paciente_meta": "Pacientes adultos con dolor agudo de moderado a intenso (musculoesquelético, dismenorrea, odontalgia, cólico renal o dolor postoperatorio)",
        "paciente_meta_ped": "Pacientes adolescentes mayores con dolor agudo traumático, odontalgia o dismenorrea",
        "caracteristica": "Dexketoprofeno en 3 vías (Tabletas 25 mg, Solución oral bebible 25 mg/10 ml e Inyectable 50 mg/2 ml) + Dalivio Tramax (Dexketoprofeno 25 mg + Tramadol 75 mg para analgesia multimodal)",
        "beneficio": "proporciona alivio rápido y potente del dolor agudo en minutos (sobre bebible o ampolla) y analgesia multimodal en dolor severo",
        "arg_imagen": "le devuelve la movilidad y el alivio al paciente en los primeros 15 a 30 minutos con menor carga racémica sobre la mucosa gástrica",
        "arg_finanzas": "permite el rescate rápido en sobre bebible o ampolla y la continuidad exacta en tabletas sin requerir gastroprotección adicional costosa en esquemas cortos",
        "nicho_flanqueo": "pacientes con dolor agudo severo donde otros AINEs de la clase tardan más en actuar o irritan la mucosa gástrica",
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
            "RELAJANTE MUSCULAR", "M03B", "TIZANIDINA", "CICLOBENZAPRINA", "SIRDALUD", "DORIXINA RELAX"
        ],
        "paciente_meta": "Pacientes adultos y adolescentes (>16 años) con contracturas musculares, cervicalgia, dorsalgia o lumbalgia aguda",
        "paciente_meta_ped": "Adolescentes a partir de los 16 años con contracturas musculares deportivas o posturales",
        "caracteristica": "Conflexil (Tiocolchicósido 4 mg y Fuerte 8 mg que NO produce sueño) + Conflexil Plus Tabletas y Conflexil Plus Shot (bebible en stick pack con Tiocolchicósido 4 mg + Diclofenaco potásico 50 mg, aprobado por Guías ACP)",
        "beneficio": "ejerce triple acción (analgésica, antiinflamatoria y miorrelajante) de rápida absorción en Shot bebible, recuperando la movilidad sin sedación diurna",
        "arg_imagen": "resuelve la contractura muscular permitiendo que el paciente siga trabajando y conduciendo sin la somnolencia de otros relajantes centrales",
        "arg_finanzas": "reúne en un solo stick bebible o tableta el miorrelajante y el antiinflamatorio potásico de acción rápida, ahorrando la compra de dos fármacos",
        "nicho_flanqueo": "pacientes laboralmente activos con lumbalgia o contractura que no pueden permitirse la somnolencia de otros miorrelajantes",
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
        "paciente_meta": "Pacientes con procesos inflamatorios severos, crisis alérgicas agudas o patologías articulares que requieren corticoterapia de doble acción",
        "paciente_meta_ped": "Pacientes con cuadros alérgicos o inflamatorios agudos severos que requieren control inmediato y sostenido",
        "caracteristica": "Fosfato sódico de Betametasona + Dipropionato de Betametasona en ampolla de 1 ml y 2 ml con viscosidad adecuada y óptima homogeneidad",
        "beneficio": "asegura doble acción comprobada: inicio rápido a los 30 minutos (fosfato) y efecto prolongado hasta por 30 días (dipropionato) en una aplicación suave",
        "arg_imagen": "evita el dolor en el sitio de inyección gracias a su micronización homogénea y previene el efecto rebote de los corticoides de acción corta",
        "arg_finanzas": "resuelve el cuadro agudo y sostiene el control inflamatorio en una sola aplicación sin necesidad de múltiples ampollas",
        "nicho_flanqueo": "cuadros inflamatorios o alérgicos agudos donde un corticoide simple pierde efecto rápido y genera recaída",
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
        "paciente_meta": "Pacientes adultos con dolor articular inflamatorio, desgaste de cartílago o enfermedades degenerativas articulares",
        "paciente_meta_ped": "Adolescentes deportistas con sobrecarga articular",
        "caracteristica": "Fórmula pentavalente en sticks sabor naranja: Colágeno 100% hidrolizado bioactivo (10 g) + Cúrcuma longa (400 mg) + N-AcetilGlucosamina (1000 mg) + Condroitina (800 mg) + Vitamina C (60 mg)",
        "beneficio": "nutre el cartílago y controla el dolor e inflamación articular gracias a los curcuminoides, sin azúcar, sin lactosa y bajo en sodio",
        "arg_imagen": "ofrece al paciente con desgaste articular el condroprotector más completo del mercado que disminuye la rigidez y el dolor desde el primer mes",
        "arg_finanzas": "integra 5 componentes terapéuticos en un solo sobre diario, evitando el gasto en colágeno y glucosamina por separado",
        "nicho_flanqueo": "pacientes con artrosis donde un colágeno simple sin cúrcuma ni glucosamina no alivia el dolor articular",
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
        "paciente_meta": "Pacientes con infecciones bacterianas primarias de la piel (impétigo, foliculitis, furunculosis) o secundarias (heridas, cortaduras, quemaduras)",
        "paciente_meta_ped": "Pacientes pediátricos (desde los 2 meses de edad) con impétigo, foliculitis o heridas sobreinfectadas",
        "caracteristica": "Mupirocina al 2% en ungüento tópico (tubo de 15 g), seguro en adultos y niños desde los 2 meses de edad",
        "beneficio": "logra erradicación bacteriana localizada altamente eficaz con excelente tolerabilidad cutánea",
        "arg_imagen": "asegura resolución rápida de infecciones cutáneas estafilocócicas y estreptocócicas sin riesgo de resistencia cruzada con antibióticos sistémicos",
        "arg_finanzas": "su tubo de 15 g rinde el tratamiento tópico completo para toda la lesión sin requerir un segundo envase",
        "nicho_flanqueo": "infecciones cutáneas o heridas donde otros antibióticos tópicos ya presentan resistencia",
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
        "paciente_meta": "Pacientes (>12 años y adultos) con dermatitis inflamatorias complicadas con infecciones por bacterias y/o hongos (piodermias, tiñas)",
        "paciente_meta_ped": "Pacientes mayores de 12 años con dermatitis alérgica o por contacto sobreinfectada con hongos o bacterias",
        "caracteristica": "Fórmula cuádruple en crema (15 g): Betametasona (0.5 mg) + Gentamicina (1 mg) + Tolnaftato (10 mg) + Yodoclorohidroxiquinoleína (10 mg)",
        "beneficio": "controla simultáneamente la inflamación, el prurito, la infección bacteriana y la micosis en lesiones dérmicas mixtas",
        "arg_imagen": "frena el prurito y la inflamación desde las primeras aplicaciones mientras cubre tanto bacterias como hongos",
        "arg_finanzas": "resuelve lesiones dérmicas mixtas en un solo tubo de 15 g de alta cosmética médica",
        "nicho_flanqueo": "dermatitis mixtas rebeldes donde una crema simple no cubre hongos y bacterias a la vez",
        "love_brand": "Resolución integral para afecciones complejas de la piel."
    },
    "MR FEMGYL": {
        "producto": "Femgyl",
        "clase_terapeutica": "Anticonceptivos Hormonales Inyectables (G03A)",
        "prioridad": 3,
        "categoria_mercado": "Prioridad 3 (Complemento)",
        "apto_pediatria": False,
        "terminos_busqueda": ["FEMGYL", "NORETISTERONA", "MESIGYNA", "ANTICONCEPTIVO INYECTABLE"],
        "paciente_meta": "Pacientes en edad reproductiva que buscan anticoncepción hormonal mensual cómoda y segura",
        "paciente_meta_ped": "Pacientes ginecológicas en control anticonceptivo",
        "caracteristica": "Enantato de noretisterona (50 mg) + Valerato de estradiol (5 mg) en ampolla de 1 ml de aplicación mensual fecha calendario",
        "beneficio": "ofrece alta eficacia anticonceptiva en una sola aplicación mensual que evita olvidos diarios",
        "arg_imagen": "brinda seguridad anticonceptiva con excelente control del ciclo menstrual",
        "arg_finanzas": "esquema mensual accesible con calidad hormonal certificada",
        "nicho_flanqueo": "usuarias que olvidan la toma diaria de tabletas orales",
        "love_brand": "Tranquilidad y confianza mensual en salud femenina."
    },
    "MR NORGYLEN": {
        "producto": "Norgylen",
        "clase_terapeutica": "Anticonceptivos Hormonales Orales (G03A)",
        "prioridad": 3,
        "categoria_mercado": "Prioridad 3 (Complemento)",
        "apto_pediatria": False,
        "terminos_busqueda": ["NORGYLEN", "LEVONORGESTREL", "ETINILESTRADIOL", "MICROGYNON", "ANTICONCEPTIVO ORAL"],
        "paciente_meta": "Pacientes que requieren anticoncepción oral hormonal combinada confiable",
        "paciente_meta_ped": "Pacientes ginecológicas en regulación de ciclo o anticoncepción",
        "caracteristica": "Levonorgestrel (0.15 mg) + Etinilestradiol (0.03 mg) en caja con 21 tabletas recubiertas",
        "beneficio": "garantiza control predecible del ciclo menstrual con alta eficacia y seguridad",
        "arg_imagen": "estabilidad hormonal confiable respaldada por Gutis",
        "arg_finanzas": "alta accesibilidad mensual para la continuidad anticonceptiva",
        "nicho_flanqueo": "pacientes que buscan estabilidad hormonal oral con respaldo farmacéutico",
        "love_brand": "Cuidado confiable todos los días para la mujer."
    },
    "MR ANSIOLIT": {
        "producto": "Ansiolit",
        "clase_terapeutica": "Ansiolíticos Benzodiazepínicos (N05B)",
        "prioridad": 3,
        "categoria_mercado": "Prioridad 3 (Complemento)",
        "apto_pediatria": False,
        "terminos_busqueda": ["ANSIOLIT", "ALPRAZOLAM", "ANSIOLITICO", "ANSIOLITICOS", "N05B", "TAFIL"],
        "paciente_meta": "Pacientes adultos con ansiedad generalizada, ansiedad asociada a depresión o estados de pánico",
        "paciente_meta_ped": "Pacientes adultos en manejo de ansiedad",
        "caracteristica": "Alprazolam 0.5 mg en tabletas ranuradas para dosificación individualizada",
        "beneficio": "logra rápido control de las crisis de ansiedad y síntomas somáticos asociados",
        "arg_imagen": "permite titular la dosis con precisión gracias a su tableta ranurada de alta uniformidad",
        "arg_finanzas": "tratamiento ansiolítico accesible y seguro",
        "nicho_flanqueo": "pacientes con crisis de angustia o insomnio por ansiedad aguda",
        "love_brand": "Paz mental y control oportuno en trastornos de ansiedad."
    },
    "MR DEPAX": {
        "producto": "Depax",
        "clase_terapeutica": "Antidepresivos ISRS - Sertralina (N06A)",
        "prioridad": 3,
        "categoria_mercado": "Prioridad 3 (Complemento)",
        "apto_pediatria": False,
        "terminos_busqueda": ["DEPAX", "SERTRALINA", "ALTRULINE", "ZOLOFT"],
        "paciente_meta": "Pacientes adultos con depresión, TOC, trastorno de pánico, estrés postraumático o fobia social",
        "paciente_meta_ped": "Pacientes en manejo por neurociencias",
        "caracteristica": "Sertralina 50 mg en tabletas recubiertas con Sello de Bioequivalencia Comprobada",
        "beneficio": "garantiza idéntica biodisponibilidad y eficacia clínica que el innovador con un costo accesible para el apego a largo plazo",
        "arg_imagen": "le otorga la certeza clínica de prescribir una Sertralina con Bioequivalencia Comprobada",
        "arg_finanzas": "evita el abandono del tratamiento crónico al ofrecer bioequivalencia certificada a una fracción del costo del innovador",
        "nicho_flanqueo": "pacientes crónicos que necesitan seguridad bioequivalente certificada",
        "love_brand": "Bioequivalencia comprobada para acompañar la recuperación emocional."
    },
    "MR FELICITAT": {
        "producto": "Felicitat",
        "clase_terapeutica": "Antidepresivos ISRS - Escitalopram (N06A)",
        "prioridad": 3,
        "categoria_mercado": "Prioridad 3 (Complemento)",
        "apto_pediatria": False,
        "terminos_busqueda": ["FELICITAT", "ESCITALOPRAM", "LEXAPRO", "ANTIDEPRESIVO", "N06A"],
        "paciente_meta": "Pacientes adultos con episodios depresivos mayores, trastorno de angustia o ansiedad generalizada",
        "paciente_meta_ped": "Pacientes en manejo de estado de ánimo",
        "caracteristica": "Escitalopram en presentaciones de 10 mg y 20 mg (30 tabletas recubiertas) con acción dual en el receptor SERT",
        "beneficio": "ofrece inhibición altamente selectiva de la recaptación de serotonina para una mejoría emocional sostenida",
        "arg_imagen": "alta selectividad serotoninérgica con excelente perfil de tolerabilidad",
        "arg_finanzas": "cajas completas de 30 tabletas en 10 mg y 20 mg que aseguran el mes completo de terapia",
        "nicho_flanqueo": "pacientes que requieren ajustar dosis entre 10 mg y 20 mg con excelente tolerabilidad",
        "love_brand": "Ayudar a miles de pacientes a volver a disfrutar de la vida."
    }
}

MARCAS_OFICIALES_GUTIS_NIC = [
    "GASTROALIVIO", "TALERDIN", "DALIVIO", "CONFLEXIL",
    "VALERPAN", "RENOVART", "BIOTOS", "CLEMBROXIL", "MOMETZONA",
    "VENTILAR", "FEMGYL", "NORGYLEN", "BICORPAN", "MUPIRAL",
    "ANSIOLIT", "DEPAX", "FELICITAT"
]

PATRON_REGEX_GUTIS = re.compile(r'\b(' + '|'.join(MARCAS_OFICIALES_GUTIS_NIC) + r')\b')

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
        padding: 15px 26px;
        border-radius: 6px;
        margin-bottom: 14px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 4px 12px rgba(0, 43, 92, 0.18);
    }
    .gutis-brand { font-size: 1.4rem; font-weight: 800; letter-spacing: 0.5px; color: #ffffff; }
    .gutis-brand span { font-size: 0.7rem; font-weight: 600; color: #cbd5e1; display: block; letter-spacing: 1.1px; text-transform: uppercase; }
    .gutis-center-title { font-size: 1.2rem; font-weight: 700; color: #ffffff; letter-spacing: 0.4px; }
    .gutis-bi-badge { text-align: right; font-size: 0.82rem; font-weight: 700; color: #e2e8f0; }
    .gutis-bi-badge span { font-size: 0.66rem; color: #93c5fd; display: block; letter-spacing: 1px; text-transform: uppercase; }

    .ticker-bar {
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-left: 6px solid #002b5c;
        border-radius: 8px;
        padding: 11px 16px;
        margin-bottom: 12px;
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.03);
    }
    .ticker-item { flex: 1 1 190px; border-right: 1px solid #f1f5f9; padding-right: 12px; }
    .ticker-item:last-child { border-right: none; }
    .ticker-label { font-size: 0.66rem; text-transform: uppercase; color: #64748b; font-weight: 800; letter-spacing: 0.7px; }
    .ticker-val { font-size: 1.1rem; font-weight: 800; color: #0f172a; margin-top: 2px; }
    .ticker-sub { font-size: 0.74rem; color: #475569; font-weight: 600; margin-top: 2px; }

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
        padding: 10px 14px;
        transition: all 0.15s ease-in-out;
        box-shadow: 0 2px 5px rgba(0,0,0,0.04);
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
        border-left: 6px solid #38bdf8;
        box-shadow: 0 3px 8px rgba(0, 43, 92, 0.22);
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
        margin-bottom: 12px;
        border-left: 5px solid #38bdf8;
        font-weight: 700;
        font-size: 0.88rem;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    .subnav-label {
        font-size: 0.72rem;
        font-weight: 800;
        text-transform: uppercase;
        color: #475569;
        letter-spacing: 0.6px;
        margin-bottom: 6px;
    }
    .canvas-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin-top: 10px; margin-bottom: 16px; }
    .quad-card { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 16px; box-shadow: 0 2px 5px rgba(0,0,0,0.03); }
    .quad-title { font-size: 0.76rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; padding-bottom: 6px; border-bottom: 2px solid #f1f5f9; }
    .quad-body { font-size: 0.85rem; color: #1e293b; line-height: 1.5; }
    .drill-panel { background: #ffffff; border: 1px solid #cbd5e1; border-top: 4px solid #002b5c; border-radius: 6px; padding: 16px; margin-top: 14px; margin-bottom: 16px; }
</style>
""", unsafe_allow_html=True)

# --- LECTOR CON AUTOCACHÉ BINARIO EN DISCO (.PKL) PARA CARGA EN 0.1 SEGUNDOS ---
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

def leer_excel_ultrarrapido(filepath, sheet_name=0):
    if not filepath or not os.path.exists(filepath):
        return pd.DataFrame()
    try:
        mtime = int(os.path.getmtime(filepath))
        fsize = int(os.path.getsize(filepath))
        nombre_seguro = re.sub(r'[^a-zA-Z0-9_]', '_', os.path.basename(filepath))
        cache_pkl = f".fastcache_{nombre_seguro}_{sheet_name}_{mtime}_{fsize}.pkl"
        if os.path.exists(cache_pkl):
            return pd.read_pickle(cache_pkl)
    except Exception:
        cache_pkl = None

    df = pd.read_excel(filepath, sheet_name=sheet_name)
    if cache_pkl:
        try:
            df.to_pickle(cache_pkl)
        except Exception:
            pass
    return df

def resolver_clave_mercado_gutis(texto_mercado_o_clase, nombre_prod=""):
    t_norm = normalizar_txt(f"{texto_mercado_o_clase} {nombre_prod}")
    if not t_norm or t_norm in ["TOTAL", "NAN", "NONE"]:
        return None
    if any(ex in t_norm for ex in ["VALVIREX", "PRIMABELA", "BELEZA", "GESIMAX", "FLUKIT", "ZITRO"]):
        return None
    for m_key, m_info in MERCADOS_PRIORITARIOS.items():
        if any(normalizar_txt(term) in t_norm for term in m_info["terminos_busqueda"]):
            return m_key
    return None

# --- CARGA Y VECTORIZACIÓN DE ALTO RENDIMIENTO ---
@st.cache_data(show_spinner="Cargando motor analítico de alta velocidad...")
def cargar_datos():
    f_panel = encontrar_archivo_local(["PANEL"]) or "PANEL ERICK 2026.xlsx"
    df_p = leer_excel_ultrarrapido(f_panel)

    f_rx = encontrar_archivo_local(["PRODUCTOS"], ["SEPTIEMBRE", "2026"])
    df_rx = leer_excel_ultrarrapido(f_rx)

    f_labs = encontrar_archivo_local(["LABORATORIOS"], ["SEPTIEMBRE", "2026"])
    df_labs_raw = leer_excel_ultrarrapido(f_labs)

    f_clases = encontrar_archivo_local(["CLASES", "TERAPEUTICAS"], ["SEPTIEMBRE", "2026"])
    df_clases_raw = leer_excel_ultrarrapido(f_clases)

    try:
        df_v1 = leer_excel_ultrarrapido("VENTA PRIMER TRIMESTRE 2026.xlsx")
        if not df_v1.empty: df_v1["Trimestre"] = "Q1"
    except Exception:
        df_v1 = pd.DataFrame()
    try:
        df_v2 = leer_excel_ultrarrapido("VENTAS SEGUNDO TRIMESTRE 2026.xlsx")
        if not df_v2.empty: df_v2["Trimestre"] = "Q2"
    except Exception:
        df_v2 = pd.DataFrame()
    try:
        df_v3 = leer_excel_ultrarrapido("VENTAS TERCER TRIMESTRE 2026.xlsx", sheet_name="Export")
        if not df_v3.empty: df_v3["Trimestre"] = "Q3"
    except Exception:
        try:
            df_v3 = leer_excel_ultrarrapido("VENTAS TERCER TRIMESTRE 2026.xlsx")
            if not df_v3.empty: df_v3["Trimestre"] = "Q3"
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

    col_pxs_mes = next((c for c in df_rx.columns if c.upper() == "PXS-MES"), None) if not df_rx.empty else None
    if not col_pxs_mes and not df_rx.empty:
        col_pxs_mes = next((c for c in df_rx.columns if "MES" in c.upper() and "PXS" in c.upper()), None)

    col_pxs_ytd = next((c for c in df_rx.columns if c.upper() == "PXS-YTD"), None) if not df_rx.empty else None
    if not col_pxs_ytd and not df_rx.empty:
        col_pxs_ytd = next((c for c in df_rx.columns if "YTD" in c.upper() and "PXS" in c.upper()), None)

    if not df_rx.empty:
        if col_pxs_mes and col_pxs_mes in df_rx.columns:
            df_rx[col_pxs_mes] = pd.to_numeric(df_rx[col_pxs_mes], errors="coerce").fillna(0)
        if col_pxs_ytd and col_pxs_ytd in df_rx.columns:
            df_rx[col_pxs_ytd] = pd.to_numeric(df_rx[col_pxs_ytd], errors="coerce").fillna(0)

        col_fab_rx = next((c for c in df_rx.columns if "FABRICANTE" in c.upper() or "LAB" in c.upper()), None)
        prod_norm_s = normalizar_serie_rapida(df_rx["NOMBRE_PRODUCTO"])
        es_gutis_mask = prod_norm_s.str.contains(PATRON_REGEX_GUTIS, na=False)
        if col_fab_rx:
            fab_norm_s = normalizar_serie_rapida(df_rx[col_fab_rx])
            es_gutis_mask = es_gutis_mask | fab_norm_s.str.contains("GUTIS", na=False)
        df_rx["Es_Gutis"] = es_gutis_mask

        df_rx["_clave_combo"] = (
            df_rx["MERCADO"].fillna("").astype(str) + " || " +
            df_rx["CLASE_TERAPEUTICA_ARCHIVO"].fillna("").astype(str) + " || " +
            df_rx["NOMBRE_PRODUCTO"].fillna("").astype(str)
        )
        combos_unicos = df_rx["_clave_combo"].unique()
        mapa_claves = {}
        for combo in combos_unicos:
            partes = combo.split(" || ")
            m_txt = f"{partes[0]} {partes[1]}" if len(partes) > 1 else partes[0]
            p_txt = partes[2] if len(partes) > 2 else ""
            k_m = resolver_clave_mercado_gutis(m_txt, "")
            if not k_m:
                k_m = resolver_clave_mercado_gutis(m_txt, p_txt)
            mapa_claves[combo] = k_m
        df_rx["Clave_Gutis"] = df_rx["_clave_combo"].map(mapa_claves)
        df_rx = df_rx.drop(columns=["_clave_combo"])

        if col_pxs_mes:
            tot_cat_mes = df_rx.groupby(["Médico", "MERCADO"])[col_pxs_mes].transform("sum")
            df_rx["MS_CAT_MES"] = np.where(tot_cat_mes > 0, (df_rx[col_pxs_mes] / tot_cat_mes) * 100.0, 0.0)
        else:
            df_rx["MS_CAT_MES"] = 0.0

        if col_pxs_ytd:
            tot_cat_ytd = df_rx.groupby(["Médico", "MERCADO"])[col_pxs_ytd].transform("sum")
            df_rx["MS_CAT_YTD"] = np.where(tot_cat_ytd > 0, (df_rx[col_pxs_ytd] / tot_cat_ytd) * 100.0, 0.0)
        else:
            df_rx["MS_CAT_YTD"] = 0.0

        if not df_p.empty and "Médico" in df_p.columns:
            df_p_unico = df_p.drop_duplicates(subset=["Médico"]).set_index("Médico")
            mapa_ciu = df_p_unico["CIUDAD"].to_dict() if "CIUDAD" in df_p_unico.columns else {}
            mapa_esp = df_p_unico["Especialidad"].to_dict() if "Especialidad" in df_p_unico.columns else {}
            mapa_cat = df_p_unico["CATEGORIA"].to_dict() if "CATEGORIA" in df_p_unico.columns else {}
            df_rx["CIUDAD_PANEL"] = df_rx["Médico"].map(mapa_ciu).fillna("FUERA DE PANEL")
            df_rx["ESP_PANEL"] = df_rx["Médico"].map(mapa_esp).fillna("ESPECIALISTA")
            df_rx["CAT_PANEL"] = df_rx["Médico"].map(mapa_cat).fillna("S/C")

    if not df_v.empty and "DESCRIPCION_RUTA" in df_v.columns:
        df_v["DESCRIPCION_RUTA"] = df_v["DESCRIPCION_RUTA"].astype(str).str.strip().str.upper()

    archivos_cargados = {
        "panel": f_panel, "rx": f_rx, "labs": f_labs, "clases": f_clases,
        "col_mes": col_pxs_mes, "col_ytd": col_pxs_ytd
    }
    return df_p, df_rx, df_labs_raw, df_clases_raw, df_v, archivos_cargados

df_panel, df_productos, df_labs, df_clases, df_ventas, info_archivos = cargar_datos()
COL_PXS_MES = info_archivos.get("col_mes")
COL_PXS_YTD = info_archivos.get("col_ytd")

LISTA_CIUDADES_REALES = sorted([c for c in df_panel["CIUDAD"].dropna().unique() if str(c).strip() not in ["", "NAN"]]) if not df_panel.empty and "CIUDAD" in df_panel.columns else []
LISTA_ESPECIALIDADES_REALES = sorted([e for e in df_panel["Especialidad"].dropna().unique() if str(e).strip() not in ["", "NAN"]]) if not df_panel.empty and "Especialidad" in df_panel.columns else []
LISTA_MERCADOS_GUTIS_KEYS = list(MERCADOS_PRIORITARIOS.keys())

def diagnosticar_escala_adopcion(pxs_gutis_mes, pxs_tot_mes, ms_gutis_mes, pxs_gutis_ytd=0, pxs_tot_ytd=0, ms_gutis_ytd=0.0):
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

@st.cache_data(show_spinner=False)
def calcular_kpis_globales_hub():
    tot_meds = len(df_panel["Médico"].dropna().unique()) if not df_panel.empty else 0
    if df_productos.empty or df_panel.empty:
        return tot_meds, 0, 0, 0, 0.0, 0, 0, 0.0
    meds_set = set(df_panel["Médico"].dropna().unique())
    sub = df_productos[df_productos["Médico"].isin(meds_set) & df_productos["Clave_Gutis"].notna()]
    activos = len(sub[sub[COL_PXS_YTD] > 0]["Médico"].unique()) if COL_PXS_YTD else 0
    m_tot = int(sub[COL_PXS_MES].sum()) if COL_PXS_MES else 0
    m_gut = int(sub[sub["Es_Gutis"]][COL_PXS_MES].sum()) if m_tot > 0 else 0
    ms_m = (m_gut / m_tot * 100.0) if m_tot > 0 else 0.0
    y_tot = int(sub[COL_PXS_YTD].sum()) if COL_PXS_YTD else 0
    y_gut = int(sub[sub["Es_Gutis"]][COL_PXS_YTD].sum()) if y_tot > 0 else 0
    ms_y = (y_gut / y_tot * 100.0) if y_tot > 0 else 0.0
    return tot_meds, activos, m_tot, m_gut, ms_m, y_tot, y_gut, ms_y

# --- ESTADO GLOBAL DE SESIÓN Y BOTONERAS MODULARES ("UNA COSA A LA VEZ") ---
if "modulo_activo" not in st.session_state:
    st.session_state.modulo_activo = "HUB"
if "medico_activo_global" not in st.session_state:
    st.session_state.medico_activo_global = sorted(df_panel["Médico"].dropna().unique().tolist())[0] if not df_panel.empty else ""
if "chira_history" not in st.session_state:
    st.session_state.chira_history = []
if "tvp_custom_script" not in st.session_state:
    st.session_state.tvp_custom_script = {}
if "tvp_variant_counter" not in st.session_state:
    st.session_state.tvp_variant_counter = 0
if "ultimo_audio_hash" not in st.session_state:
    st.session_state.ultimo_audio_hash = None
if "bitacora_memoria" not in st.session_state:
    st.session_state.bitacora_memoria = []
if "perfiles_memoria" not in st.session_state:
    st.session_state.perfiles_memoria = {}

# Estados de las botoneras internas de cada módulo
if "sub_previsita" not in st.session_state:
    st.session_state.sub_previsita = "MAPA"
if "sub_previsita_auditoria" not in st.session_state:
    st.session_state.sub_previsita_auditoria = "CLASES"
if "sub_top_medicos" not in st.session_state:
    st.session_state.sub_top_medicos = "RANKING"
if "sub_analisis_mercado" not in st.session_state:
    st.session_state.sub_analisis_mercado = "LABS"
if "sub_evolucion" not in st.session_state:
    st.session_state.sub_evolucion = "SINCRONIA"
if "sub_chira" not in st.session_state:
    st.session_state.sub_chira = "COPILOTO"
if "pos_m1_idx" not in st.session_state:
    st.session_state.pos_m1_idx = 0
if "pos_m2_idx" not in st.session_state:
    st.session_state.pos_m2_idx = 1
if "pos_m3_idx" not in st.session_state:
    st.session_state.pos_m3_idx = 2
if "ctx_cita_global" not in st.session_state:
    st.session_state.ctx_cita_global = "Visita con cita previa"
if "ctx_ndn_global" not in st.session_state:
    st.session_state.ctx_ndn_global = "Desempeño (Eficacia y adherencia clínica)"

def ir_a_modulo(nombre_mod, medico_destino=None):
    st.session_state.modulo_activo = nombre_mod
    if medico_destino:
        st.session_state.medico_activo_global = medico_destino
        st.session_state.pos_m1_idx = 0
        st.session_state.pos_m2_idx = 1
        st.session_state.pos_m3_idx = 2

# --- DESCUBRIMIENTO DINÁMICO DE MODELOS GEMINI ---
@st.cache_data(ttl=3600, show_spinner=False)
def obtener_modelos_gemini_activos(api_key):
    modelos_base = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-pro"]
    if not api_key:
        return modelos_base
    try:
        r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}", timeout=4)
        if r.status_code == 200:
            todos = r.json().get("models", [])
            dinamicos = [
                m["name"].replace("models/", "")
                for m in todos
                if "generateContent" in m.get("supportedGenerationMethods", [])
            ]
            for d in reversed(dinamicos):
                if "flash" in d.lower() and d not in modelos_base:
                    modelos_base.insert(0, d)
    except Exception:
        pass
    return modelos_base

def llamar_gemini(prompt_text, max_tok=3500):
    api_key = st.secrets.get("GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {"maxOutputTokens": max_tok, "temperature": 0.35}
    }
    for mod in obtener_modelos_gemini_activos(api_key):
        try:
            url_p = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            res = requests.post(url_p, headers=headers, json=payload, timeout=16)
            if res.status_code == 200:
                cands = res.json().get("candidates", [])
                if cands and "content" in cands[0] and "parts" in cands[0]["content"]:
                    texto_r = cands[0]["content"]["parts"][0].get("text", "").strip()
                    if len(texto_r) > 60:
                        return texto_r
        except Exception:
            continue
    return None

def transcribir_audio_gemini(audio_bytes):
    api_key = st.secrets.get("GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
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
    for mod in obtener_modelos_gemini_activos(api_key):
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

# --- GENERADOR DINÁMICO DE GUIONES TVP (ADAPTADO A ADOPCIÓN, CONTEXTO Y NDN) ---
def construir_guion_tvp_dinamico(
    medico_raw, especialidad, ciudad, m_primario, prod2, benef2, rival2_raw, prod3,
    tipo_cita_sel, nec_detras_sel, top_farmacias_str, num_variante=0, notas_rapport=""
):
    nom_corto = formatear_nombre_medico(medico_raw)
    es_ped = "PEDIAT" in especialidad.upper()
    meta1 = m_primario["meta_info"]
    prod1 = m_primario["prod_gutis"]
    modo_tac = m_primario["modo_tactico"]
    rival_marca, rival_forma, rival_completo = limpiar_sku_competencia(m_primario["rival_principal"])
    rival2_marca, _, _ = limpiar_sku_competencia(rival2_raw)
    paciente_meta = meta1.get("paciente_meta_ped", meta1["paciente_meta"]) if es_ped else meta1["paciente_meta"]
    farmacia_top1 = top_farmacias_str.split(",")[0].strip()

    if "Imagen" in nec_detras_sel:
        enfoque_ndn_titulo = "Prestigio Clínico y Satisfacción del Paciente (NdN: Imagen)"
        argumento_ndn = meta1.get("arg_imagen", meta1["beneficio"])
        pregunta_ndn = f"¿qué impacto tiene en la confianza de la familia cuando el paciente evoluciona sin efectos secundarios ni rechazo a la {rival_forma.lower()}?"
    elif "Finanzas" in nec_detras_sel:
        enfoque_ndn_titulo = "Rendimiento Terapéutico y Economía del Paciente (NdN: Finanzas)"
        argumento_ndn = meta1.get("arg_finanzas", meta1["beneficio"])
        pregunta_ndn = f"¿cuánto influye en el apego al tratamiento completo el hecho de que el paciente no tenga que suspender o gastar doble en farmacia?"
    else:
        enfoque_ndn_titulo = "Eficacia Clínica y Adherencia Terapéutica (NdN: Desempeño)"
        argumento_ndn = meta1["beneficio"]
        pregunta_ndn = f"¿qué aspecto considera prioritario optimizar en rapidez de acción y tolerabilidad frente a {rival_marca} en {rival_forma.lower()}?"

    rap_txt = f" Tenía presente además lo conversado sobre {notas_rapport}." if notas_rapport else ""
    if "Pasillo" in tipo_cita_sel:
        intro_contexto = f"Doctor(a) {nom_corto}, sé que va en movimiento hacia consulta; le tomo literalmente 45 segundos.{rap_txt}"
    elif "Improvisto" in tipo_cita_sel:
        intro_contexto = f"Doctor(a) {nom_corto}, agradezco mucho que me reciba este minuto entre pacientes.{rap_txt}"
    else:
        intro_contexto = f"Doctor(a) {nom_corto}, qué gusto saludarlo(a) en esta visita programada.{rap_txt}"

    v_idx = num_variante % 3

    if modo_tac == "LEALTAD":
        if v_idx == 0:
            return f"""#### Guion Táctico TVP — Socio en Lealtad ({enfoque_ndn_titulo})
1. **Apertura de Reconocimiento y Valoración ({tipo_cita_sel}):**
   > «{intro_contexto} Hoy mi prioridad es agradecerle su respaldo contundente a **{prod1}** ({m_primario['gutis_mes']} recetas en el mes y {m_primario['gutis_ytd']} en el acumulado anual); usted lidera el estándar de cuidado en {ciudad} para **{paciente_meta.lower()}**.»

2. **Sondeo de Blindaje y Validación Clínica:**
   > «En esta amplia experiencia que ya tiene prescribiendo **{prod1}**, {pregunta_ndn} Le confirmo que en **{top_farmacias_str}** ya blindamos el inventario completo de todas nuestras presentaciones para que ninguna receta suya sufra cambios en mostrador.»

3. **El Puente de Autoridad hacia la 2da Posición (`{prod2}`):**
   > «Precisamente porque usted ya comprueba a diario la nobleza galénica de Gutis con **{prod1}** (*{meta1['caracteristica']}*), quiero apoyarme en esa misma confianza para sus pacientes donde requiere **{benef2}** (donde en la categoría aún se observan prescripciones hacia **{rival2_marca}**).»

4. **Cierre Bilateral en el Producto Puente y Recordación (`{prod3}`):**
   > «¿Me permite que esta semana extendamos esa misma alianza iniciando con **{prod2}** en sus próximos 3 a 5 pacientes de este perfil, contando además con **{prod3}** totalmente disponible en **{farmacia_top1}**?»"""
        elif v_idx == 1:
            return f"""#### Variante Táctica II (Enfoque Consultivo de Blindaje + Extensión de Línea)
1. **Apertura Ejecutiva de Socio Estratégico:**
   > «{intro_contexto} Viendo el comportamiento de la categoría de *{m_primario['clase_terapeutica']}* en {ciudad}, **{prod1}** representa el **{m_primario['ms_mes']:.0f}%** de su elección actual. Gracias por esa confianza en nuestra tecnología.»

2. **Pregunta de Retención Activa:**
   > «Para asegurar que el 100% de sus pacientes reciban exactamente el esquema que usted indica ({ 'incluyendo esos ' + str(m_primario['comp_mes']) + ' casos mensuales donde a veces se filtra ' + rival_marca if m_primario['comp_mes'] > 0 else 'manteniendo su fidelidad total' }), ¿hay alguna presentación específica de **{prod1}** que desee que reforcemos hoy mismo en **{farmacia_top1}**?»

3. **Apoyo Cruzado y Salto al Puente (`{prod2}`):**
   > «Con **{prod1}** usted {argumento_ndn}. Esa misma exigencia farmacéutica la tiene disponible en **{prod2}**, diseñado para que en su consulta de **{especialidad}** logre **{benef2}**.»

4. **Acuerdo de Expansión Cruzada:**
   > «Doctor(a) {nom_corto}, mantengamos a **{prod1}** como su referencia indiscutible y démosle la oportunidad a **{prod2}** en los próximos 4 pacientes donde antes consideraba **{rival2_marca}**. ¿Trato hecho?»"""
        else:
            return f"""#### Variante Táctica III (Abordaje de Impacto Rápido y Respaldo en Farmacias Aliadas)
1. **Apertura Directa al Grano:**
   > «{intro_contexto} Vengo con dos objetivos muy concretos: agradecerle que **{prod1}** sea su marca número uno en la categoría y actualizarle nuestra cobertura en **{top_farmacias_str}**.»

2. **Validación de Necesidad detrás de la Necesidad ({nec_detras_sel.split('(')[0].strip()}):**
   > «Sabemos que para usted lo más importante es que el tratamiento **{argumento_ndn}**. ¿Cómo han respondido sus pacientes más recientes con nuestro esquema?»

3. **Conexión Inmediata P1 -> P2 -> P3:**
   > «Así como **{prod1}** le responde sin fallas, hoy tenemos stock garantizado de **{prod2}** y **{prod3}** en **{farmacia_top1}** para respaldar sus esquemas integrales en **{especialidad}**.»

4. **Cierre de Compromiso Dual:**
   > «Cuente con mi gestión personal en las farmacias de {ciudad} para cuidar cada receta suya de **{prod1}**, y acompáñeme esta semana evaluando **{prod2}** en sus próximos casos. ¿Le parece bien?»"""

    elif modo_tac == "EXPANSION":
        if v_idx == 0:
            return f"""#### Guion Táctico TVP — Expansión de Cuota ({enfoque_ndn_titulo})
1. **Apertura de Seguimiento Clínico ({tipo_cita_sel}):**
   > «{intro_contexto} Quiero agradecerle los pacientes que ya está tratando con **{prod1}** ({m_primario['gutis_mes']} en el mes / {m_primario['gutis_ytd']} en el año) y proponerle revisar cómo consolidar la adherencia en **{paciente_meta.lower()}**. ¿Le parece bien?»

2. **Sondeo de Valor Mutuo (Aislar el Segmento que Comparte con `{rival_marca}`):**
   > «Al **comparar** la evolución de sus pacientes tratados con **{prod1}** frente a los casos donde aún indica **{rival_completo}** ({m_primario['comp_mes']} recetas en el mes), ¿en qué perfil específico siente que todavía alterna con esa opción y {pregunta_ndn}»

3. **Apoyo Galénico Diferencial y Love Brand:**
   > «Comprendo perfectamente su criterio, Doctor(a) {nom_corto}. Justamente para cubrir también a ese subgrupo de **{meta1['nicho_flanqueo']}**, **{prod1}** cuenta con **{meta1['caracteristica']}**, con lo cual **{argumento_ndn}**. *{meta1['love_brand']}*»

4. **Cierre de Migración y Puente hacia `{prod2}`:**
   > «Ya que usted conoce de primera mano la respuesta de **{prod1}**, ¿migramos esta semana a esos próximos 4 a 6 pacientes que antes alternaba con **{rival_marca}**, con disponibilidad garantizada en **{top_farmacias_str}**? Y como puente clínico, recuerde que cuenta también con **{prod2}** y **{prod3}**.»"""
        elif v_idx == 1:
            return f"""#### Variante Táctica II (Cierre de Brecha Competitiva frente a {rival_marca})
1. **Apertura Focalizada en Resultados:**
   > «{intro_contexto} Revisando la evolución de sus pacientes en **{especialidad}**, vemos una excelente respuesta en el **{m_primario['ms_mes']:.0f}%** de los casos donde ya prescribe **{prod1}**.»

2. **Pregunta de Descubrimiento de Brecha:**
   > «Noté que en el segmento de *{m_primario['clase_terapeutica']}* todavía hay un grupo de pacientes donde se utiliza **{rival_marca}** en {rival_forma.lower()}. Al **evaluar** ambos esquemas, ¿qué factor le haría sentir total seguridad para unificar toda su categoría en **{prod1}**?»

3. **Demostración de Superioridad Galénica:**
   > «Frente a las presentaciones convencionales, **{prod1}** le asegura **{meta1['caracteristica']}**, lo que significa que **{argumento_ndn}**.»

4. **Cierre de Unificación + Puente a `{prod2}`:**
   > «Hagamos la prueba de unificar sus próximos 5 casos de esta semana bajo **{prod1}** apoyándonos en el inventario de **{farmacia_top1}**, y aprovechemos para incorporar **{prod2}** donde requiera **{benef2}**. ¿Arrancamos hoy?»"""
        else:
            return f"""#### Variante Táctica III (Flanqueo por Subgrupo Clínico y Fidelización)
1. **Apertura Ágil de Consultorio:**
   > «{intro_contexto} Gracias por respaldarnos ya con parte de su recetario en **{prod1}**. Hoy quiero enfocarme específicamente en sus pacientes más difíciles dentro de **{paciente_meta.lower()}**.»

2. **Sondeo de Precisión:**
   > «Cuando recibe a **{meta1['nicho_flanqueo']}**, ¿cómo evita que el paciente interrumpa el esquema que usted le calculó?»

3. **Argumento de Valor ({nec_detras_sel.split('(')[0].strip()}):**
   > «Ahí es donde **{prod1}** marca la diferencia: **{argumento_ndn}**, respaldado con inventario permanente en **{top_farmacias_str}**.»

4. **Cierre de Escalón hacia Lealtad (>50% MS):**
   > «Démosle a ese grupo específico la ventaja de **{prod1}** a partir de su consulta de hoy, y tengámoslo conectado con **{prod2}** como segunda línea. ¿De acuerdo, Doctor(a) {nom_corto}?»"""

    else:
        if v_idx == 0:
            return f"""#### Guion Táctico TVP — Conquista y Flanqueo ({enfoque_ndn_titulo})
1. **Apertura Centrada en el Paciente ({tipo_cita_sel} — Sin mencionar marca):**
   > «{intro_contexto} Quería proponerle analizar brevemente cómo optimizar la rapidez de respuesta y eliminar el abandono terapéutico en **{paciente_meta.lower()}**. ¿Le parece bien revisarlo?»

2. **Sondeo del Embudo frente a `{rival_marca}` (Unidad 4 TVP):**
   > «Actualmente en estos cuadros donde suele prescribirse **{rival_completo}** ({m_primario['comp_mes']} Pxs Mes / {m_primario['comp_ytd']} YTD), al **evaluar** la evolución en las primeras 48 horas, {pregunta_ndn}»

3. **Apoyo Galénico y Storytelling de Marca (Unidad 5 TVP):**
   > «Coincido plenamente con su prioridad, Doctor(a) {nom_corto}. Por ello en Gutis desarrollamos **{prod1}**, que aporta **{meta1['caracteristica']}**, logrando que **{argumento_ndn}**. *{meta1['love_brand']}* ¿No es este el estándar clínico que busca para sus pacientes?»

4. **Cierre de Prueba Inicial y Puente hacia `{prod2}` (Unidad 6 TVP):**
   > «Cuando reciba esta semana a sus próximos 3 a 5 pacientes con este cuadro (especialmente en **{meta1['nicho_flanqueo']}**), ¿iniciamos el período de prueba con **{prod1}** mientras yo le garantizo el stock en **{top_farmacias_str}**? Y conectando con su consulta de **{especialidad}**, cuente también con **{prod2}** y **{prod3}**.»"""
        elif v_idx == 1:
            return f"""#### Variante Táctica II (Técnica de Flanqueo por Nicho Clínico sin Fricción — Unidad 7 TVP)
1. **Apertura de Desarme Psicológico:**
   > «{intro_contexto} Conozco su experiencia manejando *{m_primario['clase_terapeutica']}* y mi intención hoy no es pedirle que cambie de golpe el esquema general que ya utiliza con **{rival_marca}**.»

2. **Pregunta de Grieta Clínica (Nicho Específico):**
   > «Solo quiero consultarle por un subgrupo muy puntual: cuando le llega ese paciente de **{meta1['nicho_flanqueo']}**, ¿qué alternativa utiliza para asegurar que cumpla todo el tratamiento sin molestias?»

3. **Presentación de Solución Focalizada (`{prod1}`):**
   > «Para ese nicho exacto de pacientes, **{prod1}** le ofrece **{meta1['caracteristica']}**, con lo cual **{argumento_ndn}**.»

4. **Cierre de Rescate (2 a 3 Pacientes) + Puente (`{prod2}`):**
   > «No le pido cambiar todo su recetario hoy: solo ponga a prueba a **{prod1}** en sus próximos **3 pacientes de ese perfil específico**, con abastecimiento listo en **{farmacia_top1}**, y evalúe a la par la respuesta de **{prod2}**. ¿Lo ponemos a prueba esta semana?»"""
        else:
            return f"""#### Variante Táctica III (Pregunta Disruptiva de Alto Impacto y Retorno Clínico)
1. **Apertura Disruptiva ({tipo_cita_sel}):**
   > «{intro_contexto} ¿Qué impacto tendría en su consulta de **{especialidad}** eliminar desde hoy el rechazo o incumplimiento al segundo día en **{paciente_meta.lower()}**?»

2. **Sondeo Comparativo:**
   > «Al **comparar** las opciones actuales dentro de la clase terapéutica (como **{rival_marca}** en {rival_forma.lower()}), {pregunta_ndn}»

3. **Evidencia Galénica Gutis:**
   > «Con **{prod1}** usted incorpora **{meta1['caracteristica']}**, garantizando que **{argumento_ndn}**. *{meta1['love_brand']}*»

4. **Acuerdo Bilateral Verificable:**
   > «Doctor(a) {nom_corto}, permítame demostrarle el resultado en terreno: yo aseguro hoy mismo la disponibilidad completa en **{top_farmacias_str}** y usted evalúa a **{prod1}** y **{prod2}** en sus próximos 3 a 5 casos. ¿Trato hecho?»"""

# --- MOTORES ANALÍTICOS CACHEADOS EN RAM ---
def filtrar_df_por_mercado_o_clase(df_in, criterio_mercado=None, prio_num=None):
    if df_in.empty:
        return df_in
    df_out = df_in[df_in["Clave_Gutis"].notna()]
    if prio_num:
        claves_prio = {k for k, v in MERCADOS_PRIORITARIOS.items() if v.get("prioridad") == prio_num}
        df_out = df_out[df_out["Clave_Gutis"].isin(claves_prio)]
    if not criterio_mercado or criterio_mercado in ["TODOS", "TODOS LOS MERCADOS"]:
        return df_out.copy()

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
            else:
                terminos_libres.append(c_norm.replace("MR ", ""))

    mask = pd.Series(False, index=df_out.index)
    if claves_buscadas:
        mask = mask | df_out["Clave_Gutis"].isin(claves_buscadas)
    if terminos_libres:
        texto_fila = normalizar_serie_rapida(
            df_out["MERCADO"].astype(str) + " " +
            df_out["CLASE_TERAPEUTICA_ARCHIVO"].astype(str) + " " +
            df_out["NOMBRE_PRODUCTO"].astype(str)
        )
        for tl in terminos_libres:
            if tl:
                mask = mask | texto_fila.str.contains(re.escape(tl), na=False)
    return df_out[mask].copy()

@st.cache_data(show_spinner=False)
def obtener_desglose_productos_medico(nombre_medico, criterio_mercado=None):
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

    sub["Origen"] = np.where(sub["Es_Gutis"], "GUTIS", "COMPETENCIA")
    mapa_clase = {k: v["clase_terapeutica"] for k, v in MERCADOS_PRIORITARIOS.items()}
    sub["Clase Terapéutica"] = sub["Clave_Gutis"].map(mapa_clase).fillna("")

    if c_m:
        tot_m = sub.groupby("Clave_Gutis")[c_m].transform("sum")
        sub["% MS Mes (Categoría)"] = np.where(tot_m > 0, (sub[c_m] / tot_m * 100.0).round(1), 0.0)
        sub[c_m] = sub[c_m].astype(int)
    if c_y:
        tot_y = sub.groupby("Clave_Gutis")[c_y].transform("sum")
        sub["% MS YTD (Categoría)"] = np.where(tot_y > 0, (sub[c_y] / tot_y * 100.0).round(1), 0.0)
        sub[c_y] = sub[c_y].astype(int)

    cols_sort = [c for c in ["Clave_Gutis", c_m, c_y] if c]
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

@st.cache_data(show_spinner=False)
def obtener_matriz_clases_terapeuticas_corporativa(nombre_medico):
    """
    Reproduce la tabla corporativa de Clases Terapéuticas del Médico (con LY, YTD, Trimestre y Mes si están en el archivo).
    """
    if not df_clases.empty and "Médico" in df_clases.columns:
        sub_c = df_clases[df_clases["Médico"] == nombre_medico].copy()
        if not sub_c.empty:
            col_ct = next((c for c in sub_c.columns if any(k in normalizar_txt(c) for k in ["CLASE", "TERAPEUTICA", "ATC", "MERCADO"])), None)
            if col_ct:
                sub_c = sub_c[~sub_c[col_ct].astype(str).str.upper().isin(["TOTAL", "NAN", "NONE", ""])].copy()
                cols_num = [c for c in sub_c.columns if any(k in c.upper() for k in ["PXS", "MS", "LY", "YTD", "TRIM", "MES"])]
                for cn in cols_num:
                    sub_c[cn] = pd.to_numeric(sub_c[cn], errors="coerce").fillna(0)
                col_ord = next((c for c in cols_num if "YTD" in c.upper() and "PXS" in c.upper()), cols_num[0] if cols_num else None)
                if col_ord:
                    sub_c = sub_c.sort_values(by=col_ord, ascending=False)
                cols_mostrar = [col_ct] + cols_num
                return sub_c[cols_mostrar].reset_index(drop=True)

    # Si df_clases no tiene filas por médico, construir desde df_productos agrupando todas las clases auditadas del médico
    if df_productos.empty or "Médico" not in df_productos.columns:
        return pd.DataFrame()
    sub_p = df_productos[df_productos["Médico"] == nombre_medico].copy()
    if sub_p.empty:
        return pd.DataFrame()

    col_agrup = "CLASE_TERAPEUTICA_ARCHIVO" if ("CLASE_TERAPEUTICA_ARCHIVO" in sub_p.columns and (sub_p["CLASE_TERAPEUTICA_ARCHIVO"] != "").any()) else "MERCADO"
    c_ly = next((c for c in sub_p.columns if "LY" in c.upper() and "PXS" in c.upper()), None)
    c_ytd = COL_PXS_YTD
    c_trim = next((c for c in sub_p.columns if "TRIM" in c.upper() and "PXS" in c.upper()), None)
    c_mes = COL_PXS_MES

    agg_d = {}
    for c_x in [c_ly, c_ytd, c_trim, c_mes]:
        if c_x and c_x in sub_p.columns:
            sub_p[c_x] = pd.to_numeric(sub_p[c_x], errors="coerce").fillna(0)
            agg_d[c_x] = "sum"

    if not agg_d:
        return pd.DataFrame()

    df_g = sub_p.groupby(col_agrup, as_index=False).agg(agg_d).rename(columns={col_agrup: "CLASE TERAPEUTICA"})
    for c_x, lbl_p, lbl_ms in [
        (c_ly, "Pxs-LY", "%MS-LY"),
        (c_ytd, "Pxs-YTD", "%MS-YTD"),
        (c_trim, "Pxs-TRIM", "%MS-TRIM"),
        (c_mes, "Pxs-MES", "%MS-MES")
    ]:
        if c_x and c_x in df_g.columns:
            tot_col = df_g[c_x].sum()
            df_g[lbl_p] = df_g[c_x].astype(int)
            df_g[lbl_ms] = np.where(tot_col > 0, (df_g[c_x] / tot_col * 100.0).round(2), 0.0)

    cols_finales = ["CLASE TERAPEUTICA"]
    for lbl_p, lbl_ms in [("Pxs-LY", "%MS-LY"), ("Pxs-YTD", "%MS-YTD"), ("Pxs-TRIM", "%MS-TRIM"), ("Pxs-MES", "%MS-MES")]:
        if lbl_p in df_g.columns:
            cols_finales += [lbl_p, lbl_ms]

    col_sort_f = "Pxs-YTD" if "Pxs-YTD" in df_g.columns else cols_finales[1]
    df_g = df_g[df_g[col_sort_f] > 0].sort_values(by=col_sort_f, ascending=False).reset_index(drop=True)
    return df_g[cols_finales]

@st.cache_data(show_spinner=False)
def obtener_ranking_medicos_mercado(ciudad_target=None, esp_target=None, mer_target=None, prio_target=None, modo_panel="PANEL"):
    if df_productos.empty:
        return pd.DataFrame()

    rx_sub = filtrar_df_por_mercado_o_clase(df_productos, criterio_mercado=mer_target, prio_num=prio_target)
    if rx_sub.empty:
        return pd.DataFrame()

    todos_panel_set = set(df_panel["Médico"].dropna().unique()) if not df_panel.empty else set()
    if modo_panel == "PANEL":
        rx_sub = rx_sub[rx_sub["Médico"].isin(todos_panel_set)]
    elif modo_panel == "FUERA_PANEL":
        rx_sub = rx_sub[~rx_sub["Médico"].isin(todos_panel_set)]

    if ciudad_target and ciudad_target not in ["TODAS", "TODO MI PANEL"]:
        col_c_doc = next((c for c in rx_sub.columns if c.upper() in ["CIUDAD", "DEPARTAMENTO", "ZONA", "CIUDAD_PANEL"]), "CIUDAD_PANEL")
        mask_ciu = rx_sub["CIUDAD_PANEL"].str.contains(re.escape(ciudad_target.upper()), na=False)
        if col_c_doc != "CIUDAD_PANEL":
            mask_ciu = mask_ciu | rx_sub[col_c_doc].astype(str).str.upper().str.contains(re.escape(ciudad_target.upper()), na=False)
        rx_sub = rx_sub[mask_ciu]

    if esp_target and esp_target not in ["TODAS", "TODAS LAS ESPECIALIDADES"]:
        raiz_e = normalizar_txt(esp_target)[:5]
        col_e_doc = next((c for c in rx_sub.columns if "ESPEC" in c.upper()), "ESP_PANEL")
        mask_esp = normalizar_serie_rapida(rx_sub["ESP_PANEL"]).str.contains(raiz_e, na=False)
        if col_e_doc != "ESP_PANEL":
            mask_esp = mask_esp | normalizar_serie_rapida(rx_sub[col_e_doc]).str.contains(raiz_e, na=False)
        rx_sub = rx_sub[mask_esp]

    if rx_sub.empty:
        return pd.DataFrame()

    c_m = COL_PXS_MES
    c_y = COL_PXS_YTD

    if c_m and c_y:
        rx_sub = rx_sub[(rx_sub[c_m] > 0) | (rx_sub[c_y] > 0)].copy()
    elif c_m:
        rx_sub = rx_sub[rx_sub[c_m] > 0].copy()

    if rx_sub.empty:
        return pd.DataFrame()

    filas = []
    for nom_doc, grp in rx_sub.groupby("Médico", sort=False):
        p_mes_tot = int(grp[c_m].sum()) if c_m else 0
        p_ytd_tot = int(grp[c_y].sum()) if c_y else 0
        if p_mes_tot <= 0 and p_ytd_tot <= 0:
            continue

        grp_g = grp[grp["Es_Gutis"]]
        p_gut_mes = int(grp_g[c_m].sum()) if c_m else 0
        p_gut_ytd = int(grp_g[c_y].sum()) if c_y else 0
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

        top_marcas = [
            f"{r_p.NOMBRE_PRODUCTO} [{int(getattr(r_p, c_m, 0)) if c_m else 0}M/{int(getattr(r_p, c_y, 0)) if c_y else 0}Y]"
            for r_p in grp_ord.head(3).itertuples()
        ]

        esc_act, _, _, _ = diagnosticar_escala_adopcion(p_gut_mes, p_mes_tot, ms_gut_mes, p_gut_ytd, p_ytd_tot, ms_gut_ytd)
        primera_fila = grp.iloc[0]

        filas.append({
            "Médico": nom_doc,
            "Estatus Panel": "EN PANEL" if nom_doc in todos_panel_set else "FUERA DE PANEL",
            "Especialidad": str(primera_fila.get("ESP_PANEL", "ESPECIALISTA")),
            "Cat": str(primera_fila.get("CAT_PANEL", "S/C")),
            "Ciudad": str(primera_fila.get("CIUDAD_PANEL", "NICARAGUA")),
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

@st.cache_data(show_spinner=False)
def calcular_crecimiento_mercados_mes_vs_ytd(ciudad_sel="TODO MI PANEL", incluir_fuera_panel=False):
    if df_productos.empty:
        return pd.DataFrame()
    sub = df_productos[df_productos["Clave_Gutis"].notna()]
    if not incluir_fuera_panel and not df_panel.empty:
        sub = sub[sub["Médico"].isin(set(df_panel["Médico"].dropna().unique()))]
    if ciudad_sel not in ["TODO MI PANEL", "TODAS"]:
        sub = sub[sub["CIUDAD_PANEL"].str.contains(re.escape(ciudad_sel.upper()), na=False)]

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
        grp_g = grp[grp["Es_Gutis"]]
        gut_m = int(grp_g[c_m].sum()) if c_m else 0
        gut_y = int(grp_g[c_y].sum()) if c_y else 0
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

@st.cache_data(show_spinner=False)
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
            df_l_esp = df_l_clean[df_l_clean["Médico"].isin(meds_panel_esp)]
            df_l_esp_act = df_l_esp[df_l_esp[col_ytd_l] > 0]
            meds_captados = set(df_l_esp_act["Médico"].unique())
            num_captados = len(meds_captados)
            recetan_gutis_count, top1_count, top3_count = 0, 0, 0

            if not df_l_esp_act.empty:
                grp_mf = df_l_esp_act.groupby(["Médico", "FABRICANTE"], as_index=False)[col_ytd_l].sum()
                grp_mf = grp_mf.sort_values(by=["Médico", col_ytd_l], ascending=[True, False])
                grp_mf["Rank"] = grp_mf.groupby("Médico").cumcount() + 1
                filas_gut_mf = grp_mf[grp_mf["FABRICANTE"].astype(str).str.upper().str.contains("GUTIS", na=False) & (grp_mf[col_ytd_l] > 0)]
                recetan_gutis_count = len(filas_gut_mf["Médico"].unique())
                top1_count = int((filas_gut_mf["Rank"] == 1).sum())
                top3_count = int((filas_gut_mf["Rank"] <= 3).sum())

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

@st.cache_data(show_spinner=False)
def obtener_radar_laboratorios_doble_barra(ciudad_sel="TODO MI PANEL", esp_sel="TODAS", medico_especifico=None):
    if df_labs.empty or "FABRICANTE" not in df_labs.columns:
        return pd.DataFrame()
    sub_l = df_labs[~df_labs["FABRICANTE"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
    if medico_especifico:
        sub_l = sub_l[sub_l["Médico"] == medico_especifico].copy()
    else:
        df_p_sub = df_panel
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
    agg_d["Médico"] = "nunique"

    rk = sub_l.groupby("FABRICANTE").agg(agg_d).reset_index().rename(columns={"Médico": "Prescriptores"})
    tot_m = rk[col_m].sum() if col_m else 0
    tot_y = rk[col_y].sum() if col_y else 0

    rk["Pxs Mes"] = rk[col_m].astype(int) if col_m else 0
    rk["% MS Mes"] = np.where(tot_m > 0, (rk[col_m] / tot_m * 100.0).round(2), 0.0) if col_m else 0.0
    rk["Pxs YTD"] = rk[col_y].astype(int) if col_y else 0
    rk["% MS YTD"] = np.where(tot_y > 0, (rk[col_y] / tot_y * 100.0).round(2), 0.0) if col_y else 0.0
    rk["Delta MS (Mes vs YTD)"] = (rk["% MS Mes"] - rk["% MS YTD"]).round(2)
    rk["Laboratorio"] = np.where(rk["FABRICANTE"].astype(str).str.upper().str.contains("GUTIS", na=False), "[GUTIS] " + rk["FABRICANTE"].astype(str), rk["FABRICANTE"].astype(str))

    rk = rk.sort_values(by=["Pxs Mes", "Pxs YTD"], ascending=[False, False]).reset_index(drop=True)
    return rk[["Laboratorio", "Prescriptores", "Pxs Mes", "% MS Mes", "Pxs YTD", "% MS YTD", "Delta MS (Mes vs YTD)"]]

# --- MOTOR COGNITIVO AVANZADO DE CHIRA ---
def generar_consultoria_cognitiva_chira_medico(nombre_med, pregunta_usr):
    t_norm = normalizar_txt(pregunta_usr)
    nom_natural = formatear_nombre_medico(nombre_med)
    fila_p = df_panel[df_panel["Médico"] == nombre_med]
    esp_m = str(fila_p.iloc[0].get("Especialidad", "ESPECIALISTA")).upper() if not fila_p.empty else "ESPECIALISTA"
    ciu_m = str(fila_p.iloc[0].get("CIUDAD", "NICARAGUA")).upper() if not fila_p.empty else "NICARAGUA"
    cat_m = str(fila_p.iloc[0].get("CATEGORIA", "S/C")) if not fila_p.empty else "FUERA DE PANEL"
    es_ped_m = "PEDIAT" in esp_m

    rx_m = df_productos[(df_productos["Médico"] == nombre_med) & (df_productos["Clave_Gutis"].notna())].copy()
    if es_ped_m and not rx_m.empty:
        claves_ped = {k for k, v in MERCADOS_PRIORITARIOS.items() if v.get("apto_pediatria", True)}
        rx_m = rx_m[rx_m["Clave_Gutis"].isin(claves_ped)].copy()

    tot_mes = int(rx_m[COL_PXS_MES].sum()) if (not rx_m.empty and COL_PXS_MES) else 0
    tot_ytd = int(rx_m[COL_PXS_YTD].sum()) if (not rx_m.empty and COL_PXS_YTD) else 0
    gut_mes = int(rx_m[rx_m["Es_Gutis"]][COL_PXS_MES].sum()) if tot_mes > 0 else 0
    gut_ytd = int(rx_m[rx_m["Es_Gutis"]][COL_PXS_YTD].sum()) if tot_ytd > 0 else 0
    comp_mes = tot_mes - gut_mes
    comp_ytd = tot_ytd - gut_ytd
    ms_global_m = (gut_mes / tot_mes * 100.0) if tot_mes > 0 else ((gut_ytd / tot_ytd * 100.0) if tot_ytd > 0 else 0.0)

    mercados_doc = []
    if not rx_m.empty:
        for k_g, grp in rx_m.groupby("Clave_Gutis"):
            meta = MERCADOS_PRIORITARIOS.get(k_g, {})
            pm = int(grp[COL_PXS_MES].sum()) if COL_PXS_MES else 0
            py = int(grp[COL_PXS_YTD].sum()) if COL_PXS_YTD else 0
            if pm <= 0 and py <= 0:
                continue
            gm = int(grp[grp["Es_Gutis"]][COL_PXS_MES].sum()) if COL_PXS_MES else 0
            gy = int(grp[grp["Es_Gutis"]][COL_PXS_YTD].sum()) if COL_PXS_YTD else 0
            cm, cy = pm - gm, py - gy
            msm = (gm / pm * 100.0) if pm > 0 else 0.0
            msy = (gy / py * 100.0) if py > 0 else 0.0
            grp_ord = grp.sort_values(by=[COL_PXS_MES, COL_PXS_YTD] if (COL_PXS_MES and COL_PXS_YTD) else [COL_PXS_MES or COL_PXS_YTD], ascending=False)
            grp_riv = grp_ord[~grp_ord["Es_Gutis"]]
            riv_sku = str(grp_riv.iloc[0]["NOMBRE_PRODUCTO"]) if not grp_riv.empty else "Sin competidor activo"
            riv_m = int(grp_riv.iloc[0][COL_PXS_MES]) if (not grp_riv.empty and COL_PXS_MES) else 0
            riv_y = int(grp_riv.iloc[0][COL_PXS_YTD]) if (not grp_riv.empty and COL_PXS_YTD) else 0
            esc_act, _, modo_tac, _ = diagnosticar_escala_adopcion(gm, pm, msm, gy, py, msy)
            mercados_doc.append({
                "clave": k_g, "prod_gutis": meta.get("producto", k_g), "clase": meta.get("clase_terapeutica", ""),
                "prio": meta.get("prioridad", 3), "pm": pm, "py": py, "gm": gm, "gy": gy, "cm": cm, "cy": cy,
                "msm": msm, "msy": msy, "riv_sku": riv_sku, "riv_m": riv_m, "riv_y": riv_y,
                "escala": esc_act, "modo": modo_tac, "meta": meta
            })
        mercados_doc.sort(key=lambda x: (-x["pm"], -x["py"], x["prio"]))

    df_labs_m = obtener_radar_laboratorios_doble_barra(medico_especifico=nombre_med)
    labs_resumen = " | ".join([
        f"**#{i+1} {r['Laboratorio']}** ({r['Pxs Mes']} Mes [{r['% MS Mes']:.1f}%] / {r['Pxs YTD']} YTD [{r['% MS YTD']:.1f}%])"
        for i, (_, r) in enumerate(df_labs_m.head(5).iterrows())
    ]) if not df_labs_m.empty else "Sin desglose de fabricantes."

    farmacias_z = "principales farmacias de la zona"
    if not df_ventas.empty and "DESCRIPCION_RUTA" in df_ventas.columns:
        vz = df_ventas[df_ventas["DESCRIPCION_RUTA"].str.contains(re.escape(ciu_m), na=False)]
        if not vz.empty:
            vz = vz[~vz["NOMBRE_CLIENTE_1"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
            rk_f = vz.groupby("NOMBRE_CLIENTE_1")["Monto Real"].sum().reset_index().sort_values(by="Monto Real", ascending=False)
            if not rk_f.empty:
                farmacias_z = ", ".join(rk_f["NOMBRE_CLIENTE_1"].head(3).tolist())

    if mercados_doc:
        m1 = mercados_doc[0]
        cands_p = [m for m in mercados_doc if m["prod_gutis"] != m1["prod_gutis"] and (m["cm"] > 0 or m["cy"] > 0)]
        m2 = cands_p[0] if cands_p else (mercados_doc[1] if len(mercados_doc) > 1 else None)
    else:
        k_fb = "MR TALERDIN" if es_ped_m else "MR GASTROALIVIO"
        meta_fb = MERCADOS_PRIORITARIOS[k_fb]
        m1 = {
            "clave": k_fb, "prod_gutis": meta_fb["producto"], "clase": meta_fb["clase_terapeutica"],
            "prio": 1, "pm": 0, "py": 0, "gm": 0, "gy": 0, "cm": 0, "cy": 0, "msm": 0.0, "msy": 0.0,
            "riv_sku": "Competencia", "riv_m": 0, "riv_y": 0, "escala": "2. Consciente", "modo": "CONQUISTA", "meta": meta_fb
        }
        m2 = None

    prod1, meta1 = m1["prod_gutis"], m1["meta"]
    riv1_marca, riv1_forma, riv1_comp = limpiar_sku_competencia(m1["riv_sku"])
    prod2 = m2["prod_gutis"] if m2 else ("Biotos Inmune / Clembroxil Compuesto" if es_ped_m else "Conflexil Plus Shot / Dalivio")

    lineas_mercados = "\n".join([
        f"* **{m['prod_gutis']}** (*{m['clase']}* — `{m['escala']}`): Mes `{m['pm']} Pxs` (Gutis: `{m['gm']}` [{m['msm']:.1f}%] vs. Rival `{m['riv_sku']}`: `{m['riv_m']}`) | YTD: `{m['py']} Pxs` (Gutis: `{m['gy']}` [{m['msy']:.1f}%] vs. Comp: `{m['cy']}`)."
        for m in mercados_doc[:6]
    ]) if mercados_doc else "* _Sin prescripciones registradas en el corte actual._"

    es_dilucion = any(k in t_norm for k in ["COMPART", "DILUY", "DIVID", "CON NOSOTROS", "FUGA", "POR QUE RECETA OTROS", "QUE PASA"])
    es_comprado = any(k in t_norm for k in ["COMPRAD", "AMARRAD", "CASAD", "FIDELIZAD", "NO SUELTA"]) and not es_dilucion
    es_pedido_roi = any(k in t_norm for k in ["PIDE", "PEDIR", "PIDIO", "A CAMBIO", "CONGRESO", "INSCRIPCION", "MUESTRA", "APOYO", "PATROCINIO"])

    if es_dilucion:
        bloque_tactico = f"""#### Diagnóstico de Dilución de Receta y Abordaje TVP:
1. **Lectura del Comportamiento Prescriptivo:** El/La Dr(a). {nom_natural} genera `{tot_mes} Pxs Mes` (`{tot_ytd} YTD`), entregando a Gutis `{gut_mes} Pxs Mes` (**{ms_global_m:.1f}% MS**) mientras `{comp_mes} Pxs Mes` (`{comp_ytd} YTD`) se desvían hacia marcas competidoras.
2. **Apertura de Reconocimiento (Sin reclamar):**
   > «Doctor(a) {nom_natural}, gracias por su respaldo constante a nuestro portafolio en {ciu_m}; gracias a su confianza decenas de pacientes reciben esquemas de alta pureza.»
3. **Sondeo Sutil para Aislar el Nicho Compartido:**
   > «Dando seguimiento a la respuesta que ha tenido con **{prod1}**, noté que en un grupo de pacientes aún alterna el esquema con **{riv1_comp}**. Al **comparar** ambos perfiles en su consulta de **{esp_m}**, ¿en qué cuadro específico siente que prefiere usar la otra opción?»
4. **Cierre de Consolidación hacia Lealtad:**
   > «Conociendo de primera mano que **{prod1}** aporta **{meta1['caracteristica'].lower()}**, consolidemos también ese grupo de pacientes bajo un solo estándar de calidad con inventario garantizado en **{farmacias_z}**.»"""
    elif es_comprado:
        bloque_tactico = f"""#### Estrategia de Flanqueo por Nicho Clínico (Médico Fidelizado con Competencia):
1. **Desarme Psicológico (Unidad 7 TVP):**
   > «Doctor(a) {nom_natural}, conozco su experiencia con su esquema habitual de **{riv1_marca}** y mi intención hoy no es pedirle que cambie lo que ya utiliza en su paciente general.»
2. **Pregunta de Grieta Clínica:**
   > «Solo quiero consultarle por un subgrupo específico: cuando recibe a **{meta1['nicho_flanqueo']}**, ¿cómo asegura que el paciente no rechace ni abandone la {riv1_forma.lower()}?»
3. **Cierre de Rescate (2 a 3 Pacientes) + Puente (`{prod2}`):**
   > «Para esos casos puntuales apóyese en **{prod1}** (*{meta1['caracteristica'].lower()}*) en sus próximos **3 pacientes de rescate**, y cuente también con **{prod2}** respaldado en **{farmacias_z}**.»"""
    elif es_pedido_roi:
        bloque_tactico = f"""#### Negociación Consultiva de Retorno (Condicionalidad Invertida):
1. **Auditoría de ROI Actual:** Volumen total: `{tot_mes} Pxs Mes` (`{tot_ytd} YTD`) | Cuota Gutis: `{gut_mes} Pxs ({ms_global_m:.1f}%)` | Fuga a competencia: `{comp_mes} Pxs Mes` (`{comp_ytd} YTD`).
2. **Guion con Escudo de Dirección Médica:**
   > «Doctor(a) {nom_natural}, su consulta en {ciu_m} es prioritaria para Gutis y cuenta con mi gestión para este apoyo. Para que Dirección Médica me apruebe el patrocinio en este ciclo, el sistema me exige respaldarlo subiendo nuestra participación mediante la migración de al menos **10 a 15 pacientes** que hoy van a **{riv1_marca}** hacia **{prod1}** y **{prod2}**, reflejados en **{farmacias_z}**. Si arrancamos esta semana con esos pacientes, yo presento su solicitud con números en verde. ¿Iniciamos hoy?»"""
    else:
        bloque_tactico = construir_guion_tvp_dinamico(
            nombre_med, esp_m, ciu_m,
            {
                "prod_gutis": prod1, "clase_terapeutica": m1["clase"], "modo_tactico": m1["modo"],
                "gutis_mes": m1["gm"], "gutis_ytd": m1["gy"], "comp_mes": m1["cm"], "comp_ytd": m1["cy"],
                "ms_mes": m1["msm"], "rival_principal": m1["riv_sku"], "meta_info": meta1
            },
            prod2, m2["meta"]["beneficio"] if m2 else "eficacia comprobada",
            m2["riv_sku"] if m2 else "la competencia", "Ventilar / Mometzona" if es_ped_m else "Valerpan / Renovart Platinum",
            "Visita con cita previa", "Desempeño (Eficacia y adherencia clínica)", farmacias_z, 0
        )

    return f"""### Expediente Estratégico y Plan TVP: Dr(a). {nombre_med}
**Especialidad:** `{esp_m}` | **Categoría:** `{cat_m}` | **Ciudad:** `{ciu_m}` | **Volumen Auditado:** `{tot_mes} Pxs Mes` (`{tot_ytd} YTD`) — **Gutis:** `{gut_mes} Mes / {gut_ytd} YTD ({ms_global_m:.1f}% MS)` | **Competencia:** `{comp_mes} Mes / {comp_ytd} YTD`

#### 1. Radiografía por Clase Terapéutica (Vademécum Nicaragua 2026):
{lineas_mercados}

#### 2. Ranking de Laboratorios en su Recetario (Mes vs. YTD):
* {labs_resumen}
* **Farmacias Aliadas en {ciu_m}:** {farmacias_z}

{bloque_tactico}
"""

def generar_analisis_mercado_chira_rico(df_rk_q, mer_q, ciu_q, nota_expansion=""):
    z_lbl = ciu_q or "TODO MI PANEL"
    if mer_q and mer_q in MERCADOS_PRIORITARIOS:
        meta_m = MERCADOS_PRIORITARIOS[mer_q]
        m_lbl = f"{meta_m['producto']} — {meta_m['clase_terapeutica']}"
        marca_foco = meta_m["producto"]
    else:
        m_lbl = mer_q or "Portafolio Oficial Gutis Nicaragua"
        marca_foco = "Portafolio Gutis"

    tot_m_zona = int(df_rk_q["Pxs Mes"].sum())
    gut_m_zona = int(df_rk_q["Gutis Mes"].sum())
    comp_m_zona = int(df_rk_q["Comp Mes"].sum())
    ms_m_zona = (gut_m_zona / tot_m_zona * 100.0) if tot_m_zona > 0 else 0.0

    tot_y_zona = int(df_rk_q["Pxs YTD"].sum())
    gut_y_zona = int(df_rk_q["Gutis YTD"].sum())
    comp_y_zona = int(df_rk_q["Comp YTD"].sum())
    ms_y_zona = (gut_y_zona / tot_y_zona * 100.0) if tot_y_zona > 0 else 0.0

    meds_leales = df_rk_q[df_rk_q["% MS Mes"] >= 50.0]
    if meds_leales.empty:
        meds_leales = df_rk_q[df_rk_q["% MS YTD"] >= 50.0]

    meds_conquista = df_rk_q.sort_values(by=["Comp Mes", "Comp YTD"], ascending=[False, False])

    txt_leales = ", ".join([
        f"**Dr(a). {formatear_nombre_medico(r['Médico'])}** ({r['Gutis Mes']} Mes / {r['Gutis YTD']} YTD — {r['% MS Mes']:.0f}% MS)"
        for _, r in meds_leales.head(3).iterrows()
    ]) if not meds_leales.empty else "Sin médicos en escalón de Lealtad (>50% MS) en este corte; prioridad total en Conquista y Expansión."

    txt_conquista = "\n".join([
        f"  - **Dr(a). {formatear_nombre_medico(r['Médico'])}** ({r['Especialidad']} | Cat {r['Cat']}): Entrega **{r['Comp Mes']} Pxs Mes** (`{r['Comp YTD']} YTD`) a la competencia -> Rival #1: `{r['Rival Principal en la Clase']}`."
        for _, r in meds_conquista.head(4).iterrows() if (r["Comp Mes"] > 0 or r["Comp YTD"] > 0)
    ]) or "  - _Todo el volumen auditado ya pertenece a Gutis._"

    df_vista_q = df_rk_q.head(12)[["Médico", "Estatus Panel", "Especialidad", "Cat", "Ciudad", "Pxs Mes", "Gutis Mes", "Comp Mes", "% MS Mes", "Pxs YTD", "% MS YTD", "Escala TVP", "Desglose Marcas [Mes/YTD]"]]
    md_rk = df_a_markdown_nativo(df_vista_q)

    return f"""### Auditoría Estratégica de Mercado | {m_lbl} — Territorio: {z_lbl}
{nota_expansion}**Volumen Categoría Mes:** `{tot_m_zona} Pxs` (Gutis: `{gut_m_zona}` [**{ms_m_zona:.1f}% MS**] | Competencia: `{comp_m_zona} Pxs`)  
**Volumen Categoría YTD:** `{tot_y_zona} Pxs` (Gutis: `{gut_y_zona}` [**{ms_y_zona:.1f}% MS**] | Competencia: `{comp_y_zona} Pxs`)

{md_rk}

#### Plan de Acción Táctico en {z_lbl} para {marca_foco}:
1. **Socios Leales a Blindar y Apalancar con Puente (>50% MS):** {txt_leales}
2. **Objetivos Prioritarios de Conquista y Migración (Donde está el volumen de la competencia):**
{txt_conquista}
3. **Directriz de Ejecución en Campo:** En los médicos de **Lealtad**, agradece su respaldo sin vender de cero y construye el puente hacia una segunda línea. En los médicos de **Conquista/Expansión**, aplica flanqueo directo sobre la presentación del rival principal asegurando disponibilidad previa en las farmacias líderes de {z_lbl}.
"""

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

if st.session_state.medico_activo_global and st.session_state.medico_activo_global not in lista_meds_sb:
    lista_meds_sb = [st.session_state.medico_activo_global] + lista_meds_sb

idx_med_sb = lista_meds_sb.index(st.session_state.medico_activo_global) if st.session_state.medico_activo_global in lista_meds_sb else 0
med_elegido_sb = st.sidebar.selectbox("Especialista en Foco:", lista_meds_sb, index=idx_med_sb)
if med_elegido_sb != st.session_state.medico_activo_global:
    st.session_state.medico_activo_global = med_elegido_sb
    st.session_state.pos_m1_idx = 0
    st.session_state.pos_m2_idx = 1
    st.session_state.pos_m3_idx = 2
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

tot_medicos_panel, meds_activos_global, pxs_mes_global_tot, pxs_mes_global_gut, ms_mes_global_gut, pxs_ytd_global_tot, pxs_ytd_global_gut, ms_ytd_global_gut = calcular_kpis_globales_hub()

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

    sp1, col_b1, sp2, col_b2, sp3 = st.columns([0.4, 1.8, 0.4, 1.8, 0.4])
    with col_b1:
        if st.button("TOP MÉDICOS (inf.target)\nProspección Macro, Clases Terapéuticas y Fuera de Panel", use_container_width=True):
            ir_a_modulo("TOP_MEDICOS")
            st.rerun()
    with col_b2:
        if st.button("PREVISITA TVP (inf.target)\nMapa de Mercado, Canvas, Guion TVP y Auditoría 360", use_container_width=True):
            ir_a_modulo("PREVISITA")
            st.rerun()

    st.write("")
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
    sp7, col_b5, sp8 = st.columns([1.5, 1.8, 1.5])
    with col_b5:
        if st.button("CHIRA\nCopiloto Estratégico con Voz y Registro CRM Post-Visita", use_container_width=True, type="primary"):
            ir_a_modulo("CHIRA")
            st.rerun()

# ==============================================================================
# MÓDULO 1: TOP MÉDICOS (inf.target) — NAVEGACIÓN POR 3 BOTONES LIMPIOS
# ==============================================================================
elif st.session_state.modulo_activo == "TOP_MEDICOS":
    c_back, c_tit = st.columns([0.8, 3.2])
    with c_back:
        if st.button("Volver al Menú Principal", use_container_width=True):
            ir_a_modulo("HUB"); st.rerun()
    with c_tit:
        st.markdown("<div class='module-banner'>MÓDULO 1: TOP MÉDICOS (inf.target) — PROSPECCIÓN MACRO, CRECIMIENTO Y CONQUISTA</div>", unsafe_allow_html=True)

    # Botonera de 3 vistas limpias ("una cosa a la vez")
    st.markdown("<div class='subnav-label'>SELECCIONE LA VISTA ANALÍTICA:</div>", unsafe_allow_html=True)
    btm1, btm2, btm3 = st.columns(3)
    with btm1:
        if st.button(
            "1. Ranking por Clase Terapéutica",
            use_container_width=True,
            type="primary" if st.session_state.sub_top_medicos == "RANKING" else "secondary"
        ):
            st.session_state.sub_top_medicos = "RANKING"; st.rerun()
    with btm2:
        if st.button(
            "2. Mercados que Crecen (Mes vs. YTD)",
            use_container_width=True,
            type="primary" if st.session_state.sub_top_medicos == "CRECIMIENTO" else "secondary"
        ):
            st.session_state.sub_top_medicos = "CRECIMIENTO"; st.rerun()
    with btm3:
        if st.button(
            "3. Médicos Fuera de Panel (Prospección)",
            use_container_width=True,
            type="primary" if st.session_state.sub_top_medicos == "FUERA_PANEL" else "secondary"
        ):
            st.session_state.sub_top_medicos = "FUERA_PANEL"; st.rerun()

    st.write("")
    f1, f2, f3 = st.columns([1.1, 1.5, 1.1])
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

    if st.session_state.sub_top_medicos in ["RANKING", "FUERA_PANEL"]:
        modo_p_actual = "FUERA_PANEL" if st.session_state.sub_top_medicos == "FUERA_PANEL" else "PANEL"
        df_top_meds = obtener_ranking_medicos_mercado(
            ciudad_target=None if tm_ciu == "TODO MI PANEL" else tm_ciu,
            esp_target=None if tm_esp == "TODAS" else tm_esp,
            mer_target=None if tm_mer == "TODOS LOS MERCADOS" else tm_mer,
            modo_panel=modo_p_actual
        )
        if df_top_meds.empty and modo_p_actual == "PANEL":
            df_top_meds = obtener_ranking_medicos_mercado(
                ciudad_target=None if tm_ciu == "TODO MI PANEL" else tm_ciu,
                esp_target=None if tm_esp == "TODAS" else tm_esp,
                mer_target=None if tm_mer == "TODOS LOS MERCADOS" else tm_mer,
                modo_panel="TODOS"
            )

        if not df_top_meds.empty:
            st.caption("Haz clic sobre cualquier médico de la tabla para abrir debajo las marcas que receta en esta clase terapéutica:")
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
            st.info("No se encontraron registros activos para esa combinación de filtros.")

    elif st.session_state.sub_top_medicos == "CRECIMIENTO":
        st.markdown(f"##### Dinamismo de Clases Terapéuticas: Comparativa Mes Actual vs. Acumulado YTD ({tm_ciu})")
        df_crec = calcular_crecimiento_mercados_mes_vs_ytd(tm_ciu, incluir_fuera_panel=False)
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
# MÓDULO 2: PREVISITA TVP (inf.target) — 4 BOTONES DEDICADOS ("UNA COSA A LA VEZ")
# ==============================================================================
elif st.session_state.modulo_activo == "PREVISITA":
    c_back, c_tit = st.columns([0.8, 3.2])
    with c_back:
        if st.button("Volver al Menú Principal", use_container_width=True):
            ir_a_modulo("HUB"); st.rerun()
    with c_tit:
        st.markdown("<div class='module-banner'>MÓDULO 2: PREVISITA TVP (inf.target) — PREPARACIÓN EJECUTIVA PASO A PASO</div>", unsafe_allow_html=True)

    # Procesar datos del médico activo
    rx_med = df_productos[(df_productos["Médico"] == medico_sel) & (df_productos["Clave_Gutis"].notna())].copy() if not df_productos.empty else pd.DataFrame()
    if es_pediatra and not rx_med.empty:
        claves_ped = {k for k, v in MERCADOS_PRIORITARIOS.items() if v.get("apto_pediatria", True)}
        rx_med = rx_med[rx_med["Clave_Gutis"].isin(claves_ped)].copy()

    tot_pxs_med_mes = int(rx_med[COL_PXS_MES].sum()) if (not rx_med.empty and COL_PXS_MES) else 0
    tot_pxs_med_ytd = int(rx_med[COL_PXS_YTD].sum()) if (not rx_med.empty and COL_PXS_YTD) else 0
    gut_pxs_med_mes = int(rx_med[rx_med["Es_Gutis"]][COL_PXS_MES].sum()) if tot_pxs_med_mes > 0 else 0
    gut_pxs_med_ytd = int(rx_med[rx_med["Es_Gutis"]][COL_PXS_YTD].sum()) if tot_pxs_med_ytd > 0 else 0
    comp_pxs_med_mes = tot_pxs_med_mes - gut_pxs_med_mes

    opciones_mercados_medico = []
    cards_ataque_html = ""

    if not rx_med.empty:
        for k_gut, df_m in rx_med.groupby("Clave_Gutis"):
            meta = MERCADOS_PRIORITARIOS.get(k_gut)
            if not meta:
                continue
            p_m_tot = int(df_m[COL_PXS_MES].sum()) if COL_PXS_MES else 0
            p_y_tot = int(df_m[COL_PXS_YTD].sum()) if COL_PXS_YTD else 0
            if p_m_tot <= 0 and p_y_tot <= 0:
                continue
            df_m_g = df_m[df_m["Es_Gutis"]]
            p_m_gut = int(df_m_g[COL_PXS_MES].sum()) if COL_PXS_MES else 0
            p_y_gut = int(df_m_g[COL_PXS_YTD].sum()) if COL_PXS_YTD else 0
            p_m_comp = p_m_tot - p_m_gut
            p_y_comp = p_y_tot - p_y_gut

            ms_m = round((p_m_gut / p_m_tot * 100.0), 1) if p_m_tot > 0 else 0.0
            ms_y = round((p_y_gut / p_y_tot * 100.0), 1) if p_y_tot > 0 else 0.0

            df_m_ord = df_m.sort_values(by=[COL_PXS_MES, COL_PXS_YTD] if (COL_PXS_MES and COL_PXS_YTD) else [COL_PXS_MES or COL_PXS_YTD], ascending=False)
            lider_row = df_m_ord.iloc[0]
            lider_nom = str(lider_row["NOMBRE_PRODUCTO"]).strip()
            lider_es_g = bool(lider_row["Es_Gutis"])

            df_riv = df_m_ord[~df_m_ord["Es_Gutis"]]
            if not df_riv.empty:
                r_row = df_riv.iloc[0]
                rival_nom = str(r_row["NOMBRE_PRODUCTO"]).strip()
                rival_m = int(r_row[COL_PXS_MES]) if COL_PXS_MES else 0
                rival_y = int(r_row[COL_PXS_YTD]) if COL_PXS_YTD else 0
            else:
                rival_nom, rival_m, rival_y = "Sin competidor activo", 0, 0

            esc_act, esc_meta, modo_tac, _ = diagnosticar_escala_adopcion(p_m_gut, p_m_tot, ms_m, p_y_gut, p_y_tot, ms_y)
            opciones_mercados_medico.append({
                "clave_gutis": k_gut,
                "prod_gutis": meta["producto"],
                "clase_terapeutica": meta["clase_terapeutica"],
                "prioridad": meta["prioridad"],
                "lider_actual": lider_nom,
                "lider_es_gutis": lider_es_g,
                "pxs_mes": p_m_tot, "gutis_mes": p_m_gut, "comp_mes": p_m_comp, "ms_mes": ms_m,
                "pxs_ytd": p_y_tot, "gutis_ytd": p_y_gut, "comp_ytd": p_y_comp, "ms_ytd": ms_y,
                "rival_principal": rival_nom, "rival_mes": rival_m, "rival_ytd": rival_y,
                "escala_actual": esc_act, "escala_meta": esc_meta, "modo_tactico": modo_tac,
                "meta_info": meta
            })

    opciones_mercados_medico = sorted(opciones_mercados_medico, key=lambda x: (-x["pxs_mes"], -x["pxs_ytd"], x["prioridad"]))
    num_mercados_activos = len(opciones_mercados_medico)

    # Sell-Out Zonal y Farmacias Aliadas
    total_sellout_zona, total_pdv_zona = 0.0, 0
    top_farmacias_ciudad_str = "principales farmacias de la zona"
    if not df_ventas.empty and "DESCRIPCION_RUTA" in df_ventas.columns:
        vz = df_ventas[df_ventas["DESCRIPCION_RUTA"].str.contains(re.escape(ciudad), na=False)]
        if not vz.empty:
            vz = vz[~vz["NOMBRE_CLIENTE_1"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
            rk_f = vz.groupby("NOMBRE_CLIENTE_1")["Monto Real"].sum().reset_index().sort_values(by="Monto Real", ascending=False)
            total_sellout_zona = float(rk_f["Monto Real"].sum())
            total_pdv_zona = len(rk_f)
            if not rk_f.empty:
                top_farmacias_ciudad_str = ", ".join(rk_f["NOMBRE_CLIENTE_1"].head(3).tolist())

    foco_primario_marca = opciones_mercados_medico[0]["prod_gutis"] if opciones_mercados_medico else ("Talerdín" if es_pediatra else "Gastroalivio")
    foco_primario_lider = opciones_mercados_medico[0]["lider_actual"][:18] if opciones_mercados_medico else "S/D"
    foco_primario_escala = opciones_mercados_medico[0]["escala_actual"].split("(")[0] if opciones_mercados_medico else "2. Consciente"

    # TICKER SUPERIOR SIEMPRE VISIBLE EN PREVISITA
    st.markdown(f"""
    <div class='ticker-bar'>
        <div class='ticker-item'>
            <div class='ticker-label'>ESPECIALISTA EN FOCO</div>
            <div class='ticker-val'>{medico_sel[:26]}</div>
            <div class='ticker-sub'>{especialidad} | Cat {categoria} | {ciudad}</div>
        </div>
        <div class='ticker-item'>
            <div class='ticker-label'>AUDITORÍA DE RECETAS (RX)</div>
            <div class='ticker-val'>{tot_pxs_med_mes} Pxs Mes <span style='font-size:0.85rem; color:#0284c7;'>({tot_pxs_med_ytd} YTD)</span></div>
            <div class='ticker-sub'>Gutis Mes: {gut_pxs_med_mes} ({gut_pxs_med_ytd} YTD) | Comp Mes: {comp_pxs_med_mes}</div>
        </div>
        <div class='ticker-item'>
            <div class='ticker-label'>FOCO PRIMARIO ({foco_primario_marca.upper()})</div>
            <div class='ticker-val'>{foco_primario_lider}</div>
            <div class='ticker-sub'>Escala TVP: <b>{foco_primario_escala}</b></div>
        </div>
        <div class='ticker-item'>
            <div class='ticker-label'>SELL-OUT ZONAL ({ciudad} - {total_pdv_zona} PDV)</div>
            <div class='ticker-val'>${total_sellout_zona:,.2f}</div>
            <div class='ticker-sub'>Aliadas: {top_farmacias_ciudad_str[:34]}...</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 4 BOTONES PRINCIPALES DE PREVISITA ("UNA COSA A LA VEZ")
    st.markdown("<div class='subnav-label'>SELECCIONE LA HERRAMIENTA DE PREVISITA:</div>", unsafe_allow_html=True)
    bp1, bp2, bp3, bp4 = st.columns(4)
    with bp1:
        if st.button(
            "1. Mapa de Mercado del Especialista",
            use_container_width=True,
            type="primary" if st.session_state.sub_previsita == "MAPA" else "secondary"
        ):
            st.session_state.sub_previsita = "MAPA"; st.rerun()
    with bp2:
        if st.button(
            "2. Canvas TVP (4 Cuadrantes)",
            use_container_width=True,
            type="primary" if st.session_state.sub_previsita == "CANVAS" else "secondary"
        ):
            st.session_state.sub_previsita = "CANVAS"; st.rerun()
    with bp3:
        if st.button(
            "3. Mapa Conversacional del TVP",
            use_container_width=True,
            type="primary" if st.session_state.sub_previsita == "GUION" else "secondary"
        ):
            st.session_state.sub_previsita = "GUION"; st.rerun()
    with bp4:
        if st.button(
            "4. Clases Terapéuticas, Labs & 360",
            use_container_width=True,
            type="primary" if st.session_state.sub_previsita == "AUDITORIA" else "secondary"
        ):
            st.session_state.sub_previsita = "AUDITORIA"; st.rerun()

    # Cargar notas de Ficha 360 si existen
    perfil_360_med = st.session_state.perfiles_memoria.get(medico_sel, {})
    if not perfil_360_med and os.path.exists(ARCHIVO_PERFIL_360):
        try:
            df_p360 = pd.read_excel(ARCHIVO_PERFIL_360)
            c_360 = df_p360[df_p360["Médico"].astype(str).str.upper() == medico_sel]
            if not c_360.empty:
                perfil_360_med = c_360.iloc[0].to_dict()
        except Exception:
            pass
    notas_rapport_med = str(perfil_360_med.get("Deporte", "")) if str(perfil_360_med.get("Deporte", "")) not in ["nan", "None", ""] else ""

    # Resolver posiciones P1, P2 y P3 activas para Canvas y Guion
    if opciones_mercados_medico:
        n_op = len(opciones_mercados_medico)
        idx_puente_sug = 1 if n_op > 1 else 0
        for idx_c, o_c in enumerate(opciones_mercados_medico):
            if idx_c > 0 and o_c["modo_tactico"] != "LEALTAD" and (o_c["comp_mes"] > 0 or o_c["comp_ytd"] > 0):
                idx_puente_sug = idx_c
                break
        i1 = st.session_state.pos_m1_idx if st.session_state.pos_m1_idx < n_op else 0
        i2 = st.session_state.pos_m2_idx if st.session_state.pos_m2_idx < n_op else idx_puente_sug
        i3 = st.session_state.pos_m3_idx if st.session_state.pos_m3_idx < n_op else (2 if n_op > 2 else idx_puente_sug)
        m_primario = opciones_mercados_medico[i1]
        m_secundario = opciones_mercados_medico[i2] if n_op > 1 else None
        m_terciario = opciones_mercados_medico[i3] if n_op > 2 else None
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

    # --- VISTA BOTÓN 1: MAPA DE MERCADO DEL ESPECIALISTA ---
    if st.session_state.sub_previsita == "MAPA":
        for item_m in opciones_mercados_medico:
            badge_p = f"P{item_m['prioridad']}"
            color_p = "#1e3a8a" if item_m["prioridad"] == 1 else ("#0284c7" if item_m["prioridad"] == 2 else "#64748b")
            ms_mostrar = item_m["ms_mes"] if item_m["pxs_mes"] > 0 else item_m["ms_ytd"]
            if item_m["modo_tactico"] == "LEALTAD" or item_m["lider_es_gutis"]:
                cards_ataque_html += f"""
                <div style="background:linear-gradient(180deg, #ecfdf5 0%, #ffffff 100%); border:1px solid #a7f3d0; border-top:4px solid #059669; border-radius:6px; padding:12px 14px; min-width:225px; flex:1 1 calc(25% - 12px); font-family:'Segoe UI', sans-serif; box-shadow:0 2px 5px rgba(0,0,0,0.04);">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:0.72rem; font-weight:800; color:#065f46;">{item_m['prod_gutis'].upper()}</span>
                        <span style="background:{color_p}; color:white; font-size:0.62rem; padding:2px 7px; border-radius:4px; font-weight:700;">{badge_p}</span>
                    </div>
                    <div style="font-size:0.86rem; color:#0f172a; margin:5px 0;">Líder: <b style="color:#047857;">{item_m['prod_gutis']} ({ms_mostrar:.0f}% MS)</b></div>
                    <div style="font-size:0.74rem; color:#475569;">Mes: <b>{item_m['pxs_mes']}</b> (Gutis: {item_m['gutis_mes']} | Comp: {item_m['comp_mes']}) | YTD: <b>{item_m['pxs_ytd']}</b></div>
                    <div style="font-size:0.71rem; color:#334155; margin-top:3px;">Escala: <b>{item_m['escala_actual'].split('(')[0]}</b></div>
                    <div style="margin-top:6px; font-size:0.72rem; font-weight:800; color:#047857; border-top:1px dashed #cbd5e1; padding-top:5px;">Agradecer, Blindar y Puente</div>
                </div>"""
            else:
                cards_ataque_html += f"""
                <div style="background:linear-gradient(180deg, #fff1f2 0%, #ffffff 100%); border:1px solid #fecdd3; border-top:4px solid #e11d48; border-radius:6px; padding:12px 14px; min-width:225px; flex:1 1 calc(25% - 12px); font-family:'Segoe UI', sans-serif; box-shadow:0 2px 5px rgba(0,0,0,0.04);">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:0.72rem; font-weight:800; color:#9f1239;">{item_m['prod_gutis'].upper()}</span>
                        <span style="background:{color_p}; color:white; font-size:0.62rem; padding:2px 7px; border-radius:4px; font-weight:700;">{badge_p}</span>
                    </div>
                    <div style="font-size:0.86rem; color:#0f172a; margin:5px 0;">Rival: <b style="color:#be123c;">{item_m['rival_principal'][:20]}</b></div>
                    <div style="font-size:0.74rem; color:#475569;">Mes: <b>{item_m['pxs_mes']}</b> (Comp: {item_m['comp_mes']}) | YTD: <b>{item_m['pxs_ytd']}</b> (Comp: {item_m['comp_ytd']})</div>
                    <div style="font-size:0.71rem; color:#334155; margin-top:3px;">Escala: <b>{item_m['escala_actual'].split('(')[0]}</b></div>
                    <div style="margin-top:6px; font-size:0.72rem; font-weight:800; color:#047857; border-top:1px dashed #cbd5e1; padding-top:5px;">Conquistar con {item_m['prod_gutis']}</div>
                </div>"""

        if cards_ataque_html:
            altura_c = 220 if num_mercados_activos <= 4 else (370 if num_mercados_activos <= 8 else 480)
            st.components.v1.html(f"""
            <div style="background-color:#ffffff; border:1px solid #cbd5e1; border-left:5px solid #002b5c; padding:14px 16px; border-radius:8px; font-family:'Segoe UI', sans-serif;">
                <div style="font-size:0.78rem; font-weight:800; color:#0f172a; margin-bottom:12px; letter-spacing:0.5px;">
                    MAPA DE MERCADOS ACTIVOS DEL ESPECIALISTA (CLASES TERAPÉUTICAS VADEMÉCUM NICARAGUA 2026 — {num_mercados_activos} CATEGORÍAS AUDITADAS)
                </div>
                <div style="display:flex; flex-wrap:wrap; gap:12px;">{cards_ataque_html}</div>
            </div>
            """, height=altura_c, scrolling=True)
        else:
            st.info("El especialista no registra prescripciones activas en las clases terapéuticas del corte actual.")

    # --- VISTA BOTÓN 2: CANVAS TVP (4 CUADRANTES) ---
    elif st.session_state.sub_previsita == "CANVAS":
        with st.container(border=True):
            if opciones_mercados_medico:
                etiquetas_m = [
                    f"[{o['modo_tactico']}] {o['prod_gutis']} | Mes: {o['pxs_mes']} ({o['ms_mes']}% MS) | YTD: {o['pxs_ytd']} ({o['ms_ytd']}% MS)"
                    for o in opciones_mercados_medico
                ]
                cm1, cm2, cm3 = st.columns(3)
                with cm1:
                    st.session_state.pos_m1_idx = st.selectbox("1ra Posición (Foco / Ancla):", range(len(etiquetas_m)), index=i1, format_func=lambda i: etiquetas_m[i])
                with cm2:
                    st.session_state.pos_m2_idx = st.selectbox("2da Posición (Puente Clínico):", range(len(etiquetas_m)), index=i2, format_func=lambda i: etiquetas_m[i])
                with cm3:
                    st.session_state.pos_m3_idx = st.selectbox("3ra Posición (Recordación):", range(len(etiquetas_m)), index=i3, format_func=lambda i: etiquetas_m[i])
                m_primario = opciones_mercados_medico[st.session_state.pos_m1_idx]
                m_secundario = opciones_mercados_medico[st.session_state.pos_m2_idx] if len(opciones_mercados_medico) > 1 else None
                m_terciario = opciones_mercados_medico[st.session_state.pos_m3_idx] if len(opciones_mercados_medico) > 2 else None

            ct1, ct2 = st.columns(2)
            opc_citas = ["Visita con cita previa", "Visita sin cita (Improvisto)", "Encuentro casual (Pasillo)"]
            opc_ndn = ["Desempeño (Eficacia y adherencia clínica)", "Imagen (Prestigio clínico)", "Finanzas (Costo-beneficio)"]
            with ct1:
                st.session_state.ctx_cita_global = st.selectbox("Contexto de Visita:", opc_citas, index=opc_citas.index(st.session_state.ctx_cita_global))
            with ct2:
                st.session_state.ctx_ndn_global = st.selectbox("Necesidad detrás de la Necesidad (NdN):", opc_ndn, index=opc_ndn.index(st.session_state.ctx_ndn_global))

        tipo_cita_sel = st.session_state.ctx_cita_global
        nec_detras_sel = st.session_state.ctx_ndn_global
        meta1 = m_primario["meta_info"]
        prod1 = m_primario["prod_gutis"]
        rival1_marca, rival1_forma, rival1_comp = limpiar_sku_competencia(m_primario["rival_principal"])
        modo_tac1 = m_primario["modo_tactico"]
        perfil_paciente_adaptado = meta1.get("paciente_meta_ped", meta1["paciente_meta"]) if es_pediatra else meta1["paciente_meta"]

        if m_secundario and m_secundario["prod_gutis"] != prod1:
            prod2 = m_secundario["prod_gutis"]
            benef2 = m_secundario["meta_info"]["beneficio"]
            rival2_marca, _, _ = limpiar_sku_competencia(m_secundario["rival_principal"])
        else:
            prod2 = "Biotos Inmune / Clembroxil Compuesto" if es_pediatra else "Conflexil Plus Shot / Dalivio"
            benef2 = "cuádruple acción respiratoria libre de alcohol" if es_pediatra else "triple acción analgésica, antiinflamatoria y miorrelajante"
            rival2_marca = "la competencia"

        prod3 = m_terciario["prod_gutis"] if (m_terciario and m_terciario["prod_gutis"] not in [prod1, prod2]) else ("Ventilar / Mometzona" if es_pediatra else "Valerpan / Renovart Platinum")
        arg_ndn_canvas = meta1.get("arg_imagen", meta1["beneficio"]) if "Imagen" in nec_detras_sel else (meta1.get("arg_finanzas", meta1["beneficio"]) if "Finanzas" in nec_detras_sel else meta1["beneficio"])

        if modo_tac1 == "LEALTAD":
            q1_html = f"""
                • <b>Escala Actual:</b> <span style='color:#047857; font-weight:800;'>{m_primario['escala_actual']} (Socio Leal)</span><br>
                • <b>Clase Terapéutica:</b> {m_primario['clase_terapeutica']}<br>
                • <b>Meta SMART Hoy:</b> Agradecer y blindar sus recetas de <b>{prod1}</b> (Mes: {m_primario['gutis_mes']} Pxs | YTD: {m_primario['gutis_ytd']} Pxs) y usar esa confianza como puente para iniciar <b>3 a 5 pacientes en {prod2}</b>.<br>
                • <b>Plan de Respaldo:</b> Asegurar rotación en <b>{top_farmacias_ciudad_str.split(',')[0]}</b>.
            """
            q2_html = f"""
                • <b>Postura ({tipo_cita_sel.split('(')[0].strip()}):</b> Reconocimiento de lealtad (sin vender de cero lo que ya prescribe).<br>
                • <b>Apertura ({especialidad}):</b> Agradecer su preferencia sostenida en <i>{perfil_paciente_adaptado}</i>.<br>
                • <b>Pregunta de Validación:</b> <i>«¿Cómo ha notado la respuesta y adherencia de sus pacientes con nuestras presentaciones de {prod1} este mes?»</i>
            """
            q3_html = f"""
                • <b>Blindaje Sutil ({prod1}):</b> Recordar dosificación y ventaja diferencial ({meta1['caracteristica']}).<br>
                • <b>Enfoque ({nec_detras_sel.split('(')[0].strip()}):</b> {arg_ndn_canvas.capitalize()}.<br>
                • <b>Mensaje de Marca:</b> <i>«{meta1['love_brand']}»</i>
            """
            q4_html = f"""
                • <b>Cierre en {prod1}:</b> Agradecer su preferencia #1 y asegurar stock en <b>{top_farmacias_ciudad_str.split(',')[0]}</b>.<br>
                • <b>PUENTE PROTAGONISTA ({prod1} hacia {prod2}):</b> <i>«Apoyándome en su excelente experiencia con {prod1}, extendamos esa misma calidad hacia <b>{prod2}</b> ({benef2}) en los casos donde aún utiliza {rival2_marca}.»</i><br>
                • <b>3ra Posición ({prod3}):</b> Recordación de disponibilidad zonal.
            """
        elif modo_tac1 == "EXPANSION":
            q1_html = f"""
                • <b>Escala Actual:</b> <span style='color:#0284c7; font-weight:800;'>{m_primario['escala_actual']} (Comparte Categoría)</span><br>
                • <b>Escalón Meta Hoy:</b> <span style='color:#047857; font-weight:700;'>{m_primario['escala_meta']}</span><br>
                • <b>Meta SMART:</b> Agradecer sus recetas actuales en <b>{prod1}</b> (Mes: {m_primario['gutis_mes']} | YTD: {m_primario['gutis_ytd']}) y migrar <b>4 a 6 pacientes</b> que aún van a <b>{rival1_comp}</b>.<br>
                • <b>Plan de Respaldo:</b> Capturar el subgrupo de {meta1['nicho_flanqueo']}.
            """
            q2_html = f"""
                • <b>Postura ({tipo_cita_sel.split('(')[0].strip()}):</b> Explorar su experiencia positiva con los pacientes ya tratados.<br>
                • <b>Agenda ({especialidad}):</b> Analizar evolución en <i>{perfil_paciente_adaptado}</i>.<br>
                • <b>Pregunta Sutil:</b> <i>«En los casos donde ya prescribió {prod1} frente a {rival1_marca}, ¿qué diferencias observó en tolerabilidad y apego?»</i>
            """
            q3_html = f"""
                • <b>Sondeo de Migración:</b> <i>«¿En qué perfil específico de paciente siente que todavía alterna con {rival1_marca} en {rival1_forma.lower()}?»</i><br>
                • <b>Ventaja Diferencial ({prod1}):</b> {meta1['caracteristica']}.<br>
                • <b>Enfoque ({nec_detras_sel.split('(')[0].strip()}):</b> {arg_ndn_canvas.capitalize()}.
            """
            q4_html = f"""
                • <b>Pido al Médico:</b> Consolidar a <b>{prod1}</b> como primera elección en el segmento que compartía con <b>{rival1_marca}</b>.<br>
                • <b>Mi Compromiso:</b> Garantizar inventario en <b>{top_farmacias_ciudad_str.split(',')[0]}</b>.<br>
                • <b>Puente a 2da Posición ({prod2}):</b> <i>«Y siguiendo con eficacia clínica, cuente con <b>{prod2}</b> ({benef2}).»</i>
            """
        else:
            q1_html = f"""
                • <b>Escala Actual:</b> <span style='color:#b91c1c; font-weight:700;'>{m_primario['escala_actual']}</span><br>
                • <b>Escalón Meta Hoy:</b> <span style='color:#047857; font-weight:700;'>{m_primario['escala_meta']}</span><br>
                • <b>Meta SMART:</b> Capturar los primeros <b>3 a 5 pacientes</b> que hoy prescribe en <b>{rival1_comp}</b> (Comp Mes: {m_primario['comp_mes']} | Comp YTD: {m_primario['comp_ytd']}) hacia <b>{prod1}</b>.<br>
                • <b>Plan de Respaldo:</b> Flanqueo en 2 pacientes de rescate ({meta1['nicho_flanqueo']}).
            """
            q2_html = f"""
                • <b>Postura ({tipo_cita_sel.split('(')[0].strip()}):</b> Agenda centrada en el paciente de <b>{especialidad}</b> (sin mencionar marca en apertura).<br>
                • <b>Agenda:</b> Optimizar adherencia en <i>{perfil_paciente_adaptado}</i>.<br>
                • <b>Pregunta Disruptiva:</b> <i>«¿Qué impacto tendría en su consulta eliminar desde hoy el abandono terapéutico al segundo día en estos pacientes?»</i>
            """
            q3_html = f"""
                • <b>Sondeo de Valor Mutuo:</b> <i>«Al <b>evaluar</b> la respuesta actual con {rival1_marca} ({rival1_forma.lower()}), ¿qué considera prioritario optimizar?»</i><br>
                • <b>Ventaja ({prod1}):</b> {meta1['caracteristica']}.<br>
                • <b>Enfoque ({nec_detras_sel.split('(')[0].strip()}):</b> {arg_ndn_canvas.capitalize()}.
            """
            q4_html = f"""
                • <b>Pido al Médico:</b> Iniciar período de prueba con <b>{prod1}</b> en sus próximos 3 a 5 pacientes.<br>
                • <b>Mi Compromiso:</b> Asegurar disponibilidad hoy en <b>{top_farmacias_ciudad_str.split(',')[0]}</b>.<br>
                • <b>Puente a 2da Posición ({prod2}):</b> <i>«Siguiendo con seguridad clínica, cuenta también con <b>{prod2}</b> ({benef2}).»</i>
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

    # --- VISTA BOTÓN 3: MAPA CONVERSACIONAL DEL TVP (GUION EN PANTALLA COMPLETA) ---
    elif st.session_state.sub_previsita == "GUION":
        with st.container(border=True):
            cg1, cg2, cg3 = st.columns([1.2, 1.2, 1.2])
            opc_citas = ["Visita con cita previa", "Visita sin cita (Improvisto)", "Encuentro casual (Pasillo)"]
            opc_ndn = ["Desempeño (Eficacia y adherencia clínica)", "Imagen (Prestigio clínico)", "Finanzas (Costo-beneficio)"]
            with cg1:
                if opciones_mercados_medico:
                    etiquetas_m = [f"[{o['modo_tactico']}] {o['prod_gutis']} ({o['ms_mes']}% MS)" for o in opciones_mercados_medico]
                    st.session_state.pos_m1_idx = st.selectbox("Producto Foco (1ra Posición):", range(len(etiquetas_m)), index=i1, format_func=lambda i: etiquetas_m[i])
                    m_primario = opciones_mercados_medico[st.session_state.pos_m1_idx]
            with cg2:
                st.session_state.ctx_cita_global = st.selectbox("Contexto de Visita:", opc_citas, index=opc_citas.index(st.session_state.ctx_cita_global))
            with cg3:
                st.session_state.ctx_ndn_global = st.selectbox("Resorte Psicológico (NdN):", opc_ndn, index=opc_ndn.index(st.session_state.ctx_ndn_global))

        tipo_cita_sel = st.session_state.ctx_cita_global
        nec_detras_sel = st.session_state.ctx_ndn_global
        meta1 = m_primario["meta_info"]
        prod1 = m_primario["prod_gutis"]
        rival1_marca, rival1_forma, rival1_comp = limpiar_sku_competencia(m_primario["rival_principal"])
        modo_tac1 = m_primario["modo_tactico"]

        if m_secundario and m_secundario["prod_gutis"] != prod1:
            prod2 = m_secundario["prod_gutis"]
            benef2 = m_secundario["meta_info"]["beneficio"]
            rival2_raw = m_secundario["rival_principal"]
        else:
            prod2 = "Biotos Inmune / Clembroxil Compuesto" if es_pediatra else "Conflexil Plus Shot / Dalivio"
            benef2 = "cuádruple acción respiratoria libre de alcohol" if es_pediatra else "triple acción analgésica, antiinflamatoria y miorrelajante"
            rival2_raw = "la competencia"

        prod3 = m_terciario["prod_gutis"] if (m_terciario and m_terciario["prod_gutis"] not in [prod1, prod2]) else ("Ventilar / Mometzona" if es_pediatra else "Valerpan / Renovart Platinum")

        clave_cache_guion = f"{medico_sel}_{prod1}_{prod2}_{modo_tac1}_{tipo_cita_sel}_{nec_detras_sel}"

        if st.button("Generar / Cambiar Variante Táctica de Guion (Motor Cognitivo TVP + IA)", use_container_width=True, type="primary"):
            st.session_state.tvp_variant_counter += 1
            num_v = st.session_state.tvp_variant_counter
            with st.spinner("Estructurando variante táctica personalizada para el consultorio..."):
                prompt_g = f"""{REGLAS_FARMA}
Redacta un guion conversacional TVP paso a paso (1. Apertura adaptada a '{tipo_cita_sel}', 2. Sondeo de Valor Mutuo enfocado en '{nec_detras_sel}', 3. Apoyo Galénico y Love Brand, 4. Cierre Bilateral y Puente) para visitar al Dr(a). {formatear_nombre_medico(medico_sel)} ({especialidad} en {ciudad}).
Datos reales auditados:
- Producto 1: {prod1} ({meta1['caracteristica']}) | Escala actual: {m_primario['escala_actual']} (Modo: {modo_tac1}).
- Pacientes Gutis Mes: {m_primario['gutis_mes']} (YTD: {m_primario['gutis_ytd']}) | Competidor principal en la clase: {rival1_comp} (Comp Mes: {m_primario['comp_mes']} | Comp YTD: {m_primario['comp_ytd']}).
- Producto 2 (Puente): {prod2} ({benef2}) | Producto 3: {prod3}.
- Farmacias aliadas en {ciudad}: {top_farmacias_ciudad_str}.
Haz que el diálogo suene 100% natural, ejecutivo, sin códigos internos de SKU y diferente a una plantilla genérica (Variante #{num_v})."""
                res_g = llamar_gemini(prompt_g)
                if res_g and len(res_g.strip()) > 120:
                    st.session_state.tvp_custom_script[clave_cache_guion] = res_g
                else:
                    st.session_state.tvp_custom_script[clave_cache_guion] = construir_guion_tvp_dinamico(
                        medico_sel, especialidad, ciudad, m_primario, prod2, benef2, rival2_raw, prod3,
                        tipo_cita_sel, nec_detras_sel, top_farmacias_ciudad_str, num_variante=num_v, notas_rapport=notas_rapport_med
                    )

        guion_mostrar = st.session_state.tvp_custom_script.get(
            clave_cache_guion,
            construir_guion_tvp_dinamico(
                medico_sel, especialidad, ciudad, m_primario, prod2, benef2, rival2_raw, prod3,
                tipo_cita_sel, nec_detras_sel, top_farmacias_ciudad_str, num_variante=0, notas_rapport=notas_rapport_med
            )
        )
        with st.container(border=True):
            st.markdown(guion_mostrar)

    # --- VISTA BOTÓN 4: CLASES TERAPÉUTICAS, RADAR DE LABORATORIOS & FICHA OMNICANAL 360 ---
    elif st.session_state.sub_previsita == "AUDITORIA":
        ba1, ba2, ba3, ba4 = st.columns(4)
        with ba1:
            if st.button(
                "A. Matriz Clases Terapéuticas (LY/YTD/Mes)",
                use_container_width=True,
                type="primary" if st.session_state.sub_previsita_auditoria == "CLASES" else "secondary"
            ):
                st.session_state.sub_previsita_auditoria = "CLASES"; st.rerun()
        with ba2:
            if st.button(
                "B. Marcas por Categoría Terapéutica",
                use_container_width=True,
                type="primary" if st.session_state.sub_previsita_auditoria == "MARCAS" else "secondary"
            ):
                st.session_state.sub_previsita_auditoria = "MARCAS"; st.rerun()
        with ba3:
            if st.button(
                "C. Radar de Laboratorios (Doble Barra)",
                use_container_width=True,
                type="primary" if st.session_state.sub_previsita_auditoria == "LABS" else "secondary"
            ):
                st.session_state.sub_previsita_auditoria = "LABS"; st.rerun()
        with ba4:
            if st.button(
                "D. Ficha de Omnicanalidad 360",
                use_container_width=True,
                type="primary" if st.session_state.sub_previsita_auditoria == "FICHA360" else "secondary"
            ):
                st.session_state.sub_previsita_auditoria = "FICHA360"; st.rerun()

        st.write("")
        if st.session_state.sub_previsita_auditoria == "CLASES":
            st.markdown(f"##### Matriz Corporativa de Clases Terapéuticas — Dr(a). {medico_sel}")
            df_mat_ct = obtener_matriz_clases_terapeuticas_corporativa(medico_sel)
            if not df_mat_ct.empty:
                cfg_ct = {}
                for col_c in df_mat_ct.columns:
                    if "MS" in col_c.upper():
                        cfg_ct[col_c] = st.column_config.ProgressColumn(col_c, format="%.2f%%", min_value=0, max_value=100)
                st.dataframe(df_mat_ct, hide_index=True, use_container_width=True, height=420, column_config=cfg_ct)
            else:
                st.info("Sin registros de clases terapéuticas para este especialista.")

        elif st.session_state.sub_previsita_auditoria == "MARCAS":
            st.markdown(f"##### Desglose de Marcas Prescritas por Categoría Terapéutica — Dr(a). {medico_sel}")
            df_desg_pre = obtener_desglose_productos_medico(medico_sel)
            if not df_desg_pre.empty:
                st.dataframe(
                    df_desg_pre,
                    hide_index=True,
                    use_container_width=True,
                    height=420,
                    column_config={
                        "% MS Mes (Categoría)": st.column_config.ProgressColumn("% MS Mes", format="%.1f%%", min_value=0, max_value=100),
                        "% MS YTD (Categoría)": st.column_config.ProgressColumn("% MS YTD", format="%.1f%%", min_value=0, max_value=100),
                    }
                )
            else:
                st.info("El especialista no registra prescripciones activas en el corte actual.")

        elif st.session_state.sub_previsita_auditoria == "LABS":
            st.markdown(f"##### Radar de Laboratorios en el Recetario del Médico (Doble Barra: % MS Mes vs. % MS YTD)")
            df_labs_doc_pre = obtener_radar_laboratorios_doble_barra(medico_especifico=medico_sel)
            if not df_labs_doc_pre.empty:
                st.dataframe(
                    df_labs_doc_pre.drop(columns=["Prescriptores"]),
                    hide_index=True,
                    use_container_width=True,
                    height=420,
                    column_config={
                        "% MS Mes": st.column_config.ProgressColumn("% MS Mes (Actual)", format="%.2f%%", min_value=0, max_value=100),
                        "% MS YTD": st.column_config.ProgressColumn("% MS YTD (Acumulado)", format="%.2f%%", min_value=0, max_value=100),
                    }
                )
            else:
                st.info("Sin registros de laboratorios para este especialista.")

        elif st.session_state.sub_previsita_auditoria == "FICHA360":
            st.markdown(f"##### Ficha de Omnicanalidad 360 — Dr(a). {medico_sel}")
            with st.form("form_perfil_360_previsita"):
                f3_1, f3_2 = st.columns(2)
                with f3_1:
                    v_minsa = st.text_input("Código MINSA:", value=str(perfil_360_med.get("MINSA", "")) if str(perfil_360_med.get("MINSA", "")) not in ["nan", "None"] else "")
                    v_cel = st.text_input("Celular / WhatsApp:", value=str(perfil_360_med.get("Celular", "")) if str(perfil_360_med.get("Celular", "")) not in ["nan", "None"] else "")
                with f3_2:
                    v_cumple = st.text_input("Cumpleaños:", value=str(perfil_360_med.get("Cumpleaños", "")) if str(perfil_360_med.get("Cumpleaños", "")) not in ["nan", "None"] else "")
                    opc_est = ["Ultra-ejecutiva", "Discusión científica", "Casos clínicos"]
                    idx_e = opc_est.index(perfil_360_med.get("Estilo_Visita", opc_est[0])) if perfil_360_med.get("Estilo_Visita") in opc_est else 0
                    v_estilo = st.selectbox("Estilo de Visita:", opc_est, index=idx_e)
                v_notas = st.text_input("Afinidad / Notas de Rapport (se integran automáticamente al Mapa Conversacional TVP):", value=notas_rapport_med)
                if st.form_submit_button("Guardar Ficha 360 y Sincronizar con el Guion TVP", use_container_width=True, type="primary"):
                    reg_360 = {
                        "Médico": medico_sel, "MINSA": v_minsa, "Celular": v_cel,
                        "Cumpleaños": v_cumple, "Deporte": v_notas, "Estilo_Visita": v_estilo,
                        "Ultima_Actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }
                    st.session_state.perfiles_memoria[medico_sel] = reg_360
                    try:
                        if os.path.exists(ARCHIVO_PERFIL_360):
                            df_s = pd.read_excel(ARCHIVO_PERFIL_360)
                            df_s = df_s[df_s["Médico"].astype(str).str.upper() != medico_sel]
                            df_s = pd.concat([df_s, pd.DataFrame([reg_360])], ignore_index=True)
                        else:
                            df_s = pd.DataFrame([reg_360])
                        df_s.to_excel(ARCHIVO_PERFIL_360, index=False)
                        st.success("Ficha 360 guardada y conectada al Mapa Conversacional.")
                    except Exception as e_360:
                        st.warning(f"Guardado en memoria de sesión ({e_360}).")

# ==============================================================================
# MÓDULO 3: ANÁLISIS MERCADO (inf.market) — 2 BOTONES LIMPIOS
# ==============================================================================
elif st.session_state.modulo_activo == "ANALISIS_MERCADO":
    c_back, c_tit = st.columns([0.8, 3.2])
    with c_back:
        if st.button("Volver al Menú Principal", use_container_width=True):
            ir_a_modulo("HUB"); st.rerun()
    with c_tit:
        st.markdown("<div class='module-banner'>MÓDULO 3: ANÁLISIS DE MERCADO (inf.market) — CLASES TERAPÉUTICAS Y DOBLE BARRA MES / YTD</div>", unsafe_allow_html=True)

    st.markdown("<div class='subnav-label'>SELECCIONE LA VISTA DE MERCADO:</div>", unsafe_allow_html=True)
    bam1, bam2 = st.columns(2)
    with bam1:
        if st.button(
            "1. Radar de Laboratorios (Doble Barra: % MS Mes vs. % MS YTD)",
            use_container_width=True,
            type="primary" if st.session_state.sub_analisis_mercado == "LABS" else "secondary"
        ):
            st.session_state.sub_analisis_mercado = "LABS"; st.rerun()
    with bam2:
        if st.button(
            "2. Matriz de Penetración por Especialidad y Top 5 Competencia",
            use_container_width=True,
            type="primary" if st.session_state.sub_analisis_mercado == "PENETRACION" else "secondary"
        ):
            st.session_state.sub_analisis_mercado = "PENETRACION"; st.rerun()

    st.write("")
    am1, am2, am3 = st.columns(3)
    with am1:
        am_ciu = st.selectbox("1. Territorio / Ciudad:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="am_ciu")
    with am2:
        am_esp = st.selectbox("2. Especialidad:", ["TODAS"] + LISTA_ESPECIALIDADES_REALES, key="am_esp")
    with am3:
        am_med_foco = st.selectbox("3. Nivel de Radar de Laboratorios:", ["Agregado Territorial / Especialidad", f"Solo Especialista Activo ({medico_sel[:20]})"])

    if st.session_state.sub_analisis_mercado == "LABS":
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

    elif st.session_state.sub_analisis_mercado == "PENETRACION":
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
# MÓDULO 4: EVOLUCIÓN (inf.target) — 2 BOTONES LIMPIOS
# ==============================================================================
elif st.session_state.modulo_activo == "EVOLUCION":
    c_back, c_tit = st.columns([0.8, 3.2])
    with c_back:
        if st.button("Volver al Menú Principal", use_container_width=True):
            ir_a_modulo("HUB"); st.rerun()
    with c_tit:
        st.markdown("<div class='module-banner'>MÓDULO 4: EVOLUCIÓN (inf.target) — DESEMPEÑO DE RECETAS (MES / YTD) Y SELL-OUT EN FARMACIAS (Q1-Q3)</div>", unsafe_allow_html=True)

    st.markdown("<div class='subnav-label'>SELECCIONE LA VISTA DE EVOLUCIÓN:</div>", unsafe_allow_html=True)
    bev1, bev2 = st.columns(2)
    with bev1:
        if st.button(
            "1. Sincronía Temporal (Cuota Rx Mes/YTD vs. Sell-Out Trimestral)",
            use_container_width=True,
            type="primary" if st.session_state.sub_evolucion == "SINCRONIA" else "secondary"
        ):
            st.session_state.sub_evolucion = "SINCRONIA"; st.rerun()
    with bev2:
        if st.button(
            "2. Auditoría Detallada de Sell-Out por Sucursal Farmacéutica",
            use_container_width=True,
            type="primary" if st.session_state.sub_evolucion == "FARMACIAS" else "secondary"
        ):
            st.session_state.sub_evolucion = "FARMACIAS"; st.rerun()

    st.write("")
    ev_ciu = st.selectbox("Seleccionar Territorio:", ["TODO MI PANEL"] + LISTA_CIUDADES_REALES, key="ev_ciu")

    df_v_sub = df_ventas.copy() if not df_ventas.empty else pd.DataFrame()
    if not df_v_sub.empty and ev_ciu != "TODO MI PANEL" and "DESCRIPCION_RUTA" in df_v_sub.columns:
        df_v_sub = df_v_sub[df_v_sub["DESCRIPCION_RUTA"].str.contains(re.escape(ev_ciu), na=False)].copy()
    if not df_v_sub.empty:
        df_v_sub = df_v_sub[~df_v_sub["NOMBRE_CLIENTE_1"].astype(str).str.upper().isin(["TOTAL", "NAN", ""])]
    col_prod_v = "VM4" if (not df_v_sub.empty and "VM4" in df_v_sub.columns) else (next((c for c in df_v_sub.columns if "PRODUCTO" in c.upper()), None) if not df_v_sub.empty else None)

    if st.session_state.sub_evolucion == "SINCRONIA":
        df_ev_rx = calcular_crecimiento_mercados_mes_vs_ytd(ev_ciu, incluir_fuera_panel=False).copy()
        if not df_ev_rx.empty:
            q1_list, q2_list, q3_list, var_so_list = [], [], [], []
            for r_ev in df_ev_rx.itertuples():
                kw_v = str(getattr(r_ev, "_2", "")).split()[0].upper()
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

            st.markdown(f"##### Comparativa Auditada por Marca: Cuota Prescriptiva (Mes vs. YTD) y Facturación Trimestral PDV ({ev_ciu})")
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
        else:
            st.info("Sin registros de evolución para la zona seleccionada.")

    elif st.session_state.sub_evolucion == "FARMACIAS":
        st.markdown(f"##### Auditoría Detallada de Sell-Out por Sucursal Farmacéutica ({ev_ciu})")
        if not df_v_sub.empty and col_prod_v:
            cf1, cf2 = st.columns(2)
            with cf1:
                f_sel = st.multiselect("Filtrar Farmacia(s):", sorted(df_v_sub["NOMBRE_CLIENTE_1"].dropna().unique().tolist()), placeholder="Todas las sucursales...")
            with cf2:
                p_sel = st.multiselect("Filtrar Producto:", sorted(df_v_sub[col_prod_v].dropna().unique().tolist()), placeholder="Todas las líneas...")
            df_vm = df_v_sub
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
        else:
            st.info("Sin registros de facturación para la zona seleccionada.")

# ==============================================================================
# MÓDULO 5: CHIRA — 2 BOTONES LIMPIOS (CONSOLA COPILOTO VS BITÁCORA CRM)
# ==============================================================================
elif st.session_state.modulo_activo == "CHIRA":
    c_back, c_tit = st.columns([0.8, 3.2])
    with c_back:
        if st.button("Volver al Menú Principal", use_container_width=True):
            ir_a_modulo("HUB"); st.rerun()
    with c_tit:
        st.markdown("<div class='module-banner'>MÓDULO 5: CHIRA — INTELIGENCIA COMERCIAL CONVERSACIONAL Y BITÁCORA CRM</div>", unsafe_allow_html=True)

    st.markdown("<div class='subnav-label'>SELECCIONE LA HERRAMIENTA DE CHIRA:</div>", unsafe_allow_html=True)
    bch1, bch2 = st.columns(2)
    with bch1:
        if st.button(
            "1. Consola Copiloto CHIRA (Voz y Consultoría Táctica)",
            use_container_width=True,
            type="primary" if st.session_state.sub_chira == "COPILOTO" else "secondary"
        ):
            st.session_state.sub_chira = "COPILOTO"; st.rerun()
    with bch2:
        if st.button(
            f"2. Bitácora CRM Post-Visita (Unidad 9 — {medico_sel[:20]})",
            use_container_width=True,
            type="primary" if st.session_state.sub_chira == "CRM" else "secondary"
        ):
            st.session_state.sub_chira = "CRM"; st.rerun()

    st.write("")
    if st.session_state.sub_chira == "COPILOTO":
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

        chat_box = st.container(height=390)
        for msg in st.session_state.chira_history:
            with chat_box.chat_message(msg["role"]):
                st.markdown(msg["content"])

        txt_input = st.chat_input("Pregunta a CHIRA (ej: analiza el mercado de expectorantes en rivas / qué pasa con el Dr. Henry Larios)...")
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

                mer_q = resolver_clave_mercado_gutis(t_norm)
                if not mer_q and ch_mer != "TODOS LOS MERCADOS":
                    mer_q = ch_mer

                esp_q = None
                for e_r in LISTA_ESPECIALIDADES_REALES:
                    e_n = normalizar_txt(e_r)
                    if e_n in t_norm or any(p[:5] in t_norm for p in re.split(r'[\s/,-]+', e_n) if len(p) >= 4):
                        esp_q = e_r; break
                if not esp_q and ch_esp != "TODAS":
                    esp_q = ch_esp

                es_plural = any(fp in t_norm for fp in ["CUALES SON", "QUIENES SON", "MEDICOS MAS IMPORTANTES", "ANALISA EL MERCADO", "ANALIZA EL MERCADO", "MERCADO DE", "TOP", "RANKING"])
                med_especifico_q = None
                if not es_plural:
                    universo_m = sorted(list(set(df_panel["Médico"].dropna().unique()).union(set(df_productos["Médico"].dropna().unique()))))
                    palabras_ign = {"PARA", "COMO", "RIVAS", "GRANADA", "MASAYA", "CARAZO", "CHONTALES", "BOACO", "MANAGUA", "TALERDIN", "BIOTOS", "DALIVIO", "GASTROALIVIO", "VENTILAR", "MOMETZONA", "CLEMBROXIL", "MEDICO", "DOCTOR", "DOCTORA", "COMPROMISO", "GUTIS", "LABORATORIO", "LABORATORIOS"}
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

            with st.spinner("Analizando bases de datos y estructurando consultoría táctica..."):
                if modo_q == "MEDICO_INDIVIDUAL":
                    base_cog_med = generar_consultoria_cognitiva_chira_medico(med_especifico_q, consulta_activa)
                    prompt_m = f"""{REGLAS_FARMA}
El usuario consulta sobre el Dr(a). {med_especifico_q}: "{consulta_activa}".
Aquí tienes el expediente auditado y el plan táctico calculado con las cifras reales de Close-Up:
{base_cog_med}
Refina y presenta una respuesta ejecutiva completa que mantenga todas las cifras exactas y responda directamente a la inquietud de Erick."""
                    res_ia_m = llamar_gemini(prompt_m)
                    respuesta_chira = res_ia_m if (res_ia_m and len(res_ia_m.strip()) > 220) else base_cog_med

                elif modo_q == "CRECIMIENTO":
                    z_lbl = ciu_q or "TODO MI PANEL"
                    df_cr = calcular_crecimiento_mercados_mes_vs_ytd(z_lbl, incluir_fuera_panel=True)
                    respuesta_chira = f"### Evolución de Clases Terapéuticas (Mes vs. YTD) — {z_lbl}\n\n{df_a_markdown_nativo(df_cr)}"

                elif modo_q == "LABS":
                    z_lbl = ciu_q or "TODO MI PANEL"
                    df_lb = obtener_radar_laboratorios_doble_barra(ciudad_sel=z_lbl, esp_sel=esp_q or "TODAS")
                    respuesta_chira = f"### Radar de Laboratorios (Mes vs. YTD) — {z_lbl}\n\n{df_a_markdown_nativo(df_lb.head(top_q))}"

                else:
                    modo_p = "FUERA_PANEL" if modo_q == "FUERA_PANEL" else "PANEL"
                    df_rk_q = obtener_ranking_medicos_mercado(ciudad_target=ciu_q, esp_target=esp_q, mer_target=mer_q, modo_panel=modo_p)
                    nota_expansion = ""
                    if df_rk_q.empty and modo_p == "PANEL":
                        df_rk_q = obtener_ranking_medicos_mercado(ciudad_target=ciu_q, esp_target=esp_q, mer_target=mer_q, modo_panel="TODOS")
                        if not df_rk_q.empty:
                            nota_expansion = "_Nota: Se incluyen prescriptores de toda la auditoría Close-Up para mostrar el universo completo de la categoría._\n\n"

                    if not df_rk_q.empty:
                        if modo_q == "CONQUISTA":
                            df_rk_q = df_rk_q.sort_values(by=["Comp Mes", "Comp YTD", "Pxs Mes"], ascending=[False, False, False])
                        base_mercado_rico = generar_analisis_mercado_chira_rico(df_rk_q, mer_q, ciu_q, nota_expansion)
                        prompt_rk = f"""{REGLAS_FARMA}
El usuario preguntó: "{texto_mostrar}".
Presenta este informe auditado de mercado conservando la tabla íntegra y enriqueciendo el plan de acción táctico con base en los nombres y marcas rivales reales:
{base_mercado_rico}"""
                        res_ia_rk = llamar_gemini(prompt_rk)
                        respuesta_chira = res_ia_rk if (res_ia_rk and len(res_ia_rk.strip()) > 250) else base_mercado_rico
                    else:
                        df_cr_fallback = calcular_crecimiento_mercados_mes_vs_ytd(ciu_q or "TODO MI PANEL", incluir_fuera_panel=True)
                        respuesta_chira = f"### Radiografía de Clases Terapéuticas Activas en {ciu_q or 'TODO MI PANEL'}\n\n{df_a_markdown_nativo(df_cr_fallback)}"

            st.session_state.chira_history.append({"role": "assistant", "content": respuesta_chira})
            st.rerun()

    elif st.session_state.sub_chira == "CRM":
        st.markdown(f"##### BITÁCORA CRM POST-VISITA (UNIDAD 9) — DR(A). {medico_sel}")
        with st.form("form_crm_verificado"):
            c1, c2, c3, c4 = st.columns(4)
            with c1: p_foco = st.selectbox("1. Producto Foco (P1):", [m["producto"] for m in MERCADOS_PRIORITARIOS.values()])
            with c2: p_puente = st.selectbox("2. Producto Puente (P2):", ["Ninguno"] + [m["producto"] for m in MERCADOS_PRIORITARIOS.values()], index=2)
            with c3: res_smart = st.selectbox("3. Resultado SMART:", ["Objetivo Principal Logrado", "Objetivo de Respaldo Logrado", "Seguimiento Pendiente"])
            with c4: esc_alc = st.selectbox("4. Escalón Alcanzado:", ["1. No Consciente", "2. Consciente", "3. Prueba (2-10 Pxs)", "4. Adopción (25-50%)", "5. Lealtad (>50%)"])
            ca1, ca2 = st.columns(2)
            with ca1: ac_med = st.text_input("Compromiso del Médico:", value="Consolidar prescripción y puente clínico")
            with ca2: ac_vis = st.text_input("Compromiso del Visitador:", value="Garantizar inventario en farmacias aliadas")
            notas_crm = st.text_area("Observaciones Clínicas y Próxima Apertura:", height=75)

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
            st.dataframe(df_hist_crm.tail(10), hide_index=True, use_container_width=True, height=240)
            csv_b = df_hist_crm.to_csv(index=False).encode("utf-8-sig")
            st.download_button("Descargar Bitácora CRM Completa (CSV)", data=csv_b, file_name=f"Bitacora_CRM_Gutis_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)
