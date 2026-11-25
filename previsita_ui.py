"""
Visuales del Módulo 2 (Previsita TVP) para Gutis BI.

Reemplaza la cabecera y la pestaña «Mapa de Mercado del Especialista» por una vista que
responde, en este orden: ¿quién es el médico?, ¿cuánto receta y cuánto es de Gutis?,
¿en qué mercados estoy y qué debo hacer en cada uno?

No cambia ninguna fórmula: usa los mismos campos que `mercados_evaluados` en app.py.
"""
from __future__ import annotations

import re
from typing import Any, Callable

import numpy as np
import pandas as pd
import streamlit as st

from analisis_ventas import CSS, _emit, esc
from mercado_ui import CSS_MK, delta_pill

CSS_PV = """
<style>
.pv-head{display:grid;grid-template-columns:1.25fr 1.35fr 1.2fr 1.1fr;gap:12px;margin:2px 0 14px}
@media(max-width:1100px){.pv-head{grid-template-columns:1fr 1fr}}
.pv-c{background:#fff;border:1px solid #e2e8f0;border-top:4px solid #002b5c;border-radius:12px;padding:14px 16px;box-shadow:0 1px 3px rgba(15,23,42,.05);min-width:0}
.pv-l{font-size:.68rem;font-weight:800;letter-spacing:.06em;color:#64748b;text-transform:uppercase}
.pv-v{font-size:1.3rem;font-weight:800;color:#0f172a;margin:6px 0 4px;line-height:1.2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pv-v small{font-size:.8rem;font-weight:700;color:#64748b}
.pv-s{font-size:.78rem;color:#64748b;line-height:1.4}
.pv-chip{display:inline-block;font-size:.68rem;font-weight:800;padding:2px 8px;border-radius:6px;margin-right:4px;white-space:nowrap}
.pv-sb{display:flex;height:16px;border-radius:5px;overflow:hidden;background:#f1f5f9}
.pv-sb>div{display:flex;align-items:center;justify-content:center;font-size:.68rem;font-weight:800;color:#fff;min-width:0;overflow:hidden}
.pv-sb .g{background:#002b5c}.pv-sb .c{background:#94a3b8}
.pv-bl{display:flex;align-items:center;gap:8px;margin:3px 0;font-size:.74rem;color:#475569}
.pv-bl>b{width:30px;color:#0f172a}.pv-bl>.pv-sb{flex:1}.pv-bl>span{width:92px;text-align:right;font-variant-numeric:tabular-nums}
.pv-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:12px}
.pv-card{background:#fff;border:1px solid #e2e8f0;border-top:5px solid #cbd5e1;border-radius:12px;padding:14px 16px;display:flex;flex-direction:column;gap:10px;min-width:0}
.pv-top{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap}
.pv-n{font-weight:800;color:#0f172a;font-size:1.05rem;line-height:1.25}
.pv-n small{display:block;font-weight:600;color:#64748b;font-size:.76rem;margin-top:3px;line-height:1.3}
.pv-pb{display:grid;grid-template-columns:40px 1fr 56px;gap:8px;align-items:center}
.pv-pb>b{font-size:.78rem;color:#475569}
.pv-pb .tr{position:relative;height:20px;border-radius:6px;background:#eef2f7;overflow:hidden}
.pv-pb .tr i{position:absolute;left:0;top:0;bottom:0;border-radius:6px}
.pv-pb .tr u{position:absolute;top:0;bottom:0;width:2px;background:#64748b;opacity:.55}
.pv-pb .tr.none{display:flex;align-items:center;padding-left:8px;font-size:.74rem;color:#94a3b8;font-weight:600}
.pv-pb>span{font-size:1.15rem;font-weight:800;color:#0f172a;text-align:right;font-variant-numeric:tabular-nums}
.pv-pn{font-size:.74rem;color:#64748b;margin:3px 0 8px 48px}
.pv-jr{display:flex;gap:6px}
.pv-jr .d{width:26px;height:26px;border-radius:50%;background:#e2e8f0;color:#94a3b8;font-size:.76rem;font-weight:800;display:flex;align-items:center;justify-content:center}
.pv-jr .d.goal{background:#fff;border:2px dashed #475569;color:#334155}
.pv-jr .d.on{color:#fff}
.pv-lt{font-size:.8rem;color:#64748b;margin-top:4px}
.pv-lt b{color:#0f172a}
.pv-act{font-size:.82rem;color:#334155;line-height:1.4;background:#f8fafc;border-radius:8px;padding:8px 10px}
.pv-note{font-size:.74rem;color:#92400e;background:#fffbeb;border-radius:6px;padding:4px 8px}
.pv-rec{padding:10px 6px;border-bottom:1px solid #f1f5f9}
.pv-rec.gut{background:#f0f7ff}
.pv-rec .nm{font-weight:700;color:#0f172a;font-size:.9rem;margin-bottom:5px;line-height:1.3}
.pv-rec .mt{font-size:.76rem;color:#64748b;margin-top:4px}
.pv-plan{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:14px}
@media(max-width:1000px){.pv-plan{grid-template-columns:1fr}}
.pv-pc{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px 16px;position:relative}
.pv-pc .num{position:absolute;top:12px;right:14px;width:26px;height:26px;border-radius:50%;background:#002b5c;color:#fff;font-weight:800;font-size:.8rem;display:flex;align-items:center;justify-content:center}
.pv-pc .rol{font-size:.68rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:#0284c7}
.pv-pc .nom{font-size:1.1rem;font-weight:800;color:#0f172a;margin:4px 0 6px}
</style>
"""

NOMBRES_ESCALA = ["No consciente", "Consciente", "Prueba", "Adopción", "Lealtad"]

# (fondo chip, texto chip, color de acento, etiqueta)
MODOS = {
    "LEALTAD": ("#dcfce7", "#166534", "#059669", "LEALTAD · Blindar y puente"),
    "LIDER": ("#e0f2fe", "#075985", "#0284c7", "LÍDER · Consolidar"),
    "EXPANSION": ("#fef3c7", "#92400e", "#d97706", "EXPANSIÓN · Crecer"),
    "CONQUISTA": ("#fee2e2", "#991b1b", "#dc2626", "CONQUISTA · Abrir"),
}


def _paso(texto: str, por_defecto: int = 1, usar_max: bool = False) -> int:
    nums = [int(n) for n in re.findall(r"(\d)\.", str(texto)) if 1 <= int(n) <= 5]
    if not nums:
        return por_defecto
    return max(nums) if usar_max else nums[0]


def modo_visual(m: dict) -> str:
    """Misma lógica de clasificación que usaba el mapa original (lealtad / líder / resto)."""
    if m["modo_tactico"] == "LEALTAD":
        return "LEALTAD"
    if m["gutis_mes"] > 0 and m["gutis_mes"] >= m["rival_mes_top"]:
        return "LIDER"
    return m["modo_tactico"] if m["modo_tactico"] in MODOS else "CONQUISTA"


def _chip(modo: str) -> str:
    bg, fg, _, txt = MODOS[modo]
    return f"<span class='pv-chip' style='background:{bg};color:{fg}'>{txt}</span>"


def _barra_pct(etiqueta: str, g: int, t: int, color: str) -> str:
    """Barra de % Gutis (0-100) con marcas en 25% y 50% (niveles de Adopción y Lealtad)."""
    if t <= 0:
        return f"<div class='pv-pb'><b>{etiqueta}</b><div class='tr none'>sin recetas</div><span></span></div>"
    pct = g / t * 100
    w = max(pct, 2.0) if g > 0 else 0
    return (f"<div class='pv-pb'><b>{etiqueta}</b><div class='tr'><i style='width:{w:.1f}%;background:{color}'></i>"
            f"<u style='left:25%'></u><u style='left:50%'></u></div><span>{pct:.0f}%</span></div>"
            f"<div class='pv-pn'>{g} de {t} Rx son de Gutis</div>")


def _viaje(m: dict, modo: str) -> str:
    actual = _paso(m["escala_nivel"], 1)
    meta = _paso(m["escala_meta"], min(actual + 1, 5), usar_max=True)
    color = MODOS[modo][2]
    pasos = []
    for i in range(1, 6):
        if i <= actual:
            pasos.append(f"<span class='d on' style='background:{color}' title='{i}. {NOMBRES_ESCALA[i - 1]}'>{i}</span>")
        elif i == meta:
            pasos.append(f"<span class='d goal' title='Meta: {i}. {NOMBRES_ESCALA[i - 1]}'>{i}</span>")
        else:
            pasos.append(f"<span class='d' title='{i}. {NOMBRES_ESCALA[i - 1]}'>{i}</span>")
    texto = f"Hoy: <b>{NOMBRES_ESCALA[actual - 1]}</b>" + (f" → Meta: <b>{NOMBRES_ESCALA[meta - 1]}</b>" if meta > actual else " · <b>Meta cumplida</b>")
    return f"<div><div class='pv-jr'>{''.join(pasos)}</div><div class='pv-lt'>{texto}</div></div>"


# -----------------------------------------------------------------------------
# CABECERA
# -----------------------------------------------------------------------------
def render_header_previsita(medico: str, especialidad: str, categoria: str, ciudad: str,
                            dp: dict[str, Any], m_foco: dict, sell_z: dict[str, Any]) -> None:
    _emit(CSS)
    _emit(CSS_MK)
    _emit(CSS_PV)
    pm, py = int(dp.get("Pxs Mes", 0)), int(dp.get("Pxs YTD", 0))
    gm, gy = int(dp.get("Gutis Mes", 0)), int(dp.get("Gutis YTD", 0))
    cm, cy = int(dp.get("Comp Mes", 0)), int(dp.get("Comp YTD", 0))
    if pm > 0:
        ref_lbl, g_ref, c_ref, ms_ref = "este mes", gm, cm, gm / pm * 100
        total_txt = f"{pm:,} <small>Rx este mes · {py:,} YTD</small>"
    else:
        ref_lbl, g_ref, c_ref, ms_ref = "YTD", gy, cy, (gy / py * 100 if py > 0 else 0.0)
        total_txt = f"{py:,} <small>Rx YTD · sin recetas este mes</small>"
    modo = modo_visual(m_foco)
    aliadas = [a.strip() for a in str(sell_z.get("top_farmacias", "")).split(",") if a.strip()]
    aliadas_txt = ", ".join(aliadas[:2]) + (f" +{len(aliadas) - 2} más" if len(aliadas) > 2 else "") if aliadas else "Sin farmacias aliadas registradas"
    _emit(f"""
    <div class='pv-head' translate='no'>
      <div class='pv-c'>
        <div class='pv-l'>Especialista en foco</div>
        <div class='pv-v' title='{esc(medico)}' style='white-space:normal;font-size:1.15rem'>{esc(medico)}</div>
        <div class='pv-s'><span class='pv-chip' style='background:#f1f5f9;color:#334155'>{esc(especialidad)}</span>
        <span class='pv-chip' style='background:#dbeafe;color:#1e40af'>Cat {esc(categoria)}</span>
        <span class='pv-chip' style='background:#e0f2fe;color:#075985'>{esc(ciudad)}</span></div>
      </div>
      <div class='pv-c' style='border-top-color:#0284c7'>
        <div class='pv-l'>Recetas auditadas del médico</div>
        <div class='pv-v'>{total_txt}</div>
        <div class='pv-bl' style='margin-top:6px'><b>Gutis</b><div class='pv-sb' style='flex:1'><div class='g' style='width:{max(min(ms_ref, 100), 0):.1f}%'></div><div class='c' style='width:{100 - max(min(ms_ref, 100), 0):.1f}%'></div></div><span style='width:46px;text-align:right;font-weight:800;color:#0f172a'>{ms_ref:.0f}%</span></div>
        <div class='pv-s'>{g_ref} de Gutis y {c_ref} de competencia ({ref_lbl}).</div>
      </div>
      <div class='pv-c' style='border-top-color:{MODOS[modo][2]}'>
        <div class='pv-l'>Prioridad #1 de esta visita</div>
        <div class='pv-v'>{esc(m_foco['prod_gutis'])}</div>
        <div class='pv-s'>{_chip(modo)}<br>Rival principal: <b>{esc(m_foco['rival_corto'])}</b></div>
      </div>
      <div class='pv-c' style='border-top-color:#10b981'>
        <div class='pv-l'>Sell-out de la zona · {esc(ciudad)}</div>
        <div class='pv-v' style='color:#047857'>&#36;{float(sell_z.get('total', 0)):,.0f}</div>
        <div class='pv-s'>{int(sell_z.get('pdvs', 0))} puntos de venta<br>Aliadas: {esc(aliadas_txt)}</div>
      </div>
    </div>
    """)


# -----------------------------------------------------------------------------
# MAPA DE MERCADOS
# -----------------------------------------------------------------------------
def _fila_mercado(m: dict) -> str:
    modo = modo_visual(m)
    acento = MODOS[modo][2]
    riv = esc(m["rival_corto"]) if m["comp_mes"] + m["comp_ytd"] > 0 else "sin competidor registrado"
    nota = "<div class='pv-note'>Menos de 5 recetas este mes: el % puede cambiar mucho con una sola.</div>" if 0 < m["tot_mes"] < 5 else ""
    return (
        f"<div class='pv-card' style='border-top-color:{acento}'>"
        f"<div class='pv-top'><div class='pv-n'>{esc(m['prod_gutis'])} <span class='pv-chip' style='background:#002b5c;color:#fff;font-size:.62rem'>P{m['prioridad']}</span>"
        f"<small>{esc(m['clase_terapeutica'])}<br>Rival: <b style='color:#b91c1c'>{riv}</b></small></div>{_chip(modo)}</div>"
        f"<div>{_barra_pct('Mes', m['gutis_mes'], m['tot_mes'], acento)}{_barra_pct('Año', m['gutis_ytd'], m['tot_ytd'], acento)}</div>"
        f"{nota}{_viaje(m, modo)}"
        f"<div class='pv-act'>{esc(m['paso_recomendado'])}</div></div>"
    )


def render_mapa_previsita(
    lista: list[dict],
    idx_plan: tuple[int, int, int],
    medico: str,
    df_productos: pd.DataFrame,
    productos_medico_fn: Callable[[pd.DataFrame, str, str], pd.DataFrame],
) -> None:
    _emit(CSS)
    _emit(CSS_MK)
    _emit(CSS_PV)

    # ---- Plan de visita (misma selección que el Canvas) ----
    roles = ["1ª posición · Ancla", "2ª posición · Puente clínico", "3ª posición · Recordación"]
    tarjetas = []
    for n, (i, rol) in enumerate(zip(idx_plan, roles), 1):
        if i is None or i >= len(lista):
            continue
        m = lista[i]
        modo = modo_visual(m)
        tarjetas.append(
            f"<div class='pv-pc' style='border-top:4px solid {MODOS[modo][2]}'><span class='num'>{n}</span>"
            f"<div class='rol'>{rol}</div><div class='nom'>{esc(m['prod_gutis'])}</div>{_chip(modo)}"
            f"<div class='pv-s' style='margin-top:6px'>{m['ms_mes']:.0f}% Gutis este mes · {m['gutis_ytd']} de {m['tot_ytd']} Rx en el año</div>"
            f"<div class='pv-act'>{esc(m['paso_recomendado'])}</div></div>"
        )
    if tarjetas:
        _emit("<div class='ca-card' translate='no' style='margin-bottom:10px'><div class='ca-h'>Plan de visita (posiciones del Canvas TVP)</div>"
              "<div class='ca-sub'>Por defecto son los mercados con más recetas del médico. Puedes cambiarlos en el Canvas TVP.</div>"
              f"<div class='pv-plan' style='margin-bottom:0'>{''.join(tarjetas)}</div></div>")
        st.button("Editar posiciones en el Canvas TVP →", key="pv_ir_canvas", on_click=lambda: st.session_state.update(sub_previsita="CANVAS"))

    # ---- Radiografía de mercados ----
    c1, c2, c3 = st.columns([1.6, 1.6, 1.0])
    with c1:
        ver = st.radio("Mostrar", ["Todos", "Para conquistar", "Para expandir", "Líder / lealtad"], horizontal=True, key="pv_ver")
    with c2:
        orden = st.radio("Ordenar por", ["Más recetas", "Más recetas de competencia (oportunidad)", "Menor % Gutis"], horizontal=True, key="pv_orden")
    with c3:
        n = st.slider("Mercados", 3, max(len(lista), 4), min(9, len(lista)), key="pv_n")

    d = list(lista)
    if ver == "Para conquistar":
        d = [m for m in d if modo_visual(m) == "CONQUISTA"]
    elif ver == "Para expandir":
        d = [m for m in d if modo_visual(m) == "EXPANSION"]
    elif ver == "Líder / lealtad":
        d = [m for m in d if modo_visual(m) in ("LIDER", "LEALTAD")]
    if orden.startswith("Más recetas de competencia"):
        d.sort(key=lambda m: (-m["comp_mes"], -m["comp_ytd"]))
    elif orden == "Menor % Gutis":
        d = [m for m in d if m["tot_ytd"] > 0] + [m for m in d if m["tot_ytd"] == 0]
        d.sort(key=lambda m: (m["tot_ytd"] == 0, m["ms_ytd"]))
    d = d[:n]
    if not d:
        st.info("Ningún mercado cumple ese filtro para este especialista.")
    else:
        _emit(
            "<div class='ca-card' translate='no'><div class='ca-h'>Mercados del especialista</div>"
            "<div class='ca-sub'>La barra muestra qué % de las recetas del médico son de Gutis. Las rayas verticales marcan 25% (Adopción) y 50% (Lealtad). "
            "Los círculos son los 5 escalones: lleno = ya alcanzado, punteado = meta de esta visita. "
            f"Mostrando {len(d)} de {len(lista)} mercados.</div><div class='pv-grid'>" + "".join(_fila_mercado(m) for m in d) + "</div></div>"
        )

    # ---- Recetario ----
    opciones = ["—"] + [m["clave"] for m in lista]
    nombres = {m["clave"]: m["prod_gutis"] for m in lista}
    actual = st.session_state.get("mercado_drill_sel")
    sel = st.selectbox(
        "Ver el recetario completo de un mercado (qué marcas receta este médico):",
        opciones,
        index=opciones.index(actual) if actual in opciones else 0,
        format_func=lambda k: "Elige un mercado…" if k == "—" else nombres.get(k, k),
        key=f"pv_drill_sel_{medico}",
    )
    st.session_state.mercado_drill_sel = None if sel == "—" else sel
    if sel != "—":
        df_drill = productos_medico_fn(df_productos, medico, sel)
        render_recetario(df_drill, nombres.get(sel, sel))


def render_recetario(df: pd.DataFrame, titulo: str) -> None:
    if df is None or df.empty:
        st.info("Este médico aún no registra recetas auditadas en esta clase terapéutica.")
        return
    d = df.sort_values(["Pxs YTD", "Pxs Mes"], ascending=False).reset_index(drop=True)
    tot_m, tot_y = int(d["Pxs Mes"].sum()), int(d["Pxs YTD"].sum())
    g = d[d["Origen"] == "GUTIS"]
    g_m, g_y = int(g["Pxs Mes"].sum()), int(g["Pxs YTD"].sum())
    vmax = float(max(d["Pxs YTD"].max(), 1))
    filas = []
    for i, r in d.iterrows():
        es_g = r["Origen"] == "GUTIS"
        w = r["Pxs YTD"] / vmax * 100
        filas.append(
            f"<div class='pv-rec{' gut' if es_g else ''}'><div class='nm'>{i + 1}. {esc(r['Marca Prescrita'])}"
            f"{'<span class=mk-chip>GUTIS</span>' if es_g else ''}</div>"
            f"<div class='mk-bar'><div class='mk-fill' style='width:{max(w, 1.5):.1f}%;background:{'#002b5c' if es_g else '#94a3b8'}'></div>"
            f"<span class='{'in' if w > 30 else ''}'>{int(r['Pxs YTD'])} {'receta' if int(r['Pxs YTD']) == 1 else 'recetas'} en el año</span></div>"
            f"<div class='mt'>Este mes: <b>{int(r['Pxs Mes'])}</b> {'receta' if int(r['Pxs Mes']) == 1 else 'recetas'} ({r['% MS Mes (Categoría)']:.0f}% del mes) · Año: <b>{r['% MS YTD (Categoría)']:.0f}%</b> del mercado</div></div>"
        )
    _emit(
        f"<div class='ca-card' translate='no'><div class='ca-h'>Recetario en {esc(titulo)}</div>"
        f"<div class='ca-sub'>Gutis tiene {g_m} de {tot_m} recetas este mes y {g_y} de {tot_y} en el año. La barra compara el volumen del año de cada marca.</div>"
        + "".join(filas) + "</div>"
    )
    with st.expander("Ver tabla completa"):
        st.dataframe(df[["Marca Prescrita", "Origen", "Pxs Mes", "% MS Mes (Categoría)", "Pxs YTD", "% MS YTD (Categoría)"]], width="stretch", hide_index=True)
