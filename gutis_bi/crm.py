"""
Persistencia Relacional SQLite para Gutis BI (CRM y Ficha 360).
Elimina los problemas de concurrencia, duplicación infinita y corrupción de Excel.
"""

import sqlite3
import pandas as pd
from pathlib import Path
from typing import Optional, Union, Dict, Any
import contextlib

def get_connection(db_path: Union[str, Path]) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: Union[str, Path]) -> None:
    with contextlib.closing(get_connection(db_path)) as conn:
        with conn:
            conn.execute("""
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
            conn.execute("""
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

def guardar_visita(record: Dict[str, Any], db_path: Union[str, Path]) -> None:
    init_db(db_path)
    with contextlib.closing(get_connection(db_path)) as conn:
        with conn:
            conn.execute("""
                INSERT INTO visitas (
                    Fecha, Ciudad, Médico, Especialidad, Producto_Foco, Producto_Puente,
                    Logro_SMART, Escala_TVP, Acuerdo_Medico, Acuerdo_Visitador, Notas
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(record.get("Fecha", "")), str(record.get("Ciudad", "")), str(record.get("Médico", "")), 
                str(record.get("Especialidad", "")), str(record.get("Producto_Foco", "")), 
                str(record.get("Producto_Puente", "")), str(record.get("Logro_SMART", "")),
                str(record.get("Escala_TVP", "")), str(record.get("Acuerdo_Medico", "")), 
                str(record.get("Acuerdo_Visitador", "")), str(record.get("Notas", ""))
            ))

def leer_visitas(medico: Optional[str] = None, db_path: Union[str, Path] = "gutis_bi.db") -> pd.DataFrame:
    init_db(db_path)
    with contextlib.closing(get_connection(db_path)) as conn:
        if medico:
            return pd.read_sql_query("SELECT * FROM visitas WHERE Médico = ? ORDER BY id DESC", conn, params=(medico,))
        return pd.read_sql_query("SELECT * FROM visitas ORDER BY id DESC", conn)

def guardar_perfil_360(record: Dict[str, Any], db_path: Union[str, Path]) -> None:
    init_db(db_path)
    with contextlib.closing(get_connection(db_path)) as conn:
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO perfiles_360 (
                    Médico, MINSA, Celular, Cumpleaños, Deporte, Estilo_Visita, Ultima_Actualizacion
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                str(record.get("Médico", "")), str(record.get("MINSA", "")), str(record.get("Celular", "")),
                str(record.get("Cumpleaños", "")), str(record.get("Deporte", "")), 
                str(record.get("Estilo_Visita", "")), str(record.get("Ultima_Actualizacion", ""))
            ))

def leer_perfil_360(medico: str, db_path: Union[str, Path]) -> Dict[str, Any]:
    init_db(db_path)
    with contextlib.closing(get_connection(db_path)) as conn:
        cur = conn.execute("SELECT * FROM perfiles_360 WHERE Médico = ?", (medico,))
        row = cur.fetchone()
        return dict(row) if row else {}

def migrar_excels_anteriores(legacy_history: Optional[Path], legacy_profile: Optional[Path], db_path: Union[str, Path]) -> Dict[str, int]:
    init_db(db_path)
    migrados = {"visitas": 0, "perfiles": 0}
    
    if legacy_history and legacy_history.exists():
        try:
            # astype(str) fuerza la conversión para que SQLite no choque con Fechas/Numpy de Excel
            df_v = pd.read_excel(legacy_history).astype(str).fillna("")
            for _, r in df_v.iterrows():
                guardar_visita(r.to_dict(), db_path)
                migrados["visitas"] += 1
            # Evita el bucle infinito y duplicación renombrando el excel tras el primer pase exitoso
            legacy_history.rename(legacy_history.with_suffix('.xlsx.migrado'))
        except Exception as e:
            print(f"Error migrando historial: {e}")
            
    if legacy_profile and legacy_profile.exists():
        try:
            df_p = pd.read_excel(legacy_profile).astype(str).fillna("")
            for _, r in df_p.iterrows():
                guardar_perfil_360(r.to_dict(), db_path)
                migrados["perfiles"] += 1
            legacy_profile.rename(legacy_profile.with_suffix('.xlsx.migrado'))
        except Exception as e:
            print(f"Error migrando perfiles: {e}")
            
    return migrados

def exportar_visitas_csv(db_path: Union[str, Path]) -> str:
    df = leer_visitas(None, db_path)
    return df.to_csv(index=False).encode("utf-8-sig")
