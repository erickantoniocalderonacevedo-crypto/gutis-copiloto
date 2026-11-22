"""
Motor Cognitivo y Analítico Todo-en-Uno CHIRA v4.0 para Gutis BI.
Autocontenido (sin riesgo de desincronización con ai_service.py).
Cubre:
  - 15 objeciones reales de campo (precio, genérico, hábito, sabor/pediatría, somnolencia,
    ardor nasal, irritación gástrica, posología, estudios, quiebre de stock, cambio en
    mostrador, sin tiempo/30 seg, solo pide muestras y compliance/congreso).
  - Comparativas técnicas (Vs.), consultas clínicas rápidas y redacción de WhatsApp.
  - 6 motores de datos exactos: Evolución de Sucursales (6 meses), Abordaje de Sucursales,
    Caída de Recetas, Subida de Cuota, Potencial de Expansión y Cruce Rx vs. Venta Mensual.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from gutis_bi.ai_service import llamar_gemini, obtener_api_key
from gutis_bi.analytics import (
    df_a_markdown_nativo,
    formatear_nombre_medico,
    generar_analisis_mercado_chira_rico,
    generar_consultoria_cognitiva_chira_medico,
    ranking_medicos,
    resumen_mercados,
    resumen_ventas_ciudad,
)
from gutis_bi.catalog import MERCADOS_PRIORITARIOS
from gutis_bi.data import normalizar_txt, resolver_clave_mercado_gutis

ALIAS_VENTA_A_TOKENS = {
    "BIOTOS": ["BIOTOS"],
    "TALERDIN": ["TALERDIN"],
    "MOMETZONA": ["MOMETZONA"],
    "CLEMBROXIL": ["CLEMBROXIL"],
    "VENTILAR": ["VENTILAR"],
    "MUPIRAL": ["MUPIRAL"],
    "BICORPAN": ["BICORPAN"],
    "GASTROALIVIO": ["GASTROALIVIO"],
    "DALIVIUM": ["DALIVIO", "DALIVIUM"],
}


def canonizar_departamento(texto: Any) -> str:
    t = normalizar_txt(texto)
    if not t:
        return "OTROS"
    for depto in [
        "MANAGUA", "MASAYA", "GRANADA", "CARAZO", "RIVAS",
        "BOACO", "CHONTALES", "NUEVA GUINEA", "JINOTEGA",
        "MATAGALPA", "LEON", "CHINANDEGA", "ESTELI", "RAAN",
    ]:
        if depto in t:
            return depto
    if "WALMART" in t or "CSU" in t:
        return "CADENA WALMART"
    if "FARMACOSTO" in t:
        return "FARMACOSTO"
    return t


def _match_producto_venta(df_v: pd.DataFrame, clave_mercado: Optional[str]) -> pd.DataFrame:
    if df_v.empty or not clave_mercado or "PRODUCTO_VENTA" not in df_v.columns:
        return df_v
    meta = MERCADOS_PRIORITARIOS.get(clave_mercado, {})
    objetivo = normalizar_txt(f"{clave_mercado} {meta.get('producto', '')}")
    pv_norm = df_v["PRODUCTO_VENTA"].apply(normalizar_txt)

    tokens_match = []
    for vm4_key, aliases in ALIAS_VENTA_A_TOKENS.items():
        if vm4_key in objetivo or any(a in objetivo for a in aliases):
            tokens_match.append(vm4_key)
    if tokens_match:
        return df_v[pv_norm.isin(tokens_match)].copy()

    raiz = normalizar_txt(meta.get("producto", clave_mercado)).split()[0]
    return df_v[pv_norm.str.contains(re.escape(raiz[:6]), na=False)].copy()


def _clave_desde_vm4(vm4_str: str) -> Optional[str]:
    v_norm = normalizar_txt(vm4_str)
    if not v_norm:
        return None
    if v_norm == "DALIVIUM":
        return resolver_clave_mercado_gutis("DALIVIO", "DALIVIO")
    return resolver_clave_mercado_gutis(v_norm, v_norm)


def _orden_meses_ventas(df_v: pd.DataFrame) -> List[str]:
    if df_v.empty:
        return []
    if "Mes_Label" in df_v.columns:
        if "Mes_Orden" in df_v.columns:
            return (
                df_v[["Mes_Orden", "Mes_Label"]]
                .drop_duplicates()
                .sort_values("Mes_Orden")["Mes_Label"]
                .tolist()
            )
        return df_v["Mes_Label"].dropna().unique().tolist()
    if "Trimestre" in df_v.columns:
        return sorted(df_v["Trimestre"].dropna().unique().tolist())
    return []


# ============================================================================
# 1. TABLA MENSUAL DE 6 MESES + REAL VS CUOTA (Módulo 4 Evolución)
# ============================================================================
def ventas_mensuales_resumen(
    df_ventas: pd.DataFrame,
    ciudad: Optional[str] = None,
    producto: Optional[str] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    kpis = {
        "meses": [],
        "totales_mes": {},
        "cuotas_mes": {},
        "total_real": 0.0,
        "total_cuota": 0.0,
        "pct_cumpl": 0.0,
        "brecha_total": 0.0,
        "es_mensual": False,
    }
    if df_ventas.empty or "Monto Real" not in df_ventas.columns:
        return pd.DataFrame(), kpis

    sub = df_ventas.copy()
    if "Mes_Label" not in sub.columns and "Trimestre" in sub.columns:
        sub["Mes_Label"] = sub["Trimestre"]
    sub["DEPTO_CANON"] = sub["DESCRIPCION_RUTA"].apply(canonizar_departamento)
    if ciudad and ciudad not in ("TODO MI PANEL", "TODAS"):
        ciu_canon = canonizar_departamento(ciudad)
        sub = sub[
            (sub["DEPTO_CANON"] == ciu_canon)
            | (sub["DESCRIPCION_RUTA"].str.contains(re.escape(normalizar_txt(ciudad)), na=False))
        ]
    if producto and producto not in ("TODOS", "Todos"):
        p_norm = normalizar_txt(producto)
        sub = sub[sub["PRODUCTO_VENTA"].apply(normalizar_txt).str.contains(re.escape(p_norm[:6]), na=False)]

    if sub.empty:
        return pd.DataFrame(), kpis

    meses = _orden_meses_ventas(sub)
    kpis["meses"] = meses
    kpis["es_mensual"] = len(meses) >= 2 and not all(m in ("Q1", "Q2", "Q3", "Q4") for m in meses)

    tiene_cuota = "Monto Cuota" in sub.columns
    for m in meses:
        sm = sub[sub["Mes_Label"] == m]
        kpis["totales_mes"][m] = round(float(sm["Monto Real"].sum()), 2)
        kpis["cuotas_mes"][m] = round(float(sm["Monto Cuota"].sum()), 2) if tiene_cuota else 0.0

    kpis["total_real"] = round(float(sub["Monto Real"].sum()), 2)
    kpis["total_cuota"] = round(float(sub["Monto Cuota"].sum()), 2) if tiene_cuota else 0.0
    kpis["pct_cumpl"] = round((kpis["total_real"] / kpis["total_cuota"] * 100.0), 1) if kpis["total_cuota"] > 0 else 0.0
    kpis["brecha_total"] = round(kpis["total_real"] - kpis["total_cuota"], 2)

    piv = pd.pivot_table(
        sub,
        values="Monto Real",
        index=["DEPTO_CANON", "NOMBRE_CLIENTE_1", "PRODUCTO_VENTA"],
        columns=["Mes_Label"],
        aggfunc="sum",
        fill_value=0.0,
    ).reset_index()

    for m in meses:
        if m not in piv.columns:
            piv[m] = 0.0
        piv[m] = piv[m].round(2)

    piv["Real Semestre ($)"] = piv[meses].sum(axis=1).round(2)

    if tiene_cuota:
        cuota_grp = (
            sub.groupby(["DEPTO_CANON", "NOMBRE_CLIENTE_1", "PRODUCTO_VENTA"], as_index=False)["Monto Cuota"]
            .sum()
            .rename(columns={"Monto Cuota": "Cuota Semestre ($)"})
        )
        piv = piv.merge(cuota_grp, on=["DEPTO_CANON", "NOMBRE_CLIENTE_1", "PRODUCTO_VENTA"], how="left")
        piv["Cuota Semestre ($)"] = piv["Cuota Semestre ($)"].fillna(0.0).round(2)
        piv["% Cumpl."] = np.where(
            piv["Cuota Semestre ($)"] > 0,
            (piv["Real Semestre ($)"] / piv["Cuota Semestre ($)"] * 100.0).round(1),
            0.0,
        )
        piv["Brecha ($)"] = (piv["Real Semestre ($)"] - piv["Cuota Semestre ($)"]).round(2)

    if len(meses) >= 2:
        ult, prev = meses[-1], meses[-2]
        piv["Var. Últ. Mes ($)"] = (piv[ult] - piv[prev]).round(2)

    piv = piv.rename(
        columns={
            "DEPTO_CANON": "Departamento",
            "NOMBRE_CLIENTE_1": "Sucursal / Farmacia",
            "PRODUCTO_VENTA": "Producto",
        }
    )
    orden_cols = ["Departamento", "Sucursal / Farmacia", "Producto"] + meses + ["Real Semestre ($)"]
    for extra in ["Cuota Semestre ($)", "% Cumpl.", "Brecha ($)", "Var. Últ. Mes ($)"]:
        if extra in piv.columns:
            orden_cols.append(extra)

    piv = piv[orden_cols].sort_values(by="Real Semestre ($)", ascending=False).reset_index(drop=True)
    return piv, kpis


# ============================================================================
# 2. PLAYBOOK COMPLETO DE LAS 15 OBJECIONES REALES + COMPARATIVAS + WHATSAPP
# ============================================================================
def construir_playbook_objecion(
    consulta: str,
    clave_mercado: str,
    medico_foco: str,
    especialidad: str,
    ciudad: str,
    farmacias_str: str,
) -> str:
    meta = MERCADOS_PRIORITARIOS.get(clave_mercado, next(iter(MERCADOS_PRIORITARIOS.values())))
    prod = meta.get("producto", clave_mercado)
    clase = meta.get("clase_terapeutica", "")
    caract = meta.get("caracteristica", "")
    benef = meta.get("beneficio", "")
    arg_fin = meta.get("arg_finanzas", "")
    arg_img = meta.get("arg_imagen", "")
    nicho = meta.get("nicho_flanqueo", "")
    love = meta.get("love_brand", "")
    farm = farmacias_str or "las farmacias aliadas de la zona"
    doc_corto = formatear_nombre_medico(medico_foco) if medico_foco else "Doctor(a)"

    q = normalizar_txt(consulta)

    # Identificar cuál de las 15 objeciones reales es
    if any(w in q for w in ["GENERICO", "MISMA MOLECULA", "COPIA", "IGUAL DE BARATO"]):
        tipo = "Objeción de Genérico («El genérico cuesta la mitad y trae la misma molécula»)"
        verbal = (
            f"«Tiene razón en que el principio activo es el mismo, {doc_corto}. Donde se define el éxito "
            f"en consulta es en la **pureza farmacéutica, excipientes y biodisponibilidad**: **{prod}** "
            f"({caract}) asegura respuesta predecible desde las primeras tomas, evitando recaídas o "
            f"reconsultas que terminan saliendo más caras que el ahorro inicial del genérico.»"
        )
        cierre = f"Póngalo a prueba en sus próximos **3 pacientes donde el genérico haya tenido respuesta lenta**."
    elif any(w in q for w in ["CARO", "PRECIO", "COSTO", "ECONOM", "BARATO", "CARINOSO", "BOLSILLO", "SEGURO"]):
        tipo = "Objeción de Precio / Bolsillo («Es muy caro para mis pacientes»)"
        verbal = (
            f"«Comprendo perfectamente su cuidado por el bolsillo del paciente, {doc_corto}. Cuando "
            f"evaluamos **costo por tratamiento efectivo** y no solo el precio de caja, **{prod}** "
            f"({caract}) permite que **{arg_fin}**, evitando que el paciente compre doble frasco o abandone a mitad.»"
        )
        cierre = f"Resérvelo inicialmente para ese perfil de **{nicho}** donde fallar el tratamiento sale más costoso."
    elif any(w in q for w in ["CASADO", "FIDELIZADO", "NO SUELTA", "FUNCIONA BIEN", "NO SE QUEJAN", "NO ESTA ROTO", "INNOVADOR", "MAS ANOS", "SIEMPRE USO", "RIVAL"]):
        tipo = "Objeción de Hábito / Fidelidad al Rival («Ya estoy casado con otra marca y me funciona»)"
        verbal = (
            f"«Respeto totalmente su experiencia clínica, {doc_corto}, y no vengo a pedirle que cambie "
            f"lo que ya le funciona en su paciente habitual. Solo quiero hacerle una pregunta puntual: "
            f"cuando recibe a ese subgrupo específico de **{nicho}**, ¿qué busca optimizar? Justo para ese "
            f"nicho, **{prod}** aporta **{caract}**.»"
        )
        cierre = f"No cambie su esquema general: pruebe **{prod}** únicamente en **3 casos de rescate** de ese perfil."
    elif any(w in q for w in ["SABOR", "VOMIT", "RECHAZ", "NINOS", "PEDIATR", "JARABE"]):
        tipo = "Objeción Pediátrica / Palatabilidad («Los niños rechazan el sabor o lo vomitan»)"
        verbal = (
            f"«En pediatría la mitad del éxito es que el niño se tome la dosis sin pelea, {doc_corto}. "
            f"**{prod}** fue formulado pensando en palatabilidad y tolerabilidad ({caract}), logrando "
            f"que **{benef}** y mejorando la tranquilidad de los padres.»"
        )
        cierre = f"Indíquelo en sus próximos **3 pacientes pediátricos** donde el rechazo al jarabe sea un reto."
    elif any(w in q for w in ["SUENO", "SOMNOLENCIA", "DORMIDO", "SEDA"]):
        tipo = "Objeción de Tolerabilidad («Causa sueño / somnolencia»)"
        verbal = (
            f"«Justamente ese es el diferencial clave para el paciente activo, {doc_corto}: **{prod}** "
            f"({caract}) está diseñado para mantener control sintomático sin comprometer el desempeño "
            f"diario ni escolar, logrando que **{arg_img}**.»"
        )
        cierre = f"Pruébelo esta semana en pacientes que manejan, estudian o trabajan y no pueden permitirse sedación."
    elif any(w in q for w in ["ARDE", "ARDOR", "RESECA", "NARIZ", "MUCOSA", "MAL SABOR", "SPRAY"]):
        tipo = "Objeción Nasal / Galénica («Arde en la nariz, reseca o deja mal sabor»)"
        verbal = (
            f"«Ese es el motivo #1 por el que el paciente abandona el spray a los 3 días, {doc_corto}. "
            f"Con **{prod}** ({caract}), buscamos proteger la mucosa y dar confort de aplicación para "
            f"que el paciente complete el ciclo y **{benef}**.»"
        )
        cierre = f"Indíquelo en pacientes sensibles o con rinitis persistente que abandonaron sprays irritantes."
    elif any(w in q for w in ["ESTOMAGO", "GASTRI", "IRRITA", "MUY FUERTE", "POSOLOGIA", "MUCHAS TOMAS", "INCOMOD"]):
        tipo = "Objeción de Tolerabilidad Gástrica / Posología («Irrita el estómago o muchas tomas»)"
        verbal = (
            f"«Entiendo su preocupación por el apego y la tolerabilidad, {doc_corto}. Precisamente "
            f"**{prod}** ({caract}) simplifica la adherencia y cuida la tolerabilidad para que **{benef}**.»"
        )
        cierre = f"Evalúelo en sus próximos **3 pacientes** con historial de abandono por molestias digestivas o esquema complejo."
    elif any(w in q for w in ["ESTUDIO", "EVIDENCIA", "ARTICULO", "EXPERIENCIA CLINICA"]):
        tipo = "Objeción Científica («No conozco estudios de esa combinación»)"
        verbal = (
            f"«Valoro mucho su rigor basado en evidencia, {doc_corto}. **{prod}** respalda su mecanismo "
            f"en **{caract}**, orientado a **{benef}**. Hoy mismo le comparto el resumen clínico y "
            f"ficha técnica para que lo revise con calma.»"
        )
        cierre = f"Le envío la monografía por WhatsApp hoy y en la próxima visita revisamos sus impresiones clínicas."
    elif any(w in q for w in ["NO ENCUENTRA", "STOCK", "QUIEBRE", "DISPONIB", "NO DISTRIBUY", "NO HAY EN FARMACIA"]):
        tipo = "Objeción de Disponibilidad («Yo lo receto pero el paciente no lo encuentra»)"
        verbal = (
            f"«Gracias por decírmelo de frente, {doc_corto}; mi trabajo es que ninguna receta suya se pierda "
            f"por inventario. Hoy mismo verifico personalmente el stock de **{prod}** en **{farm}** y le "
            f"confirmo por WhatsApp en qué puntos exactos alrededor de su clínica quedó abastecido.»"
        )
        cierre = f"Acción inmediata hoy: auditar inventario en **{farm}** antes de cerrar la ruta en {ciudad}."
    elif any(w in q for w in ["CAMBIA LA RECETA", "DEPENDIENTE", "MOSTRADOR", "SUSTITU"]):
        tipo = "Objeción de Sustitución en Mostrador («El dependiente me cambia la receta»)"
        verbal = (
            f"«Es un dolor real del mercado, {doc_corto}. Para blindar su prescripción de **{prod}**, "
            f"estamos reforzando capacitación y acuerdos de respeto a receta en **{farm}**, y además "
            f"ayuda mucho indicarle al paciente el beneficio exacto ({caract}) para que no acepte sustitutos.»"
        )
        cierre = f"Hoy paso por el mostrador de **{farm}** para defender su receta y asegurar exhibición/stock."
    elif any(w in q for w in ["NO TENGO TIEMPO", "30 SEGUNDOS", "45 SEGUNDOS", "PASILLO", "RAPIDO", "APURADO"]):
        tipo = "Visita de Pasillo / Sin Tiempo («Dime rápido en 30 segundos»)"
        verbal = (
            f"«Le tomo 25 segundos exactos, {doc_corto}: en **{nicho}**, **{prod}** aporta **{caract}**, "
            f"logrando **{benef}**. Ya lo dejé disponible en **{farm}**. ¿Me permite contar con él en sus "
            f"próximos 3 casos de esta semana?»"
        )
        cierre = f"Entregar recordatorio breve, agradecer su minuto y retirarse puntual."
    elif any(w in q for w in ["MUESTRA", "DEJAME MUESTRAS", "PROBARLO PRIMERO"]):
        tipo = "Objeción de Muestras («Déjame muestras para probarlo primero»)"
        verbal = (
            f"«Con gusto le apoyo con muestras de inicio de **{prod}**, {doc_corto}, para que compruebe "
            f"de primera mano **{benef}**. Para que el paciente complete el tratamiento sin interrumpirlo, "
            f"ya dejé garantizada la presentación comercial en **{farm}**. ¿En qué perfil de paciente "
            f"las empezaría a evaluar esta semana?»"
        )
        cierre = f"Amarrar la entrega de muestras a un perfil específico (**{nicho}**) y dar seguimiento en la siguiente visita."
    elif any(w in q for w in ["CONGRESO", "PATROCINIO", "INSCRIPCION", "CENA", "A CAMBIO", "APOYAME"]):
        tipo = "Objeción de Negociación / Compliance («Apóyame con un congreso y te ayudo con recetas»)"
        verbal = (
            f"«{doc_corto}, su práctica en {ciudad} es muy valiosa para nosotros. Nuestro programa de "
            f"educación médica continua respalda la actualización científica de forma transparente y sin "
            f"condicionamiento de recetas. De mi lado, gestiono su solicitud por el canal institucional "
            f"correspondiente y sigo asegurando stock de **{prod}** en **{farm}** para cuando usted decida indicarlo.»"
        )
        cierre = f"Mantener postura ética firme, amable y profesional sin prometer favores ligados a volumen de prescripción."
    else:
        tipo = f"Argumentario Clínico y Objeciones — {prod} ({clase})"
        verbal = (
            f"«Comprendo su criterio, {doc_corto}. Precisamente para **{nicho}**, **{prod}** aporta "
            f"**{caract}**, logrando que **{benef}** y reforzando **{arg_img}**.»"
        )
        cierre = f"Evaluar **{prod}** en los próximos 3 pacientes de este perfil con respaldo en **{farm}**."

    return f"""### {tipo}
**Producto:** `{prod}` ({clase}) | **Territorio:** `{ciudad}` | **Farmacias Aliadas:** `{farm}`

#### 1. Qué decir en el momento (Verbalización Exacta)
> {verbal}

#### 2. Tres Pilares de Valor del Vademécum Gutis
- **Galénica / Formulación:** {caract.capitalize()}.
- **Beneficio Clínico:** {benef.capitalize()}.
- **Ecuación Costo-Apego:** {arg_fin.capitalize()}.

#### 3. Cierre Práctico de Calle
- **Siguiente paso:** {cierre}
- **Frase de recordación:** *{love}*
"""


def construir_comparativa_vs(
    consulta: str,
    clave_mercado: str,
    ciudad: str,
    farmacias_str: str,
) -> str:
    meta = MERCADOS_PRIORITARIOS.get(clave_mercado, next(iter(MERCADOS_PRIORITARIOS.values())))
    prod = meta.get("producto", clave_mercado)
    clase = meta.get("clase_terapeutica", "")
    caract = meta.get("caracteristica", "")
    benef = meta.get("beneficio", "")
    arg_fin = meta.get("arg_finanzas", "")
    nicho = meta.get("nicho_flanqueo", "")

    return f"""### Comparativa Estratégica Táctica — {prod} ({clase})
**Consulta:** *«{consulta}»* | **Respaldo en {ciudad}:** `{farmacias_str}`

| Dimensión | Ventaja Diferencial de **{prod}** (Gutis) | Enfoque frente a la Competencia |
| :--- | :--- | :--- |
| **Formulación / Galénica** | {caract.capitalize()} | Evita fricciones de tolerabilidad, sabor o esquema fragmentado. |
| **Impacto Clínico** | {benef.capitalize()} | Posicionamiento directo en **{nicho}**. |
| **Valor / Adherencia** | {arg_fin.capitalize()} | Mejor relación costo-tratamiento efectivo para que el paciente termine el ciclo. |

#### Frase de Flanqueo en 15 Segundos:
> «Sin desplazar lo que usted ya conoce, en pacientes con **{nicho}**, **{prod}** le aporta **{caract}**, con disponibilidad inmediata en **{farmacias_str}**.»
"""


def construir_whatsapp_seguimiento(
    consulta: str,
    clave_mercado: str,
    medico_foco: str,
    ciudad: str,
    farmacias_str: str,
) -> str:
    meta = MERCADOS_PRIORITARIOS.get(clave_mercado, next(iter(MERCADOS_PRIORITARIOS.values())))
    prod = meta.get("producto", clave_mercado)
    benef = meta.get("beneficio", "eficacia y adherencia clínica")
    doc_corto = formatear_nombre_medico(medico_foco) if medico_foco else "Doctor(a)"
    farm = farmacias_str or f"farmacias aliadas de {ciudad}"

    return f"""### Mensaje Corto de WhatsApp (Listo para Copiar y Pegar)
**Destinatario sugerido:** `{doc_corto}` ({ciudad}) | **Producto:** `{prod}`

> Buenos días Dr(a). {doc_corto}, le saluda Erick Calderón de Laboratorio Gutis. Muchas gracias por su tiempo y apertura en nuestra visita. Le confirmo que dejamos verificado el inventario de **{prod}** (*{benef}*) en **{farm}** para el respaldo de sus pacientes. Quedo a sus órdenes para cualquier consulta o necesidad de información clínica. ¡Excelente jornada!
"""


# ============================================================================
# 3. MOTOR: EVOLUCIÓN MENSUAL DE SUCURSALES (CRECIMIENTO / CAÍDA EN 6 MESES)
# ============================================================================
def analizar_evolucion_sucursales(
    bundle: Any,
    clave_mercado: Optional[str] = None,
    ciudad: Optional[str] = None,
    consulta: str = "",
) -> str:
    df_v = bundle.ventas
    if df_v.empty:
        return "No se encontró el archivo de ventas mensuales (`datos 2026.xlsx`) para evaluar sucursales."

    sub = df_v.copy()
    if "Mes_Label" not in sub.columns and "Trimestre" in sub.columns:
        sub["Mes_Label"] = sub["Trimestre"]
    sub["DEPTO_CANON"] = sub["DESCRIPCION_RUTA"].apply(canonizar_departamento)
    if ciudad:
        ciu_canon = canonizar_departamento(ciudad)
        sub = sub[
            (sub["DEPTO_CANON"] == ciu_canon)
            | (sub["DESCRIPCION_RUTA"].str.contains(re.escape(normalizar_txt(ciudad)), na=False))
        ]
    if clave_mercado:
        sub = _match_producto_venta(sub, clave_mercado)

    if sub.empty:
        return "No se encontraron ventas por sucursal para ese producto o territorio."

    meses = _orden_meses_ventas(sub)
    if len(meses) < 2:
        return "Se requieren al menos 2 períodos cargados para medir crecimiento por sucursal."

    aviso_cache = ""
    if all(m in ("Q1", "Q2", "Q3", "Q4") for m in meses):
        aviso_cache = "> ⚠️ **Aviso de Caché:** Todavía estás viendo los archivos trimestrales (`Q1–Q3`) en memoria. Abre la barra lateral izquierda → **Estado de Bases de Datos y Caché → Recargar Excels y Limpiar Caché** para cargar los 6 meses de `datos 2026.xlsx`.\n\n"

    piv = pd.pivot_table(
        sub,
        values="Monto Real",
        index=["DEPTO_CANON", "NOMBRE_CLIENTE_1"],
        columns=["Mes_Label"],
        aggfunc="sum",
        fill_value=0.0,
    ).reset_index()

    for m in meses:
        if m not in piv.columns:
            piv[m] = 0.0
        piv[m] = piv[m].round(2)

    piv["Total Período ($)"] = piv[meses].sum(axis=1).round(2)
    piv = piv[piv["Total Período ($)"] > 0].copy()

    mitad = max(1, len(meses) // 2)
    bloque_1 = meses[:mitad]
    bloque_2 = meses[mitad:]
    ult_m, prev_m = meses[-1], meses[-2]

    piv["Prom. 1ra Mitad ($)"] = (piv[bloque_1].sum(axis=1) / len(bloque_1)).round(2)
    piv["Prom. 2da Mitad ($)"] = (piv[bloque_2].sum(axis=1) / len(bloque_2)).round(2)
    piv["Crecimiento ($/mes)"] = (piv["Prom. 2da Mitad ($)"] - piv["Prom. 1ra Mitad ($)"]).round(2)
    piv["Var. Últ. Mes ($)"] = (piv[ult_m] - piv[prev_m]).round(2)

    if "Monto Cuota" in sub.columns:
        cuota_g = sub.groupby(["DEPTO_CANON", "NOMBRE_CLIENTE_1"], as_index=False)["Monto Cuota"].sum()
        piv = piv.merge(cuota_g, on=["DEPTO_CANON", "NOMBRE_CLIENTE_1"], how="left")
        piv["% Cuota"] = np.where(
            piv["Monto Cuota"] > 0,
            (piv["Total Período ($)"] / piv["Monto Cuota"] * 100.0).round(1),
            0.0,
        )
        piv = piv.drop(columns=["Monto Cuota"])

    piv = piv.rename(columns={"DEPTO_CANON": "Departamento", "NOMBRE_CLIENTE_1": "Sucursal / Farmacia"})

    q_up = normalizar_txt(consulta)
    pide_caida = any(w in q_up for w in ["CAIDA", "CAYO", "CAYERON", "BAJANDO", "BAJARON", "DISMINU", "PERDIENDO", "ENFRI"])

    prod_lbl = MERCADOS_PRIORITARIOS[clave_mercado]["producto"] if clave_mercado in MERCADOS_PRIORITARIOS else "Portafolio Gutis"
    ciu_lbl = ciudad.upper() if ciudad else "TODO TU TERRITORIO"
    rango_lbl = f"{meses[0]} → {meses[-1]}"

    cols_mostrar = ["Departamento", "Sucursal / Farmacia"] + meses + ["Total Período ($)", "Crecimiento ($/mes)", "Var. Últ. Mes ($)"]
    if "% Cuota" in piv.columns:
        cols_mostrar.append("% Cuota")

    if pide_caida:
        df_res = piv[piv["Crecimiento ($/mes)"] < 0].sort_values(by="Crecimiento ($/mes)", ascending=True).reset_index(drop=True)
        titulo = f"Sucursales con Mayor Contracción en {prod_lbl} ({rango_lbl}) — {ciu_lbl}"
        resumen_top = "\n".join([
            f"- **{r['Sucursal / Farmacia']}** ({r['Departamento']}): Bajó de `${r['Prom. 1ra Mitad ($)']:,.2f}/mes` a `${r['Prom. 2da Mitad ($)']:,.2f}/mes` (Cierre {ult_m}: `${r[ult_m]:,.2f}` | Total: `${r['Total Período ($)']:,.2f}`)."
            for _, r in df_res.head(5).iterrows()
        ])
    else:
        df_res = piv[piv["Crecimiento ($/mes)"] > 0].sort_values(by="Crecimiento ($/mes)", ascending=False).reset_index(drop=True)
        titulo = f"Sucursales con Mayor Crecimiento en {prod_lbl} ({rango_lbl}) — {ciu_lbl}"
        resumen_top = "\n".join([
            f"- **{r['Sucursal / Farmacia']}** ({r['Departamento']}): Creció de `${r['Prom. 1ra Mitad ($)']:,.2f}/mes` (`{'/'.join(bloque_1)}`) a `${r['Prom. 2da Mitad ($)']:,.2f}/mes` (`{'/'.join(bloque_2)}`) | Cierre {ult_m}: `${r[ult_m]:,.2f}` | Total: `${r['Total Período ($)']:,.2f}`."
            for _, r in df_res.head(5).iterrows()
        ])

    if df_res.empty:
        return f"{aviso_cache}### {titulo}\nNo se encontraron sucursales con esa variación neta en el período seleccionado."

    return f"""{aviso_cache}### {titulo}
Comparativa mes a mes de tus **{len(meses)} períodos** (`{rango_lbl}`) midiendo la aceleración entre la primera mitad (`{' + '.join(bloque_1)}`) y la segunda mitad (`{' + '.join(bloque_2)}`).

{df_a_markdown_nativo(df_res[cols_mostrar].head(15))}

#### Top 5 Sucursales Destacadas:
{resumen_top}
"""


# ============================================================================
# 4. MOTOR: MÉDICOS CON TENDENCIA DE CAÍDA EN RECETAS (CAIDA_RX)
# ============================================================================
def analizar_caida_rx_medicos(
    bundle: Any,
    clave_mercado: Optional[str] = None,
    ciudad: Optional[str] = None,
    solo_panel: bool = True,
) -> str:
    df_prod = bundle.productos
    df_panel = bundle.panel
    df_aud = bundle.auditoria

    if df_prod.empty:
        return "No hay datos de Close-Up cargados para analizar caídas prescriptivas."

    sub = df_prod[df_prod["Clave_Gutis"].notna()].copy()
    if solo_panel and not df_panel.empty:
        sub = sub[sub["Médico"].isin(set(df_panel["Médico"].dropna().unique()))]
    if clave_mercado:
        sub = sub[sub["Clave_Gutis"] == clave_mercado]
    if ciudad:
        c_norm = canonizar_departamento(ciudad)
        sub = sub[sub["CIUDAD_PANEL"].apply(canonizar_departamento) == c_norm]

    if sub.empty:
        return "No se encontraron registros prescriptivos con esos filtros para evaluar tendencia de caída."

    delta_aud_map: Dict[str, Tuple[float, float, float]] = {}
    if not df_aud.empty and "% MS - Mes" in df_aud.columns and "% MS - Ant" in df_aud.columns:
        aud_sub = df_aud.copy()
        if clave_mercado:
            aud_sub = aud_sub[aud_sub["Clave_Gutis"] == clave_mercado]
        aud_g = aud_sub[aud_sub["MARCA"].str.endswith(" GPR") | aud_sub["MARCA"].str.contains("GUTIS|TALERDIN|BIOTOS|MOMETZONA|CLEMBROXIL|VENTILAR|MUPIRAL|BICORPAN|GASTROALIVIO|DALIVIO", na=False)]
        if not aud_g.empty:
            grp_a = aud_g.groupby("Médico")[["% MS - TrasAnt", "% MS - Ant", "% MS - Mes"]].sum() * 100.0
            for m_doc, r in grp_a.iterrows():
                delta_aud_map[m_doc] = (round(float(r["% MS - TrasAnt"]), 1), round(float(r["% MS - Ant"]), 1), round(float(r["% MS - Mes"]), 1))

    filas = []
    for doc, grp in sub.groupby("Médico"):
        pm = int(grp["Pxs-MES"].sum())
        py = int(grp["Pxs-YTD"].sum())
        gm = int(grp[grp["Es_Gutis"]]["Pxs-MES"].sum())
        gy = int(grp[grp["Es_Gutis"]]["Pxs-YTD"].sum())
        if gy <= 0 and py <= 0:
            continue

        ms_m = round((gm / pm * 100.0), 1) if pm > 0 else 0.0
        ms_y = round((gy / py * 100.0), 1) if py > 0 else 0.0
        ritmo_g = round(gy / 9.0, 1)
        caida_pxs = round(gm - ritmo_g, 1)
        delta_ms_ytd = round(ms_m - ms_y, 1)

        _, ant_ms, mes_aud_ms = delta_aud_map.get(doc, (np.nan, np.nan, np.nan))
        caida_aud = (mes_aud_ms - ant_ms) if not np.isnan(ant_ms) else 0.0

        esta_cayendo = (
            (gy >= 3 and gm == 0)
            or (caida_pxs <= -1.0 and gm < ritmo_g)
            or (delta_ms_ytd <= -8.0 and pm >= 2)
            or (caida_aud <= -5.0)
        )
        if not esta_cayendo:
            continue

        grp_riv = grp[~grp["Es_Gutis"]].sort_values(by=["Pxs-MES", "Pxs-YTD"], ascending=False)
        riv_top = f"{grp_riv.iloc[0]['NOMBRE_PRODUCTO']} ({int(grp_riv.iloc[0]['Pxs-MES'])}M)" if not grp_riv.empty else "Sin rival claro"

        pf = grp.iloc[0]
        severidad = abs(min(caida_pxs, 0.0)) * 3.0 + abs(min(delta_ms_ytd, 0.0)) * 0.4 + (10.0 if gm == 0 and gy >= 5 else 0.0)
        alerta = "APAGÓN TOTAL (0 Mes)" if (gm == 0 and gy >= 4) else ("CAÍDA FUERTE" if delta_ms_ytd <= -15 or caida_pxs <= -3 else "ENFRIAMIENTO")

        filas.append({
            "Médico": doc,
            "Ciudad": str(pf.get("CIUDAD_PANEL", "N/D")),
            "Cat": str(pf.get("CAT_PANEL", "S/C")),
            "Gutis Mes": gm,
            "Prom. Mes YTD": ritmo_g,
            "Gutis YTD": gy,
            "% MS Mes": ms_m,
            "% MS YTD": ms_y,
            "Delta MS (pp)": delta_ms_ytd,
            "Alerta": alerta,
            "Rival Absorbiendo": riv_top,
            "_sev": severidad,
        })

    etiqueta_prod = MERCADOS_PRIORITARIOS[clave_mercado]["producto"] if clave_mercado in MERCADOS_PRIORITARIOS else "Portafolio Gutis"
    etiqueta_ciu = ciudad.upper() if ciudad else "TODO TU PANEL"

    if not filas:
        return f"### Radar de Caída Prescriptiva — {etiqueta_prod} ({etiqueta_ciu})\nNo se detectaron médicos con caída significativa en **{etiqueta_prod}** en este corte."

    df_caida = pd.DataFrame(filas).sort_values(by="_sev", ascending=False).drop(columns=["_sev"]).reset_index(drop=True)
    top3 = df_caida.head(3)
    foco_txt = "\n".join([
        f"- **Dr(a). {formatear_nombre_medico(r['Médico'])}** ({r['Ciudad']}, Cat {r['Cat']}): Bajó a `{r['Gutis Mes']} Pxs` este mes frente a su promedio YTD de `{r['Prom. Mes YTD']} Pxs/mes` (`{r['Gutis YTD']} YTD` | `{r['% MS Mes']}%` vs `{r['% MS YTD']}% MS YTD`). Rival activo: `{r['Rival Absorbiendo']}`."
        for _, r in top3.iterrows()
    ])

    return f"""### Alerta de Caída y Enfriamiento Prescriptivo — {etiqueta_prod} ({etiqueta_ciu})
Se detectaron **{len(df_caida)} médicos** con señal de caída o apagón reciente en **{etiqueta_prod}** (Mes actual vs. promedio mensual YTD).

{df_a_markdown_nativo(df_caida.head(12))}

#### Prioridad Inmediata de Rescate en Ruta:
{foco_txt}
"""


# ============================================================================
# 5. MOTOR: SUBIDA DE CUOTA (Close-Up % MS + Sell-Out % Cumplimiento)
# ============================================================================
def analizar_subida_cuota(
    bundle: Any,
    ciudad: Optional[str] = None,
    solo_panel: bool = True,
) -> str:
    df_mer = resumen_mercados(bundle.productos, bundle.panel, ciudad=ciudad, incluir_fuera_panel=not solo_panel)
    df_v = bundle.ventas

    ciu_lbl = ciudad.upper() if ciudad else "TODO TU TERRITORIO"
    bloques = [f"### Auditoría de Subida de Cuota (Prescripción Close-Up + Venta Mensual) — {ciu_lbl}"]

    if not df_mer.empty:
        suben_rx = df_mer[df_mer["Brecha MS Mes vs YTD (pp)"] > 0].sort_values(by="Brecha MS Mes vs YTD (pp)", ascending=False)
        bajan_rx = df_mer[df_mer["Brecha MS Mes vs YTD (pp)"] < 0].sort_values(by="Brecha MS Mes vs YTD (pp)", ascending=True)

        cols_rx = ["Marca Gutis", "Gutis Mes", "Mercado Mes", "% MS Mes", "% MS YTD", "Brecha MS Mes vs YTD (pp)", "Diagnóstico de Evolución"]
        bloques.append("#### 1. Productos que Subieron Cuota Prescriptiva (Close-Up % MS Mes vs. YTD)")
        if not suben_rx.empty:
            bloques.append(df_a_markdown_nativo(suben_rx[cols_rx]))
        else:
            bloques.append("_Ninguna marca registró ganancia neta de % MS este mes frente a su promedio YTD._")

        if not bajan_rx.empty:
            bloques.append("\n**Atención (Marcas que cedieron cuota este mes):** " + ", ".join([
                f"**{r['Marca Gutis']}** (`{r['Brecha MS Mes vs YTD (pp)']:+.1f} pp`)" for _, r in bajan_rx.head(4).iterrows()
            ]))

    if not df_v.empty and "Monto Cuota" in df_v.columns:
        v_sub = df_v.copy()
        if "Mes_Label" not in v_sub.columns and "Trimestre" in v_sub.columns:
            v_sub["Mes_Label"] = v_sub["Trimestre"]
        v_sub["DEPTO_CANON"] = v_sub["DESCRIPCION_RUTA"].apply(canonizar_departamento)
        if ciudad:
            v_sub = v_sub[v_sub["DEPTO_CANON"] == canonizar_departamento(ciudad)]

        meses = _orden_meses_ventas(v_sub)
        if len(meses) >= 2 and not v_sub.empty:
            ult, prev = meses[-1], meses[-2]
            g_ult = v_sub[v_sub["Mes_Label"] == ult].groupby("PRODUCTO_VENTA")[["Monto Real", "Monto Cuota"]].sum()
            g_prev = v_sub[v_sub["Mes_Label"] == prev].groupby("PRODUCTO_VENTA")[["Monto Real", "Monto Cuota"]].sum()
            g_sem = v_sub.groupby("PRODUCTO_VENTA")[["Monto Real", "Monto Cuota"]].sum()

            comp = pd.DataFrame(index=g_sem.index)
            comp[f"Real {prev} ($)"] = g_prev["Monto Real"].reindex(comp.index).fillna(0.0).round(2)
            comp[f"Real {ult} ($)"] = g_ult["Monto Real"].reindex(comp.index).fillna(0.0).round(2)
            comp[f"% Cuota {prev}"] = np.where(g_prev["Monto Cuota"].reindex(comp.index).fillna(0.0) > 0, (comp[f"Real {prev} ($)"] / g_prev["Monto Cuota"].reindex(comp.index) * 100.0).round(1), 0.0)
            comp[f"% Cuota {ult}"] = np.where(g_ult["Monto Cuota"].reindex(comp.index).fillna(0.0) > 0, (comp[f"Real {ult} ($)"] / g_ult["Monto Cuota"].reindex(comp.index) * 100.0).round(1), 0.0)
            comp["Delta Cuota (pp)"] = (comp[f"% Cuota {ult}"] - comp[f"% Cuota {prev}"]).round(1)
            comp["% Cuota Semestre"] = np.where(g_sem["Monto Cuota"] > 0, (g_sem["Monto Real"] / g_sem["Monto Cuota"] * 100.0).round(1), 0.0)
            comp = comp.reset_index().rename(columns={"PRODUCTO_VENTA": "Producto Venta"}).sort_values(by="Delta Cuota (pp)", ascending=False)

            bloques.append(f"\n#### 2. Evolución de Cumplimiento de Cuota en Ventas ({prev} vs. {ult})")
            bloques.append(df_a_markdown_nativo(comp))

    return "\n".join(bloques)


# ============================================================================
# 6. MOTOR: PRODUCTOS CON MAYOR POTENCIAL PARA SUBIR MÁS AÚN
# ============================================================================
def analizar_potencial_expansion(
    bundle: Any,
    ciudad: Optional[str] = None,
    solo_panel: bool = True,
) -> str:
    df_prod = bundle.productos
    df_panel = bundle.panel
    df_v = bundle.ventas

    if df_prod.empty:
        return "No hay datos de prescripción disponibles para calcular potencial de expansión."

    sub = df_prod[df_prod["Clave_Gutis"].notna()].copy()
    if solo_panel and not df_panel.empty:
        sub = sub[sub["Médico"].isin(set(df_panel["Médico"].dropna().unique()))]
    if ciudad:
        sub = sub[sub["CIUDAD_PANEL"].apply(canonizar_departamento) == canonizar_departamento(ciudad)]

    if sub.empty:
        return "No hay registros suficientes para calcular potencial en este territorio."

    brecha_venta_map: Dict[str, float] = {}
    if not df_v.empty and "Monto Cuota" in df_v.columns:
        v_s = df_v.copy()
        if "Mes_Label" not in v_s.columns and "Trimestre" in v_s.columns:
            v_s["Mes_Label"] = v_s["Trimestre"]
        v_s["DEPTO_CANON"] = v_s["DESCRIPCION_RUTA"].apply(canonizar_departamento)
        if ciudad:
            v_s = v_s[v_s["DEPTO_CANON"] == canonizar_departamento(ciudad)]
        meses = _orden_meses_ventas(v_s)
        if meses:
            v_ult = v_s[v_s["Mes_Label"] == meses[-1]]
            for prod_v, grp_v in v_ult.groupby("PRODUCTO_VENTA"):
                k_m = _clave_desde_vm4(str(prod_v))
                if k_m:
                    brecha = max(0.0, float(grp_v["Monto Cuota"].sum() - grp_v["Monto Real"].sum()))
                    brecha_venta_map[k_m] = round(brecha, 2)

    filas = []
    for k_gut, grp in sub.groupby("Clave_Gutis"):
        meta = MERCADOS_PRIORITARIOS.get(k_gut, {})
        tot_m = int(grp["Pxs-MES"].sum())
        gut_m = int(grp[grp["Es_Gutis"]]["Pxs-MES"].sum())
        comp_m = tot_m - gut_m
        ms_m = round((gut_m / tot_m * 100.0), 1) if tot_m > 0 else 0.0

        meds_escalables = 0
        meds_conquista_alta = 0
        for _, g_doc in grp.groupby("Médico"):
            dm = int(g_doc["Pxs-MES"].sum())
            dg = int(g_doc[g_doc["Es_Gutis"]]["Pxs-MES"].sum())
            dc = dm - dg
            if dg > 0 and dc > dg:
                meds_escalables += 1
            elif dg == 0 and dc >= 5:
                meds_conquista_alta += 1

        brecha_usd = brecha_venta_map.get(k_gut, 0.0)
        techo_factor = max(0.15, (100.0 - ms_m) / 100.0)
        score = round((comp_m * 0.7 + meds_escalables * 12.0 + meds_conquista_alta * 8.0) * techo_factor + (brecha_usd / 500.0), 1)

        filas.append({
            "Producto": meta.get("producto", k_gut),
            "% MS Mes": ms_m,
            "Vol. Rival Mes (Pxs)": comp_m,
            "Médicos Listos p/ Escalar": meds_escalables,
            "Médicos Alta Conquista (0% MS)": meds_conquista_alta,
            "Brecha Cuota Últ. Mes ($)": brecha_usd,
            "Índice Oportunidad": score,
        })

    df_pot = pd.DataFrame(filas).sort_values(by="Índice Oportunidad", ascending=False).reset_index(drop=True)
    top3 = df_pot.head(3)
    resumen_top = "\n".join([
        f"- **{r['Producto']}** (`{r['% MS Mes']}% MS`): **{r['Vol. Rival Mes (Pxs)']} recetas/mes** en manos de la competencia, **{r['Médicos Listos p/ Escalar']} médicos** listos para escalar y **${r['Brecha Cuota Últ. Mes ($)']:,.0f}** disponibles para cerrar cuota."
        for _, r in top3.iterrows()
    ])

    ciu_lbl = ciudad.upper() if ciudad else "TODO TU PANEL"
    return f"""### Radar de Potencial de Expansión («Dónde hay más margen para subir») — {ciu_lbl}

{df_a_markdown_nativo(df_pot)}

#### Top 3 Palancas de Crecimiento Rápido:
{resumen_top}
"""


# ============================================================================
# 7. MOTOR: SUCURSALES A ABORDAR Y CON QUÉ PRODUCTOS (DÉFICIT DE CUOTA)
# ============================================================================
def analizar_sucursales_abordaje(
    bundle: Any,
    ciudad: Optional[str] = None,
    clave_mercado: Optional[str] = None,
) -> str:
    df_v = bundle.ventas
    df_prod = bundle.productos

    if df_v.empty:
        return "No se encontró el archivo de ventas mensuales (`datos 2026.xlsx`) para priorizar sucursales."

    sub = df_v.copy()
    if "Mes_Label" not in sub.columns and "Trimestre" in sub.columns:
        sub["Mes_Label"] = sub["Trimestre"]
    sub["DEPTO_CANON"] = sub["DESCRIPCION_RUTA"].apply(canonizar_departamento)
    if ciudad:
        ciu_canon = canonizar_departamento(ciudad)
        sub = sub[
            (sub["DEPTO_CANON"] == ciu_canon)
            | (sub["DESCRIPCION_RUTA"].str.contains(re.escape(normalizar_txt(ciudad)), na=False))
        ]
    if clave_mercado:
        sub = _match_producto_venta(sub, clave_mercado)

    if sub.empty:
        return "No hay datos de sucursales en ventas para ese filtro."

    meses = _orden_meses_ventas(sub)
    ult_mes = meses[-1] if meses else "Últ. Mes"
    tiene_cuota = "Monto Cuota" in sub.columns

    aviso_cache = ""
    if meses and all(m in ("Q1", "Q2", "Q3", "Q4") for m in meses):
        aviso_cache = "> ⚠️ **Aviso de Caché:** Todavía estás viendo los archivos trimestrales (`Q1–Q3`). Toca **Recargar Excels y Limpiar Caché** en la barra lateral para cargar `datos 2026.xlsx`.\n\n"

    demanda_rx_depto: Dict[Tuple[str, str], int] = {}
    if not df_prod.empty:
        p_g = df_prod[df_prod["Es_Gutis"] & df_prod["Clave_Gutis"].notna()].copy()
        p_g["DEPTO_CANON"] = p_g["CIUDAD_PANEL"].apply(canonizar_departamento)
        for (dep, k_m), g_rx in p_g.groupby(["DEPTO_CANON", "Clave_Gutis"]):
            meta_n = normalizar_txt(MERCADOS_PRIORITARIOS.get(k_m, {}).get("producto", k_m)).split()[0]
            if meta_n == "DALIVIO":
                meta_n = "DALIVIUM"
            demanda_rx_depto[(dep, meta_n)] = int(g_rx["Pxs-MES"].sum())

    sub_ult = sub[sub["Mes_Label"] == ult_mes] if meses else sub
    filas_pdv = []

    for (depto, pdv), grp_sem in sub.groupby(["DEPTO_CANON", "NOMBRE_CLIENTE_1"]):
        real_sem = float(grp_sem["Monto Real"].sum())
        n_meses = max(1, grp_sem["Mes_Label"].nunique())
        prom_mes = real_sem / n_meses

        grp_u = sub_ult[(sub_ult["DEPTO_CANON"] == depto) & (sub_ult["NOMBRE_CLIENTE_1"] == pdv)]
        real_ult = float(grp_u["Monto Real"].sum())
        cuota_ult = float(grp_u["Monto Cuota"].sum()) if tiene_cuota else 0.0
        brecha_ult = cuota_ult - real_ult if tiene_cuota else max(0.0, prom_mes - real_ult)
        pct_ult = round((real_ult / cuota_ult * 100.0), 1) if cuota_ult > 0 else 0.0

        if cuota_ult < 250 and prom_mes < 250:
            continue
        if brecha_ult <= 50:
            continue

        if not grp_u.empty and tiene_cuota:
            gp = grp_u.groupby("PRODUCTO_VENTA")[["Monto Real", "Monto Cuota"]].sum()
            gp["Brecha"] = gp["Monto Cuota"] - gp["Monto Real"]
            gp["Pct"] = np.where(gp["Monto Cuota"] > 0, (gp["Monto Real"] / gp["Monto Cuota"] * 100.0).round(0), 0.0)
            gp["Rx_Zona"] = [demanda_rx_depto.get((depto, normalizar_txt(p)), 0) for p in gp.index]
            gp_foco = gp[gp["Brecha"] > 20].sort_values(by=["Brecha", "Rx_Zona"], ascending=[False, False]).head(3)
            prods_rec = " | ".join([
                f"{p} (-${r['Brecha']:,.0f}, {int(r['Pct'])}% cuota" + (f", {int(r['Rx_Zona'])} Rx zona)" if r["Rx_Zona"] > 0 else ")")
                for p, r in gp_foco.iterrows()
            ]) or "Revisar mix completo"
        else:
            prods_rec = "Surtido general del portafolio"

        estado_pdv = "CAÍDA + BAJA CUOTA" if (real_ult < prom_mes * 0.8 and pct_ult < 70) else ("BRECHA DE CUOTA" if pct_ult < 75 else "RECUPERAR RITMO")

        filas_pdv.append({
            "Departamento": depto,
            "Sucursal / Farmacia": pdv,
            f"Real {ult_mes} ($)": round(real_ult, 2),
            f"Cuota {ult_mes} ($)": round(cuota_ult, 2),
            "% Cuota": pct_ult,
            "Déficit ($)": round(brecha_ult, 2),
            "Prom. Semestral ($)": round(prom_mes, 2),
            "Diagnóstico": estado_pdv,
            "Productos a Abordar (Brecha + Demanda Rx)": prods_rec,
        })

    ciu_lbl = ciudad.upper() if ciudad else "TODO TU TERRITORIO"
    if not filas_pdv:
        return f"{aviso_cache}### Plan de Abordaje de Sucursales ({ult_mes}) — {ciu_lbl}\nTodas las sucursales relevantes se encuentran en línea o por encima de su cuota en este filtro."

    df_pdv = pd.DataFrame(filas_pdv).sort_values(by="Déficit ($)", ascending=False).reset_index(drop=True)
    deficit_top10 = df_pdv.head(10)["Déficit ($)"].sum()

    return f"""{aviso_cache}### Plan Prioritario de Abordaje a Sucursales ({ult_mes}) — {ciu_lbl}
Farmacias con mayor brecha pendiente frente a su cuota de **{ult_mes}** (**${deficit_top10:,.2f}** en el Top 10) y los **códigos exactos** a empujar en mostrador.

{df_a_markdown_nativo(df_pdv.head(12))}
"""


# ============================================================================
# 8. MOTOR: CRUCE DEPARTAMENTAL RX (Close-Up) VS. VENTA MENSUAL
# ============================================================================
def analizar_cruce_rx_vs_venta(
    bundle: Any,
    clave_mercado: Optional[str] = None,
    ciudad: Optional[str] = None,
) -> str:
    df_prod = bundle.productos
    df_v = bundle.ventas

    if df_prod.empty or df_v.empty:
        return "Se requieren tanto Close-Up (`PRODUCTOS`) como las ventas mensuales (`datos 2026.xlsx`) para ejecutar el cruce por departamento."

    p_sub = df_prod[df_prod["Clave_Gutis"].notna()].copy()
    if clave_mercado:
        p_sub = p_sub[p_sub["Clave_Gutis"] == clave_mercado]
    p_sub["DEPTO"] = p_sub["CIUDAD_PANEL"].apply(canonizar_departamento)
    p_sub = p_sub[p_sub["DEPTO"] != "FUERA DE PANEL"]

    rx_dep = {}
    for dep, grp in p_sub.groupby("DEPTO"):
        pm = int(grp["Pxs-MES"].sum())
        py = int(grp["Pxs-YTD"].sum())
        gm = int(grp[grp["Es_Gutis"]]["Pxs-MES"].sum())
        gy = int(grp[grp["Es_Gutis"]]["Pxs-YTD"].sum())
        ms_m = round((gm / pm * 100.0), 1) if pm > 0 else 0.0
        ms_y = round((gy / py * 100.0), 1) if py > 0 else 0.0
        rx_dep[dep] = {
            "gm": gm,
            "ritmo_g": round(gy / 9.0, 1),
            "ms_m": ms_m,
            "ms_y": ms_y,
            "delta_ms": round(ms_m - ms_y, 1),
        }

    v_sub = _match_producto_venta(df_v.copy(), clave_mercado)
    if "Mes_Label" not in v_sub.columns and "Trimestre" in v_sub.columns:
        v_sub["Mes_Label"] = v_sub["Trimestre"]
    v_sub["DEPTO"] = v_sub["DESCRIPCION_RUTA"].apply(canonizar_departamento)
    meses = _orden_meses_ventas(v_sub)
    if len(meses) < 2:
        return "No hay al menos 2 meses en ventas para comparar variación mensual contra recetas."

    ult, prev = meses[-1], meses[-2]
    tiene_cuota = "Monto Cuota" in v_sub.columns

    deptos_todos = sorted(set(rx_dep.keys()) | set(v_sub["DEPTO"].unique()))
    if ciudad:
        c_can = canonizar_departamento(ciudad)
        deptos_todos = [d for d in deptos_todos if d == c_can]

    filas = []
    for dep in deptos_todos:
        r_info = rx_dep.get(dep, {"gm": 0, "ritmo_g": 0.0, "ms_m": 0.0, "ms_y": 0.0, "delta_ms": 0.0})
        v_d = v_sub[v_sub["DEPTO"] == dep]
        v_ult = float(v_d[v_d["Mes_Label"] == ult]["Monto Real"].sum())
        v_prev = float(v_d[v_d["Mes_Label"] == prev]["Monto Real"].sum())
        c_ult = float(v_d[v_d["Mes_Label"] == ult]["Monto Cuota"].sum()) if tiene_cuota else 0.0
        if r_info["gm"] == 0 and v_ult == 0 and v_prev == 0:
            continue

        var_v_pct = round(((v_ult - v_prev) / v_prev * 100.0), 1) if v_prev > 0 else (100.0 if v_ult > 0 else 0.0)
        pct_cuota = round((v_ult / c_ult * 100.0), 1) if c_ult > 0 else 0.0

        rx_sube = r_info["delta_ms"] >= 2.0 or (r_info["gm"] > r_info["ritmo_g"] * 1.08)
        rx_baja = r_info["delta_ms"] <= -2.0 or (r_info["ritmo_g"] > 0 and r_info["gm"] < r_info["ritmo_g"] * 0.85)
        v_sube = var_v_pct >= 5.0
        v_baja = var_v_pct <= -5.0

        if rx_sube and v_baja:
            diag = "ALERTA FUGA MOSTRADOR / STOCK (Sube Rx, cae Venta)"
        elif rx_sube and v_sube:
            diag = "CRECIMIENTO SANO (Sube Rx + Sube Venta)"
        elif rx_baja and v_baja:
            diag = "CONTRACCIÓN DUAL (Cae Rx + Cae Venta)"
        elif rx_baja and v_sube:
            diag = "EMPUJE EN FARMACIA / REVISAR MÉDICOS (Cae Rx, sube Venta)"
        else:
            diag = "ESTABLE / EN SEGUIMIENTO"

        filas.append({
            "Departamento": dep,
            "Gutis Rx Mes": r_info["gm"],
            "% MS Mes": r_info["ms_m"],
            "Delta MS (pp)": r_info["delta_ms"],
            f"Venta {prev} ($)": round(v_prev, 2),
            f"Venta {ult} ($)": round(v_ult, 2),
            "Var. Venta (%)": var_v_pct,
            f"% Cuota {ult}": pct_cuota,
            "Diagnóstico Cruzado Rx vs. Venta": diag,
        })

    prod_lbl = MERCADOS_PRIORITARIOS[clave_mercado]["producto"] if clave_mercado in MERCADOS_PRIORITARIOS else "Portafolio Completo Gutis"
    if not filas:
        return f"No se encontraron departamentos comparables entre Close-Up y ventas para **{prod_lbl}**."

    df_cruce = pd.DataFrame(filas).sort_values(by=f"Venta {ult} ($)", ascending=False).reset_index(drop=True)
    return f"""### Cruce Estratégico por Departamento: Recetas Close-Up vs. Venta Mensual ({prev} → {ult}) — {prod_lbl}

{df_a_markdown_nativo(df_cruce)}
"""


# ============================================================================
# 9. CLASIFICADOR COLOQUIAL AUTOCONTENIDO + ORQUESTADOR MAESTRO CHIRA v4.0
# ============================================================================
def _detectar_intencion_local(q_norm: str) -> str:
    tiene_sucursal = any(w in q_norm for w in ["SUCURSAL", "FARMAC", "PDV", "CLIENTE", "PUNTO DE VENTA"])
    tiene_crec_o_caida = any(w in q_norm for w in ["CRECI", "SUBI", "AUMENT", "MEJOR", "MAS VEND", "IMPULS", "CAID", "CAY", "BAJ", "DISMINU", "PERDIEN", "ENFRI"])

    if any(w in q_norm for w in ["WHATSAPP", "MENSAJE", "REDACTAME", "AGRADECERLE"]):
        return "WHATSAPP"
    if any(w in q_norm for w in [" VS ", "VERSUS", "DIFERENCIA ENTRE", "COMPARATIVA", "VENTAJA SOBRE", "VENTAJA TIENE"]):
        return "COMPARATIVA"
    if any(w in q_norm for w in [
        "CARO", "PRECIO", "COSTO", "ECONOM", "BARATO", "CARINOSO", "GENERICO", "MISMA MOLECULA",
        "OBJECION", "QUE HACER", "COMO LE DIGO", "COMO RESPONDO", "COMO ARGUMENTO", "BATEO",
        "SABOR", "VOMIT", "RECHAZ", "SUENO", "SOMNOLENCIA", "ARDE", "ARDOR", "RESECA", "IRRITA",
        "POSOLOGIA", "MUCHAS TOMAS", "ESTUDIOS", "NO ENCUENTRA", "QUIEBRE", "CAMBIA LA RECETA",
        "DEPENDIENTE", "NO TENGO TIEMPO", "30 SEGUNDOS", "45 SEGUNDOS", "MUESTRAS",
        "CONGRESO", "PATROCINIO", "A CAMBIO", "CASADO", "FIDELIZADO", "NO SUELTA",
    ]):
        return "OBJECION"
    if tiene_sucursal and tiene_crec_o_caida:
        return "SUCURSALES_EVOLUCION"
    if tiene_sucursal:
        return "SUCURSALES_ABORDAJE"
    if any(w in q_norm for w in ["VS VENTA", "CONTRA LA VENTA", "ANALIZALO VS", "SELL OUT", "SELL-OUT", "DEPARTAMENTO PRESENTO", "DEPARTAMENTO CAYO", "DEPARTAMENTO SUBIO"]):
        return "CRUCE_RX_VENTA"
    if any(w in q_norm for w in ["CAID", "CAY", "BAJANDO", "ENFRIANDO", "DURMIENDO", "DEJARON DE RECETAR", "FUGA"]):
        return "CAIDA_RX"
    if any(w in q_norm for w in ["SUBIO LA CUOTA", "SUBIERON", "GANE", "VOLANDO", "SUBIDA DE CUOTA", "MAS CUOTA"]):
        return "SUBIDA_CUOTA"
    if any(w in q_norm for w in ["PUEDEN SUBIR", "POTENCIAL", "CARNITA", "JUGO", "MAS MARGEN", "CRECER MAS"]):
        return "POTENCIAL_EXPANSION"
    if any(w in q_norm for w in ["EXPEDIENTE", "GUION", "DILUYE", "COMPARTE"]):
        return "EXPEDIENTE_MEDICO"
    return "AUDITORIA_MERCADO"


def _clasificar_con_gemini_opcional(consulta: str, lista_ciudades: List[str]) -> Optional[Dict[str, str]]:
    if not obtener_api_key():
        return None
    claves = list(MERCADOS_PRIORITARIOS.keys())
    prompt = f"""Traduce la pregunta coloquial de un Visitador Médico en Nicaragua a un JSON de 3 llaves.
Intenciones válidas:
- "OBJECION": qué decir ante objeciones (caro, genérico, hábito/rival, sabor, sueño, ardor, estómago, estudios, stock, mostrador, 30 seg, muestras, congreso).
- "COMPARATIVA": comparar producto Gutis vs rival o pedir ventajas/diferencias.
- "WHATSAPP": redactar mensaje corto de WhatsApp.
- "SUCURSALES_EVOLUCION": qué sucursales/farmacias crecieron, subieron, cayeron o venden más.
- "SUCURSALES_ABORDAJE": qué sucursales/farmacias ir a abordar hoy, déficit de cuota o qué productos empujar en mostrador.
- "CAIDA_RX": qué médicos vienen bajando recetas o se están enfriando.
- "SUBIDA_CUOTA": en qué productos subió la cuota.
- "POTENCIAL_EXPANSION": qué productos pueden subir más aún o tienen mayor potencial.
- "CRUCE_RX_VENTA": comparar recetas/departamentos contra venta real/Sell-Out.
- "EXPEDIENTE_MEDICO": guion o expediente de un médico específico.
- "AUDITORIA_MERCADO": ranking general de médicos por producto o ciudad.

Claves válidas: {json.dumps(claves, ensure_ascii=False)}
Ciudades válidas: {json.dumps(lista_ciudades, ensure_ascii=False)}
Pregunta: "{consulta}"
Devuelve SOLO JSON: {{"intencion":"...","clave_mercado":"...","ciudad":"..."}}"""
    raw = llamar_gemini(prompt, max_tok=180)
    if not raw:
        return None
    try:
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
        m_json = re.search(r"\{.*\}", clean, re.DOTALL)
        if m_json:
            return json.loads(m_json.group(0))
    except Exception:
        pass
    return None


def enrutar_consulta_chira(
    bundle: Any,
    consulta_final: str,
    medico_sel: str,
    especialidad_sel: str,
    ciudad_sel: str,
    alcance_sb: str,
    lista_ciudades: List[str],
    lista_medicos_busqueda: List[str],
) -> Tuple[str, str]:
    q_norm = normalizar_txt(consulta_final)
    solo_panel = alcance_sb.startswith("SOLO")

    # 1. Detección de médico mencionado
    stop_w = {
        "DOCTOR", "DOCTORA", "MEDICO", "BIOTOS", "TALERDIN", "MOMETZONA", "VENTILAR",
        "MASAYA", "GRANADA", "CARAZO", "MANAGUA", "CHONTALES", "RIVAS", "BOACO",
        "PRECIO", "CUOTA", "VENTA", "CAIDA", "SUCURSALES", "SUCURSALS", "CRECIENDO", "CRECIDO",
    }
    medico_detectado = None
    tokens_q = [w for w in re.split(r"[^A-Z0-9]+", q_norm) if len(w) >= 4 and w not in stop_w]
    for m_cand in lista_medicos_busqueda:
        if normalizar_txt(m_cand) in q_norm:
            medico_detectado = m_cand
            break
    if not medico_detectado and tokens_q:
        for m_cand in lista_medicos_busqueda:
            partes_m = set(normalizar_txt(m_cand).split())
            if sum(1 for t in tokens_q if t in partes_m) >= 2:
                medico_detectado = m_cand
                break

    # 2. Intención: regla local infalible primero + refinamiento con Gemini si es ambigua
    intencion = _detectar_intencion_local(q_norm)
    ciu_detectada = next((c for c in lista_ciudades if normalizar_txt(c) in q_norm), None)
    mer_detectado = resolver_clave_mercado_gutis(consulta_final, consulta_final)

    if intencion == "AUDITORIA_MERCADO" and not medico_detectado:
        cls_g = _clasificar_con_gemini_opcional(consulta_final, lista_ciudades)
        if cls_g:
            if cls_g.get("intencion"):
                intencion = cls_g["intencion"]
            if not ciu_detectada and cls_g.get("ciudad") in lista_ciudades:
                ciu_detectada = cls_g["ciudad"]
            if not mer_detectado and cls_g.get("clave_mercado") in MERCADOS_PRIORITARIOS:
                mer_detectado = cls_g["clave_mercado"]

    doc_ctx = medico_detectado or medico_sel
    ciu_ctx = ciu_detectada or ciudad_sel
    sell_ctx = resumen_ventas_ciudad(bundle.ventas, ciu_ctx)

    # 3. Enrutamiento a los motores
    if intencion == "OBJECION":
        mer_obj = mer_detectado or "MR BIOTOS"
        return construir_playbook_objecion(consulta_final, mer_obj, doc_ctx, especialidad_sel, ciu_ctx, sell_ctx["top_farmacias"]), "Playbook de Objeciones TVP (15 Escenarios)"

    if intencion == "COMPARATIVA":
        mer_obj = mer_detectado or "MR BIOTOS"
        return construir_comparativa_vs(consulta_final, mer_obj, ciu_ctx, sell_ctx["top_farmacias"]), "Comparativa Técnica & Flanqueo (Vs.)"

    if intencion == "WHATSAPP":
        mer_obj = mer_detectado or "MR BIOTOS"
        return construir_whatsapp_seguimiento(consulta_final, mer_obj, doc_ctx, ciu_ctx, sell_ctx["top_farmacias"]), "Redacción Rápida de WhatsApp"

    if intencion == "SUCURSALES_EVOLUCION":
        return analizar_evolucion_sucursales(bundle, clave_mercado=mer_detectado, ciudad=ciu_detectada, consulta=consulta_final), "Evolución Mensual de Sucursales (6M)"

    if intencion == "SUCURSALES_ABORDAJE":
        return analizar_sucursales_abordaje(bundle, ciudad=ciu_detectada, clave_mercado=mer_detectado), "Plan de Abordaje a Sucursales (Sell-Out)"

    if intencion == "CAIDA_RX":
        return analizar_caida_rx_medicos(bundle, clave_mercado=mer_detectado, ciudad=ciu_detectada, solo_panel=solo_panel), "Radar de Caída Prescriptiva"

    if intencion == "SUBIDA_CUOTA":
        return analizar_subida_cuota(bundle, ciudad=ciu_detectada, solo_panel=solo_panel), "Auditoría de Subida de Cuota"

    if intencion == "POTENCIAL_EXPANSION":
        return analizar_potencial_expansion(bundle, ciudad=ciu_detectada, solo_panel=solo_panel), "Radar de Potencial de Expansión"

    if intencion == "CRUCE_RX_VENTA":
        return analizar_cruce_rx_vs_venta(bundle, clave_mercado=mer_detectado, ciudad=ciu_detectada), "Cruce Departamental Rx vs. Venta Mensual"

    if medico_detectado or intencion == "EXPEDIENTE_MEDICO":
        return generar_consultoria_cognitiva_chira_medico(bundle, doc_ctx, consulta_final), "Expediente 360 & Guion TVP"

    df_rk_chira = ranking_medicos(
        bundle.productos,
        bundle.panel,
        ciudad=ciu_detectada,
        mercado=mer_detectado,
        modo_panel="PANEL" if solo_panel else "TODOS",
    )
    if not df_rk_chira.empty:
        return generar_analisis_mercado_chira_rico(df_rk_chira, mer_detectado, ciu_detectada), "Auditoría de Mercado Close-Up"

    return generar_consultoria_cognitiva_chira_medico(bundle, medico_sel, consulta_final), "Expediente 360 & Guion TVP"
