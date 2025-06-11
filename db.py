from flask import g, current_app

oracle_pool = None

def init_oracle_pool(oracledb, app):
    global oracle_pool
    try:
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
        app.logger.error("Verifica ORACLE_USER, ORACLE_PASSWORD y ORACLE_DSN en tu configuración.")
        oracle_pool = None
        # Lanza excepción para detener la app si el pool no se crea
        raise RuntimeError("No se pudo crear el pool de conexiones de Oracle. Revisa la configuración y la conexión a la base de datos.")

def get_db():
    if 'db' not in g:
        if not oracle_pool:
            raise Exception("Error crítico: El pool de conexiones de Oracle no está disponible.")
        try:
            g.db = oracle_pool.acquire()
        except Exception as e:
            current_app.logger.error(f"Error al adquirir conexión del pool: {e}")
            raise
    return g.db
