"""
Visuales de mercado para Gutis BI (Módulo 1 y Módulo 3).

- Módulo 1 (Top Médicos / Visor BI): matriz de marcas, ranking de médicos y hallazgos.
- Módulo 3 (Análisis de Mercado): radar de laboratorios con doble barra Mes vs. YTD.

Reutiliza el estilo de analisis_ventas.py (mismo semáforo y tarjetas), sin librerías extra.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
import streamlit as st

from analisis_ventas import CSS, _emit, esc

CSS_MK = """
<style>
.mk-h,.mk-r{display:grid;grid-template-columns:minmax(150px,1.5fr) minmax(160px,2.6fr) 92px 96px 118px;gap:12px;align-items:center}
.mk-h{font-size:.68rem;font-weight:700;letter-spacing:.05em;color:#64748b;text-transform:uppercase;padding:0 6px 6px;border-bottom:1px solid #e2e8f0}
.mk-r{padding:8px 6px;border-bottom:1px solid #f1f5f9;font-size:.85rem}
.mk-r:hover{background:#f8fafc}
.mk-r.gut{background:#f0f7ff}
.mk-n{font-weight:700;color:#0f172a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;line-height:1.25}
.mk-n small{display:block;color:#64748b;font-weight:600;font-size:.72rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mk-n .rk{color:#94a3b8;font-weight:700;font-size:.72rem;margin-right:6px}
.mk-chip{display:inline-block;font-size:.62rem;font-weight:800;letter-spacing:.04em;padding:1px 6px;border-radius:5px;margin-left:6px;vertical-align:1px;background:#dbeafe;color:#1e40af}
.mk-bar{position:relative;height:20px;background:#f1f5f9;border-radius:6px;overflow:hidden}
.mk-fill{position:absolute;left:0;top:0;bottom:0;border-radius:6px}
.mk-bar span{position:absolute;right:8px;top:0;bottom:0;display:flex;align-items:center;font-size:.76rem;font-weight:800;color:#0f172a;font-variant-numeric:tabular-nums}
.mk-bar span.in{color:#fff;right:auto;left:8px}
.mk-dbl{display:flex;flex-direction:column;gap:3px}
.mk-dbl .b{position:relative;border-radius:5px;background:#f1f5f9;overflow:hidden}
.mk-dbl .b.m{height:14px}.mk-dbl .b.y{height:8px}
.mk-dbl .b>i{position:absolute;left:0;top:0;bottom:0;border-radius:5px}
.mk-num{text-align:right;font-variant-numeric:tabular-nums;font-weight:800;color:#0f172a;line-height:1.2}
.mk-num small{display:block;color:#64748b;font-weight:600;font-size:.7rem}
.mk-spark{display:flex;align-items:flex-end;gap:3px;height:28px}
.mk-spark i{display:block;width:12px;border-radius:3px 3px 0 0;background:#cbd5e1;min-height:2px}
.mk-spark i.last{background:#0284c7}
.mk-two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:1000px){.mk-two{grid-template-columns:1fr}}
.mk-mv{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:7px 4px;border-bottom:1px solid #f1f5f9;font-size:.84rem}
.mk-mv b{color:#0f172a}
.mk-mv .w{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600;color:#0f172a}
.mk-note{font-size:.8rem;color:#64748b;margin:2px 0 8px}
</style>
"""

AZUL_GUTIS, GRIS_COMP = "#002b5c", "#94a3b8"


def _es_gutis_txt(v: str) -> bool:
    t = str(v).upper()
    return "GUTIS" in t or t.rstrip().endswith(" GPR")


def delta_pill(v: float, dec: int = 2, sufijo: str = " pp") -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "<span class='ca-pill ca-p-na'>—</span>"
    if abs(v) < 0.05:
        return f"<span class='ca-pill ca-p-na'>▬ {v:+.{dec}f}{sufijo}</span>"
    cls, flecha = ("ca-p-ok", "▲") if v > 0 else ("ca-p-bad", "▼")
    return f"<span class='ca-pill {cls}'>{flecha} {v:+.{dec}f}{sufijo}</span>"


def _kpi(label: str, valor: str, sub: str, dark: bool = False) -> str:
    return (f"<div class='ca-kpi{' dark' if dark else ''}'><div class='ca-kpi-l'>{label}</div>"
            f"<div class='ca-kpi-v'>{valor}</div><div class='ca-kpi-s'>{sub}</div></div>")


def _spark(vals: list[float], titulo: str) -> str:
    top = max([v for v in vals if v == v] + [1e-9])
    barras = []
    for i, v in enumerate(vals):
        h = 0 if v != v else max(2, round(v / top * 26))
        barras.append(f"<i class='{'last' if i == len(vals) - 1 else ''}' style='height:{h}px'></i>")
    return f"<div class='mk-spark' title='{esc(titulo)}'>{''.join(barras)}</div>"


# -----------------------------------------------------------------------------
# MÓDULO 1 · MARCAS
# -----------------------------------------------------------------------------
def hallazgos_marcas(df: pd.DataFrame) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if df.empty:
        return out
    d = df.copy()
    d["gut"] = d["Origen"].eq("GUTIS")
    lider = d.sort_values("% MS - Ytd", ascending=False).iloc[0]
    out.append(("good" if lider["gut"] else "warn",
                f"<b>{esc(lider['MARCA'])} lidera con {lider['% MS - Ytd']:.2f}% YTD</b> "
                f"({'es de Gutis' if lider['gut'] else 'es de la competencia'})."))
    comp = d[~d["gut"]]
    if not comp.empty and comp["Dif %"].max() >= 0.3:
        c = comp.loc[comp["Dif %"].idxmax()]
        out.append(("bad", f"<b>Competencia que más crece: {esc(c['MARCA'])}</b> ({c['Dif %']:+.2f} pp vs año pasado, ya en {c['% MS - Ytd']:.2f}% YTD)."))
    g = d[d["gut"]]
    if not g.empty:
        peor = g.loc[g["Dif %"].idxmin()]
        mejor = g.loc[g["Dif %"].idxmax()]
        if peor["Dif %"] <= -0.3:
            out.append(("warn", f"<b>Tu marca que más pierde: {esc(peor['MARCA'])}</b> ({peor['Dif %']:+.2f} pp vs año pasado)."))
        if mejor["Dif %"] >= 0.3:
            out.append(("good", f"<b>Tu marca que más gana: {esc(mejor['MARCA'])}</b> ({mejor['Dif %']:+.2f} pp vs año pasado)."))
        caida_mes = g.assign(m=g["% MS - Mes"] - g["% MS - Ytd"]).sort_values("m").iloc[0]
        if caida_mes["m"] <= -0.5:
            out.append(("warn", f"<b>Este mes {esc(caida_mes['MARCA'])} está {abs(caida_mes['m']):.2f} pp por debajo de su promedio del año.</b>"))
    return out[:4]


def render_matriz_marcas(df: pd.DataFrame, key: str = "mk") -> None:
    """Reemplaza la tabla de marcas por KPIs + hallazgos + ranking visual."""
    _emit(CSS)
    _emit(CSS_MK)
    if df is None or df.empty:
        st.info("No hay marcas para los filtros seleccionados.")
        return
    d = df.copy()
    gut = d[d["Origen"] == "GUTIS"]
    ms_y, ms_ly, ms_m = gut["% MS - Ytd"].sum(), gut["% MS - LY"].sum(), gut["% MS - Mes"].sum()
    suben = int((gut["Dif %"] >= 0.05).sum())
    bajan = int((gut["Dif %"] <= -0.05).sum())
    lider = d.sort_values("% MS - Ytd", ascending=False).iloc[0]
    _emit(
        "<div class='ca-kpis' translate='no'>"
        + _kpi("Cuota Gutis YTD", f"{ms_y:.1f}%", delta_pill(ms_y - ms_ly) + "<span>vs año pasado</span>")
        + _kpi("Cuota Gutis del mes", f"{ms_m:.1f}%", delta_pill(ms_m - ms_y) + "<span>vs su YTD</span>")
        + _kpi("Marcas Gutis vs año pasado", f"{suben} ▲ · {bajan} ▼", f"<span>de {len(gut)} marcas Gutis en vista</span>")
        + _kpi("Líder del mercado", esc(lider["MARCA"]), f"<span>{lider['% MS - Ytd']:.2f}% YTD · {'Gutis' if lider['Origen'] == 'GUTIS' else 'Competencia'}</span>", dark=True)
        + "</div>"
    )
    hs = hallazgos_marcas(d)
    if hs:
        _emit("<div class='ca-ins' translate='no'>" + "".join(f"<div class='ca-in {t}'>{x}</div>" for t, x in hs) + "</div>")

    c1, c2, c3 = st.columns([1.6, 1.2, 1.0])
    with c1:
        orden = st.radio("Ordenar por", ["Cuota YTD", "Cuota del mes", "Más crecen", "Más caen"], horizontal=True, key=f"{key}_ord")
    with c2:
        quien = st.radio("Mostrar", ["Todas", "Solo Gutis", "Solo competencia"], horizontal=True, key=f"{key}_quien")
    with c3:
        n = st.slider("Cantidad", 5, 40, 12, key=f"{key}_n")
    if quien == "Solo Gutis":
        d = d[d["Origen"] == "GUTIS"]
    elif quien == "Solo competencia":
        d = d[d["Origen"] != "GUTIS"]
    d = {"Cuota YTD": d.sort_values("% MS - Ytd", ascending=False),
         "Cuota del mes": d.sort_values("% MS - Mes", ascending=False),
         "Más crecen": d.sort_values("Dif %", ascending=False),
         "Más caen": d.sort_values("Dif %")}[orden].head(n)
    if d.empty:
        st.info("Sin marcas con ese filtro.")
        return
    vmax = float(max(d["% MS - Ytd"].max(), d["% MS - Mes"].max(), 1e-9))
    filas = []
    for i, (_, r) in enumerate(d.iterrows(), 1):
        es_g = r["Origen"] == "GUTIS"
        ytd, mes, dif = r["% MS - Ytd"], r["% MS - Mes"], r["Dif %"]
        w = ytd / vmax * 100
        color = AZUL_GUTIS if es_g else GRIS_COMP
        etiqueta = f"{ytd:.2f}%"
        dentro = w > 22
        tend = [r["% MS - LY"], r["% MS - Ytd"], r["% MS - TrasAnt"], r["% MS - Ant"], r["% MS - Mes"]]
        tip = f"LY {tend[0]:.2f}% · YTD {tend[1]:.2f}% · Trasant {tend[2]:.2f}% · Ant {tend[3]:.2f}% · Mes {tend[4]:.2f}%"
        filas.append(
            f"<div class='mk-r{' gut' if es_g else ''}'>"
            f"<div class='mk-n' title='{esc(r['MARCA'])}'><span class='rk'>{i}</span>{esc(r['MARCA'])}"
            f"{'<span class=mk-chip>GUTIS</span>' if es_g else ''}</div>"
            f"<div class='mk-bar'><div class='mk-fill' style='width:{w:.1f}%;background:{color}'></div>"
            f"<span class='{'in' if dentro else ''}'>{etiqueta}</span></div>"
            f"<div class='mk-num'>{mes:.2f}%<small>{delta_pill(mes - ytd, sufijo='')}</small></div>"
            f"<div>{_spark(tend, tip)}</div>"
            f"<div style='text-align:right'>{delta_pill(dif)}</div></div>"
        )
    _emit(
        "<div class='ca-card' translate='no'><div class='ca-h'>Participación de mercado por marca</div>"
        "<div class='ca-sub'>Barra = cuota YTD. Azul oscuro = marcas Gutis. La mini-gráfica va de izquierda (año pasado) a derecha (mes actual).</div>"
        "<div class='mk-h'><div>Marca</div><div>Cuota YTD</div><div style='text-align:right'>Mes · vs YTD</div><div>Tendencia</div><div style='text-align:right'>vs año pasado</div></div>"
        + "".join(filas) + "</div>"
    )


# -----------------------------------------------------------------------------
# MÓDULO 1 · MÉDICOS
# -----------------------------------------------------------------------------
def render_medicos(df: pd.DataFrame, key: str = "md", titulo: str = "Médicos prescriptores", n_default: int = 15) -> None:
    _emit(CSS)
    _emit(CSS_MK)
    if df is None or df.empty:
        st.info("No hay médicos para los filtros seleccionados.")
        return
    col_foco = next((c for c in df.columns if c in ("Gutis Pxs Mes", "Pxs Marca Mes")), None)
    col_foco_y = next((c for c in df.columns if c in ("Gutis Pxs YTD", "Pxs Marca YTD")), None)
    n = st.slider("Cantidad de médicos", 5, 50, n_default, key=f"{key}_n")
    d = df.head(n).copy()
    usa_pxs = col_foco is not None
    vcol = col_foco if usa_pxs else "% MS - Ytd"
    vmax = float(max(d[vcol].max(), 1e-9))
    filas = []
    for i, (_, r) in enumerate(d.iterrows(), 1):
        sub = " · ".join(x for x in [str(r.get("Especialidad", "")).title(), str(r.get("Zona", "")).title(), f"Cat {r['Categoria_TAM']}" if "Categoria_TAM" in r else ""] if x)
        v = r[vcol]
        w = v / vmax * 100
        etiqueta = f"{int(v)} Rx" if usa_pxs else f"{v:.2f}%"
        if usa_pxs:
            num = f"{int(r[col_foco_y]) if col_foco_y else 0}<small>YTD · de {int(r['Total Pxs Cat. Mes'])} Rx cat.</small>" if "Total Pxs Cat. Mes" in r else f"{int(r[col_foco_y])}<small>YTD</small>"
        else:
            num = f"{r['% MS - Mes']:.2f}%<small>mes</small>"
        filas.append(
            f"<div class='mk-r' style='grid-template-columns:minmax(170px,1.7fr) minmax(130px,2fr) 130px 118px'>"
            f"<div class='mk-n' title='{esc(r['Médico'])}'><span class='rk'>{i}</span>{esc(str(r['Médico']).replace('#', 'Ñ'))}<small>{esc(sub)}</small></div>"
            f"<div class='mk-bar'><div class='mk-fill' style='width:{w:.1f}%;background:#0284c7'></div><span class='{'in' if w > 25 else ''}'>{etiqueta}</span></div>"
            f"<div class='mk-num'>{num}</div>"
            f"<div style='text-align:right'>{delta_pill(r['% MS - Mes'] - r['% MS - Ytd'])}</div></div>"
        )
    cab_barra = "Recetas del mes (foco)" if usa_pxs else "Cuota YTD"
    _emit(
        f"<div class='ca-card' translate='no'><div class='ca-h'>{esc(titulo)}</div>"
        "<div class='ca-sub'>Ordenados por recetas del mes de la marca o mercado en foco. La flecha compara el mes con el promedio del año.</div>"
        f"<div class='mk-h' style='grid-template-columns:minmax(170px,1.7fr) minmax(130px,2fr) 130px 118px'><div>Médico</div><div>{cab_barra}</div>"
        "<div style='text-align:right'>Acumulado</div><div style='text-align:right'>Mes vs YTD</div></div>"
        + "".join(filas) + "</div>"
    )


# -----------------------------------------------------------------------------
# MÓDULO 3 · RADAR DE LABORATORIOS
# -----------------------------------------------------------------------------
def _limpia_lab(v: str) -> str:
    return str(v).replace("[GUTIS] ", "").strip()


def hallazgos_labs(d: pd.DataFrame) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if d.empty:
        return out
    gut = d[d["es_gutis"]]
    if not gut.empty:
        g = gut.iloc[0]
        pos = int(g["pos"])
        out.append(("good" if pos <= 3 else "info", f"<b>Gutis es #{pos} entre los laboratorios identificados con {g['% MS Mes']:.2f}% de cuota del mes</b> ({g['delta']:+.2f} pp frente a su promedio del año)."))
    top3 = d[d["ident"]].sort_values("% MS Mes", ascending=False).head(3)["% MS Mes"].sum()
    out.append(("info", f"<b>Los 3 primeros laboratorios concentran {top3:.0f}% del mes.</b> El resto del mercado está muy fragmentado." if top3 < 70 else f"<b>Los 3 primeros laboratorios concentran {top3:.0f}% del mes:</b> mercado muy concentrado."))
    rel = d[(d["% MS YTD"] >= 0.5) & d["ident"]]
    if len(rel) >= 3:
        up, dn = rel.loc[rel["delta"].idxmax()], rel.loc[rel["delta"].idxmin()]
        if up["delta"] >= 0.3:
            out.append(("bad" if not up["es_gutis"] else "good", f"<b>{esc(up['lab'])} es quien más sube este mes</b> ({up['delta']:+.2f} pp)."))
        if dn["delta"] <= -0.3:
            out.append(("warn", f"<b>{esc(dn['lab'])} es quien más cae este mes</b> ({dn['delta']:+.2f} pp)."))
    return out[:4]


def render_radar_labs(df_rk: pd.DataFrame, tabla_fn: Callable[[pd.DataFrame, int], None] | None = None, key: str = "rl") -> None:
    _emit(CSS)
    _emit(CSS_MK)
    if df_rk is None or df_rk.empty:
        st.info("No hay registros de laboratorios para esta combinación.")
        return
    d = df_rk.reset_index(drop=True).copy()
    d["lab"] = d["Laboratorio"].map(_limpia_lab)
    d["ident"] = ~d["lab"].str.upper().str.contains("NO INDICADO|SIN INDICAR|OTROS", regex=True, na=False)
    d["pos"] = d.loc[d["ident"], "% MS Mes"].rank(ascending=False, method="first")
    d["es_gutis"] = d["Laboratorio"].str.contains("GUTIS", case=False, na=False)
    d["delta"] = (d["% MS Mes"] - d["% MS YTD"]).round(2)

    gut = d[d["es_gutis"]]
    lider = d[d["ident"]].sort_values("% MS Mes", ascending=False).iloc[0] if d["ident"].any() else d.iloc[0]
    sin_id = d[~d["ident"]]
    if not gut.empty:
        g = gut.iloc[0]
        k1 = _kpi("Posición de Gutis (mes)", f"#{int(g['pos'])}", f"<span>de {int(d['ident'].sum())} laboratorios identificados</span>")
        k2 = _kpi("Cuota Gutis del mes", f"{g['% MS Mes']:.2f}%", delta_pill(g["delta"]) + "<span>vs su YTD</span>")
        k3 = _kpi("Cuota Gutis YTD", f"{g['% MS YTD']:.2f}%", f"<span>{int(g['Pxs YTD']):,} recetas</span>")
    else:
        k1 = _kpi("Posición de Gutis (mes)", "—", "<span>Gutis no aparece en esta selección</span>")
        k2 = _kpi("Cuota Gutis del mes", "—", "")
        k3 = _kpi("Cuota Gutis YTD", "—", "")
    k4 = _kpi("Líder del mes", esc(lider["lab"]), f"<span>{lider['% MS Mes']:.2f}% · {int(lider['Pxs Mes']):,} recetas</span>", dark=True)
    _emit(f"<div class='ca-kpis' translate='no'>{k1}{k2}{k3}{k4}</div>")
    hs = hallazgos_labs(d)
    if hs:
        _emit("<div class='ca-ins' translate='no'>" + "".join(f"<div class='ca-in {t}'>{x}</div>" for t, x in hs) + "</div>")

    c1, c2 = st.columns([2.0, 1.0])
    with c1:
        orden = st.radio("Ordenar por", ["Volumen del mes", "Cuota YTD", "Mayor alza vs YTD", "Mayor caída vs YTD"], horizontal=True, key=f"{key}_ord")
    with c2:
        n = st.slider("Laboratorios a mostrar", 5, 30, 12, key=f"{key}_n")
    ordenado = {"Volumen del mes": d.sort_values("% MS Mes", ascending=False),
                "Cuota YTD": d.sort_values("% MS YTD", ascending=False),
                "Mayor alza vs YTD": d[(d["% MS YTD"] >= 0.5) & d["ident"]].sort_values("delta", ascending=False),
                "Mayor caída vs YTD": d[(d["% MS YTD"] >= 0.5) & d["ident"]].sort_values("delta")}[orden]
    vista = ordenado.head(n)
    extra = ordenado[ordenado["es_gutis"] & ~ordenado["lab"].isin(vista["lab"])]
    vmax = float(max(vista[["% MS Mes", "% MS YTD"]].max().max(), extra[["% MS Mes", "% MS YTD"]].max().max() if not extra.empty else 0, 1e-9))

    def fila(r, num: int) -> str:
        es_g = bool(r["es_gutis"])
        c_m = AZUL_GUTIS if es_g else "#0284c7"
        return (
            f"<div class='mk-r{' gut' if es_g else ''}' style='grid-template-columns:minmax(150px,1.5fr) minmax(170px,2.8fr) 82px 82px 118px'>"
            f"<div class='mk-n' title='{esc(r['lab'])}'><span class='rk'>{num}</span>{esc(r['lab'])}{'<span class=mk-chip>GUTIS</span>' if es_g else ''}{'' if r['ident'] else '<span class=mk-chip style=background:#e2e8f0;color:#475569>SIN IDENTIFICAR</span>'}"
            f"<small>{int(r['Prescriptores']):,} prescriptores</small></div>"
            f"<div class='mk-dbl'><div class='b m'><i style='width:{r['% MS Mes'] / vmax * 100:.1f}%;background:{c_m}'></i></div>"
            f"<div class='b y'><i style='width:{r['% MS YTD'] / vmax * 100:.1f}%;background:#94a3b8'></i></div></div>"
            f"<div class='mk-num'>{r['% MS Mes']:.2f}%<small>{int(r['Pxs Mes']):,} Rx</small></div>"
            f"<div class='mk-num' style='color:#475569'>{r['% MS YTD']:.2f}%<small>{int(r['Pxs YTD']):,} Rx</small></div>"
            f"<div style='text-align:right'>{delta_pill(r['delta'])}</div></div>"
        )

    def _n(r, i):
        return (int(r["pos"]) if r["ident"] else "–") if orden == "Volumen del mes" else i
    filas = [fila(r, _n(r, i)) for i, (_, r) in enumerate(vista.iterrows(), 1)]
    if not extra.empty:
        filas.append("<div class='mk-note' style='text-align:center;padding:4px 0'>· · ·</div>")
        filas.extend(fila(r, int(r["pos"])) for _, r in extra.iterrows() if r["ident"])
    _emit(
        "<div class='ca-card' translate='no'><div class='ca-h'>Laboratorios: cuota del mes vs. acumulado del año</div>"
        "<div class='ca-sub'>Barra gruesa = cuota del mes · barra delgada gris = cuota YTD. La flecha muestra si el laboratorio sube o baja este mes.</div>"
        "<div class='mk-h' style='grid-template-columns:minmax(150px,1.5fr) minmax(170px,2.8fr) 82px 82px 118px'><div>Laboratorio</div><div>Mes vs YTD</div>"
        "<div style='text-align:right'>% Mes</div><div style='text-align:right'>% YTD</div><div style='text-align:right'>Cambio</div></div>"
        + "".join(filas)
        + "<div class='ca-legend'><span><i style='background:#0284c7'></i>Mes</span><span><i style='background:#002b5c'></i>Mes (Gutis)</span><span><i style='background:#94a3b8'></i>YTD</span></div></div>"
    )

    rel = d[(d["% MS YTD"] >= 0.5) & d["ident"]]
    sube, baja = rel[rel["delta"] >= 0.05].sort_values("delta", ascending=False).head(5), rel[rel["delta"] <= -0.05].sort_values("delta").head(5)

    def movers(m: pd.DataFrame, vacio: str) -> str:
        if m.empty:
            return f"<div class='mk-note'>{vacio}</div>"
        return "".join(
            f"<div class='mk-mv'><span class='w' title='{esc(r['lab'])}'>{esc(r['lab'])}</span>"
            f"<span>{r['% MS YTD']:.2f}% → <b>{r['% MS Mes']:.2f}%</b></span>{delta_pill(r['delta'])}</div>"
            for _, r in m.iterrows()
        )
    _emit(
        "<div class='mk-two' translate='no'>"
        f"<div class='ca-card'><div class='ca-h'>Quién gana cuota este mes</div><div class='ca-sub'>Laboratorios con al menos 0.5% YTD.</div>{movers(sube, 'Nadie sube de forma relevante.')}</div>"
        f"<div class='ca-card'><div class='ca-h'>Quién pierde cuota este mes</div><div class='ca-sub'>Laboratorios con al menos 0.5% YTD.</div>{movers(baja, 'Nadie cae de forma relevante.')}</div>"
        "</div>"
    )

    with st.expander("Ver tabla completa y exportar"):
        if tabla_fn:
            tabla_fn(df_rk, 420)
        else:
            st.dataframe(df_rk, hide_index=True, width="stretch", height=420)
