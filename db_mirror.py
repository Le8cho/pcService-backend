# db_mirror.py
import os
import csv
from flask import current_app

# Ruta base para los archivos de texto que actúan como espejo de la BD
BASE_DIR = os.path.join(os.path.dirname(__file__), 'db_mirror_txt')

def get_mirror_path(table_name):
    """Construye la ruta al archivo de texto para una tabla dada."""
    # Asegurarse de que el nombre del archivo sea en mayúsculas y termine en .txt
    filename = f"{table_name.upper()}.txt"
    return os.path.join(BASE_DIR, filename)

def create_record(table_name, record_data, fields):
    """
    Añade un nuevo registro al archivo CSV correspondiente, escribiendo la cabecera si el archivo no existe.
    fields: lista de nombres de campos en orden.
    """
    try:
        filepath = get_mirror_path(table_name)
        file_exists = os.path.exists(filepath)
        current_app.logger.info(f"MIRROR: Intentando crear registro en {table_name}")
        current_app.logger.info(f"MIRROR: Datos a escribir: {record_data}")
        current_app.logger.info(f"MIRROR: Campos esperados: {fields}")
        current_app.logger.info(f"MIRROR: Ruta del archivo: {filepath}")
        current_app.logger.info(f"MIRROR: ¿Archivo existe? {file_exists}")
        
        with open(filepath, 'a', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            if not file_exists:
                current_app.logger.info(f"MIRROR: Escribiendo cabecera en {filepath}")
                writer.writeheader()
            
            # Preparar los datos para escribir
            row_data = {k: record_data.get(k, "") for k in fields}
            current_app.logger.info(f"MIRROR: Datos preparados para escribir: {row_data}")
            
            writer.writerow(row_data)
            current_app.logger.info(f"MIRROR: Registro creado exitosamente en {filepath}")
            
    except Exception as e:
        current_app.logger.error(f"MIRROR ERROR en create_record para tabla {table_name}: {e}")
        current_app.logger.error(f"MIRROR ERROR: Datos que causaron el error: {record_data}")
        current_app.logger.error(f"MIRROR ERROR: Campos esperados: {fields}")
        import traceback
        current_app.logger.error(f"MIRROR ERROR: Traceback completo: {traceback.format_exc()}")

def update_record(table_name, record_id, new_data, fields, id_field=None):
    """
    Actualiza un registro en el archivo CSV buscándolo por su campo id_field (por defecto el primero de fields).
    """
    try:
        filepath = get_mirror_path(table_name)
        if not os.path.exists(filepath):
            current_app.logger.warning(f"MIRROR WARNING: Archivo {filepath} no encontrado para actualizar. Creando nuevo registro en su lugar.")
            create_record(table_name, new_data, fields)
            return
        id_field = id_field or fields[0]
        updated_lines = []
        record_found = False
        with open(filepath, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get(id_field) == str(record_id):
                    updated_lines.append({k: new_data.get(k, "") for k in fields})
                    record_found = True
                else:
                    updated_lines.append(row)
        if not record_found:
            updated_lines.append({k: new_data.get(k, "") for k in fields})
            current_app.logger.info(f"MIRROR: Registro con {id_field}={record_id} no encontrado en {filepath}. Se añadió como nuevo.")
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(updated_lines)
        if record_found:
            current_app.logger.info(f"MIRROR: Registro con {id_field}={record_id} actualizado en {filepath}")
    except Exception as e:
        current_app.logger.error(f"MIRROR ERROR en update_record para tabla {table_name}: {e}")

def delete_record(table_name, record_id, fields, id_field=None):
    """
    Elimina un registro del archivo CSV buscándolo por su campo id_field (por defecto el primero de fields).
    """
    try:
        filepath = get_mirror_path(table_name)
        if not os.path.exists(filepath):
            current_app.logger.warning(f"MIRROR WARNING: Archivo {filepath} no encontrado para eliminar.")
            return
        id_field = id_field or fields[0]
        kept_lines = []
        record_deleted = False
        with open(filepath, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get(id_field) == str(record_id):
                    record_deleted = True
                    continue
                kept_lines.append(row)
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(kept_lines)
        if record_deleted:
            current_app.logger.info(f"MIRROR: Registro con {id_field}={record_id} eliminado de {filepath}")
        else:
            current_app.logger.warning(f"MIRROR WARNING: Registro con {id_field}={record_id} no encontrado para eliminar en {filepath}")
    except Exception as e:
        current_app.logger.error(f"MIRROR ERROR en delete_record para tabla {table_name}: {e}")
