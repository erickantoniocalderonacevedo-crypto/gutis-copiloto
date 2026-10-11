import pandas as pd

print("Cargando bases...")
df_panel = pd.read_excel("PANEL ERICK 2026.xlsx")
df_productos = pd.read_excel("DATA MEDICOS AGOSTO PRODUCTOS TOTAL NICARAGUA.xlsx")
df_ventas = pd.read_excel("VENTAS TERCER TRIMESTRE 2026.xlsx", sheet_name="Export")

# Limpieza básica de encabezados y texto
for df in [df_panel, df_productos, df_ventas]:
    df.columns = df.columns.str.strip()

df_panel["Médico"] = df_panel["Médico"].astype(str).str.strip().str.upper()
df_productos["Médico"] = df_productos["Médico"].astype(str).str.strip().str.upper()
df_ventas["DESCRIPCION_RUTA"] = df_ventas["DESCRIPCION_RUTA"].astype(str).str.strip().str.upper()

# Médico evaluado (Ejemplo: Dr. Henry Larios)
medico_ejemplo = df_panel.iloc[0]
nombre_medico = medico_ejemplo["Médico"]
ciudad = str(medico_ejemplo.get("CIUDAD", "")).strip().upper()

print(f"\n==========================================")
print(f"PERFIL: {nombre_medico}")
print(f"CIUDAD: {ciudad} | ESP: {medico_ejemplo.get('Especialidad', 'N/D')} | CAT: {medico_ejemplo.get('CATEGORIA', 'N/D')}")
print(f"==========================================")

# 1. Top 5 productos prescritos
rx = df_productos[df_productos["Médico"] == nombre_medico].dropna(subset=["NOMBRE_PRODUCTO"])
if not rx.empty:
    print("\nTOP PRESCRIPCIONES EN EL MERCADO:")
    top_rx = rx[["MERCADO", "NOMBRE_PRODUCTO", "Pxs-TAM", "%MS-TAM"]].sort_values(by="Pxs-TAM", ascending=False).head(5)
    print(top_rx.to_string(index=False))

# 2. Ventas en la zona/ruta del médico
ventas_zona = df_ventas[df_ventas["DESCRIPCION_RUTA"].str.contains(ciudad, na=False)]
if not ventas_zona.empty:
    print(f"\nTOP FARMACIAS / CLIENTES EN SU ZONA ({ciudad}):")
    top_farmacias = ventas_zona.groupby("NOMBRE_CLIENTE_1")["Monto Real"].sum().reset_index()
    top_farmacias = top_farmacias.sort_values(by="Monto Real", ascending=False).head(5)
    print(top_farmacias.to_string(index=False))
else:
    print(f"\nRutas registradas en Ventas:")
    print(df_ventas["DESCRIPCION_RUTA"].unique()[:5])