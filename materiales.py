import sqlite3
import csv
import os

def cargar_datos_masivos_sqlite(nombre_archivo_csv, ruta_bd, nombre_tabla, codificacion='utf-8'):
    """
    Carga datos masivamente desde un archivo CSV a una tabla en una base de datos SQLite.
    """
    conexion = None
    cursor = None
    try:
        # Conexión a la base de datos SQLite
        conexion = sqlite3.connect(ruta_bd)
        cursor = conexion.cursor()

        with open(nombre_archivo_csv, 'r', encoding=codificacion) as archivo_csv:
            lector_csv = csv.reader(archivo_csv, delimiter=';')
            next(lector_csv)  # Omitir la primera fila (encabezados)

            datos_para_insertar = []
            for fila in lector_csv:
                # Modificación clave: Reemplazar la coma por un punto en el campo de costo_unitario
                # Se asume que la columna 'costo_unitario' es la quinta columna (índice 4).
                fila[5] = fila[5].replace(',', '.')
                
                # Se limpia el espacio en blanco al final de algunos campos.
                fila = [x.strip() for x in fila]
                fila.append(0)  # Agregar stock inicial como 0
                datos_para_insertar.append(fila)

            # Prepara la consulta SQL para la inserción
            placeholders = ', '.join(['?'] * len(datos_para_insertar[0]))
            
            # La consulta de inserción especifica las 5 columnas del CSV.
            consulta_insert = f"INSERT INTO {nombre_tabla} (codigo, nombre, unidad, familia, sistema, costo_unitario, stock) VALUES ({placeholders})"
            
            # Usar `executemany` para una carga masiva eficiente
            cursor.executemany(consulta_insert, datos_para_insertar)

        # Confirma los cambios
        conexion.commit()
        print(f"Datos {nombre_archivo_csv} cargados correctamente.")

    except (Exception, sqlite3.Error) as error:
        print("Error al cargar datos:", error)
        if conexion:
            conexion.rollback()
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()


ruta_db_django = 'db.sqlite3'
cargar_datos_masivos_sqlite(
    nombre_archivo_csv='materiales_VRF.csv',
    ruta_bd=ruta_db_django,
    nombre_tabla='app_material'
)

cargar_datos_masivos_sqlite(
    nombre_archivo_csv='materiales_CHW.csv',
    ruta_bd=ruta_db_django,
    nombre_tabla='app_material'
)