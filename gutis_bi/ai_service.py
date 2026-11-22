"""
Servicio de Integración con Gemini AI para Gutis BI.
Incluye Traductor de Lenguaje Coloquial (Intent Classifier), Manejo de Objeciones
y Síntesis Ejecutiva conectada al motor de auditoría Close-Up + Sell-Out mensual.
"""

from __future__ import annotations

import base64
import json
import os
import re
from typing import Any, Optional

import requests
import streamlit as st

MODELOS_GEMINI = ["gemini-2.5-flash", "gemini-2.0-flash"]


def obtener_api_key() -> str:
    try:
        val = st.secrets.get("GEMINI_API_KEY", "")
        if val:
            return str(val).strip()
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "").strip()


def llamar_gemini(prompt_text: str, max_tok: int = 2500, temperatura: float = 0.3) -> Optional[str]:
    api_key = obtener_api_key()
    if not api_key:
        return None

    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "maxOutputTokens": max_tok,
            "temperature": temperatura,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    for mod in MODELOS_GEMINI:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent"
            res = requests.post(url, headers=headers, json=payload, timeout=28)
            if res.status_code == 200:
                data = res.json()
                cands = data.get("candidates", [])
                if cands and "content" in cands[0] and "parts" in cands[0]["content"]:
                    text = cands[0]["content"]["parts"][0].get("text", "").strip()
                    if len(text) > 30:
                        return text
        except Exception:
            continue
    return None


def transcribir_audio_gemini(audio_bytes: bytes, mime_type: str = "audio/wav") -> Optional[str]:
    api_key = obtener_api_key()
    if not api_key or not audio_bytes:
        return None

    b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Transcribe exactamente en español lo que dice este audio de un visitador médico "
                            "en Nicaragua (nombres de médicos, fármacos como Talerdín, Biotos Inmune, Mometzona, "
                            "Clembroxil, Ventilar, Mupiral, Bicorpan, Valerpan, Conflexil, Gastroalivio, Renovart, "
                            "farmacias, departamentos y consultas), sin agregar comentarios ni saludos."
                        )
                    },
                    {"inline_data": {"mime_type": mime_type, "data": b64_audio}},
                ]
            }
        ]
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    for mod in MODELOS_GEMINI:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent"
            res = requests.post(url, headers=headers, json=payload, timeout=28)
            if res.status_code == 200:
                data = res.json()
                cands = data.get("candidates", [])
                if cands and "content" in cands[0] and "parts" in cands[0]["content"]:
                    txt = cands[0]["content"]["parts"][0].get("text", "").strip()
                    if txt:
                        return txt
        except Exception:
            continue
    return None


def clasificar_intencion_coloquial(
    consulta: str,
    ciudades_validas: list[str],
    claves_mercado_validas: list[str],
    medicos_validos: list[str],
) -> dict[str, Any]:
    q_up = (consulta or "").upper()

    def _fallback_local() -> dict[str, Any]:
        intencion = "AUDITORIA_MERCADO"
        tiene_sucursal = any(w in q_up for w in ["SUCURSAL", "FARMACIA", "PDV", "CLIENTE", "PUNTO DE VENTA"])
        tiene_crecimiento = any(w in q_up for w in ["CRECI", "SUBIERON", "SUBIO", "AUMENT", "MEJOR", "TOP", "MAS VENDEN", "IMPULSO"])
        tiene_caida = any(w in q_up for w in ["CAIDA", "CAYO", "CAYERON", "BAJANDO", "BAJARON", "BAJO", "ENFRIANDO", "DURMIENDO", "DEJARON DE RECETAR", "PERDIENDO", "DISMINUCION", "DISMINUYO", "FUGA"])

        if any(w in q_up for w in ["CARO", "PRECIO", "COSTO", "ECONOM", "BARATO", "OBJECION", "QUE HACER", "COMO LE DIGO", "COMO RESPONDO", "COMO ARGUMENTO", "BATEO", "CARIÑOSO", "CARINOSO", "ARDOR", "ARDE", "SABOR", "SUEÑO", "SOMNOLENCIA", "GENERICO"]):
            intencion = "OBJECION"
        elif tiene_sucursal and (tiene_crecimiento or tiene_caida):
            intencion = "SUCURSALES_EVOLUCION"
        elif tiene_sucursal:
            intencion = "SUCURSALES_ABORDAJE"
        elif tiene_caida:
            if any(w in q_up for w in ["DEPARTAMENTO", "VENTA", "SELL", "RUTA", "INCREMENTO O DISMINUCION"]):
                intencion = "CRUCE_RX_VENTA"
            else:
                intencion = "CAIDA_RX"
        elif any(w in q_up for w in ["SUBIO LA CUOTA", "SUBIERON", "GANE", "VOLANDO", "CRECIO", "SUBIDA DE CUOTA", "MAS CUOTA"]):
            intencion = "SUBIDA_CUOTA"
        elif any(w in q_up for w in ["PUEDEN SUBIR", "POTENCIAL", "CARNITA", "JUGO", "MAS MARGEN", "CRECER MAS", "OPORTUNIDAD"]):
            intencion = "POTENCIAL_EXPANSION"
        elif any(w in q_up for w in ["VS VENTA", "CONTRA LA VENTA", "SELL OUT", "SELL-OUT", "DEPARTAMENTO PRESENTO", "CAMBIANDO LA RECETA"]):
            intencion = "CRUCE_RX_VENTA"
        elif any(w in q_up for w in ["EXPEDIENTE", "GUION", "DILUYE", "COMPARTE", "CASADO", "FIDELIZADO", "CONGRESO", "PATROCINIO"]):
            intencion = "EXPEDIENTE_MEDICO"

        ciu_det = next((c for c in ciudades_validas if c.upper() in q_up), "")
        med_det = next((m for m in medicos_validos if m.upper() in q_up), "")
        return {"intencion": intencion, "ciudad": ciu_det, "medico": med_det, "producto_texto": consulta}

    api_key = obtener_api_key()
    if not api_key:
        return _fallback_local()

    intenciones_permitidas = [
        "OBJECION",
        "CAIDA_RX",
        "SUBIDA_CUOTA",
        "POTENCIAL_EXPANSION",
        "SUCURSALES_EVOLUCION",
        "SUCURSALES_ABORDAJE",
        "CRUCE_RX_VENTA",
        "EXPEDIENTE_MEDICO",
        "AUDITORIA_MERCADO",
    ]

    prompt_cls = f"""
Eres el enrutador semántico de un Visitador Médico en Nicaragua. Traduce la consulta coloquial a un JSON estricto.

Intenciones válidas (elige UNA):
- "OBJECION": preguntas sobre qué decir o hacer ante objeciones del médico/farmacia (precio caro, genéricos, sabor, ardor nasal, sueño, "casado con otra marca", pedidos de patrocinio/congreso).
- "SUCURSALES_EVOLUCION": preguntas sobre qué sucursales o farmacias han CRECIDO, subido, bajado o vendido más en un producto o en general durante los últimos meses.
- "SUCURSALES_ABORDAJE": preguntas sobre qué sucursales/farmacias ir a abordar hoy, cuáles tienen déficit de cuota o con qué productos entrar en mostrador.
- "CAIDA_RX": preguntas sobre MÉDICOS que vienen bajando recetas, "se están enfriando" o muestran tendencia de caída en un producto.
- "SUBIDA_CUOTA": preguntas sobre en qué productos subió la cuota (% MS o % Real), dónde va ganando terreno o "volando".
- "POTENCIAL_EXPANSION": preguntas sobre qué productos pueden subir más aún, "tienen más carnita/jugo" o mayor potencial de crecimiento.
- "CRUCE_RX_VENTA": preguntas que comparan recetas médicas / departamentos (incremento o disminución) contra la venta real / Sell-Out en farmacias.
- "EXPEDIENTE_MEDICO": preguntas centradas en un médico específico (su guion TVP, expediente, por qué comparte recetas o cómo abordarlo).
- "AUDITORIA_MERCADO": ranking general de médicos por producto o ciudad.

Catálogo de claves de mercado válidas: {json.dumps(claves_mercado_validas, ensure_ascii=False)}
Ciudades/Rutas válidas: {json.dumps(ciudades_validas, ensure_ascii=False)}

Consulta del visitador: "{consulta}"

Devuelve ÚNICAMENTE un JSON con estas 4 llaves:
{{
  "intencion": "UNA_DE_LAS_9",
  "clave_mercado": "CLAVE_EXACTA_O_VACIO",
  "ciudad": "CIUDAD_EXACTA_O_VACIO",
  "medico": "NOMBRE_MEDICO_SI_LO_MENCIONA_O_VACIO"
}}
"""
    payload = {
        "contents": [{"parts": [{"text": prompt_cls}]}],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 220,
            "responseMimeType": "application/json",
        },
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    for mod in MODELOS_GEMINI:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent"
            res = requests.post(url, headers=headers, json=payload, timeout=12)
            if res.status_code == 200:
                data = res.json()
                cands = data.get("candidates", [])
                if cands and "content" in cands[0] and "parts" in cands[0]["content"]:
                    raw_txt = cands[0]["content"]["parts"][0].get("text", "").strip()
                    raw_txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_txt).strip()
                    parsed = json.loads(raw_txt)
                    if isinstance(parsed, dict) and parsed.get("intencion") in intenciones_permitidas:
                        parsed["producto_texto"] = consulta
                        return parsed
        except Exception:
            continue

    return _fallback_local()


def generar_respuesta_objecion_tactica(
    consulta: str,
    clave_mercado: str,
    meta_prod: dict[str, Any],
    medico_foco: str = "",
    especialidad: str = "",
    ciudad: str = "",
    farmacias_str: str = "",
) -> str:
    prod = meta_prod.get("producto", clave_mercado)
    clase = meta_prod.get("clase_terapeutica", "")
    caract = meta_prod.get("caracteristica", "")
    benef = meta_prod.get("beneficio", "")
    arg_fin = meta_prod.get("arg_finanzas", "")
    arg_img = meta_prod.get("arg_imagen", "")
    nicho = meta_prod.get("nicho_flanqueo", "")
    love = meta_prod.get("love_brand", "")

    q_low = (consulta or "").lower()
    es_obj_precio = any(w in q_low for w in ["caro", "precio", "costo", "econ", "barato", "bolsillo", "cariñoso", "carinoso", "generico", "genérico"])
    es_obj_habito = any(w in q_low for w in ["casado", "fidelizado", "no suelta", "rival", "competencia", "siempre usa", "funciona bien"])
    es_obj_compliance = any(w in q_low for w in ["congreso", "patrocinio", "apoyo", "inscripcion", "inscripción", "a cambio"])

    encabezado_doc = f"Contexto Médico Activo: **{medico_foco}** ({especialidad}, {ciudad})" if medico_foco else ""
    farm_txt = farmacias_str if farmacias_str else "farmacias aliadas de la zona"

    if es_obj_precio:
        enfoque_titulo = f"Manejo Táctico de Objeción de Costo / Precio — **{prod}** ({clase})"
        reencuadre = (
            f"«Comprendo perfectamente su enfoque en el presupuesto del paciente, Doctor(a). "
            f"Cuando evaluamos **costo por tratamiento efectivo** y no solo el precio de caja, **{prod}** "
            f"({caract}) permite que **{arg_fin}** — evitando terapias fragmentadas, duplicidad de frascos "
            f"o recaídas que terminan resultando más costosas para la familia.»"
        )
    elif es_obj_habito:
        enfoque_titulo = f"Estrategia de Flanqueo frente a Hábito con Competencia — **{prod}** ({clase})"
        reencuadre = (
            f"«Conozco su experiencia con su esquema habitual, Doctor(a), y no vengo a pedirle que cambie "
            f"de golpe lo que ya le funciona en su paciente general. Solo quiero preguntarle: cuando recibe "
            f"ese perfil específico de **{nicho}**, ¿cómo asegura rapidez de respuesta sin abandono? Para ese nicho "
            f"puntual, **{prod}** aporta **{caract}**.»"
        )
    elif es_obj_compliance:
        enfoque_titulo = f"Respuesta Ética de Educación Médica (Compliance) — **{prod}**"
        reencuadre = (
            f"«Doctor(a), su práctica clínica es muy importante para nosotros. Nuestro programa de educación "
            f"médica continua respalda la actualización científica sin condicionamientos de prescripción. "
            f"De mi lado, mi compromiso es mantenerle actualizado en opciones como **{prod}** y asegurar "
            f"disponibilidad completa en **{farm_txt}** para los pacientes en quienes usted decida indicarlo.»"
        )
    else:
        enfoque_titulo = f"Argumentario Clínico y Manejo de Objeciones — **{prod}** ({clase})"
        reencuadre = (
            f"«Comprendo su criterio clínico, Doctor(a). Precisamente en casos de **{nicho}**, "
            f"**{prod}** aporta **{caract}**, logrando que **{benef}** y reforzando **{arg_img}**.»"
        )

    bloques = [
        f"### {enfoque_titulo}",
        f"*{encabezado_doc}*" if encabezado_doc else "",
        "",
        "#### 1. Empatía y Reencuadre en Consultorio (Verbalización)",
        f"> {reencuadre}",
        "",
        "#### 2. Tres Pilares de Valor para Sostener la Prescripción",
        f"- **Diferencial Galénico / Formulación:** {caract.capitalize()}.",
        f"- **Impacto Clínico Directo:** {benef.capitalize()}.",
        f"- **Ecuación Costo-Apego:** {arg_fin.capitalize()}.",
        "",
        "#### 3. Nicho de Entrada Rápida y Respaldo en Punto de Venta",
        f"- **Perfil ideal para iniciar:** Pacientes con *{nicho}*.",
        f"- **Disponibilidad verificada:** Asegurar respaldo de inventario en **{farm_txt}**.",
        f"- **Cierre de recordación:** *{love}*",
    ]

    return "\n".join(b for b in bloques if b is not None)
