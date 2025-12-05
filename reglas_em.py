import sqlite3
import csv
import os

def cargar_reglas_em_sqlite(nombre_archivo_csv, ruta_bd, nombre_tabla, codificacion='utf-8'):
    """
    Carga datos masivamente desde un archivo CSV (reglas Equipo-Material)
    a una tabla en una base de datos SQLite.
    
    El archivo CSV tiene el formato: cantidad;equipo_origen_id;material_requerido_id
    """
    conexion = None
    cursor = None
    try:
        # 1. Conexión a la base de datos SQLite
        conexion = sqlite3.connect(ruta_bd)
        cursor = conexion.cursor()

        # 2. Leer el archivo CSV
        with open(nombre_archivo_csv, 'r', encoding=codificacion) as archivo_csv:
            # Usamos el delimitador ';' como en tu archivo de reglas
            lector_csv = csv.reader(archivo_csv, delimiter=';')
            next(lector_csv)  # Omitir la primera fila (encabezados)

            datos_para_insertar = []
            for fila in lector_csv:
                # Asegurarse de que no haya espacios en blanco alrededor de los campos
                fila_limpia = [x.strip() for x in fila]
                
                # El orden en la lista limpia es:
                # [0] = cantidad (int/str)
                # [1] = equipo_origen_id (str)
                # [2] = material_requerido_id (str)
                
                # Si 'cantidad' viene como cadena, convertirla a entero o flotante si es necesario,
                # aunque para este caso simple, SQLite suele manejar la inserción de texto en campos numéricos.
                # Aquí simplemente insertamos la lista de 3 elementos tal cual.
                datos_para_insertar.append(fila_limpia)

            # 3. Preparar la consulta SQL para la inserción
            # La tabla de reglas debe tener 3 columnas para estos datos:
            # cantidad, equipo_origen_id, material_requerido_id
            
            # Usamos 3 placeholders, uno para cada columna
            placeholders = ', '.join(['?'] * 3)
            
            # La consulta de inserción
            consulta_insert = f"""
                INSERT INTO {nombre_tabla} (cantidad_requerida, equipo_origen_id, material_requerido_id) 
                VALUES ({placeholders})
            """
            
            # 4. Usar `executemany` para una carga masiva eficiente
            cursor.executemany(consulta_insert, datos_para_insertar)

        # 5. Confirma los cambios
        conexion.commit()
        print(f"Datos del archivo '{nombre_archivo_csv}' cargados correctamente en la tabla '{nombre_tabla}'.")

    except (Exception, sqlite3.Error) as error:
        print(f"Error al cargar datos del archivo {nombre_archivo_csv}:", error)
        if conexion:
            conexion.rollback()
    finally:
        # 6. Cerrar recursos
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()


# --- Ejecución del Script ---

ruta_db_django = 'db.sqlite3' # Asegúrate de que esta ruta sea correcta para tu proyecto Django

# Llama a la función para cargar las reglas VRF
cargar_reglas_em_sqlite(
    nombre_archivo_csv='reglas_em_VRF.csv',
    ruta_bd=ruta_db_django,
    nombre_tabla='app_reglaequipomaterial' # Usamos el nombre de la tabla de reglas
)

# Si tuvieras más archivos de reglas, podrías añadirlos aquí:
# cargar_reglas_em_sqlite(
#     nombre_archivo_csv='reglas_em_CHW.csv',
#     ruta_bd=ruta_db_django,
#     nombre_tabla='app_reglaequipomaterial'
# )