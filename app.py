# app.py (Versión Mejorada y Limpia)

# Importamos la configuración ya procesada desde nuestro módulo config.py
from config import Config, ORACLE_CLIENT_LIB_DIR, TNS_ADMIN
from flask import Flask, g, jsonify, request
from flask_cors import CORS

<<<<<<< Updated upstream
=======
from flask import Flask, g, jsonify
from flask_cors import CORS  # Agrega esta importación
import oracledb  # <-- Mueve esta línea aquí, antes de usar oracledb
import traceback # Útil para imprimir errores completos durante la depuración
from routes.clientes import clientes_bp  # Importa el blueprint de clientes
from db import init_oracle_pool, get_db  # Importa desde db.py
>>>>>>> Stashed changes
import oracledb
import traceback # Útil para imprimir errores completos durante la depuración
from werkzeug.security import check_password_hash
import jwt
import datetime

# Importar las rutas de mantenimientos
from servicios_routes import register_servicios_routes  # Agregar esta línea

from mantenimientos_routes import register_mantenimientos_routes  # Agregar esta línea

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
    # En un caso real, podrías querer que la aplicación no continúe si esto falla.
    
# --- Creación de la Aplicación Flask ---
app = Flask(__name__)
<<<<<<< Updated upstream

CORS(app)
=======
CORS(app)  # Habilita CORS para toda la app

>>>>>>> Stashed changes
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

# Ruta de ejemplo para probar la conexión
@app.route('/')
def index():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT sysdate FROM dual")
        # Corregido: fetchone() y conversión a string para JSON
        db_time, = cursor.fetchone()
        cursor.close()
        return jsonify(message="Conexión a Oracle ATP exitosa!", db_time=str(db_time))
    except Exception as e:
        app.logger.error(f"Error en la ruta /: {e}")
        return jsonify(error=str(e)), 500
    
@app.route('/api/auth/login', methods=['POST'])
def login():
    """
    Endpoint para autenticar un usuario y devolver un token JWT.
    """
    try:
        # Obtener los datos del cuerpo de la petición (JSON)
        auth_data = request.get_json()
        if not auth_data or not auth_data.get('nombre_usuario') or not auth_data.get('contrasena'):
            return jsonify({"error": "Faltan nombre de usuario o contraseña"}), 400

        nombre_usuario = auth_data['nombre_usuario']
        contrasena = auth_data['contrasena']

        # Conectarse a la BD y buscar al usuario
        conn = get_db()
        cursor = conn.cursor()
        
        sql = "SELECT ID_USUARIO, NOMBRE_USUARIO, CONTRASENA_HASH, ACTIVO FROM USUARIOS WHERE NOMBRE_USUARIO = :1"
        cursor.execute(sql, [nombre_usuario])
        
        user_row = cursor.fetchone()
        cursor.close()

        # Validar si el usuario existe, está activo y la contraseña es correcta
        if user_row is None:
            return jsonify({"error": "Credenciales inválidas"}), 401
        
        # Desempaquetar los datos del usuario
        id_usuario, db_nombre_usuario, db_contrasena_hash, db_activo = user_row

        if db_activo == 0:
            return jsonify({"error": "La cuenta de usuario está inactiva"}), 403

        # Comparar el hash de la contraseña de la BD con la contraseña enviada
        if not check_password_hash(db_contrasena_hash, contrasena):
            return jsonify({"error": "Credenciales inválidas"}), 401

        # Si todo es correcto, generar el token JWT
        token_payload = {
            'sub': id_usuario, # 'subject', el ID del usuario, es un estándar
            'name': db_nombre_usuario,
            'iat': datetime.datetime.now(datetime.timezone.utc), # 'issued at', hora de creación
            'exp': datetime.datetime.now() + datetime.timedelta(hours=8) # 'expiration time', ej. 8 horas
        }
        
        # Firmar el token con la SECRET_KEY de la configuración de Flask
        token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm='HS256')

        return jsonify({"token": token})

    except Exception as e:
        app.logger.error(f"Error en /api/auth/login: {e}")
        return jsonify(error="Ocurrió un error en el servidor"), 500

# Registrar todas las rutas de mantenimientos (agregar esta línea)
register_servicios_routes(app)
register_mantenimientos_routes(app)

if __name__ == '__main__':
    # El debug=True es genial para desarrollo
    app.run(debug=True)