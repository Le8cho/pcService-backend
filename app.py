# app.py (Versión Mejorada y Limpia)

# Importamos la configuración ya procesada desde nuestro módulo config.py
from config import Config, ORACLE_CLIENT_LIB_DIR, TNS_ADMIN

from flask import Flask, g, jsonify
from flask_cors import CORS  # Agrega esta importación
import oracledb  # <-- Mueve esta línea aquí, antes de usar oracledb
import traceback # Útil para imprimir errores completos durante la depuración
from routes.clientes import clientes_bp  # Importa el blueprint de clientes
from db import init_oracle_pool, get_db  # Importa desde db.py

# --- Inicialización del Cliente Oracle ---
try:
    if ORACLE_CLIENT_LIB_DIR:
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
CORS(app)  # Habilita CORS para toda la app

# Carga las variables de la CLASE Config en el objeto app.config
app.config.from_object(Config)

# Registra el blueprint de clientes
app.register_blueprint(clientes_bp, url_prefix='/clientes')

# Llama a la inicialización del pool cuando la app se crea
with app.app_context():
    try:
        init_oracle_pool(oracledb, app)
    except Exception as pool_error:
        print(f"ERROR CRÍTICO: {pool_error}")
        import sys
        sys.exit(1)  # Detiene la app si el pool no se puede crear

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

if __name__ == '__main__':
    # El debug=True es genial para desarrollo
    app.run(debug=True)

