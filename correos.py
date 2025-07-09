import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta


def alertar_cliente():
    try:
        remitente = "brayan.goicochea@unmsm.edu.pe"
        clave_app = "qsxzsfmciinsftjg"  # Contraseña de aplicación (sin espacios)
        destinatario = "brayangoicocheac@gmail.com"
        asunto = "Tu servicio está por terminar"
        mensaje_texto = (
            "Hola, tu servicio está por vencer.\n\n"
            "Por favor, renueva tu licencia para no perder el acceso.\n\n"
            "-- Sistema de Servicio Técnico"
        )

        mensaje = MIMEMultipart()
        mensaje['From'] = remitente
        mensaje['To'] = destinatario
        mensaje['Subject'] = asunto
        mensaje.attach(MIMEText(mensaje_texto, 'plain'))

        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.starttls()
        servidor.login(remitente, clave_app)
        servidor.send_message(mensaje)
        servidor.quit()

        print("✅ Correo enviado exitosamente.")
    except Exception as e:
        print("❌ Error al enviar el correo:", e)

# Si deseas probar directamente desde este archivo:
if __name__ == '__main__':
    alertar_cliente()
