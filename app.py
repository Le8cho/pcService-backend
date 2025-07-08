# app.py (Versión Mejorada y Limpia)

# Importamos la configuración ya procesada desde nuestro módulo config.py
from config import Config, ORACLE_CLIENT_LIB_DIR, TNS_ADMIN

from flask import Flask, g, jsonify, request
from flask_cors import CORS
import oracledb
import traceback # Útil para imprimir errores completos durante la depuración
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

# --- Inicialización del Cliente Oracle ---
# Usa las variables importadas directamente desde config.py
try:
    if ORACLE_CLIENT_LIB_DIR:
        # Pasamos TNS_ADMIN a config_dir para ser explícitos.
        oracledb.init_oracle_client(lib_dir=ORACLE_CLIENT_LIB_DIR, config_dir=TNS_ADMIN)
        print(f"INFO: Oracle Client inicializado desde: {ORACLE_CLIENT_LIB_DIR}")
    else:
        print("ADVERTENCIA: ORACLE_CLIENT_LIB_DIR no está configurado en .env. "
              "python-oracledb intentará usar librerías del PATH del sistema si opera en modo Thick.")
except Exception as e_init:
    print(f"ERROR CRÍTICO al inicializar Oracle Client: {e_init}")
    print(traceback.format_exc())
    
# --- Creación de la Aplicación Flask ---
app = Flask(__name__)
CORS(app)  # Habilitar CORS para todas las rutas
# Carga las variables de la CLASE Config en el objeto app.config
app.config.from_object(Config)

# Variable global para el pool de conexiones
oracle_pool = None

def init_oracle_pool():
    global oracle_pool
    try:
        # Ahora usa app.config, que fue poblado desde la clase Config
        oracle_pool = oracledb.create_pool(
            user=app.config['ORACLE_USER'],
            password=app.config['ORACLE_PASSWORD'],
            dsn=app.config['ORACLE_DSN'],
            min=2,
            max=5,
            increment=1
        )
        app.logger.info("Oracle Connection Pool creado exitosamente.")
    except Exception as e:
        app.logger.error(f"Error al crear Oracle Connection Pool: {e}")
        oracle_pool = None

# Llama a la inicialización del pool cuando la app se crea
with app.app_context():
    init_oracle_pool()

# Funciones para obtener y cerrar conexiones del pool
def get_db():
    if 'db' not in g:
        if not oracle_pool:
            raise Exception("Error crítico: El pool de conexiones de Oracle no está disponible.")
        try:
            g.db = oracle_pool.acquire()
        except Exception as e:
            app.logger.error(f"Error al adquirir conexión del pool: {e}")
            raise
    return g.db

@app.teardown_appcontext
def teardown_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Ruta para ver la estructura de una tabla
@app.route('/api/table/<table_name>/structure')
def get_table_structure(table_name):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT column_name, data_type, data_length, nullable
            FROM user_tab_columns
            WHERE table_name = :1
            ORDER BY column_id
        """, [table_name.upper()])
        columns = [{"name": row[0], "type": row[1], "length": row[2], "nullable": row[3]} 
                  for row in cursor.fetchall()]
        cursor.close()
        return jsonify({"structure": columns})
    except Exception as e:
        app.logger.error(f"Error al obtener estructura de tabla: {e}")
        return jsonify(error=str(e)), 500

# Ruta para ver los datos de una tabla
@app.route('/api/table/<table_name>/data')
def get_table_data(table_name):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name.upper()}")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        results = []
        for row in rows:
            result = dict(zip(columns, map(str, row)))
            results.append(result)
        cursor.close()
        return jsonify({"data": results})
    except Exception as e:
        app.logger.error(f"Error al obtener datos de tabla: {e}")
        return jsonify(error=str(e)), 500

# Ruta para listar todas las tablas
@app.route('/api/tables')
def list_tables():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT table_name 
            FROM user_tables 
            ORDER BY table_name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return jsonify({"tables": tables})
    except Exception as e:
        app.logger.error(f"Error al listar tablas: {e}")
        return jsonify(error=str(e)), 500

# Ruta de ejemplo para probar la conexión
@app.route('/')
def index():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT sysdate FROM dual")
        db_time, = cursor.fetchone()
        cursor.close()
        return jsonify(message="Conexión a Oracle ATP exitosa!", db_time=str(db_time))
    except Exception as e:
        app.logger.error(f"Error en la ruta /: {e}")
        return jsonify(error=str(e)), 500

# Rutas para el CRUD de clientes
@app.route('/api/clientes', methods=['GET'])
def get_clientes():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clientes")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        results = []
        for row in rows:
            result = dict(zip(columns, map(str, row)))
            results.append(result)
        cursor.close()
        return jsonify(results)
    except Exception as e:
        app.logger.error(f"Error al obtener clientes: {e}")
        return jsonify(error=str(e)), 500

@app.route('/api/clientes', methods=['POST'])
def crear_cliente():
    try:
        cliente = request.json
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO clientes (nombre, direccion, celular, correo) 
            VALUES (:1, :2, :3, :4)
            RETURNING id INTO :5
        """, [
            cliente['nombre'],
            cliente['direccion'],
            cliente['celular'],
            cliente['correo'],
            cursor.var(int)
        ])
        id_cliente = cursor.var.getvalue()
        conn.commit()
        cursor.close()
        return jsonify({"id": id_cliente, **cliente})
    except Exception as e:
        app.logger.error(f"Error al crear cliente: {e}")
        return jsonify(error=str(e)), 500


@app.route('/api/clientes/<int:id>', methods=['PUT'])
def actualizar_cliente(id):
    try:
        cliente = request.json
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE clientes 
            SET nombre = :1, direccion = :2, celular = :3, correo = :4
            WHERE id = :5
        """, [
            cliente['nombre'],
            cliente['direccion'],
            cliente['celular'],
            cliente['correo'],
            id
        ])
        conn.commit()
        cursor.close()
        return jsonify({"id": id, **cliente})
    except Exception as e:
        app.logger.error(f"Error al actualizar cliente: {e}")
        return jsonify(error=str(e)), 500

@app.route('/api/clientes/<int:id>', methods=['DELETE'])
def eliminar_cliente(id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM clientes WHERE id = :1", [id])
        conn.commit()
        cursor.close()
        return jsonify({"message": f"Cliente {id} eliminado correctamente"})
    except Exception as e:
        app.logger.error(f"Error al eliminar cliente: {e}")
        return jsonify(error=str(e)), 500


@app.route('/api/licencias/<tipo_licencia>', methods=['GET'])
def obtener_licencias_por_tipo(tipo_licencia):
    try:
        conn = get_db()
        cursor = conn.cursor()

        if tipo_licencia == 'antivirus':
            query = """
                SELECT 
                    v.ID_LICENCIA,
                    o.FECHA as FECHA_ADQUISICION,
                    1 as TOTAL_DISPOSITIVOS,
                    1 as DISPONIBILIDAD,
                    (c.NOMBRE || ' ' || c.APELLIDO) as CLIENTE,
                    a.DETALLES,
                    a.FECHA_FIN as FECHA_VENCIMIENTO
                FROM VENTAS v
                JOIN OPERACIONES o ON v.ID_OPERACION = o.ID_OPERACION
                JOIN CLIENTES c ON o.ID_CLIENTE = c.ID_CLIENTE
                JOIN ANTIVIRUS a ON v.ID_LICENCIA = a.ID_LICENCIA
                ORDER BY o.FECHA DESC
            """
        elif tipo_licencia == 'ofimatica':
            query = """
                SELECT 
                    v.ID_LICENCIA,
                    o.FECHA as FECHA_ADQUISICION,
                    1 as TOTAL_DISPOSITIVOS,
                    1 as DISPONIBILIDAD,
                    (c.NOMBRE || ' ' || c.APELLIDO) as CLIENTE,
                    m.DETALLES,
                    m.FECHA_FIN as FECHA_VENCIMIENTO
                FROM VENTAS v
                JOIN OPERACIONES o ON v.ID_OPERACION = o.ID_OPERACION
                JOIN CLIENTES c ON o.ID_CLIENTE = c.ID_CLIENTE
                JOIN MICROSOFT365 m ON v.ID_LICENCIA = m.ID_LICENCIA
                ORDER BY o.FECHA DESC
            """
        elif tipo_licencia == 'sistema_operativo':
            query = """
                SELECT 
                    v.ID_LICENCIA,
                    o.FECHA as FECHA_ADQUISICION,
                    1 as TOTAL_DISPOSITIVOS,
                    1 as DISPONIBILIDAD,
                    (c.NOMBRE || ' ' || c.APELLIDO) as CLIENTE,
                    w.DETALLES,
                    w.FECHA_FIN as FECHA_VENCIMIENTO
                FROM VENTAS v
                JOIN OPERACIONES o ON v.ID_OPERACION = o.ID_OPERACION
                JOIN CLIENTES c ON o.ID_CLIENTE = c.ID_CLIENTE
                JOIN WINDOWS w ON v.ID_LICENCIA = w.ID_LICENCIA
                ORDER BY o.FECHA DESC
            """
        else:
            return jsonify({'error': 'Tipo de licencia no válido'}), 400

        cursor.execute(query)
        resultados = cursor.fetchall()

        licencias = []
        for row in resultados:
            licencia = {
                'idLicencia': row[0],
                'fechaAdquisicion': row[1].isoformat() if row[1] else None,
                'totalDispositivos': row[2] or 0,
                'disponibilidad': row[3] or 0,
                'cliente': row[4] or '',
                'detalles': row[5] or '',
                'fechaVencimiento': row[6].isoformat() if row[6] else None,
                'tipoLicencia': tipo_licencia
            }
            licencias.append(licencia)

        cursor.close()
        return jsonify(licencias)

    except Exception as e:
        app.logger.error(f"Error al obtener licencias {tipo_licencia}: {e}")
        app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


def generar_nuevo_id_licencia(prefijo, tabla):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(f"SELECT ID_LICENCIA FROM {tabla} WHERE ID_LICENCIA LIKE :prefijo ORDER BY ID_LICENCIA DESC", {'prefijo': f'{prefijo}%'} )
    row = cursor.fetchone()
    if row:
        last_id = row[0]
        last_num = int(last_id.split('-')[1])
        next_num = last_num + 1
    else:
        next_num = 1
    return f"{prefijo}{next_num:03d}"


@app.route('/api/licencias/registrar-antivirus', methods=['POST'])
def registrar_antivirus():
    try:
        data = request.json
        # Debug: imprime los datos recibidos para ver si llegan correctamente
        print("DEBUG registrar-antivirus data:", data)
        # Generar ID automático para Antivirus
        id_licencia = generar_nuevo_id_licencia('A-', 'ANTIVIRUS')
        detalles = data.get('detalles', '')
        fecha_inicio = data.get('fechaInicio')
        fecha_fin = data.get('fechaFin')
        fecha_aviso = data.get('fechaAviso')
        tiempo_licencia = data.get('tiempoLicencia', '')
        nombre_antivirus = data.get('nombreAntivirus', '')
        user_antivirus = data.get('userAntivirus', '')
        id_cliente = data.get('idCliente')
        ingreso = data.get('ingreso', 0)
        egreso = data.get('egreso', 0)

        conn = get_db()
        cursor = conn.cursor()

        # Validar que el cliente exista
        cursor.execute("SELECT ID_CLIENTE FROM CLIENTES WHERE ID_CLIENTE = :id_cliente", {'id_cliente': id_cliente})
        row = cursor.fetchone()
        if not row:
            print("DEBUG: Cliente no encontrado, id_cliente recibido:", id_cliente)
            return jsonify({'error': 'Cliente no encontrado'}), 400

        # 2. Insertar en OPERACIONES (ahora usando ingreso y egreso del frontend)
        id_operacion_var = cursor.var(oracledb.NUMBER)
        cursor.execute("""
            INSERT INTO OPERACIONES (ID_CLIENTE, FECHA, TIPO_OPERACION, INGRESO, EGRESO)
            VALUES (:id_cliente, TRUNC(SYSDATE), 'VENTA', :ingreso, :egreso)
            RETURNING ID_OPERACION INTO :id_operacion
        """, id_cliente=id_cliente, ingreso=ingreso, egreso=egreso, id_operacion=id_operacion_var)
        id_operacion = int(id_operacion_var.getvalue()[0])

        # 3. Insertar en VENTAS
        cursor.execute("""
            INSERT INTO VENTAS (ID_OPERACION, ID_LICENCIA)
            VALUES (:id_operacion, :id_licencia)
        """, id_operacion=id_operacion, id_licencia=id_licencia)

        # 4. Insertar en ANTIVIRUS
        cursor.execute("""
            INSERT INTO ANTIVIRUS (
                ID_LICENCIA, DETALLES, FEC_INICIO, FECHA_FIN, FECHA_AVISO, TIME_LICENCIA, NOM_ANTIVIRUS, USER_ANT
            ) VALUES (
                :id_licencia, :detalles, TO_DATE(:fecha_inicio, 'YYYY-MM-DD'), TO_DATE(:fecha_fin, 'YYYY-MM-DD'), TO_DATE(:fecha_aviso, 'YYYY-MM-DD'), :tiempo_licencia, :nombre_antivirus, :user_antivirus
            )
        """, id_licencia=id_licencia, detalles=detalles, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, fecha_aviso=fecha_aviso, tiempo_licencia=tiempo_licencia, nombre_antivirus=nombre_antivirus, user_antivirus=user_antivirus)

        conn.commit()
        cursor.close()
        return jsonify({'message': 'Licencia Antivirus registrada correctamente', 'idLicencia': id_licencia})
    except Exception as e:
        app.logger.error(f"Error al registrar antivirus: {e}")
        app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/licencias/registrar-ofimatica', methods=['POST'])
def registrar_ofimatica():
    try:
        data = request.json
        print("DEBUG registrar-ofimatica data:", data)
        id_licencia = generar_nuevo_id_licencia('M-', 'MICROSOFT365')

        detalles = data.get('detalles', '')
        fecha_inicio = data.get('fechaInicio')
        fecha_fin = data.get('fechaFin')
        fecha_aviso = data.get('fechaAviso')
        tiempo_licencia = data.get('tiempoLicencia', '')
        email_ctacliente = data.get('emailCtacliente', '')
        passw_ctacliente = data.get('passwCtacliente', '')
        norma_m365 = data.get('normM365', '')
        user_m365 = data.get('userM365', '')
        pass_m365 = data.get('passM365', '')
        id_cliente = data.get('idCliente')
        ingreso = data.get('ingreso', 0)
        egreso = data.get('egreso', 0)

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT ID_CLIENTE FROM CLIENTES WHERE ID_CLIENTE = :id_cliente", {'id_cliente': id_cliente})
        row = cursor.fetchone()
        if not row:
            print("DEBUG: Cliente no encontrado, id_cliente recibido:", id_cliente)
            return jsonify({'error': 'Cliente no encontrado'}), 400

        id_operacion_var = cursor.var(oracledb.NUMBER)
        cursor.execute("""
            INSERT INTO OPERACIONES (ID_CLIENTE, FECHA, TIPO_OPERACION, INGRESO, EGRESO)
            VALUES (:id_cliente, TRUNC(SYSDATE), 'VENTA', :ingreso, :egreso)
            RETURNING ID_OPERACION INTO :id_operacion
        """, id_cliente=id_cliente, ingreso=ingreso, egreso=egreso, id_operacion=id_operacion_var)
        id_operacion = int(id_operacion_var.getvalue()[0])

        cursor.execute("""
            INSERT INTO VENTAS (ID_OPERACION, ID_LICENCIA)
            VALUES (:id_operacion, :id_licencia)
        """, id_operacion=id_operacion, id_licencia=id_licencia)

        try:
            cursor.execute("""
                INSERT INTO MICROSOFT365 (
                    ID_LICENCIA, DETALLES, FEC_INICIO, FECHA_FIN, FECHA_AVISO, EMAIL_CTACLIE, PASSW_CTACLIE, NORM_M365, USER_M365, PASS_M365
                ) VALUES (
                    :id_licencia, :detalles, TO_DATE(:fecha_inicio, 'YYYY-MM-DD'), TO_DATE(:fecha_fin, 'YYYY-MM-DD'), TO_DATE(:fecha_aviso, 'YYYY-MM-DD'), :email_ctacliente, :passw_ctacliente, :norma_m365, :user_m365, :pass_m365
                )

            """, id_licencia=id_licencia, detalles=detalles, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, fecha_aviso=fecha_aviso, email_ctacliente=email_ctacliente, passw_ctacliente=passw_ctacliente, norma_m365=norma_m365, user_m365=user_m365, pass_m365=pass_m365)

        except Exception as e_inner:
            app.logger.error(f"Error al insertar en MICROSOFT365: {e_inner}")
            app.logger.error(traceback.format_exc())
            cursor.close()
            return jsonify({'error': 'Error al insertar datos de Ofimática'}), 500

        conn.commit()
        cursor.close()
        return jsonify({'message': 'Licencia Ofimática registrada correctamente', 'idLicencia': id_licencia})
    except Exception as e:
        app.logger.error(f"Error al registrar ofimatica: {e}")
        app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500



@app.route('/api/licencias/registrar-sistema-operativo', methods=['POST'])
def registrar_sistema_operativo():
    try:
        data = request.json
        print("DEBUG registrar-sistema-operativo data:", data)
        id_licencia = generar_nuevo_id_licencia('W-', 'WINDOWS')
        
        # --- CAMPOS COMUNES ---
        detalles = data.get('detalles', '')
        fecha_inicio = data.get('fechaInicio')
        fecha_fin = data.get('fechaFin')
        fecha_aviso = data.get('fechaAviso')
        tiempo_licencia = data.get('tiempoLicencia', '')
        id_cliente = data.get('idCliente')
        ingreso = data.get('ingreso', 0)
        egreso = data.get('egreso', 0)

        # --- CAMPOS ESPECÍFICOS DE WINDOWS (CORREGIDOS) ---
        so_activado = data.get('soActivado', '')
        key = data.get('key', '')
        key_tipo = data.get('keyTipo', '')

        conn = get_db()
        cursor = conn.cursor()

        # 1. Validar que el cliente exista
        cursor.execute("SELECT ID_CLIENTE FROM CLIENTES WHERE ID_CLIENTE = :id_cliente", {'id_cliente': id_cliente})
        if not cursor.fetchone():
            return jsonify({'error': 'Cliente no encontrado'}), 400

        # 2. Insertar en OPERACIONES
        id_operacion_var = cursor.var(oracledb.NUMBER)
        cursor.execute("""
            INSERT INTO OPERACIONES (ID_CLIENTE, TIPO_OPERACION, INGRESO, EGRESO)
            VALUES (:id_cliente, 'VENTA', :ingreso, :egreso)
            RETURNING ID_OPERACION INTO :id_operacion
        """, id_cliente=id_cliente, ingreso=ingreso, egreso=egreso, id_operacion=id_operacion_var)
        id_operacion = int(id_operacion_var.getvalue()[0])

        # 3. Insertar en VENTAS
        cursor.execute("""
            INSERT INTO VENTAS (ID_OPERACION, ID_LICENCIA)
            VALUES (:id_operacion, :id_licencia)
        """, id_operacion=id_operacion, id_licencia=id_licencia)

        # 4. Insertar en WINDOWS (CORREGIDO)
        cursor.execute("""
            INSERT INTO WINDOWS (
                ID_LICENCIA, DETALLES, FEC_INICIO, FECHA_FIN, FECHA_AVISO, 
                TIME_LICENCIA, SO_ACTIVADO, "KEY", KEY_TIPO
            ) VALUES (
                :id_licencia, :detalles, TO_DATE(:fec_inicio, 'YYYY-MM-DD'), 
                TO_DATE(:fecha_fin, 'YYYY-MM-DD'), TO_DATE(:fecha_aviso, 'YYYY-MM-DD'),
                :time_licencia, :so_activado, :key, :key_tipo
            )
        """, {
            "id_licencia": id_licencia,
            "detalles": detalles,
            "fec_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "fecha_aviso": fecha_aviso,
            "time_licencia": tiempo_licencia,
            "so_activado": so_activado,
            "key": key,
            "key_tipo": key_tipo
        })

        conn.commit()
        cursor.close()
        return jsonify({'message': 'Licencia de Sistema Operativo registrada correctamente', 'idLicencia': id_licencia})
    except Exception as e:
        app.logger.error(f"Error al registrar sistema operativo: {e}")
        app.logger.error(traceback.format_exc())
        conn.rollback() # Asegurarse de revertir la transacción en caso de error
        return jsonify({'error': str(e)}), 500


# CRUD para DISPOSITIVOS
@app.route('/api/dispositivos', methods=['GET'])
def get_dispositivos():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM DISPOSITIVOS")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        results = [dict(zip(columns, row)) for row in rows]
        cursor.close()
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dispositivos', methods=['POST'])
def create_dispositivo():
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO DISPOSITIVOS (ID_CLIENTE, TIPO_DISPOSITIVO, MARCA, MODELO)
            VALUES (:id_cliente, :tipo, :marca, :modelo)
        """, id_cliente=data['ID_CLIENTE'], tipo=data['TIPO_DISPOSITIVO'], marca=data['MARCA'], modelo=data['MODELO'])
        conn.commit()
        cursor.close()
        return jsonify({'message': 'Dispositivo creado correctamente'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dispositivos/<int:id>', methods=['PUT'])
def update_dispositivo(id):
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE DISPOSITIVOS
            SET ID_CLIENTE=:id_cliente, TIPO_DISPOSITIVO=:tipo, MARCA=:marca, MODELO=:modelo
            WHERE ID_DISPOSITIVO=:id
        """, id_cliente=data['ID_CLIENTE'], tipo=data['TIPO_DISPOSITIVO'], marca=data['MARCA'], modelo=data['MODELO'], id=id)
        conn.commit()
        cursor.close()
        return jsonify({'message': 'Dispositivo actualizado correctamente'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dispositivos/<int:id>', methods=['DELETE'])
def delete_dispositivo(id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM DISPOSITIVOS WHERE ID_DISPOSITIVO=:id", id=id)
        conn.commit()
        cursor.close()
        return jsonify({'message': 'Dispositivo eliminado correctamente'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    


def enviar_correo_aviso(destinatario: str, nombre_cliente: str, tipo_licencia: str, 
                       fecha_vencimiento: str, dias_restantes: int):
    try:
        app.logger.info(f"Preparando envío de alerta a {destinatario}")
        
        # Configuración SMTP (ejemplo para Gmail)
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        remitente = "brayan.goicochea@unmsm.edu.pe"  # Cambiar por tu email real
        password = "qsxzsfmciinsftjg"     # Cambiar por contraseña de aplicación
        
        app.logger.debug(f"Configurando mensaje para {destinatario}")
        mensaje = MIMEMultipart()
        mensaje['From'] = remitente
        mensaje['To'] = destinatario
        mensaje['Subject'] = f"Alerta: Licencia {tipo_licencia} por vencer"
        
        cuerpo = f"""
        Estimado/a {nombre_cliente},

        Su licencia de {tipo_licencia} está próxima a vencer.

        Detalles:
        - Fecha de vencimiento: {fecha_vencimiento}
        - Días restantes: {dias_restantes}

        Por favor, contacte al equipo de soporte.
        """
        
        mensaje.attach(MIMEText(cuerpo, 'plain'))
        app.logger.debug("Mensaje construido correctamente")

        app.logger.info(f"Conectando a {smtp_server}:{smtp_port}")
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            app.logger.debug("Conexión TLS iniciada")
            server.login(remitente, password)
            app.logger.debug("Autenticación exitosa")
            server.send_message(mensaje)
            app.logger.info(f"Correo enviado exitosamente a {destinatario}")
            
        return True
        
    except smtplib.SMTPException as e:
        app.logger.error(f"Error SMTP al enviar a {destinatario}: {str(e)}")
        app.logger.error(f"Código SMTP: {e.smtp_code} | Mensaje: {e.smtp_error}")
        return False
        
    except Exception as e:
        app.logger.error(f"Error inesperado al enviar a {destinatario}: {str(e)}")
        app.logger.error(traceback.format_exc())
        return False

# Luego modifica la función verificar_vencimientos_licencias así:
@app.route('/api/licencias/verificar-vencimientos', methods=['GET'])
def verificar_vencimientos_licencias():
    try:
        dias_alerta = request.args.get('dias', default=7, type=int)
        fecha_actual = datetime.now().date()
        fecha_limite = fecha_actual + timedelta(days=dias_alerta)
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Consulta para licencias próximas a vencer
        cursor.execute("""
            SELECT 
                c.CORREO, 
                c.NOMBRE || ' ' || c.APELLIDO as NOMBRE_CLIENTE,
                'Antivirus' as TIPO_LICENCIA,
                a.FECHA_FIN,
                TRUNC(a.FECHA_FIN) - TRUNC(SYSDATE) as DIAS_RESTANTES
            FROM ANTIVIRUS a
            JOIN VENTAS v ON a.ID_LICENCIA = v.ID_LICENCIA
            JOIN OPERACIONES o ON v.ID_OPERACION = o.ID_OPERACION
            JOIN CLIENTES c ON o.ID_CLIENTE = c.ID_CLIENTE
            WHERE a.FECHA_FIN BETWEEN SYSDATE AND SYSDATE + :dias
            AND c.CORREO IS NOT NULL
            
            UNION ALL
            
            SELECT 
                c.CORREO, 
                c.NOMBRE || ' ' || c.APELLIDO as NOMBRE_CLIENTE,
                'Microsoft 365' as TIPO_LICENCIA,
                m.FECHA_FIN,
                TRUNC(m.FECHA_FIN) - TRUNC(SYSDATE) as DIAS_RESTANTES
            FROM MICROSOFT365 m
            JOIN VENTAS v ON m.ID_LICENCIA = v.ID_LICENCIA
            JOIN OPERACIONES o ON v.ID_OPERACION = o.ID_OPERACION
            JOIN CLIENTES c ON o.ID_CLIENTE = c.ID_CLIENTE
            WHERE m.FECHA_FIN BETWEEN SYSDATE AND SYSDATE + :dias
            AND c.CORREO IS NOT NULL
            
            UNION ALL
            
            SELECT 
                c.CORREO, 
                c.NOMBRE || ' ' || c.APELLIDO as NOMBRE_CLIENTE,
                'Windows' as TIPO_LICENCIA,
                w.FECHA_FIN,
                TRUNC(w.FECHA_FIN) - TRUNC(SYSDATE) as DIAS_RESTANTES
            FROM WINDOWS w
            JOIN VENTAS v ON w.ID_LICENCIA = v.ID_LICENCIA
            JOIN OPERACIONES o ON v.ID_OPERACION = o.ID_OPERACION
            JOIN CLIENTES c ON o.ID_CLIENTE = c.ID_CLIENTE
            WHERE w.FECHA_FIN BETWEEN SYSDATE AND SYSDATE + :dias
            AND c.CORREO IS NOT NULL
        """, dias=dias_alerta)
        
        licencias_proximas = cursor.fetchall()
        cursor.close()
        
        resultados = []
        for licencia in licencias_proximas:
            correo, nombre_cliente, tipo_licencia, fecha_vencimiento, dias_restantes = licencia
            fecha_str = fecha_vencimiento.strftime('%d/%m/%Y')
            
            # Enviar correo
            envio_exitoso = enviar_correo_aviso(
                correo, 
                nombre_cliente, 
                tipo_licencia, 
                fecha_str, 
                dias_restantes
            )
            
            resultados.append({
                'cliente': nombre_cliente,
                'correo': correo,
                'tipoLicencia': tipo_licencia,
                'fechaVencimiento': fecha_str,
                'diasRestantes': dias_restantes,
                'correoEnviado': envio_exitoso
            })
        
        return jsonify({
            'totalLicencias': len(licencias_proximas),
            'licencias': resultados,
            'mensaje': f'Se verificaron {len(licencias_proximas)} licencias próximas a vencer'
        })
        
    except Exception as e:
        app.logger.error(f"Error al verificar vencimientos: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

# Endpoint para enviar alerta manual
@app.route('/api/licencias/enviar-alerta/<id_licencia>', methods=['POST'])
def enviar_alerta_manual(id_licencia):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Determinar el tipo de licencia por su prefijo
        if id_licencia.startswith('A-'):
            tabla = 'ANTIVIRUS'
            tipo_licencia = 'Antivirus'
        elif id_licencia.startswith('M-'):
            tabla = 'MICROSOFT365'
            tipo_licencia = 'Microsoft 365'
        elif id_licencia.startswith('W-'):
            tabla = 'WINDOWS'
            tipo_licencia = 'Windows'
        else:
            return jsonify({'error': 'Tipo de licencia no reconocido'}), 400
        
        # Obtener datos de la licencia y cliente
        cursor.execute(f"""
            SELECT 
                c.CORREO, 
                c.NOMBRE || ' ' || c.APELLIDO as NOMBRE_CLIENTE,
                l.FECHA_FIN,
                TRUNC(l.FECHA_FIN) - TRUNC(SYSDATE) as DIAS_RESTANTES
            FROM {tabla} l
            JOIN VENTAS v ON l.ID_LICENCIA = v.ID_LICENCIA
            JOIN OPERACIONES o ON v.ID_OPERACION = o.ID_OPERACION
            JOIN CLIENTES c ON o.ID_CLIENTE = c.ID_CLIENTE
            WHERE l.ID_LICENCIA = :id_licencia
        """, id_licencia=id_licencia)
        
        licencia = cursor.fetchone()
        cursor.close()
        
        if not licencia:
            return jsonify({'error': 'Licencia no encontrada'}), 404
            
        correo, nombre_cliente, fecha_vencimiento, dias_restantes = licencia
        fecha_str = fecha_vencimiento.strftime('%d/%m/%Y')
        
        # Enviar correo
        envio_exitoso = enviar_correo_aviso(
            correo, 
            nombre_cliente, 
            tipo_licencia, 
            fecha_str, 
            dias_restantes
        )
        
        if envio_exitoso:
            return jsonify({
                'mensaje': 'Correo de alerta enviado exitosamente',
                'cliente': nombre_cliente,
                'correo': correo,
                'fechaVencimiento': fecha_str,
                'diasRestantes': dias_restantes
            })
        else:
            return jsonify({'error': 'Error al enviar el correo'}), 500
            
    except Exception as e:
        app.logger.error(f"Error al enviar alerta manual: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # El debug=True es genial para desarrollo
    app.run(debug=True)
