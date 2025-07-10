# mantenimientos_routes.py - VERSIÓN CORREGIDA
from flask import g, jsonify, request, current_app
import oracledb
from datetime import datetime, date
from db_mirror import create_record, update_record, delete_record

# Mover la función parse_date_for_oracle antes de su primer uso y asegurar que solo haya una versión.
def parse_date_for_oracle(date_string):
    """Convertir string de fecha a formato que Oracle entiende"""
    if not date_string:
        return None
    try:
        # Si viene como string ISO (YYYY-MM-DD)
        if isinstance(date_string, str):
            # Intentar varios formatos
            for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%S']:
                try:
                    return datetime.strptime(date_string, fmt).date()
                except ValueError:
                    continue
            # Si no funciona ningún formato, intentar parse directo
            return datetime.fromisoformat(date_string.replace('Z', '+00:00')).date()
        elif isinstance(date_string, date):
            return date_string
        elif isinstance(date_string, datetime):
            return date_string.date()
    except Exception as e:
        current_app.logger.error(f"Error parsing date '{date_string}': {e}")
        return None
    return None

OPERACIONES_FIELDS = ["ID_OPERACION", "ID_CLIENTE", "FECHA", "TIPO_OPERACION", "INGRESO", "EGRESO"]
MANTENIMIENTOS_FIELDS = ["ID_OPERACION", "DESCRIPCION", "FRECUENCIA", "PROX_MANTENIMIENTO", "TIPO_MANTENIMIENTO"]
MANTENIMIENTO_DISPOSITIVO_FIELDS = ["ID_OPERACION", "ID_DISPOSITIVO"]

def get_db_connection():
    """Obtener conexión de la base de datos usando la función de app.py"""
    if 'db' not in g:
        # Importar la función get_db del módulo principal
        import app
        return app.get_db()
    return g.db

def serialize_dates(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj

def get_mantenimientos():
    """Obtener todos los mantenimientos con información de cliente"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            o.id_operacion,
            'MP' || LPAD(o.id_operacion, 3, '0') as mant_prev,
            'CL' || LPAD(c.id_cliente, 3, '0') as cod_cliente,
            c.nombre || ' ' || c.apellido as nombre_cliente,
            o.fecha,
            o.ingreso,
            o.egreso,
            m.descripcion as equipos,
            m.frecuencia,
            m.prox_mantenimiento,
            m.tipo_mantenimiento,
            o.id_cliente
        FROM operaciones o
        INNER JOIN mantenimientos m ON o.id_operacion = m.id_operacion
        INNER JOIN clientes c ON o.id_cliente = c.id_cliente
        WHERE o.tipo_operacion = 'MANTENIMIENTO'
        ORDER BY o.fecha DESC
        """
        
        cursor.execute(query)
        columns = [col[0].lower() for col in cursor.description]
        rows = cursor.fetchall()
        
        mantenimientos = []
        for row in rows:
            mantenimiento = {col: serialize_dates(val) for col, val in zip(columns, row)}
            mantenimientos.append(mantenimiento)
        
        cursor.close()
        return jsonify(mantenimientos)
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener mantenimientos: {e}")
        return jsonify(error=str(e)), 500

def get_mantenimiento_by_id(id):
    """Obtener un mantenimiento específico por ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            o.id_operacion,
            'MP' || LPAD(o.id_operacion, 3, '0') as mant_prev,
            'CL' || LPAD(c.id_cliente, 3, '0') as cod_cliente,
            c.nombre || ' ' || c.apellido as nombre_cliente,
            o.fecha,
            o.ingreso,
            o.egreso,
            m.descripcion as equipos,
            m.frecuencia,
            m.prox_mantenimiento,
            m.tipo_mantenimiento,
            o.id_cliente
        FROM operaciones o
        INNER JOIN mantenimientos m ON o.id_operacion = m.id_operacion
        INNER JOIN clientes c ON o.id_cliente = c.id_cliente
        WHERE o.id_operacion = :id AND o.tipo_operacion = 'MANTENIMIENTO'
        """
        
        cursor.execute(query, {'id': id})
        columns = [col[0].lower() for col in cursor.description]
        row = cursor.fetchone()
        
        if row:
            mantenimiento = {col: serialize_dates(val) for col, val in zip(columns, row)}
            cursor.close()
            return jsonify(mantenimiento)
        else:
            cursor.close()
            return jsonify(error="Mantenimiento no encontrado"), 404
            
    except Exception as e:
        current_app.logger.error(f"Error al obtener mantenimiento {id}: {e}")
        return jsonify(error=str(e)), 500

def create_mantenimiento():
    """Crear un nuevo mantenimiento"""
    try:
        data = request.get_json()
        current_app.logger.info(f"[MANTENIMIENTO] Datos recibidos: {data}")
        # Validar datos requeridos
        required_fields = ['id_cliente', 'descripcion', 'frecuencia']
        for field in required_fields:
            if field not in data:
                current_app.logger.warning(f"[MANTENIMIENTO] Falta campo requerido: {field}")
                return jsonify(error=f"Campo requerido: {field}"), 400
        conn = get_db_connection()
        cursor = conn.cursor()
        # Procesar fechas
        fecha_mantenimiento = parse_date_for_oracle(data.get('fecha')) or date.today()
        prox_mantenimiento = parse_date_for_oracle(data.get('prox_mantenimiento'))
        current_app.logger.info(f"[MANTENIMIENTO] Fecha mantenimiento: {fecha_mantenimiento}, Próx: {prox_mantenimiento}")
        # Insertar en tabla OPERACIONES y obtener el ID generado de forma segura
        insert_operacion_sql = """
            INSERT INTO operaciones (id_cliente, fecha, tipo_operacion, ingreso, egreso)
            VALUES (:id_cliente, :fecha, 'MANTENIMIENTO', :ingreso, :egreso)
            RETURNING id_operacion INTO :id_operacion
        """
        id_operacion_var = cursor.var(int)
        current_app.logger.info(f"[MANTENIMIENTO] Insertando en OPERACIONES (RETURNING): id_cliente={data['id_cliente']}, fecha={fecha_mantenimiento}, ingreso={data.get('ingreso')}, egreso={data.get('egreso')}")
        cursor.execute(insert_operacion_sql, {
            'id_cliente': data['id_cliente'],
            'fecha': fecha_mantenimiento,
            'ingreso': data.get('ingreso'),
            'egreso': data.get('egreso'),
            'id_operacion': id_operacion_var
        })
        id_operacion = id_operacion_var.getvalue()[0]
        current_app.logger.info(f"[MANTENIMIENTO] id_operacion generado: {id_operacion}")
        # Insertar en tabla MANTENIMIENTOS
        insert_mantenimiento_sql = """
            INSERT INTO mantenimientos (id_operacion, descripcion, frecuencia, prox_mantenimiento, tipo_mantenimiento)
            VALUES (:id_operacion, :descripcion, :frecuencia, :prox_mantenimiento, :tipo_mantenimiento)
        """
        current_app.logger.info(f"[MANTENIMIENTO] Insertando en MANTENIMIENTOS: id_operacion={id_operacion}, descripcion={data['descripcion']}, frecuencia={data['frecuencia']}, prox_mantenimiento={prox_mantenimiento}, tipo_mantenimiento={data.get('tipo_mantenimiento', 'PREVENTIVO')}")
        cursor.execute(insert_mantenimiento_sql, {
            'id_operacion': id_operacion,
            'descripcion': data['descripcion'],
            'frecuencia': data['frecuencia'],
            'prox_mantenimiento': prox_mantenimiento,
            'tipo_mantenimiento': data.get('tipo_mantenimiento', 'PREVENTIVO')
        })
        # Si hay id_dispositivo, insertar en mantenimiento_dispositivo y reflejar en mirror
        id_dispositivo = data.get('id_dispositivo')
        if id_dispositivo is not None:
            current_app.logger.info(f"[MANTENIMIENTO] Insertando en MANTENIMIENTO_DISPOSITIVO: id_operacion={id_operacion}, id_dispositivo={id_dispositivo}")
            insert_mant_disp_sql = """
                INSERT INTO mantenimiento_dispositivo (id_operacion, id_dispositivo)
                VALUES (:id_operacion, :id_dispositivo)
            """
            cursor.execute(insert_mant_disp_sql, {
                'id_operacion': id_operacion,
                'id_dispositivo': id_dispositivo
            })
            # MIRROR: Crear en mantenimiento_dispositivo
            create_record('MANTENIMIENTO_DISPOSITIVO', {
                "ID_OPERACION": id_operacion,
                "ID_DISPOSITIVO": id_dispositivo
            }, MANTENIMIENTO_DISPOSITIVO_FIELDS)
        conn.commit()
        cursor.close()
        # MIRROR: Crear en OPERACIONES y MANTENIMIENTOS
        create_record('OPERACIONES', {
            "ID_OPERACION": id_operacion,
            "ID_CLIENTE": data['id_cliente'],
            "FECHA": fecha_mantenimiento,
            "TIPO_OPERACION": 'MANTENIMIENTO',
            "INGRESO": data.get('ingreso'),
            "EGRESO": data.get('egreso')
        }, OPERACIONES_FIELDS)
        create_record('MANTENIMIENTOS', {
            "ID_OPERACION": id_operacion,
            "DESCRIPCION": data['descripcion'],
            "FRECUENCIA": data['frecuencia'],
            "PROX_MANTENIMIENTO": prox_mantenimiento,
            "TIPO_MANTENIMIENTO": data.get('tipo_mantenimiento', 'PREVENTIVO')
        }, MANTENIMIENTOS_FIELDS)
        current_app.logger.info(f"[MANTENIMIENTO] Mantenimiento creado exitosamente: id_operacion={id_operacion}")
        return jsonify({
            'message': 'Mantenimiento creado exitosamente',
            'id_operacion': id_operacion
        }), 201
    except Exception as e:
        if 'conn' in locals() and conn:
            conn.rollback()
        current_app.logger.error(f"Error al crear mantenimiento: {e}")
        return jsonify(error=str(e)), 500

def update_mantenimiento(id):
    """Actualizar un mantenimiento existente"""
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Procesar fechas si están presentes
        fecha_mantenimiento = parse_date_for_oracle(data.get('fecha')) if data.get('fecha') else None
        prox_mantenimiento = parse_date_for_oracle(data.get('prox_mantenimiento')) if data.get('prox_mantenimiento') else None
        
        # Actualizar tabla OPERACIONES solo si hay campos para actualizar
        if any(key in data for key in ['fecha', 'ingreso', 'egreso']):
            update_operacion_sql = """
                UPDATE operaciones 
                SET fecha = COALESCE(:fecha, fecha), 
                    ingreso = COALESCE(:ingreso, ingreso), 
                    egreso = COALESCE(:egreso, egreso)
                WHERE id_operacion = :id AND tipo_operacion = 'MANTENIMIENTO'
            """
            
            cursor.execute(update_operacion_sql, {
                'id': id,
                'fecha': fecha_mantenimiento,
                'ingreso': data.get('ingreso'),
                'egreso': data.get('egreso')
            })
        
        # Actualizar tabla MANTENIMIENTOS
        update_mantenimiento_sql = """
            UPDATE mantenimientos 
            SET descripcion = COALESCE(:descripcion, descripcion), 
                frecuencia = COALESCE(:frecuencia, frecuencia), 
                prox_mantenimiento = COALESCE(:prox_mantenimiento, prox_mantenimiento),
                tipo_mantenimiento = COALESCE(:tipo_mantenimiento, tipo_mantenimiento)
            WHERE id_operacion = :id
        """
        
        cursor.execute(update_mantenimiento_sql, {
            'id': id,
            'descripcion': data.get('descripcion'),
            'frecuencia': data.get('frecuencia'),
            'prox_mantenimiento': prox_mantenimiento,
            'tipo_mantenimiento': data.get('tipo_mantenimiento')
        })
        
        if cursor.rowcount == 0:
            return jsonify(error="Mantenimiento no encontrado"), 404
            
        # Si hay id_dispositivo, actualizar en mantenimiento_dispositivo y en el mirror
        id_dispositivo = data.get('id_dispositivo')
        if id_dispositivo is not None:
            # Actualizar o insertar según corresponda
            cursor.execute("SELECT COUNT(*) FROM mantenimiento_dispositivo WHERE id_operacion = :id", {'id': id})
            existe = cursor.fetchone()[0]
            if existe:
                update_mant_disp_sql = """
                    UPDATE mantenimiento_dispositivo
                    SET id_dispositivo = :id_dispositivo
                    WHERE id_operacion = :id_operacion
                """
                cursor.execute(update_mant_disp_sql, {
                    'id_operacion': id,
                    'id_dispositivo': id_dispositivo
                })
                # MIRROR: Actualizar en mantenimiento_dispositivo
                update_record('MANTENIMIENTO_DISPOSITIVO', id, {
                    "ID_OPERACION": id,
                    "ID_DISPOSITIVO": id_dispositivo
                }, MANTENIMIENTO_DISPOSITIVO_FIELDS)
            else:
                insert_mant_disp_sql = """
                    INSERT INTO mantenimiento_dispositivo (id_operacion, id_dispositivo)
                    VALUES (:id_operacion, :id_dispositivo)
                """
                cursor.execute(insert_mant_disp_sql, {
                    'id_operacion': id,
                    'id_dispositivo': id_dispositivo
                })
                # MIRROR: Crear en mantenimiento_dispositivo
                create_record('MANTENIMIENTO_DISPOSITIVO', {
                    "ID_OPERACION": id,
                    "ID_DISPOSITIVO": id_dispositivo
                }, MANTENIMIENTO_DISPOSITIVO_FIELDS)
        
        conn.commit()
        cursor.close()
        
        # MIRROR: Actualizar en OPERACIONES y MANTENIMIENTOS
        update_record('OPERACIONES', id, {
            "ID_OPERACION": id,
            "FECHA": fecha_mantenimiento,
            "INGRESO": data.get('ingreso'),
            "EGRESO": data.get('egreso')
        }, OPERACIONES_FIELDS)
        update_record('MANTENIMIENTOS', id, {
            "ID_OPERACION": id,
            "DESCRIPCION": data.get('descripcion'),
            "FRECUENCIA": data.get('frecuencia'),
            "PROX_MANTENIMIENTO": prox_mantenimiento,
            "TIPO_MANTENIMIENTO": data.get('tipo_mantenimiento')
        }, MANTENIMIENTOS_FIELDS)
        
        return jsonify(message="Mantenimiento actualizado exitosamente")
        
    except Exception as e:
        if conn:
            conn.rollback()
        current_app.logger.error(f"Error al actualizar mantenimiento {id}: {e}")
        return jsonify(error=str(e)), 500

def delete_mantenimiento(id):
    """Eliminar un mantenimiento"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Primero eliminar de la tabla MANTENIMIENTOS (por FK constraint)
        cursor.execute("DELETE FROM mantenimientos WHERE id_operacion = :id", {'id': id})
        
        # Eliminar de mantenimiento_dispositivo si existe
        cursor.execute("DELETE FROM mantenimiento_dispositivo WHERE id_operacion = :id", {'id': id})
        # MIRROR: Eliminar en mantenimiento_dispositivo
        delete_record('MANTENIMIENTO_DISPOSITIVO', id, MANTENIMIENTO_DISPOSITIVO_FIELDS)
        
        # Luego eliminar de la tabla OPERACIONES
        cursor.execute("DELETE FROM operaciones WHERE id_operacion = :id AND tipo_operacion = 'MANTENIMIENTO'", {'id': id})
        
        if cursor.rowcount == 0:
            return jsonify(error="Mantenimiento no encontrado"), 404
            
        conn.commit()
        cursor.close()
        
        # MIRROR: Eliminar en MANTENIMIENTOS y OPERACIONES
        delete_record('MANTENIMIENTOS', id, MANTENIMIENTOS_FIELDS)
        delete_record('OPERACIONES', id, OPERACIONES_FIELDS)
        
        return jsonify(message="Mantenimiento eliminado exitosamente")
        
    except Exception as e:
        current_app.logger.error(f"Error al eliminar mantenimiento {id}: {e}")
        return jsonify(error=str(e)), 500

def search_mantenimientos():
    """Buscar mantenimientos por término"""
    try:
        search_term = request.args.get('search', '').strip()
        
        if not search_term:
            return jsonify([])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            o.id_operacion,
            'MP' || LPAD(o.id_operacion, 3, '0') as mant_prev,
            'CL' || LPAD(c.id_cliente, 3, '0') as cod_cliente,
            c.nombre || ' ' || c.apellido as nombre_cliente,
            o.fecha,
            o.ingreso,
            o.egreso,
            m.descripcion as equipos,
            m.frecuencia,
            m.prox_mantenimiento,
            m.tipo_mantenimiento,
            o.id_cliente
        FROM operaciones o
        INNER JOIN mantenimientos m ON o.id_operacion = m.id_operacion
        INNER JOIN clientes c ON o.id_cliente = c.id_cliente
        WHERE o.tipo_operacion = 'MANTENIMIENTO'
        AND (
            UPPER(c.nombre) LIKE UPPER(:search) OR
            UPPER(c.apellido) LIKE UPPER(:search) OR
            UPPER(m.descripcion) LIKE UPPER(:search) OR
            'MP' || LPAD(o.id_operacion, 3, '0') LIKE UPPER(:search) OR
            'CL' || LPAD(c.id_cliente, 3, '0') LIKE UPPER(:search)
        )
        ORDER BY o.fecha DESC
        """
        
        search_param = f"%{search_term}%"
        cursor.execute(query, {'search': search_param})
        columns = [col[0].lower() for col in cursor.description]
        rows = cursor.fetchall()
        
        mantenimientos = []
        for row in rows:
            mantenimiento = {col: serialize_dates(val) for col, val in zip(columns, row)}
            mantenimientos.append(mantenimiento)
        
        cursor.close()
        return jsonify(mantenimientos)
        
    except Exception as e:
        current_app.logger.error(f"Error al buscar mantenimientos: {e}")
        return jsonify(error=str(e)), 500

def get_mantenimientos_proximos_vencer():
    """Obtener mantenimientos próximos a vencer"""
    try:
        dias = request.args.get('dias', 7, type=int)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            o.id_operacion,
            'MP' || LPAD(o.id_operacion, 3, '0') as mant_prev,
            'CL' || LPAD(c.id_cliente, 3, '0') as cod_cliente,
            c.nombre || ' ' || c.apellido as nombre_cliente,
            o.fecha,
            o.ingreso,
            o.egreso,
            m.descripcion as equipos,
            m.frecuencia,
            m.prox_mantenimiento,
            m.tipo_mantenimiento,
            o.id_cliente
        FROM operaciones o
        INNER JOIN mantenimientos m ON o.id_operacion = m.id_operacion
        INNER JOIN clientes c ON o.id_cliente = c.id_cliente
        WHERE o.tipo_operacion = 'MANTENIMIENTO'
        AND m.prox_mantenimiento IS NOT NULL
        AND m.prox_mantenimiento <= SYSDATE + :dias
        ORDER BY m.prox_mantenimiento ASC
        """
        
        cursor.execute(query, {'dias': dias})
        columns = [col[0].lower() for col in cursor.description]
        rows = cursor.fetchall()
        
        mantenimientos = []
        for row in rows:
            mantenimiento = {col: serialize_dates(val) for col, val in zip(columns, row)}
            mantenimientos.append(mantenimiento)
        
        cursor.close()
        return jsonify(mantenimientos)
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener mantenimientos próximos a vencer: {e}")
        return jsonify(error=str(e)), 500

def get_clientesMantenimiento():
    """Obtener todos los clientes"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id_cliente, nombre, apellido, celular, direccion, correo 
            FROM clientes 
            ORDER BY nombre, apellido
        """)
        
        columns = [col[0].lower() for col in cursor.description]
        rows = cursor.fetchall()
        
        clientes = []
        for row in rows:
            cliente = {col: val for col, val in zip(columns, row)}
            clientes.append(cliente)
        
        cursor.close()
        return jsonify(clientes)
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener clientes: {e}")
        return jsonify(error=str(e)), 500

def get_dispositivos_by_cliente(cliente_id):
    """Obtener dispositivos de un cliente específico"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id_dispositivo, tipo_dispositivo, marca, modelo 
            FROM dispositivos 
            WHERE id_cliente = :cliente_id
            ORDER BY tipo_dispositivo, marca, modelo
        """, {'cliente_id': cliente_id})
        
        columns = [col[0].lower() for col in cursor.description]
        rows = cursor.fetchall()
        
        dispositivos = []
        for row in rows:
            dispositivo = {col: val for col, val in zip(columns, row)}
            dispositivos.append(dispositivo)
        
        cursor.close()
        return jsonify(dispositivos)
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener dispositivos del cliente {cliente_id}: {e}")
        return jsonify(error=str(e)), 500

def register_mantenimientos_routes(app):
    """Registra todas las rutas de mantenimientos en la aplicación Flask"""
    
    # Rutas CRUD
    app.route('/api/mantenimientos', methods=['GET'])(get_mantenimientos)
    app.route('/api/mantenimientos/<int:id>', methods=['GET'])(get_mantenimiento_by_id)
    app.route('/api/mantenimientos', methods=['POST'])(create_mantenimiento)
    app.route('/api/mantenimientos/<int:id>', methods=['PUT'])(update_mantenimiento)
    app.route('/api/mantenimientos/<int:id>', methods=['DELETE'])(delete_mantenimiento)
    
    # Rutas de búsqueda y filtros
    app.route('/api/mantenimientos/search', methods=['GET'])(search_mantenimientos)
    app.route('/api/mantenimientos/proximos-vencer', methods=['GET'])(get_mantenimientos_proximos_vencer)
    
    # Rutas auxiliares
    app.route('/api/clientesMantenimiento', methods=['GET'])(get_clientesMantenimiento)
    app.route('/api/dispositivo/cliente/<int:cliente_id>', methods=['GET'])(get_dispositivos_by_cliente)