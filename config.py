# config.py (Versión Mejorada y Centralizada)
import os
from dotenv import load_dotenv

# Cargar el archivo .env una sola vez al inicio del proyecto
load_dotenv()

# --- Variables para la configuración del cliente Oracle ---
# Se definen a nivel de módulo para ser importadas y usadas antes de que la app Flask se configure por completo.
TNS_ADMIN = os.environ.get('TNS_ADMIN')
ORACLE_CLIENT_LIB_DIR = os.environ.get('ORACLE_CLIENT_LIB_DIR')


# --- Clase para la configuración de la aplicación Flask ---
# Estas variables serán cargadas en app.config usando app.config.from_object(Config)
class Config:
    # Es una buena práctica tener una SECRET_KEY en las apps Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'una-clave-secreta-por-defecto-para-desarrollo'
    
    # Credenciales y DSN para la conexión de la app
    ORACLE_USER = os.environ.get('ORACLE_USER')
    ORACLE_PASSWORD = os.environ.get('ORACLE_PASSWORD')
    ORACLE_DSN = os.environ.get('ORACLE_DSN')
