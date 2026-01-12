import sqlite3
import csv
import os
import json # Necesario para manejar la cadena JSON si fuera necesario

def cargar_reglas_em_sqlite(nombre_archivo_csv, ruta_bd, nombre_tabla, codificacion='utf-8'):
    """
    Carga datos masivamente desde un archivo CSV (reglas Equipo-Material)
    a una tabla en una base de datos SQLite.
    
    El archivo CSV tiene el formato: equipo_origen_id;materiales_requeridos (JSON)
    
    NOTA: El nombre de la columna FK en la tabla de Django/SQLite es 'equipo_origen_id',
          el valor es el string del modelo del equipo.
    """
    conexion = None
    cursor = None
    try:
        # 1. Conexión a la base de datos SQLite y habilitar Foreign Keys (opcional, pero buena práctica)
        conexion = sqlite3.connect(ruta_bd)
        cursor = conexion.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;") # Habilitar la verificación de FKs

        # 2. Leer el archivo CSV
        with open(nombre_archivo_csv, 'r', encoding=codificacion) as archivo_csv:
            # Usamos el delimitador ';'
            lector_csv = csv.reader(archivo_csv, delimiter=';')
            next(lector_csv)  # Omitir la primera fila (encabezados)

            datos_para_insertar = []
            for fila in lector_csv:
                # Asegurarse de que no haya espacios en blanco alrededor de los campos
                fila_limpia = [x.strip() for x in fila]
                
                # El orden de los campos en el CSV es:
                # [0] = equipo_origen_id (str)
                # [1] = materiales_requeridos (str JSON)
                
                # Para la inserción en SQLite:
                # El campo equipo_origen (ForeignKey con to_field='modelo') se mapea a 'equipo_origen_id'
                # El campo JSONField de Django se almacena como TEXT en SQLite.
                
                # La estructura para insertar será: (equipo_origen_id, materiales_requeridos_json_string)
                if len(fila_limpia) == 2:
                    datos_para_insertar.append((fila_limpia[0], fila_limpia[1]))
                else:
                    print(f"Advertencia: Fila con formato incorrecto omitida: {fila}")

            # 3. Preparar la consulta SQL para la inserción
            # Las columnas en la tabla 'app_reglaequipomaterial' son:
            # 1. equipo_origen_id (para el ForeignKey al campo 'modelo' del Equipo)
            # 2. materiales_requeridos (para el JSONField, que es TEXT en SQLite)
            
            # Usamos 2 placeholders
            placeholders = ', '.join(['?'] * 2)
            
            # La consulta de inserción
            # Importante: Reemplazar 'equipo_origen_id' por el nombre real de la columna FK
            consulta_insert = f"""
                INSERT INTO {nombre_tabla} (equipo_origen_id, materiales_requeridos) 
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
    nombre_archivo_csv='reglas_em_VRF_json.csv', # Cambiado al nuevo nombre de archivo
    ruta_bd=ruta_db_django,
    nombre_tabla='app_reglaequipomaterial' # Usamos el nombre de la tabla de reglas
)