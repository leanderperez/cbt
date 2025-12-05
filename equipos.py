import sqlite3
import csv
import os

def cargar_equipos_sqlite(nombre_archivo_csv, ruta_bd, nombre_tabla, codificacion='utf-8'):
    """
    Carga datos masivamente desde un archivo CSV (Equipos)
    a una tabla en una base de datos SQLite.
    
    El archivo CSV se espera con el formato: 
    nombre;modelo;descripcion;sistema;capacidad;mca;mfa
    """
    conexion = None
    cursor = None
    try:
        # 1. Conexión a la base de datos SQLite
        conexion = sqlite3.connect(ruta_bd)
        cursor = conexion.cursor()

        # 2. Leer el archivo CSV
        with open(nombre_archivo_csv, 'r', encoding=codificacion) as archivo_csv:
            # Usamos el delimitador ';' como en tu archivo de equipos
            lector_csv = csv.reader(archivo_csv, delimiter=';')
            next(lector_csv)  # Omitir la primera fila (encabezados)

            datos_para_insertar = []
            for fila in lector_csv:
                # Asegurarse de que no haya espacios en blanco alrededor de los campos
                # y convertir el separador decimal de ',' a '.' para 'capacidad', 'mca', 'mfa' si es necesario
                # Asumimos que los datos del CSV ya están en el orden correcto.
                fila_limpia = [x.strip().replace(',', '.') for x in fila]
                
                # El orden de los campos esperados para la inserción es:
                # [0] nombre, [1] modelo, [2] descripcion, [3] sistema, 
                # [4] capacidad, [5] mca, [6] mfa
                datos_para_insertar.append(fila_limpia)

            # 3. Preparar la consulta SQL para la inserción
            # El CSV tiene 7 columnas.
            num_columnas = 7
            placeholders = ', '.join(['?'] * num_columnas)
            
            # **Importante:** Ajusta los nombres de las columnas (`nombre`, `modelo`, etc.)
            # según el esquema real de tu tabla `app_equipo`.
            columnas = "nombre, modelo, descripcion, sistema, capacidad, mca, mfa"
            
            consulta_insert = f"""
                INSERT INTO {nombre_tabla} ({columnas}) 
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

# Llama a la función para cargar los equipos
cargar_equipos_sqlite(
    nombre_archivo_csv='equipos.csv',
    ruta_bd=ruta_db_django,
    nombre_tabla='app_equipo' # Nombre de la tabla de equipos en Django
)