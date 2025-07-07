# app.py (Versión Mejorada y Limpia)

# Importamos la configuración ya procesada desde nuestro módulo config.py
from config import Config, ORACLE_CLIENT_LIB_DIR, TNS_ADMIN

from flask import Flask, g, jsonify
from flask_cors import CORS  # Agregar esta línea
import oracledb
import traceback # Útil para imprimir errores completos durante la depuración

# Importar las rutas de mantenimientos
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
# Habilitar CORS para todas las rutas (agregar esta línea)
CORS(app)
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

# Registrar todas las rutas de mantenimientos (agregar esta línea)
register_mantenimientos_routes(app)

if __name__ == '__main__':
    # El debug=True es genial para desarrollo
    app.run(debug=True)