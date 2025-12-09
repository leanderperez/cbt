import pandas as pd
import json

# Cargar el archivo CSV
# Asegúrate de que el delimitador es el correcto (usamos ';')
df = pd.read_csv("reglas_em_VRF.csv", sep=';')

# Renombrar columnas para claridad si es necesario, aunque aquí se mantienen los nombres
# df.columns = ['cantidad_requerida', 'equipo_origen_id', 'material_requerido_id']

# Agrupar por 'equipo_origen_id' y transformar los datos de material a formato JSON
def aggregate_materials(group):
    """
    Función para agrupar los materiales de un equipo en una lista de diccionarios JSON.
    """
    materials_list = []
    for _, row in group.iterrows():
        material_data = {
            "codigo": row['material_requerido_id'],
            "cantidad": int(row['cantidad_requerida']) # Aseguramos que la cantidad sea un entero
        }
        materials_list.append(material_data)
    # Convertir la lista de diccionarios a una cadena JSON
    return json.dumps(materials_list)

# Aplicar la función de agregación al DataFrame
# La función 'reset_index()' convierte el resultado de la agrupación (Serie) de nuevo en un DataFrame
df_nuevo = df.groupby('equipo_origen_id').apply(aggregate_materials).reset_index(name='materiales_requeridos')

# Mostrar las primeras filas del nuevo DataFrame para verificación
print("Primeras filas del DataFrame transformado:")
print(df_nuevo.head())

# Guardar el nuevo DataFrame en un archivo CSV con las dos columnas requeridas
# Usamos ';' como delimitador para mantener la consistencia
nombre_archivo_salida = "reglas_em_VRF_transformado.csv"
df_nuevo.to_csv(nombre_archivo_salida, sep=';', index=False)

print(f"\nArchivo guardado como: {nombre_archivo_salida}")