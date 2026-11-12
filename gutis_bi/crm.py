"""
Persistencia Relacional SQLite para Gutis BI (CRM y Ficha 360).
Elimina los problemas de concurrencia y corrupción de Excel.
"""

import sqlite3
import pandas as pd
from pathlib import Path
from typing import Optional, Union, Dict, Any

def get_connection(db_path: Union[str, Path]) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: Union[str, Path]) -> None:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS visitas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Fecha TEXT,
            Ciudad TEXT,
            Médico TEXT,
            Especialidad TEXT,
            Producto_Foco TEXT,
            Producto_Puente TEXT,
            Logro_SMART TEXT,
            Escala_TVP TEXT,
            Acuerdo_Medico TEXT,
            Acuerdo_Visitador TEXT,
            Notas TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS perfiles_360 (
            Médico TEXT PRIMARY KEY,
            MINSA TEXT,
            Celular TEXT,
            Cumpleaños TEXT,
            Deporte TEXT,
            Estilo_Visita TEXT,
            Ultima_Actualizacion TEXT
        )
    """)
    conn.commit()
    conn.close()

def guardar_visita(record: Dict[str, Any], db_path: Union[str, Path]) -> None:
    init_db(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO visitas (
            Fecha, Ciudad, Médico, Especialidad, Producto_Foco, Producto_Puente,
            Logro_SMART, Escala_TVP, Acuerdo_Medico, Acuerdo_Visitador, Notas
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.get("Fecha"), record.get("Ciudad"), record.get("Médico"), record.get("Especialidad"),
        record.get("Producto_Foco"), record.get("Producto_Puente"), record.get("Logro_SMART"),
        record.get("Escala_TVP"), record.get("Acuerdo_Medico"), record.get("Acuerdo_Visitador"),
        record.get("Notas")
    ))
    conn.commit()
    conn.close()

def leer_visitas(medico: Optional[str] = None, db_path: Union[str, Path] = "gutis_bi.db") -> pd.DataFrame:
    init_db(db_path)
    conn = get_connection(db_path)
    if medico:
        df = pd.read_sql_query("SELECT * FROM visitas WHERE Médico = ? ORDER BY id DESC", conn, params=(medico,))
    else:
        df = pd.read_sql_query("SELECT * FROM visitas ORDER BY id DESC", conn)
    conn.close()
    return df

def guardar_perfil_360(record: Dict[str, Any], db_path: Union[str, Path]) -> None:
    init_db(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO perfiles_360 (
            Médico, MINSA, Celular, Cumpleaños, Deporte, Estilo_Visita, Ultima_Actualizacion
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        record.get("Médico"), record.get("MINSA"), record.get("Celular"),
        record.get("Cumpleaños"), record.get("Deporte"), record.get("Estilo_Visita"),
        record.get("Ultima_Actualizacion")
    ))
    conn.commit()
    conn.close()

def leer_perfil_360(medico: str, db_path: Union[str, Path]) -> Dict[str, Any]:
    init_db(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM perfiles_360 WHERE Médico = ?", (medico,))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {}

def migrar_excels_anteriores(legacy_history: Optional[Path], legacy_profile: Optional[Path], db_path: Union[str, Path]) -> Dict[str, int]:
    init_db(db_path)
    migrados = {"visitas": 0, "perfiles": 0}
    if legacy_history and legacy_history.exists():
        try:
            df_v = pd.read_excel(legacy_history)
            for _, r in df_v.iterrows():
                guardar_visita(r.to_dict(), db_path)
                migrados["visitas"] += 1
        except Exception:
            pass
    if legacy_profile and legacy_profile.exists():
        try:
            df_p = pd.read_excel(legacy_profile)
            for _, r in df_p.iterrows():
                guardar_perfil_360(r.to_dict(), db_path)
                migrados["perfiles"] += 1
        except Exception:
            pass
    return migrados

def exportar_visitas_csv(db_path: Union[str, Path]) -> str:
    df = leer_visitas(None, db_path)
    return df.to_csv(index=False).encode("utf-8-sig")
