"""
Centro de Análisis de Ventas v2.0 (Sell-Out vs. Cuota) para Gutis BI.

Lee directamente el Excel de ventas (una hoja por mes, con jerarquía
Ruta > Cliente > Producto) y ofrece inteligencia comercial accionable
en HTML/CSS puro (sin librerías extra: solo streamlit, pandas y numpy).

Uso desde app.py:
    from analisis_ventas import render_centro_analisis
    render_centro_analisis(DATA_DIR, BASE_DIR)
"""
from __future__ import annotations

import html as _html
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# 1. CARGA Y LIMPIEZA DEL EXCEL DE VENTAS
# -----------------------------------------------------------------------------
MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
MES_CORTO = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}
COLS_REQUERIDAS = {"DESCRIPCION_RUTA", "NOMBRE_CLIENTE_1", "VM4", "Monto Real", "Monto Cuota"}


def esc(v: Any) -> str:
    return _html.escape(str(v if v is not None else ""))


def _parsear_hoja(nombre: str) -> tuple[int, int] | None:
    m = re.search(r"([A-Za-zÁÉÍÓÚáéíóú]+)\s*(\d{4})", str(nombre))
    if not m:
        return None
    mes = MESES_ES.get(m.group(1).lower())
    return (int(m.group(2)), mes) if mes else None


def buscar_excel_ventas(*carpetas: Path) -> Path | None:
    """Busca en las carpetas el .xlsx con más hojas mensuales válidas."""
    vistos: set[Path] = set()
    mejor: tuple[int, Path] | None = None
    for carpeta in carpetas:
        if not carpeta or not Path(carpeta).exists():
            continue
        for p in sorted(Path(carpeta).glob("*.xlsx")):
            if p.name.startswith("~$") or p in vistos:
                continue
            vistos.add(p)
            try:
                xl = pd.ExcelFile(p)
                hojas_ok = sum(
                    1
                    for hoja in xl.sheet_names
                    if _parsear_hoja(hoja) and COLS_REQUERIDAS <= set(xl.parse(hoja, nrows=0).columns)
                )
                if hojas_ok > 0 and (mejor is None or hojas_ok > mejor[0]):
                    mejor = (hojas_ok, p)
            except Exception:
                continue
    return mejor[1] if mejor else None


@st.cache_data(show_spinner="Leyendo ventas mensuales...")
def cargar_ventas(ruta: str, mtime: float) -> tuple[pd.DataFrame, str]:
    """Devuelve el detalle limpio (Ruta x Cliente x Producto x Mes) y el texto de filtros."""
    xl = pd.ExcelFile(ruta)
    piezas, filtros = [], ""
    for hoja in xl.sheet_names:
        ym = _parsear_hoja(hoja)
        if not ym:
            continue
        d = xl.parse(hoja)
        d.columns = d.columns.astype(str).str.strip()
        if not COLS_REQUERIDAS <= set(d.columns):
            continue
        if not filtros:
            col0 = d.iloc[:, 0].dropna().astype(str)
            f = col0[col0.str.startswith("Filtros aplicados")]
            if not f.empty:
                filtros = " · ".join(
                    x.strip()
                    for x in f.iloc[0].replace("Filtros aplicados:", "").split("\n")
                    if x.strip() and not x.strip().startswith(("Mes es", "ANIO es"))
                )
        for c in ("DESCRIPCION_RUTA", "NOMBRE_CLIENTE_1", "VM4"):
            d[c] = d[c].astype("string").str.strip()
        invalidos = {"TOTAL", "NAN", "NONE", ""}
        es_detalle = (
            d["DESCRIPCION_RUTA"].notna() & ~d["DESCRIPCION_RUTA"].str.upper().isin(invalidos)
            & d["NOMBRE_CLIENTE_1"].notna() & ~d["NOMBRE_CLIENTE_1"].str.upper().isin(invalidos)
            & d["VM4"].notna() & ~d["VM4"].str.upper().isin(invalidos)
        )
        det = d.loc[es_detalle].copy()
        det["Periodo"] = ym[0] * 100 + ym[1]
        det["MesNum"] = ym[1]
        det["Anio"] = ym[0]
        piezas.append(det)
    if not piezas:
        return pd.DataFrame(), filtros
    df = pd.concat(piezas, ignore_index=True)
    df = df.rename(columns={
        "DESCRIPCION_RUTA": "Territorio",
        "NOMBRE_CLIENTE_1": "Farmacia",
        "VM4": "Producto",
        "Monto Real": "Real",
        "Monto Cuota": "Cuota",
        "Und Real": "Und_Real",
        "Und Cuota": "Und_Cuota",
    })
    for c in ("Real", "Cuota", "Und_Real", "Und_Cuota"):
        if c not in df.columns:
            df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    unico_anio = df["Anio"].nunique() == 1
    df["Mes"] = [
        MES_CORTO[m] if unico_anio else f"{MES_CORTO[m]} {str(a)[2:]}"
        for m, a in zip(df["MesNum"], df["Anio"])
    ]
    for c in ("Territorio", "Farmacia", "Producto"):
        df[c] = df[c].astype(str).str.strip().str.upper()
    cols = ["Periodo", "Mes", "Territorio", "Farmacia", "Producto", "Real", "Cuota", "Und_Real", "Und_Cuota"]
    return df[cols], filtros


# -----------------------------------------------------------------------------
# 2. CÁLCULOS Y MOTORES INTELIGENTES (APAGONES, ACELERACIÓN, PLAN DE CIERRE)
# -----------------------------------------------------------------------------
def con_medida(df: pd.DataFrame, unidades: bool) -> pd.DataFrame:
    out = df.copy()
    out["R"] = out["Und_Real"] if unidades else out["Real"]
    out["Q"] = out["Und_Cuota"] if unidades else out["Cuota"]
    return out


def resumir(df: pd.DataFrame, por: str | list[str]) -> pd.DataFrame:
    g = df.groupby(por, as_index=False, sort=False)[["R", "Q"]].sum()
    g = g.rename(columns={"R": "Real", "Q": "Cuota"})
    g["Brecha"] = g["Real"] - g["Cuota"]
    g["Pct"] = np.where(g["Cuota"] > 0, g["Real"] / g["Cuota"].where(g["Cuota"] > 0) * 100.0, np.nan)
    return g


def totales(df: pd.DataFrame) -> dict[str, float]:
    r, q = float(df["R"].sum()), float(df["Q"].sum())
    return {"real": r, "cuota": q, "brecha": r - q, "pct": (r / q * 100.0) if q > 0 else float("nan")}


def estado(pct: float) -> tuple[str, str, str]:
    if pct is None or (isinstance(pct, float) and np.isnan(pct)):
        return "ca-p-na", "Sin cuota", "#94a3b8"
    if pct >= 100:
        return "ca-p-ok", "Cumple", "#059669"
    if pct >= 90:
        return "ca-p-near", "Cerca", "#0284c7"
    if pct >= 75:
        return "ca-p-risk", "En riesgo", "#d97706"
    return "ca-p-bad", "Crítico", "#dc2626"


def detectar_apagones(df: pd.DataFrame, periodos: list[int], orden_mes: dict[int, str], unidades: bool) -> pd.DataFrame:
    """Detecta clientes que venían comprando bien en meses previos y cayeron a <=10% o $0 en el último mes."""
    if df.empty or len(periodos) < 2:
        return pd.DataFrame()
    ult_p = periodos[-1]
    prev_ps = periodos[:-1]
    umbral = 15.0 if unidades else 150.0

    piv = df.pivot_table(index=["Farmacia", "Territorio"], columns="Periodo", values="R", aggfunc="sum", fill_value=0.0)
    for p in periodos:
        if p not in piv.columns:
            piv[p] = 0.0
    piv["Prom_Prev"] = piv[prev_ps].mean(axis=1)
    piv["Ult_Mes"] = piv[ult_p]
    ap = piv[(piv["Prom_Prev"] >= umbral) & (piv["Ult_Mes"] <= piv["Prom_Prev"] * 0.10)].copy()
    if ap.empty:
        return pd.DataFrame()

    ap["Riesgo_Mensual"] = ap["Prom_Prev"] - ap["Ult_Mes"]
    ap["Alerta"] = np.where(ap["Ult_Mes"] <= 0, "APAGÓN ($0)", "CAÍDA >90%")
    ap = ap.reset_index().sort_values("Riesgo_Mensual", ascending=False)
    ren = {p: orden_mes[p] for p in periodos}
    ap = ap.rename(columns=ren)
    cols_m = [orden_mes[p] for p in periodos]
    return ap[["Farmacia", "Territorio", "Alerta"] + cols_m + ["Prom_Prev", "Riesgo_Mensual"]]


def detectar_aceleracion(df: pd.DataFrame, periodos: list[int]) -> pd.DataFrame:
    """Compara el promedio mensual de la 2da mitad del período vs. la 1ra mitad para encontrar farmacias en despegue."""
    if df.empty or len(periodos) < 2:
        return pd.DataFrame()
    mitad = max(1, len(periodos) // 2)
    b1, b2 = periodos[:mitad], periodos[mitad:]
    piv = df.pivot_table(index="Farmacia", columns="Periodo", values="R", aggfunc="sum", fill_value=0.0)
    for p in periodos:
        if p not in piv.columns:
            piv[p] = 0.0
    g = resumir(df, "Farmacia").set_index("Farmacia")
    g["Prom_1ra"] = piv[b1].mean(axis=1)
    g["Prom_2da"] = piv[b2].mean(axis=1)
    g["Aceleracion"] = g["Prom_2da"] - g["Prom_1ra"]
    return g[g["Aceleracion"] > 0].sort_values("Aceleracion", ascending=False).reset_index()


def top_codigos_por_farmacia(df: pd.DataFrame, unidades: bool, k: int = 2) -> dict[str, str]:
    """Devuelve para cada farmacia los k códigos con mayor brecha negativa."""
    gp = resumir(df, ["Farmacia", "Producto"])
    neg = gp[gp["Brecha"] < 0]
    out: dict[str, str] = {}
    for farm, grp in neg.groupby("Farmacia"):
        top = grp.sort_values("Brecha").head(k)
        out[str(farm)] = " · ".join(
            f"{r.Producto} ({_num_plano(r.Brecha, unidades, True)})" for r in top.itertuples(index=False)
        )
    return out


# -----------------------------------------------------------------------------
# 3. FORMATO
# -----------------------------------------------------------------------------
def _num_plano(v: float, unidades: bool, signo: bool = False) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    pref = "" if unidades else "$"
    s = "+" if (signo and v > 0) else ("-" if v < 0 else "")
    a = abs(v)
    if a >= 10_000:
        return f"{s}{pref}{a / 1_000:,.1f}K"
    return f"{s}{pref}{a:,.0f}"


def _num(v: float, unidades: bool, compacto: bool = False, signo: bool = False) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    pref = "" if unidades else "&#36;"
    s = "+" if (signo and v > 0) else ("−" if v < 0 else "")
    a = abs(v)
    if compacto and a >= 1_000_000:
        txt = f"{a / 1_000_000:,.2f}M"
    elif compacto and a >= 10_000:
        txt = f"{a / 1_000:,.1f}K"
    else:
        txt = f"{a:,.0f}"
    return f"{s}{pref}{txt}"


def _pct(v: float, dec: int = 1) -> str:
    return "—" if v is None or np.isnan(v) else f"{v:.{dec}f}%"


def _lerp(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))


_PARADAS_PCT = [
    (50, (252, 165, 165)), (75, (253, 224, 138)), (90, (217, 240, 170)),
    (100, (134, 239, 172)), (115, (74, 222, 128)),
]


def color_pct(p: float) -> str:
    if p is None or np.isnan(p):
        return "#f1f5f9"
    if p <= _PARADAS_PCT[0][0]:
        return "rgb(%d,%d,%d)" % _PARADAS_PCT[0][1]
    for (a, ca), (b, cb) in zip(_PARADAS_PCT, _PARADAS_PCT[1:]):
        if p <= b:
            return "rgb(%d,%d,%d)" % _lerp(ca, cb, (p - a) / (b - a))
    return "rgb(%d,%d,%d)" % _PARADAS_PCT[-1][1]


def color_div(v: float, escala: float) -> str:
    if v is None or np.isnan(v) or np.isnan(escala) or escala <= 0:
        return "#f1f5f9"
    t = min(abs(v) / escala, 1.0)
    return "rgb(%d,%d,%d)" % _lerp((255, 255, 255), (248, 113, 113) if v < 0 else (74, 222, 128), t)


def color_sec(v: float, vmax: float) -> str:
    if v is None or np.isnan(v) or np.isnan(vmax) or vmax <= 0:
        return "#f1f5f9"
    return "rgb(%d,%d,%d)" % _lerp((255, 255, 255), (56, 189, 248), min(max(v, 0) / vmax, 1.0))


# -----------------------------------------------------------------------------
# 4. COMPONENTES VISUALES (HTML/CSS)
# -----------------------------------------------------------------------------
CSS = """
<style>
.ca-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:4px 0 14px}
@media(max-width:1000px){.ca-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}
.ca-kpi{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px 16px;box-shadow:0 1px 3px rgba(15,23,42,.05)}
.ca-kpi.dark{background:linear-gradient(115deg,#001f44,#002b5c);border-color:#002b5c}
.ca-kpi-l{font-size:.7rem;font-weight:700;letter-spacing:.06em;color:#64748b;text-transform:uppercase}
.ca-kpi.dark .ca-kpi-l{color:#93c5fd}
.ca-kpi-v{font-size:1.75rem;font-weight:800;line-height:1.15;margin:6px 0 4px;color:#0f172a;font-variant-numeric:tabular-nums}
.ca-kpi.dark .ca-kpi-v{color:#fff}
.ca-kpi-s{font-size:.78rem;color:#64748b;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.ca-kpi.dark .ca-kpi-s{color:#cbd5e1}
.ca-track{height:8px;background:#e2e8f0;border-radius:99px;overflow:hidden;margin-top:8px}
.ca-track>div{height:100%;border-radius:99px}
.ca-pill{display:inline-block;font-size:.72rem;font-weight:800;padding:2px 9px;border-radius:99px;white-space:nowrap}
.ca-p-ok{background:#dcfce7;color:#166534}.ca-p-near{background:#e0f2fe;color:#075985}
.ca-p-risk{background:#fef3c7;color:#92400e}.ca-p-bad{background:#fee2e2;color:#991b1b}.ca-p-na{background:#f1f5f9;color:#475569}
.ca-up{color:#059669;font-weight:700}.ca-down{color:#dc2626;font-weight:700}
.ca-card{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px 18px;margin-bottom:14px;box-shadow:0 1px 3px rgba(15,23,42,.04)}
.ca-h{font-size:.95rem;font-weight:800;color:#0f172a;margin:0 0 2px}
.ca-sub{font-size:.8rem;color:#64748b;margin:0 0 12px}
.ca-legend{display:flex;gap:16px;flex-wrap:wrap;font-size:.76rem;color:#475569;margin:8px 0 0}
.ca-legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.ca-ins{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px;margin-bottom:14px}
.ca-in{background:#fff;border:1px solid #e2e8f0;border-left:5px solid #94a3b8;border-radius:10px;padding:11px 14px;font-size:.86rem;line-height:1.45;color:#334155}
.ca-in b{color:#0f172a}.ca-in.good{border-left-color:#059669}.ca-in.warn{border-left-color:#d97706}.ca-in.bad{border-left-color:#dc2626}.ca-in.info{border-left-color:#0284c7}
.ca-cols{display:flex;align-items:flex-end;gap:10px;height:255px;padding:0 4px;border-bottom:2px solid #cbd5e1}
.ca-col{flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%}
.ca-col-stack{position:relative;width:min(66px,82%);display:flex;align-items:flex-end}
.ca-col-ghost{position:absolute;left:0;right:0;bottom:0;background:repeating-linear-gradient(135deg,#e2e8f0,#e2e8f0 5px,#f1f5f9 5px,#f1f5f9 10px);border:1px dashed #94a3b8;border-radius:6px 6px 0 0}
.ca-col-fill{position:relative;width:100%;border-radius:6px 6px 0 0}
.ca-col-target{position:absolute;left:-4px;right:-4px;border-top:2px dashed #0f172a;z-index:3}
.ca-col-top{font-size:.74rem;font-weight:800;color:#0f172a;margin-bottom:3px;white-space:nowrap}
.ca-col-lbl{display:flex;gap:10px;padding:6px 4px 0}
.ca-col-lbl>div{flex:1;text-align:center;font-size:.78rem;font-weight:800;color:#334155}
.ca-col-lbl small{display:block;font-weight:600;color:#64748b;font-size:.7rem;margin-top:2px}
.ca-rk-h,.ca-rk{display:grid;grid-template-columns:minmax(120px,1.35fr) minmax(130px,2.4fr) 96px 76px 88px;gap:12px;align-items:center}
.ca-rk-h{font-size:.68rem;font-weight:700;letter-spacing:.05em;color:#64748b;text-transform:uppercase;padding:0 4px 6px;border-bottom:1px solid #e2e8f0}
.ca-rk{padding:7px 4px;border-bottom:1px solid #f1f5f9;font-size:.83rem}
.ca-rk:hover{background:#f8fafc}
.ca-rk-l{font-weight:600;color:#0f172a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ca-rk-l small{color:#94a3b8;font-weight:600;margin-right:6px}
.ca-rk-b{position:relative;height:16px}
.ca-rk-ghost{position:absolute;left:0;top:0;bottom:0;background:repeating-linear-gradient(135deg,#e2e8f0,#e2e8f0 4px,#f1f5f9 4px,#f1f5f9 8px);border:1px dashed #94a3b8;border-radius:5px}
.ca-rk-fill{position:absolute;left:0;top:3px;bottom:3px;border-radius:4px}
.ca-rk-mark{position:absolute;top:-2px;bottom:-2px;width:2px;background:#0f172a;z-index:3}
.ca-rk-n{text-align:right;font-variant-numeric:tabular-nums;font-weight:700;color:#0f172a;line-height:1.15}
.ca-rk-n small{display:block;color:#94a3b8;font-weight:600;font-size:.7rem}
.ca-rk-g{text-align:right;font-variant-numeric:tabular-nums;font-weight:800}
.ca-hmw{overflow-x:auto}
.ca-hm{border-collapse:separate;border-spacing:3px;width:100%;font-size:.8rem}
.ca-hm th{font-size:.68rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.03em;padding:4px 4px;text-align:center;white-space:normal;line-height:1.15;max-width:86px;vertical-align:bottom}
.ca-hm th.rl,.ca-hm td.rl{text-align:left;font-weight:600;color:#0f172a;white-space:nowrap;max-width:230px;min-width:130px;overflow:hidden;text-overflow:ellipsis;padding:6px 8px;background:transparent}
.ca-hm td{text-align:center;padding:8px 6px;border-radius:6px;font-weight:700;color:#0f172a;font-variant-numeric:tabular-nums;min-width:58px}
.ca-hm td.tot{border:2px solid #cbd5e1;background:#f8fafc !important;font-weight:800}
.ca-pareto{display:flex;height:30px;border-radius:8px;overflow:hidden;border:1px solid #e2e8f0}
.ca-pareto>div{display:flex;align-items:center;justify-content:center;font-size:.72rem;font-weight:800;color:#fff;min-width:0;overflow:hidden}
.ca-note{font-size:.76rem;color:#64748b;margin:4px 0 10px}
.ca-sim-box{background:linear-gradient(115deg,#f8fafc,#eff6ff);border:1px solid #bfdbfe;border-radius:12px;padding:14px 18px;margin:10px 0 14px;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
@media(max-width:900px){.ca-sim-box{grid-template-columns:repeat(2,minmax(0,1fr))}}
.ca-sim-lbl{font-size:.68rem;font-weight:800;color:#475569;text-transform:uppercase}
.ca-sim-val{font-size:1.3rem;font-weight:800;color:#002b5c;margin-top:2px;font-variant-numeric:tabular-nums}
.ca-ficha-cta{background:#fffbeb;border:1px solid #fde68a;border-left:4px solid #d97706;border-radius:8px;padding:10px 14px;font-size:.82rem;color:#78350f;margin:6px 0 12px}
</style>
"""


def _emit(html_str: str) -> None:
    limpio = "\n".join(l.lstrip() for l in html_str.splitlines() if l.strip())
    st.markdown(limpio, unsafe_allow_html=True)


def html_kpis(t: dict, unidades: bool, n_meses: int, var_ult: tuple[str, float] | None, n_farm: int) -> str:
    cls, etiqueta, color = estado(t["pct"])
    unidad = "Unidades" if unidades else "Venta"
    gap_txt = "por debajo de la cuota" if t["brecha"] < 0 else "sobre la cuota"
    var_html = ""
    if var_ult:
        mes, v = var_ult
        flecha, c = ("▲", "ca-up") if v >= 0 else ("▼", "ca-down")
        var_html = f"<span class='{c}'>{flecha} {v:+.1f}%</span><span>{esc(mes)} vs mes previo</span>"
    pct_bar = min(max(t["pct"] if not np.isnan(t["pct"]) else 0.0, 0.0), 100.0)
    return f"""
    <div class='ca-kpis' translate='no'>
      <div class='ca-kpi'>
        <div class='ca-kpi-l'>{unidad} real · {n_meses} {'mes' if n_meses == 1 else 'meses'}</div>
        <div class='ca-kpi-v'>{_num(t['real'], unidades, True)}</div>
        <div class='ca-kpi-s'>{var_html or f'<span>{n_farm:,} farmacias con cuota</span>'}</div>
      </div>
      <div class='ca-kpi'>
        <div class='ca-kpi-l'>Cuota asignada</div>
        <div class='ca-kpi-v'>{_num(t['cuota'], unidades, True)}</div>
        <div class='ca-kpi-s'><span>{n_farm:,} farmacias con cuota</span></div>
      </div>
      <div class='ca-kpi'>
        <div class='ca-kpi-l'>Cumplimiento</div>
        <div class='ca-kpi-v'>{_pct(t['pct'])}</div>
        <div class='ca-kpi-s'><span class='ca-pill {cls}'>{etiqueta}</span></div>
        <div class='ca-track'><div style='width:{pct_bar:.0f}%;background:{color}'></div></div>
      </div>
      <div class='ca-kpi dark'>
        <div class='ca-kpi-l'>Brecha vs cuota</div>
        <div class='ca-kpi-v'>{_num(t['brecha'], unidades, True, True)}</div>
        <div class='ca-kpi-s'><span>{gap_txt}</span></div>
      </div>
    </div>
    """


def html_columnas_mes(g: pd.DataFrame, unidades: bool, alto: int = 255) -> str:
    """Columnas por mes: cuota rayada, venta real con semáforo, línea de meta si supera 100% y variación MoM."""
    if g.empty:
        return ""
    vmax = float(max(g["Cuota"].max(), g["Real"].max(), 1e-9))
    area = alto - 46
    cols, lbls = [], []
    prev_real: float | None = None
    for _, r in g.iterrows():
        cls, _etq, color = estado(r["Pct"])
        h_q = max(r["Cuota"], 0.0) / vmax * area
        h_r = max(r["Real"], 0.0) / vmax * area
        linea_meta = (
            f"<div class='ca-col-target' style='bottom:{h_q:.0f}px' title='Meta: {_num(r['Cuota'], unidades)}'></div>"
            if (r["Cuota"] > 0 and r["Real"] > r["Cuota"])
            else ""
        )
        cols.append(
            f"<div class='ca-col' title='{esc(r['Mes'])}: real {_num(r['Real'], unidades)} · cuota {_num(r['Cuota'], unidades)} · brecha {_num(r['Brecha'], unidades, signo=True)}'>"
            f"<div class='ca-col-top'>{_num(r['Real'], unidades, True)}</div>"
            f"<div class='ca-col-stack' style='height:{max(h_q, h_r):.0f}px'>"
            f"<div class='ca-col-ghost' style='height:{h_q:.0f}px'></div>"
            f"<div class='ca-col-fill' style='height:{h_r:.0f}px;background:{color}'></div>{linea_meta}</div></div>"
        )
        mom_html = ""
        if prev_real is not None and prev_real > 0:
            v_mom = (r["Real"] - prev_real) / prev_real * 100.0
            c_mom = "ca-up" if v_mom >= 0 else "ca-down"
            mom_html = f"<small><span class='{c_mom}'>{v_mom:+.1f}% MoM</span></small>"
        prev_real = float(r["Real"])

        lbls.append(
            f"<div>{esc(r['Mes'])}<small><span class='ca-pill {cls}'>{_pct(r['Pct'], 0)}</span></small>"
            f"<small>meta {_num(r['Cuota'], unidades, True)}</small>{mom_html}</div>"
        )
    leyenda = (
        "<div class='ca-legend'>"
        "<span><i style='background:#059669'></i>Cumple ≥100%</span><span><i style='background:#0284c7'></i>Cerca 90–99%</span>"
        "<span><i style='background:#d97706'></i>En riesgo 75–89%</span><span><i style='background:#dc2626'></i>Crítico &lt;75%</span>"
        "<span><i style='background:repeating-linear-gradient(135deg,#e2e8f0,#e2e8f0 3px,#f1f5f9 3px,#f1f5f9 6px);border:1px dashed #94a3b8'></i>Cuota (faltante rayado)</span></div>"
    )
    return f"<div translate='no'><div class='ca-cols' style='height:{alto}px'>{''.join(cols)}</div><div class='ca-col-lbl'>{''.join(lbls)}</div>{leyenda}</div>"


def html_ranking(g: pd.DataFrame, etiqueta: str, unidades: bool, n: int = 10) -> str:
    if g.empty:
        return "<div class='ca-note'>Sin datos para esta selección.</div>"
    g = g.head(n)
    vmax = float(max(g["Cuota"].max(), g["Real"].max(), 1e-9))
    filas = []
    for i, r in enumerate(g.itertuples(index=False), 1):
        cls, _etq, color = estado(r.Pct)
        w_q = max(r.Cuota, 0.0) / vmax * 100.0
        w_r = max(r.Real, 0.0) / vmax * 100.0
        marca = f"<div class='ca-rk-mark' style='left:{w_q:.1f}%'></div>" if (r.Cuota > 0 and r.Real > r.Cuota) else ""
        c_gap = "ca-down" if r.Brecha < 0 else "ca-up"
        filas.append(
            f"<div class='ca-rk'><div class='ca-rk-l' title='{esc(getattr(r, etiqueta))}'><small>{i}</small>{esc(getattr(r, etiqueta))}</div>"
            f"<div class='ca-rk-b'><div class='ca-rk-ghost' style='width:{w_q:.1f}%'></div><div class='ca-rk-fill' style='width:{w_r:.1f}%;background:{color}'></div>{marca}</div>"
            f"<div class='ca-rk-n'>{_num(r.Real, unidades, True)}<small>de {_num(r.Cuota, unidades, True)}</small></div>"
            f"<div><span class='ca-pill {cls}'>{_pct(r.Pct, 0)}</span></div>"
            f"<div class='ca-rk-g {c_gap}'>{_num(r.Brecha, unidades, True, True)}</div></div>"
        )
    return (
        "<div translate='no'><div class='ca-rk-h'><div>" + esc(etiqueta) + "</div><div>Venta real vs cuota (rayado)</div>"
        "<div style='text-align:right'>Real</div><div>Cumpl.</div><div style='text-align:right'>Brecha</div></div>"
        + "".join(filas) + "</div>"
    )


def html_heatmap(pv: dict[str, pd.DataFrame], tipo: str, unidades: bool, etiqueta: str) -> str:
    real, cuota = pv["real"], pv["cuota"]
    if real.empty:
        return "<div class='ca-note'>Sin datos para esta selección.</div>"
    if tipo == "pct":
        vals = (real / cuota.where(cuota > 0)) * 100.0
    elif tipo == "brecha":
        vals = real - cuota
    elif tipo == "cuota":
        vals = cuota
    else:
        vals = real
    cuerpo_v = vals.drop(index="Total", errors="ignore").drop(columns="Total", errors="ignore")
    arr = cuerpo_v.values.astype(float)
    escala = float(np.nanmax(np.abs(arr))) if (arr.size and not np.all(np.isnan(arr))) else 1.0
    if np.isnan(escala) or escala <= 0:
        escala = 1.0

    cab = "".join(f"<th>{esc(c)}</th>" for c in vals.columns)
    filas = []
    for idx in vals.index:
        celdas = []
        es_tot = idx == "Total"
        for c in vals.columns:
            v = vals.loc[idx, c]
            r_, q_ = real.loc[idx, c], cuota.loc[idx, c]
            if tipo == "pct":
                fondo, txt = color_pct(v), _pct(v, 0)
            elif tipo == "brecha":
                fondo, txt = color_div(v, escala), _num(v, unidades, True, True)
            else:
                fondo, txt = color_sec(v, escala), _num(v, unidades, True)
            extra = "tot" if (c == "Total" or es_tot) else ""
            tip = f"{esc(idx)} · {esc(c)}: real {_num(r_, unidades)} · cuota {_num(q_, unidades)}"
            celdas.append(f"<td class='{extra}' style='background:{fondo}' title='{tip}'>{txt}</td>")
        filas.append(f"<tr><td class='rl' title='{esc(idx)}'>{esc(idx)}</td>{''.join(celdas)}</tr>")
    return f"<div class='ca-hmw' translate='no'><table class='ca-hm'><thead><tr><th class='rl'>{esc(etiqueta)}</th>{cab}</tr></thead><tbody>{''.join(filas)}</tbody></table></div>"


def html_pareto(g: pd.DataFrame, etiqueta: str, unidades: bool, top: int = 5) -> str:
    neg = g[g["Brecha"] < 0].sort_values("Brecha")
    if neg.empty:
        return "<div class='ca-note'>No hay brecha negativa: todo cumple la cuota.</div>"
    total = neg["Brecha"].sum()
    paleta = ["#002b5c", "#0369a1", "#0284c7", "#38bdf8", "#7dd3fc"]
    partes, leyenda = [], []
    for i, r in enumerate(neg.head(top).itertuples(index=False)):
        share = r.Brecha / total * 100.0
        c = paleta[i % len(paleta)]
        txt_c = "#0f172a" if i >= 3 else "#fff"
        partes.append(f"<div style='width:{share:.1f}%;background:{c};color:{txt_c}' title='{esc(getattr(r, etiqueta))}: {share:.0f}%'>{share:.0f}%</div>")
        leyenda.append(f"<span><i style='background:{c}'></i>{esc(getattr(r, etiqueta))} · {_num(r.Brecha, unidades, True)}</span>")
    if len(neg) > top:
        resto = neg.iloc[top:]["Brecha"].sum()
        if resto < 0:
            share = resto / total * 100.0
            partes.append(f"<div style='width:{share:.1f}%;background:#cbd5e1;color:#334155' title='Resto: {share:.0f}%'>{share:.0f}%</div>")
            leyenda.append(f"<span><i style='background:#cbd5e1'></i>Resto ({len(neg) - top}) · {_num(resto, unidades, True)}</span>")
    return f"<div translate='no'><div class='ca-pareto'>{''.join(partes)}</div><div class='ca-legend'>{''.join(leyenda)}</div></div>"


def html_hallazgos(items: list[tuple[str, str]]) -> str:
    if not items:
        return ""
    return "<div class='ca-ins' translate='no'>" + "".join(f"<div class='ca-in {t}'>{txt}</div>" for t, txt in items) + "</div>"


def card(titulo: str, sub: str, cuerpo: str) -> str:
    return f"<div class='ca-card' translate='no'><div class='ca-h'>{esc(titulo)}</div><div class='ca-sub'>{esc(sub)}</div>{cuerpo}</div>"


# -----------------------------------------------------------------------------
# 5. HALLAZGOS AUTOMÁTICOS (INCLUYE APAGONES DEL ÚLTIMO MES)
# -----------------------------------------------------------------------------
def generar_hallazgos(df: pd.DataFrame, unidades: bool, df_apagones: pd.DataFrame, ult_mes_lbl: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    t = totales(df)
    if df.empty or np.isnan(t["pct"]):
        return out
    cls = "good" if t["pct"] >= 100 else ("info" if t["pct"] >= 90 else ("warn" if t["pct"] >= 75 else "bad"))
    out.append((
        cls,
        f"<b>Cumplimiento global: {_pct(t['pct'])}.</b> Faltan {_num(abs(t['brecha']), unidades, True)} para llegar a la cuota del período."
        if t["brecha"] < 0
        else f"<b>Cumplimiento global: {_pct(t['pct'])}.</b> Se superó la cuota por {_num(t['brecha'], unidades, True)}.",
    ))

    m = resumir(df, ["Periodo", "Mes"]).sort_values("Periodo")
    if len(m) >= 2 and m["Pct"].notna().any():
        mejor, peor = m.loc[m["Pct"].idxmax()], m.loc[m["Pct"].idxmin()]
        ult, prev = m.iloc[-1], m.iloc[-2]
        var = (ult["Real"] - prev["Real"]) / prev["Real"] * 100.0 if prev["Real"] > 0 else np.nan
        tono = "good" if (not np.isnan(var) and var >= 0) else "warn"
        out.append((
            tono,
            f"<b>Mejor mes: {esc(mejor['Mes'])} ({_pct(mejor['Pct'], 0)}). Peor: {esc(peor['Mes'])} ({_pct(peor['Pct'], 0)}).</b> "
            f"El último mes ({esc(ult['Mes'])}) {'subió' if var >= 0 else 'cayó'} {abs(var):.1f}% frente a {esc(prev['Mes'])}."
            if not np.isnan(var)
            else f"<b>Mejor mes: {esc(mejor['Mes'])} ({_pct(mejor['Pct'], 0)}). Peor: {esc(peor['Mes'])} ({_pct(peor['Pct'], 0)}).</b>",
        ))

    if not df_apagones.empty:
        riesgo = float(df_apagones["Riesgo_Mensual"].sum())
        top_ap = str(df_apagones.iloc[0]["Farmacia"])
        out.append((
            "bad",
            f"<b>🚨 {len(df_apagones)} farmacias en apagón en {esc(ult_mes_lbl)}:</b> venían comprando bien y cayeron a $0 o &gt;90% "
            f"(riesgo: {_num(riesgo, unidades, True)}/mes). Encabeza <b>{esc(top_ap)}</b>.",
        ))

    for col, nombre in (("Territorio", "territorios"), ("Producto", "productos")):
        g = resumir(df, col)
        neg = g[g["Brecha"] < 0].sort_values("Brecha")
        if len(neg) >= 2:
            share = neg.head(2)["Brecha"].sum() / neg["Brecha"].sum() * 100.0
            a, b = neg.iloc[0], neg.iloc[1]
            out.append((
                "bad" if share >= 40 else "warn",
                f"<b>{esc(a[col])} y {esc(b[col])} concentran {share:.0f}% de la brecha</b> entre {nombre} "
                f"({_num(a['Brecha'], unidades, True)} y {_num(b['Brecha'], unidades, True)}).",
            ))

    gp = resumir(df, "Producto").dropna(subset=["Pct"])
    gp = gp[gp["Cuota"] > 0]
    if len(gp) >= 3:
        b, w = gp.loc[gp["Pct"].idxmax()], gp.loc[gp["Pct"].idxmin()]
        out.append((
            "info",
            f"<b>Producto más cerca de la meta: {esc(b['Producto'])} ({_pct(b['Pct'], 0)}).</b> "
            f"El más rezagado es {esc(w['Producto'])} ({_pct(w['Pct'], 0)}).",
        ))
    return out


# -----------------------------------------------------------------------------
# 6. PIVOT PARA EL EXPLORADOR
# -----------------------------------------------------------------------------
def pivotar(df: pd.DataFrame, filas: str, columnas: str | None, top: int, orden: str, mes_orden: list[str]) -> dict[str, pd.DataFrame]:
    base = resumir(df, filas)
    if orden == "Mayor brecha":
        base = base.sort_values("Brecha")
    elif orden == "Mayor venta":
        base = base.sort_values("Real", ascending=False)
    elif orden == "Menor cumplimiento":
        base = base[base["Cuota"] > 0].sort_values("Pct")
    else:
        base = base[base["Cuota"] > 0].sort_values("Pct", ascending=False)
    claves = base[filas].head(top).tolist()
    sub = df[df[filas].isin(claves)]
    out = {}
    for nombre, col in (("real", "R"), ("cuota", "Q")):
        if columnas:
            p = sub.pivot_table(index=filas, columns=columnas, values=col, aggfunc="sum", fill_value=0.0)
            if columnas == "Mes":
                p = p[[m for m in mes_orden if m in p.columns]]
        else:
            p = sub.groupby(filas)[[col]].sum().rename(columns={col: "Valor"})
        p = p.reindex(claves)
        if columnas:
            p["Total"] = p.sum(axis=1)
        p.loc["Total"] = p.sum(axis=0)
        out[nombre] = p
    return out


# -----------------------------------------------------------------------------
# 7. INTERFAZ STREAMLIT
# -----------------------------------------------------------------------------
def _csv(df: pd.DataFrame, incluir_index: bool = True) -> bytes:
    return df.to_csv(index=incluir_index).encode("utf-8-sig")


def _tabla_farmacias(g: pd.DataFrame, unidades: bool) -> None:
    pref = "%.0f" if unidades else "$%.0f"
    d = g.rename(columns={"Pct": "% Cumpl."})[["Farmacia", "Real", "Cuota", "Brecha", "% Cumpl."]]
    st.dataframe(
        d, hide_index=True, width="stretch", height=380,
        column_config={
            "Farmacia": st.column_config.TextColumn("Farmacia", pinned=True, width="medium"),
            "Real": st.column_config.NumberColumn("Venta real", format=pref),
            "Cuota": st.column_config.NumberColumn("Cuota", format=pref),
            "Brecha": st.column_config.NumberColumn("Brecha", format=pref),
            "% Cumpl.": st.column_config.ProgressColumn("% Cumpl.", format="%.0f%%", min_value=0, max_value=120),
        },
    )


def render_centro_analisis(data_dir: Path, base_dir: Path) -> None:
    _emit(CSS)
    ruta = buscar_excel_ventas(Path(data_dir), Path(base_dir), Path(base_dir) / "DATOS", Path(base_dir) / "data")
    if ruta is None:
        st.warning(
            "No encontré el Excel de ventas. Debe ser un .xlsx con una hoja por mes (ej. «octubre 2026») y las columnas "
            "DESCRIPCION_RUTA, NOMBRE_CLIENTE_1, VM4, Monto Real y Monto Cuota."
        )
        return
    df_all, filtros_origen = cargar_ventas(str(ruta), ruta.stat().st_mtime)
    if df_all.empty:
        st.warning(f"El archivo {ruta.name} no tiene filas de detalle (Ruta > Cliente > Producto).")
        return

    meses = df_all.drop_duplicates("Periodo").sort_values("Periodo")
    periodos, etiquetas = meses["Periodo"].tolist(), meses["Mes"].tolist()
    orden_mes = dict(zip(periodos, etiquetas))

    # ---- Filtros globales -------------------------------------------------
    with st.container(border=True):
        f1, f2, f3, f4 = st.columns([1.6, 1.4, 1.4, 1.0])
        with f1:
            if len(etiquetas) > 1:
                m_ini, m_fin = st.select_slider("Período", options=etiquetas, value=(etiquetas[0], etiquetas[-1]), key="ca_per")
            else:
                m_ini = m_fin = etiquetas[0]
                st.caption(f"Período: {m_ini}")
        with f2:
            terr_sel = st.multiselect("Territorio", sorted(df_all["Territorio"].unique()), placeholder="Todos", key="ca_terr")
        with f3:
            prod_sel = st.multiselect("Producto", sorted(df_all["Producto"].unique()), placeholder="Todos", key="ca_prod")
        with f4:
            medida = st.radio("Medida", ["Monto ($)", "Unidades"], key="ca_medida", horizontal=False)
    unidades = medida == "Unidades"

    p_ini, p_fin = etiquetas.index(m_ini), etiquetas.index(m_fin)
    sel_periodos = periodos[p_ini:p_fin + 1]
    df = df_all[df_all["Periodo"].isin(sel_periodos)]
    if terr_sel:
        df = df[df["Territorio"].isin(terr_sel)]
    if prod_sel:
        df = df[df["Producto"].isin(prod_sel)]
    if df.empty:
        st.info("No hay datos con esos filtros. Quita alguno para ver resultados.")
        return
    df = con_medida(df, unidades)
    orden_meses = [orden_mes[p] for p in sel_periodos]

    t = totales(df)
    g_mes = resumir(df, ["Periodo", "Mes"]).sort_values("Periodo")
    var_ult = None
    if len(g_mes) >= 2 and g_mes.iloc[-2]["Real"] > 0:
        var_ult = (g_mes.iloc[-1]["Mes"], (g_mes.iloc[-1]["Real"] - g_mes.iloc[-2]["Real"]) / g_mes.iloc[-2]["Real"] * 100.0)
    n_farm = int(resumir(df, "Farmacia").query("Cuota > 0").shape[0])
    df_apagones = detectar_apagones(df, sel_periodos, orden_mes, unidades)
    ult_mes_lbl = orden_meses[-1]

    _emit(html_kpis(t, unidades, len(sel_periodos), var_ult, n_farm))

    tab_res, tab_alert, tab_ter, tab_pro, tab_far, tab_exp = st.tabs([
        "Resumen",
        f"🚨 Alertas y Simulador ({len(df_apagones)})",
        "Territorios",
        "Productos",
        "Farmacias",
        "Explorador libre",
    ])

   # ---- TAB 1: RESUMEN ---------------------------------------------------
    with tab_res:
        _emit(html_hallazgos(generar_hallazgos(df, unidades, df_apagones, ult_mes_lbl)))
        _emit(card(
            "Evolución mensual: venta real vs. cuota",
            "Cada columna es un mes con su % de cumplimiento y variación MoM. La parte rayada es lo que faltó para la cuota.",
            html_columnas_mes(g_mes, unidades),
        ))
        c1, c2 = st.columns(2)
        with c1:
            g = resumir(df, "Territorio").sort_values("Brecha")
            _emit(card("Territorios con mayor brecha", "Los 6 donde más falta para llegar a la cuota.", html_ranking(g, "Territorio", unidades, 6)))
        with c2:
            g = resumir(df, "Producto").sort_values("Brecha")
            _emit(card("Productos con mayor brecha", "Los 6 donde más falta para llegar a la cuota.", html_ranking(g, "Producto", unidades, 6)))

    # ---- TAB 2: ALERTAS (APAGONES) Y SIMULADOR DE CIERRE ------------------
    with tab_alert:
        st.markdown(f"##### 🎯 Simulador de Cierre de Cuota (¿Qué pasa si atacas tus farmacias Pareto?)")
        gf_sim = resumir(df, ["Farmacia", "Territorio"])
        gf_neg = gf_sim[gf_sim["Brecha"] < 0].sort_values("Brecha").reset_index(drop=True)

        if not gf_neg.empty:
            s_c1, s_c2 = st.columns(2)
            max_n = min(40, len(gf_neg))
            with s_c1:
                n_rec = st.slider("Farmacias prioritarias a visitar / reactivar:", 1, max_n, min(15, max_n), key="ca_sim_n")
            with s_c2:
                pct_rec = st.slider("% de su brecha que logras recuperar:", 10, 100, 50, step=5, key="ca_sim_pct")

            objetivo_df = gf_neg.head(n_rec).copy()
            recuperado = float(abs(objetivo_df["Brecha"].sum()) * (pct_rec / 100.0))
            nueva_venta = t["real"] + recuperado
            nuevo_pct = (nueva_venta / t["cuota"] * 100.0) if t["cuota"] > 0 else 0.0
            delta_pp = nuevo_pct - (t["pct"] if not np.isnan(t["pct"]) else 0.0)

            _emit(f"""
            <div class='ca-sim-box' translate='no'>
              <div><div class='ca-sim-lbl'>Recuperación Estimada</div><div class='ca-sim-val' style='color:#059669;'>+{_num(recuperado, unidades, True)}</div></div>
              <div><div class='ca-sim-lbl'>Nueva Venta Proyectada</div><div class='ca-sim-val'>{_num(nueva_venta, unidades, True)}</div></div>
              <div><div class='ca-sim-lbl'>Nuevo % Cumplimiento</div><div class='ca-sim-val'>{_pct(nuevo_pct)} <span style='font-size:.82rem;color:#059669;'>(+{delta_pp:.1f} pp)</span></div></div>
              <div><div class='ca-sim-lbl'>Farmacias en Plan</div><div class='ca-sim-val'>{n_rec} de {len(gf_neg)}</div></div>
            </div>
            """)

            mapa_skus = top_codigos_por_farmacia(df, unidades, k=2)
            objetivo_df["Meta Recuperación"] = (objetivo_df["Brecha"].abs() * (pct_rec / 100.0)).round(0)
            objetivo_df["Códigos Exactos a Empujar"] = objetivo_df["Farmacia"].map(mapa_skus).fillna("Mix general")
            pref_n = "%.0f" if unidades else "$%.0f"
            st.dataframe(
                objetivo_df[["Farmacia", "Territorio", "Real", "Cuota", "Brecha", "Meta Recuperación", "Códigos Exactos a Empujar"]],
                hide_index=True,
                width="stretch",
                height=310,
                column_config={
                    "Farmacia": st.column_config.TextColumn("Farmacia", pinned=True, width="medium"),
                    "Real": st.column_config.NumberColumn("Real", format=pref_n),
                    "Cuota": st.column_config.NumberColumn("Cuota", format=pref_n),
                    "Brecha": st.column_config.NumberColumn("Brecha", format=pref_n),
                    "Meta Recuperación": st.column_config.NumberColumn(f"Meta ({pct_rec}%)", format=pref_n),
                },
            )
            st.download_button(
                "Descargar Plan de Cierre de Ruta (CSV para Excel)",
                _csv(objetivo_df, incluir_index=False),
                file_name=f"plan_cierre_{n_rec}_farmacias.csv",
                mime="text/csv",
                key="ca_sim_dl",
            )
        else:
            st.success("¡Excelente! No hay farmacias con brecha negativa en esta selección.")

        st.divider()
        st.markdown(f"##### 🚨 Radar de Apagones en {ult_mes_lbl} (Clientes buenos que cayeron a $0 o >90%)")
        if not df_apagones.empty:
            pref_ap = "%.0f" if unidades else "$%.0f"
            cfg_ap: dict[str, Any] = {
                "Farmacia": st.column_config.TextColumn("Farmacia", pinned=True, width="medium"),
                "Prom_Prev": st.column_config.NumberColumn("Prom. Meses Prev.", format=pref_ap),
                "Riesgo_Mensual": st.column_config.NumberColumn("Riesgo Mensual", format=pref_ap),
            }
            for m_lbl in orden_meses:
                cfg_ap[m_lbl] = st.column_config.NumberColumn(m_lbl, format=pref_ap)
            st.dataframe(df_apagones, hide_index=True, width="stretch", height=320, column_config=cfg_ap)
            st.download_button(
                "Descargar Lista de Apagones Urgentes (CSV)",
                _csv(df_apagones, incluir_index=False),
                file_name=f"apagones_{ult_mes_lbl.lower().replace(' ', '_')}.csv",
                mime="text/csv",
                key="ca_ap_dl",
            )
        else:
            st.info(f"No se detectaron apagones críticos en {ult_mes_lbl} (o selecciona al menos 2 meses en el deslizador de Período).")

    # ---- TAB 3: TERRITORIOS -----------------------------------------------
    with tab_ter:
        orden_t = st.radio("Ordenar por", ["Mayor brecha", "Mayor venta", "Menor cumplimiento", "Mejor cumplimiento"], horizontal=True, key="ca_ord_t")
        g = resumir(df, "Territorio")
        g = {
            "Mayor brecha": g.sort_values("Brecha"),
            "Mayor venta": g.sort_values("Real", ascending=False),
            "Menor cumplimiento": g[g["Cuota"] > 0].sort_values("Pct"),
            "Mejor cumplimiento": g[g["Cuota"] > 0].sort_values("Pct", ascending=False),
        }[orden_t]
        _emit(card("Cumplimiento por territorio", "Barra = venta real; rayado = cuota. El color indica el estado de cumplimiento.", html_ranking(g, "Territorio", unidades, 20)))
        _emit(card("¿Quién explica la brecha?", "Participación de cada territorio en el faltante total.", html_pareto(resumir(df, "Territorio"), "Territorio", unidades)))
        pv = pivotar(df, "Territorio", "Mes", 20, "Mayor brecha", orden_meses)
        _emit(card("Mapa de calor: % de cumplimiento por mes", "Rojo = lejos de la cuota · verde = cumple. Pasa el cursor sobre una celda para ver montos.", html_heatmap(pv, "pct", unidades, "Territorio")))

    # ---- TAB 4: PRODUCTOS -------------------------------------------------
    with tab_pro:
        orden_p = st.radio("Ordenar por", ["Mayor brecha", "Mayor venta", "Menor cumplimiento", "Mejor cumplimiento"], horizontal=True, key="ca_ord_p")
        g = resumir(df, "Producto")
        g = {
            "Mayor brecha": g.sort_values("Brecha"),
            "Mayor venta": g.sort_values("Real", ascending=False),
            "Menor cumplimiento": g[g["Cuota"] > 0].sort_values("Pct"),
            "Mejor cumplimiento": g[g["Cuota"] > 0].sort_values("Pct", ascending=False),
        }[orden_p]
        _emit(card("Cumplimiento por producto", "Barra = venta real; rayado = cuota.", html_ranking(g, "Producto", unidades, 20)))
        _emit(card("¿Qué productos explican la brecha?", "Participación de cada producto en el faltante total.", html_pareto(resumir(df, "Producto"), "Producto", unidades)))
        pv = pivotar(df, "Producto", "Mes", 20, "Mayor brecha", orden_meses)
        _emit(card("Producto × mes: % de cumplimiento", "Detecta si un producto mejora o empeora con el tiempo.", html_heatmap(pv, "pct", unidades, "Producto")))
        pv2 = pivotar(df, "Producto", "Territorio", 20, "Mayor brecha", orden_meses)
        _emit(card("Producto × territorio: % de cumplimiento", "Cruza dónde se vende bien cada producto.", html_heatmap(pv2, "pct", unidades, "Producto")))

    # ---- TAB 5: FARMACIAS -------------------------------------------------
    with tab_far:
        a, b = st.columns([1.6, 1.0])
        with a:
            vista = st.radio(
                "Qué quieres ver",
                ["Dónde recuperar (mayor brecha)", "🚀 En aceleración (creciendo)", "Las que mejor cumplen", "Sin venta neta"],
                horizontal=True,
                key="ca_far_v",
            )
        with b:
            n_far = st.slider("Cantidad a mostrar", 5, 40, 15, key="ca_far_n")
        gf = resumir(df, "Farmacia")
        if vista.startswith("Dónde"):
            g = gf.sort_values("Brecha")
            sub_v = "Priorización para visitas y gestión comercial."
        elif "aceleración" in vista:
            g = detectar_aceleracion(df, sel_periodos)
            sub_v = "Farmacias que más aumentaron su compra mensual entre la 1ra y 2da mitad del período."
        elif vista.startswith("Las que"):
            g = gf[gf["Cuota"] > 0].sort_values("Pct", ascending=False)
            sub_v = "Mejores tasas de cumplimiento de cuota."
        else:
            g = gf[(gf["Cuota"] > 0) & (gf["Real"] <= 0)].sort_values("Cuota", ascending=False)
            sub_v = "Farmacias con cuota asignada pero sin compra neta positiva."
        _emit(card(vista, sub_v, html_ranking(g, "Farmacia", unidades, n_far)))

        st.markdown("##### Ficha de farmacia (Diagnóstico de mostrador)")
        fcol1, fcol2 = st.columns([1.2, 2.0])
        with fcol1:
            opciones = gf.sort_values("Cuota", ascending=False)["Farmacia"].tolist()
            farm = st.selectbox("Selecciona una farmacia", opciones, key="ca_far_sel")
        dfa = df[df["Farmacia"] == farm]
        tf = totales(dfa)
        cls, etq, _c = estado(tf["pct"])
        with fcol2:
            _emit(
                f"<div class='ca-note' translate='no' style='padding-top:28px;'><span class='ca-pill {cls}'>{_pct(tf['pct'])} · {etq}</span> &nbsp; "
                f"Real <b>{_num(tf['real'], unidades, True)}</b> de {_num(tf['cuota'], unidades, True)} · brecha <b>{_num(tf['brecha'], unidades, True, True)}</b></div>"
            )

        g_prods_f = resumir(dfa, "Producto").sort_values("Brecha")
        top3_emp = g_prods_f[g_prods_f["Brecha"] < 0].head(3)
        if not top3_emp.empty:
            skus_txt = " · ".join(
                f"<b>{esc(r.Producto)}</b> ({_num(r.Brecha, unidades, True)} / {_pct(r.Pct, 0)})"
                for r in top3_emp.itertuples(index=False)
            )
            _emit(f"<div class='ca-ficha-cta' translate='no'>🎯 <b>Prioridad al entrar a {esc(farm)}:</b> Empujar reposición en {skus_txt}.</div>")

        h1, h2 = st.columns([1.3, 1.0])
        with h1:
            _emit(card("Evolución mensual de la farmacia", "Venta real vs. cuota por mes.", html_columnas_mes(resumir(dfa, ["Periodo", "Mes"]).sort_values("Periodo"), unidades, 215)))
        with h2:
            _emit(card("Productos de la farmacia", "Ordenados por brecha.", html_ranking(g_prods_f, "Producto", unidades, 12)))

        with st.expander("Ver tabla completa de farmacias"):
            q = st.text_input("Buscar farmacia", key="ca_far_q")
            tabla = gf.sort_values("Brecha")
            if q.strip():
                tabla = tabla[tabla["Farmacia"].str.contains(q.strip(), case=False, na=False, regex=False)]
            _tabla_farmacias(tabla, unidades)

    # ---- TAB 6: EXPLORADOR LIBRE ------------------------------------------
    with tab_exp:
        st.caption("Arma tu propio cruce: elige qué va en filas, qué va en columnas y qué quieres medir.")
        e1, e2, e3, e4, e5 = st.columns([1, 1, 1.1, 1.1, 0.9])
        dims = ["Territorio", "Producto", "Farmacia", "Mes"]
        with e1:
            filas = st.selectbox("Filas", dims, index=0, key="ca_ex_f")
        with e2:
            col_op = ["(ninguna)"] + [d for d in dims if d != filas]
            columnas = st.selectbox("Columnas", col_op, index=col_op.index("Mes") if "Mes" in col_op else 0, key="ca_ex_c")
        with e3:
            valor = st.selectbox("Valor", ["% de cumplimiento", "Brecha vs cuota", "Venta real", "Cuota"], key="ca_ex_v")
        with e4:
            orden_e = st.selectbox("Ordenar filas por", ["Mayor brecha", "Mayor venta", "Menor cumplimiento", "Mejor cumplimiento"], key="ca_ex_o")
        with e5:
            top_e = st.number_input("Máx. filas", 5, 60, 15, step=5, key="ca_ex_n")
        col_real = None if columnas == "(ninguna)" else columnas
        pv = pivotar(df, filas, col_real, int(top_e), orden_e, orden_meses)
        tipo = {"% de cumplimiento": "pct", "Brecha vs cuota": "brecha", "Venta real": "real", "Cuota": "cuota"}[valor]
        _emit(card(
            f"{valor}: {filas}" + (f" × {columnas}" if col_real else ""),
            f"Top {int(top_e)} según «{orden_e}». Pasa el cursor sobre una celda para ver real y cuota.",
            html_heatmap(pv, tipo, unidades, filas),
        ))
        if tipo == "pct":
            salida = (pv["real"] / pv["cuota"].where(pv["cuota"] > 0) * 100.0).round(1)
        elif tipo == "brecha":
            salida = (pv["real"] - pv["cuota"]).round(2)
        else:
            salida = pv[tipo].round(2)
        st.download_button("Descargar esta tabla (CSV para Excel)", _csv(salida), file_name=f"analisis_{filas.lower()}_{tipo}.csv", mime="text/csv", key="ca_ex_dl")

    with st.expander("Origen de los datos y cómo leer este módulo"):
        st.caption(f"Archivo: `{ruta.name}` · {len(df_all):,} registros Ruta × Farmacia × Producto × Mes.")
        if filtros_origen:
            st.caption(f"Filtros del reporte original: {filtros_origen}")
        st.caption(
            "Cumplimiento = venta real ÷ cuota. Brecha = real − cuota (negativa = falta). "
            "Semáforo: Cumple ≥100% · Cerca 90–99% · En riesgo 75–89% · Crítico <75%. "
            "Apagón = farmacia con promedio previo ≥$150 (o 15 und) que cayó a $0 o >90% en el último mes."
        )
