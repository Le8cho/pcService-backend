from flask import Blueprint, request, jsonify, current_app
from db import get_db  # Cambia la importación aquí

clientes_bp = Blueprint('clientes', __name__)

# Obtener todos los clientes
@clientes_bp.route('/', methods=['GET'])
def get_clientes():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ID_CLIENTE, NOMBRE, APELLIDO, CELULAR, DIRECCION, CORREO FROM CLIENTES
        """)
        clientes = [
            {
                "id_cliente": row[0],
                "nombre": row[1],
                "apellido": row[2],
                "celular": row[3],
                "direccion": row[4],
                "correo": row[5]
            }
            for row in cursor.fetchall()
        ]
        cursor.close()
        return jsonify(clientes)
    except Exception as e:
        current_app.logger.error(f"Error al obtener clientes: {e}")
        return jsonify(error=str(e)), 500

# Obtener un cliente por ID
@clientes_bp.route('/<int:id_cliente>', methods=['GET'])
def get_cliente(id_cliente):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ID_CLIENTE, NOMBRE, APELLIDO, CELULAR, DIRECCION, CORREO
            FROM CLIENTES WHERE ID_CLIENTE = :id
        """, [id_cliente])
        row = cursor.fetchone()
        cursor.close()
        if row:
            cliente = {
                "id_cliente": row[0],
                "nombre": row[1],
                "apellido": row[2],
                "celular": row[3],
                "direccion": row[4],
                "correo": row[5]
            }
            return jsonify(cliente)
        else:
            return jsonify(error="Cliente no encontrado"), 404
    except Exception as e:
        current_app.logger.error(f"Error al obtener cliente: {e}")
        return jsonify(error=str(e)), 500

# Crear un nuevo cliente
@clientes_bp.route('/', methods=['POST'])
def crear_cliente():
    data = request.get_json()
    nombre = data.get('nombre')
    apellido = data.get('apellido')
    celular = data.get('celular')
    direccion = data.get('direccion')
    correo = data.get('correo')
    if not nombre or not apellido or not correo:
        return jsonify(error="Nombre, apellido y correo son requeridos"), 400
    try:
        conn = get_db()
        cursor = conn.cursor()
        id_cliente_var = cursor.var(int)
        cursor.execute("""
            INSERT INTO CLIENTES (NOMBRE, APELLIDO, CELULAR, DIRECCION, CORREO)
            VALUES (:nombre, :apellido, :celular, :direccion, :correo)
            RETURNING ID_CLIENTE INTO :id_cliente
        """, {
            "nombre": nombre,
            "apellido": apellido,
            "celular": celular,
            "direccion": direccion,
            "correo": correo,
            "id_cliente": id_cliente_var
        })
        conn.commit()
        cliente_id = id_cliente_var.getvalue()
        cursor.close()
        return jsonify(
            id_cliente=cliente_id,
            nombre=nombre,
            apellido=apellido,
            celular=celular,
            direccion=direccion,
            correo=correo
        ), 201
    except Exception as e:
        current_app.logger.error(f"Error al crear cliente: {e}")
        return jsonify(error=str(e)), 500

# Actualizar un cliente existente
@clientes_bp.route('/<int:id_cliente>', methods=['PUT'])
def actualizar_cliente(id_cliente):
    data = request.get_json()
    nombre = data.get('nombre')
    apellido = data.get('apellido')
    celular = data.get('celular')
    direccion = data.get('direccion')
    correo = data.get('correo')
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE CLIENTES
            SET NOMBRE = :nombre,
                APELLIDO = :apellido,
                CELULAR = :celular,
                DIRECCION = :direccion,
                CORREO = :correo
            WHERE ID_CLIENTE = :id_cliente
        """, {
            "nombre": nombre,
            "apellido": apellido,
            "celular": celular,
            "direccion": direccion,
            "correo": correo,
            "id_cliente": id_cliente
        })
        if cursor.rowcount == 0:
            cursor.close()
            return jsonify(error="Cliente no encontrado"), 404
        conn.commit()
        cursor.close()
        return jsonify(message="Cliente actualizado")
    except Exception as e:
        current_app.logger.error(f"Error al actualizar cliente: {e}")
        return jsonify(error=str(e)), 500

# Eliminar un cliente
@clientes_bp.route('/<int:id_cliente>', methods=['DELETE'])
def eliminar_cliente(id_cliente):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM CLIENTES WHERE ID_CLIENTE = :id_cliente", {"id_cliente": id_cliente})
        if cursor.rowcount == 0:
            cursor.close()
            return jsonify(error="Cliente no encontrado"), 404
        conn.commit()
        cursor.close()
        return jsonify(message="Cliente eliminado")
    except Exception as e:
        current_app.logger.error(f"Error al eliminar cliente: {e}")
        return jsonify(error=str(e)), 500
