# servicios_routes.py (VERSIÓN CORREGIDA Y DEFINITIVA)

from flask import g, jsonify, request, current_app
import oracledb
from datetime import datetime, date
from db_mirror import create_record, update_record, delete_record

# --- Funciones Helper (sin cambios) ---
def serialize_dates(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj

def parse_date_for_oracle(date_string):
    if not date_string: return None
    try:
        if isinstance(date_string, datetime):
            return date_string.date()
        elif isinstance(date_string, date):
            return date_string
        elif isinstance(date_string, str):
            return datetime.fromisoformat(date_string.replace('Z', '+00:00')).date()
    except Exception as e:
        current_app.logger.error(f"Error parsing date '{date_string}': {e}")
    return None

def get_db_connection():
    if 'db' not in g:
        import app
        return app.get_db()
    return g.db

# --- Lógica de Servicios ---

def get_servicios():
    """Obtener todos los servicios con información de cliente"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            o.id_operacion,
            'SV' || LPAD(o.id_operacion, 3, '0') as id_servicio,
            c.nombre || ' ' || c.apellido as cliente,
            s.detalle_servicio as detalle,
            s.tecnico_encargado,
            s.duracion_estimada,
            o.fecha,
            o.ingreso,
            o.egreso,
            o.id_cliente
        FROM operaciones o
        INNER JOIN servicios s ON o.id_operacion = s.id_operacion
        INNER JOIN clientes c ON o.id_cliente = c.id_cliente
        WHERE o.tipo_operacion = 'SERVICIO'
        ORDER BY o.fecha DESC
        """
        
        cursor.execute(query)
        columns = [col[0].lower() for col in cursor.description]
        rows = cursor.fetchall()
        
        servicios = [{col: serialize_dates(val) for col, val in zip(columns, row)} for row in rows]
        
        cursor.close()
        return jsonify(servicios)
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener servicios: {e}")
        return jsonify(error=str(e)), 500

# Definir campos de las tablas relevantes
OPERACIONES_FIELDS = ["ID_OPERACION", "ID_CLIENTE", "FECHA", "TIPO_OPERACION", "INGRESO", "EGRESO"]
SERVICIOS_FIELDS = ["ID_OPERACION", "DETALLE_SERVICIO", "TECNICO_ENCARGADO", "DURACION_ESTIMADA"]

def create_servicio():
    """Crear un nuevo servicio"""
    try:
        data = request.get_json()
        
        if not all(field in data for field in ['id_cliente', 'detalle']):
            return jsonify(error="Campos requeridos: id_cliente, detalle"), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # <<< CORRECCIÓN CLAVE: Asegurar que los valores numéricos sean siempre números >>>
        ingreso_valor = data.get('ingreso') or 0
        egreso_valor = data.get('egreso') or 0
        
        # 1. Insertar en OPERACIONES
        id_operacion_var = cursor.var(oracledb.NUMBER)
        cursor.execute("""
            INSERT INTO operaciones (id_cliente, fecha, tipo_operacion, ingreso, egreso)
            VALUES (:id_cliente, :fecha, 'SERVICIO', :ingreso, :egreso)
            RETURNING id_operacion INTO :id_operacion
        """, {
            'id_cliente': data['id_cliente'],
            'fecha': parse_date_for_oracle(data.get('fecha')) or date.today(),
            'ingreso': ingreso_valor, # Usar el valor seguro
            'egreso': egreso_valor,   # Usar el valor seguro
            'id_operacion': id_operacion_var
        })
        id_operacion = id_operacion_var.getvalue()[0]
        
        # 2. Insertar en SERVICIOS
        cursor.execute("""
            INSERT INTO servicios (id_operacion, detalle_servicio, tecnico_encargado, duracion_estimada)
            VALUES (:id_operacion, :detalle_servicio, :tecnico_encargado, :duracion_estimada)
        """, {
            'id_operacion': id_operacion,
            'detalle_servicio': data['detalle'],
            'tecnico_encargado': data.get('tecnico_encargado'),
            'duracion_estimada': data.get('duracion_estimada')
        })
        
        conn.commit()
        cursor.close()
        # MIRROR: Crear en OPERACIONES y SERVICIOS
        create_record('OPERACIONES', {
            "ID_OPERACION": id_operacion,
            "ID_CLIENTE": data['id_cliente'],
            "FECHA": (parse_date_for_oracle(data.get('fecha')) or date.today()),
            "TIPO_OPERACION": 'SERVICIO',
            "INGRESO": ingreso_valor,
            "EGRESO": egreso_valor
        }, OPERACIONES_FIELDS)
        create_record('SERVICIOS', {
            "ID_OPERACION": id_operacion,
            "DETALLE_SERVICIO": data['detalle'],
            "TECNICO_ENCARGADO": data.get('tecnico_encargado'),
            "DURACION_ESTIMADA": data.get('duracion_estimada')
        }, SERVICIOS_FIELDS)
        return jsonify({'message': 'Servicio creado exitosamente', 'id_operacion': id_operacion}), 201
        
    except Exception as e:
        if 'conn' in locals() and conn: conn.rollback()
        current_app.logger.error(f"Error al crear servicio: {e}")
        return jsonify(error=str(e)), 500

def update_servicio(id):
    """Actualizar un servicio existente"""
    try:
        data = request.get_json()
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Actualizar OPERACIONES
        cursor.execute("""
            UPDATE operaciones SET 
                fecha = COALESCE(:fecha, fecha), 
                ingreso = COALESCE(:ingreso, ingreso), 
                egreso = COALESCE(:egreso, egreso)
            WHERE id_operacion = :id AND tipo_operacion = 'SERVICIO'
        """, {
            'id': id,
            'fecha': parse_date_for_oracle(data.get('fecha')),
            'ingreso': data.get('ingreso'), # COALESCE maneja bien los None aquí
            'egreso': data.get('egreso')
        })
        
        # 2. Actualizar SERVICIOS de forma robusta
        cursor.execute("""
            UPDATE servicios SET 
                detalle_servicio = COALESCE(:detalle_servicio, detalle_servicio),
                tecnico_encargado = COALESCE(:tecnico_encargado, tecnico_encargado),
                duracion_estimada = COALESCE(:duracion_estimada, duracion_estimada)
            WHERE id_operacion = :id
        """, {
            'id': id, 
            'detalle_servicio': data.get('detalle'),
            'tecnico_encargado': data.get('tecnico_encargado'),
            'duracion_estimada': data.get('duracion_estimada')
        })
            
        conn.commit()
        cursor.close()
        # MIRROR: Actualizar en OPERACIONES y SERVICIOS
        update_record('OPERACIONES', id, {
            "ID_OPERACION": id,
            "FECHA": parse_date_for_oracle(data.get('fecha')),
            "INGRESO": data.get('ingreso'),
            "EGRESO": data.get('egreso')
        }, OPERACIONES_FIELDS)
        update_record('SERVICIOS', id, {
            "ID_OPERACION": id,
            "DETALLE_SERVICIO": data.get('detalle'),
            "TECNICO_ENCARGADO": data.get('tecnico_encargado'),
            "DURACION_ESTIMADA": data.get('duracion_estimada')
        }, SERVICIOS_FIELDS)
        return jsonify(message="Servicio actualizado exitosamente")
        
    except Exception as e:
        if 'conn' in locals() and conn: conn.rollback()
        current_app.logger.error(f"Error al actualizar servicio {id}: {e}")
        return jsonify(error=str(e)), 500

# El resto de las funciones (delete, search, get_clientes, register_servicios_routes)
# pueden permanecer como en la respuesta anterior.
# Se incluyen aquí por completitud.

def delete_servicio(id):
    """Eliminar un servicio"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM servicios WHERE id_operacion = :id", {'id': id})
        cursor.execute("DELETE FROM operaciones WHERE id_operacion = :id AND tipo_operacion = 'SERVICIO'", {'id': id})
        if cursor.rowcount == 0:
            return jsonify(error="Servicio no encontrado"), 404
        conn.commit()
        cursor.close()
        # MIRROR: Eliminar en SERVICIOS y OPERACIONES
        delete_record('SERVICIOS', id, SERVICIOS_FIELDS)
        delete_record('OPERACIONES', id, OPERACIONES_FIELDS)
        return jsonify(message="Servicio eliminado exitosamente")
    except Exception as e:
        if 'conn' in locals() and conn: conn.rollback()
        current_app.logger.error(f"Error al eliminar servicio {id}: {e}")
        return jsonify(error=str(e)), 500

def search_servicios():
    """Buscar servicios por un término de búsqueda"""
    try:
        search_term = request.args.get('search', '').strip()
        if not search_term: return jsonify([])
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
        SELECT 
            o.id_operacion, 'SV' || LPAD(o.id_operacion, 3, '0') as id_servicio,
            c.nombre || ' ' || c.apellido as cliente, s.detalle_servicio as detalle,
            s.tecnico_encargado, s.duracion_estimada,
            o.fecha, o.ingreso, o.egreso, o.id_cliente
        FROM operaciones o
        INNER JOIN servicios s ON o.id_operacion = s.id_operacion
        INNER JOIN clientes c ON o.id_cliente = c.id_cliente
        WHERE o.tipo_operacion = 'SERVICIO'
        AND (
            UPPER(c.nombre || ' ' || c.apellido) LIKE UPPER(:search) OR
            UPPER(s.detalle_servicio) LIKE UPPER(:search) OR
            UPPER(s.tecnico_encargado) LIKE UPPER(:search) OR
            'SV' || LPAD(o.id_operacion, 3, '0') LIKE UPPER(:search)
        )
        ORDER BY o.fecha DESC
        """
        cursor.execute(query, {'search': f"%{search_term}%"})
        columns = [col[0].lower() for col in cursor.description]
        servicios = [{col: serialize_dates(val) for col, val in zip(columns, row)} for row in cursor.fetchall()]
        cursor.close()
        return jsonify(servicios)
    except Exception as e:
        current_app.logger.error(f"Error al buscar servicios: {e}")
        return jsonify(error=str(e)), 500

def get_clientesServicio():
    """Obtener todos los clientes (función auxiliar)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id_cliente, nombre, apellido FROM clientes ORDER BY nombre, apellido")
        columns = [col[0].lower() for col in cursor.description]
        clientes = [{col: val for col, val in zip(columns, row)} for row in cursor.fetchall()]
        cursor.close()
        return jsonify(clientes)
    except Exception as e:
        current_app.logger.error(f"Error al obtener clientes: {e}")
        return jsonify(error=str(e)), 500


def register_servicios_routes(app):
    """Registra todas las rutas de servicios en la aplicación Flask"""
    app.route('/api/servicios', methods=['GET'])(get_servicios)
    app.route('/api/servicios', methods=['POST'])(create_servicio)
    app.route('/api/servicios/<int:id>', methods=['PUT'])(update_servicio)
    app.route('/api/servicios/<int:id>', methods=['DELETE'])(delete_servicio)
    app.route('/api/servicios/search', methods=['GET'])(search_servicios)
    app.route('/api/clientesServicios', methods=['GET'])(get_clientesServicio)
