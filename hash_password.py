# hash_password.py
from werkzeug.security import generate_password_hash

# Elige una contraseña segura para tu usuario administrador
password_texto_plano =  "contraseña_supersegura"  # Reemplaza con tu contraseña
# Genera el hash
print(f"Generando hash para la contraseña: {password_texto_plano}")
password_hash=generate_password_hash(password_texto_plano)

print("Copia y pega este hash en la columna CONTRASENA_HASH de tu base de datos:")
print(f"plano {password_texto_plano}: hash es '{password_hash}'")