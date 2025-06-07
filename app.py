# app.py
from flask import Flask, g, jsonify
import oracledb
import os
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Variable global para el pool
oracle_pool = None

def init_oracle_pool():
    global oracle_pool
    try:
        # Es crucial que TNS_ADMIN esté configurado en el entorno para que
        # python-oracledb (en modo Thick) encuentre el wallet.
        # Si las librerías del Instant Client no están en el PATH del sistema (LD_LIBRARY_PATH en Linux, PATH en Windows),
        # puedes necesitar inicializar el cliente explícitamente con la ruta a esas librerías.
        # Ejemplo:
        if os.name == 'nt': # Windows
            oracledb.init_oracle_client(lib_dir=r"D:/UNMSM/7mo_ciclo/DSW/Proyecto/oracle_instant_client/instantclient_23_8")
        # else: # Linux/macOS
        #    oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient_XX_X")
        # En muchos casos, si Instant Client está bien instalado y TNS_ADMIN está seteado,
        # la inicialización explícita de lib_dir no es necesaria.

        print(f"Intentando crear pool con DSN: {app.config['ORACLE_DSN']}")
        print(f"Usuario: {app.config['ORACLE_USER']}")
        print(f"TNS_ADMIN (leído del entorno): {os.environ.get('TNS_ADMIN')}")

        

        oracle_pool = oracledb.create_pool(
            user=app.config['ORACLE_USER'],
            password=app.config['ORACLE_PASSWORD'],
            dsn=app.config['ORACLE_DSN'],
            min=2, # Número mínimo de conexiones en el pool
            max=5, # Número máximo de conexiones
            increment=1 # Cuántas conexiones crear cuando se necesiten más
        )
        app.logger.info("Oracle Connection Pool creado exitosamente.")
    except Exception as e:
        app.logger.error(f"Error al crear Oracle Connection Pool: {e}")
        oracle_pool = None # Asegúrate de manejar esto en tus rutas

# Llama a la inicialización del pool cuando la app se crea
with app.app_context():
    init_oracle_pool()

# Funciones para obtener y cerrar conexiones del pool
def get_db():
    if 'db' not in g:
        if oracle_pool:
            try:
                g.db = oracle_pool.acquire()
                app.logger.debug("Conexión adquirida del pool.")
            except Exception as e:
                app.logger.error(f"Error al adquirir conexión del pool: {e}")
                raise # Propaga la excepción para que se maneje globalmente o por la ruta
        else:
            app.logger.error("El pool de Oracle no está inicializado.")
            raise Exception("Oracle Pool no disponible.")
    return g.db

@app.teardown_appcontext
def teardown_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        try:
            db.close()
            app.logger.debug("Conexión devuelta al pool.")
        except Exception as e:
            app.logger.error(f"Error al cerrar/devolver conexión al pool: {e}")
    if exception:
        app.logger.error(f"Cerrando app context debido a excepción: {exception}")


# Ruta de ejemplo para probar la conexión
@app.route('/')
def index():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT sysdate FROM dual")
        db_time, = cursor.fetall()
        cursor.close()
        return jsonify(message="Conexión a Oracle ATP exitosa!", db_time=list(db_time))
    except Exception as e:
        app.logger.error(f"Error en la ruta /: {e}")
        return jsonify(error=str(e)), 500

if __name__ == '__main__':
    # Establece TNS_ADMIN aquí si no está en el entorno global ANTES de importar oracledb o crear el pool
    # os.environ['TNS_ADMIN'] = '/ruta/completa/a/tu/directorio_wallet'
    app.run(debug=True)