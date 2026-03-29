import os
import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.hostinger.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "noreply@skybrandmx.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "SkyBrandMX")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:4010")


def generate_2fa_code() -> str:
    return "".join(random.choices(string.digits, k=6))


def _send_email(to_email: str, subject: str, html_body: str):
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


def send_confirmation_email(to_email: str, full_name: str, token: str):
    link = f"{FRONTEND_URL}/confirmar?token={token}"
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto; background: #0f172a; color: #e2e8f0; padding: 40px; border-radius: 16px;">
        <h1 style="color: #2dd4bf; font-size: 24px; margin-bottom: 8px;">SkyBrandMX</h1>
        <p style="color: #94a3b8; font-size: 14px; margin-bottom: 32px;">Plataforma de automatización empresarial</p>
        <h2 style="color: #fff; font-size: 20px;">Hola {full_name},</h2>
        <p style="color: #cbd5e1; line-height: 1.6;">Has sido invitado a SkyBrandMX. Haz clic en el botón para establecer tu contraseña y activar tu cuenta.</p>
        <a href="{link}" style="display: inline-block; background: #2dd4bf; color: #0f172a; font-weight: 800; padding: 14px 32px; border-radius: 12px; text-decoration: none; margin: 24px 0;">Activar mi cuenta</a>
        <p style="color: #64748b; font-size: 12px; margin-top: 32px;">Este enlace expira en 48 horas. Si no solicitaste esta invitación, ignora este email.</p>
    </div>
    """
    _send_email(to_email, "Activa tu cuenta — SkyBrandMX", html)


def send_2fa_code(to_email: str, code: str):
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto; background: #0f172a; color: #e2e8f0; padding: 40px; border-radius: 16px;">
        <h1 style="color: #2dd4bf; font-size: 24px; margin-bottom: 8px;">SkyBrandMX</h1>
        <p style="color: #94a3b8; font-size: 14px; margin-bottom: 32px;">Verificación de inicio de sesión</p>
        <p style="color: #cbd5e1; line-height: 1.6;">Tu código de verificación es:</p>
        <div style="background: #1e293b; border: 2px solid #2dd4bf; border-radius: 12px; padding: 20px; text-align: center; margin: 24px 0;">
            <span style="font-size: 36px; font-weight: 900; letter-spacing: 8px; color: #fff;">{code}</span>
        </div>
        <p style="color: #64748b; font-size: 12px;">Este código expira en 10 minutos. Si no intentaste iniciar sesión, cambia tu contraseña inmediatamente.</p>
    </div>
    """
    _send_email(to_email, f"Código de verificación: {code} — SkyBrandMX", html)
