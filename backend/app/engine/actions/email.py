"""Email action — sends emails via SMTP."""
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ..registry import register_action, ActionContext, ActionResult


TEMPLATES = {
    "order_confirmation": {
        "subject": "Pedido #{order_id} confirmado",
        "body": "Hola {customer},\n\nTu pedido #{order_id} ha sido confirmado.\nTotal: ${total}\n\nTe avisaremos cuando se envíe.\n\nGracias por tu compra.",
    },
    "shipping_update": {
        "subject": "Tu pedido está en camino",
        "body": "Hola {customer},\n\nTu pedido ya está en camino.\nGuía: {tracking_id}\nPaquetería: {carrier}\n\nRastreo: {label_url}",
    },
    "invoice_ready": {
        "subject": "Tu factura está lista",
        "body": "Hola {customer},\n\nTu factura {invoice_uuid} ha sido generada.\nPuedes descargarla desde tu panel.\n\nGracias.",
    },
    "welcome": {
        "subject": "Bienvenido a {company}",
        "body": "Hola {customer},\n\nGracias por tu primera compra. Estamos para servirte.\n\nSaludos.",
    },
}


@register_action("send_email")
async def send_email(ctx: ActionContext) -> ActionResult:
    """Send an email to the customer."""
    template_key = ctx.action_config.get("template", "order_confirmation")
    custom_subject = ctx.action_config.get("subject", "")

    variables = {**ctx.trigger_data, **ctx.previous_output}
    to_email = variables.get("customer_email") or variables.get("email", "")

    if not to_email:
        return ActionResult(success=False, error="No customer email found")

    template = TEMPLATES.get(template_key, TEMPLATES["order_confirmation"])

    try:
        subject = (custom_subject or template["subject"]).format(**variables)
        body = template["body"].format(**{k: variables.get(k, "") for k in _extract_keys(template["body"])})
    except (KeyError, IndexError):
        subject = template["subject"]
        body = template["body"]

    # Send via SMTP
    try:
        smtp_host = os.getenv("SMTP_HOST", "smtp.hostinger.com")
        smtp_port = int(os.getenv("SMTP_PORT", "465"))
        smtp_user = os.getenv("SMTP_USER", "noreply@skybrandmx.com")
        smtp_pass = os.getenv("SMTP_PASSWORD", "")

        msg = MIMEMultipart("alternative")
        msg["From"] = f"SkyBrandMX <{smtp_user}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        return ActionResult(
            success=True,
            output={
                "email_sent": True,
                "to": to_email,
                "subject": subject,
                "template": template_key,
            },
        )
    except Exception as e:
        return ActionResult(success=False, error=f"Email send failed: {str(e)}")


def _extract_keys(template: str) -> list[str]:
    import re
    return re.findall(r'\{(\w+)\}', template)
