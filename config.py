
# config.py
import os
from dotenv import load_dotenv

load_dotenv() # Carga variables desde un archivo .env si lo usas

class Config:
    ORACLE_USER = os.environ.get('ORACLE_USER')
    ORACLE_PASSWORD = os.environ.get('ORACLE_PASSWORD')
    ORACLE_DSN = os.environ.get('ORACLE_DSN')
    # Opcional: si no estableces TNS_ADMIN globalmente, puedes pasar esta ruta
    # al inicializar el cliente Oracle, pero TNS_ADMIN es más estándar.
    # ORACLE_WALLET_PATH = os.environ.get('ORACLE_WALLET_PATH') # Sería igual a TNS_ADMIN
