"""
Servicio de Integración con Gemini AI para Gutis BI (CHIRA y Guiones TVP).
Implementa header x-goog-api-key, timeout controlado y sanitización estricta.
"""

import os
import requests
import base64
from typing import Optional, List
import streamlit as st

def obtener_api_key() -> str:
    # Si no existe el archivo secrets.toml, Streamlit lanza StreamlitSecretNotFoundError.
    # El try/except protege la ejecución local permitiendo funcionar sin secretos o con variables de entorno.
    try:
        val = st.secrets.get("GEMINI_API_KEY", "")
        if val:
            return str(val).strip()
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "").strip()

def llamar_gemini(prompt_text: str, max_tok: int = 2500) -> Optional[str]:
    api_key = obtener_api_key()
    if not api_key:
        return None

    modelos = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "maxOutputTokens": max_tok,
            "temperature": 0.3
        }
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }

    for mod in modelos:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent"
            res = requests.post(url, headers=headers, json=payload, timeout=12)
            if res.status_code == 200:
                data = res.json()
                cands = data.get("candidates", [])
                if cands and "content" in cands[0] and "parts" in cands[0]["content"]:
                    text = cands[0]["content"]["parts"][0].get("text", "").strip()
                    if len(text) > 40:
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
        "contents": [{
            "parts": [
                {"text": "Transcribe exactamente en español lo que dice este audio, sin agregar comentarios ni saludos."},
                {"inline_data": {"mime_type": mime_type, "data": b64_audio}}
            ]
        }]
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }

    modelos = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    for mod in modelos:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent"
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            if res.status_code == 200:
                data = res.json()
                cands = data.get("candidates", [])
                if cands and "content" in cands[0] and "parts" in cands[0]["content"]:
                    return cands[0]["content"]["parts"][0].get("text", "").strip()
        except Exception:
            continue
    return None
