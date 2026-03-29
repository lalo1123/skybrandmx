"""WhatsApp action — sends messages via WhatsApp Cloud API."""
from ..registry import register_action, ActionContext, ActionResult


TEMPLATES = {
    "order_confirmation": "Hola {customer}, tu pedido #{order_id} ha sido confirmado. Total: ${total}. Te avisamos cuando se envíe.",
    "shipping_update": "Hola {customer}, tu pedido ya está en camino. Guía: {tracking_id}. Rastreo: {label_url}",
    "invoice_ready": "Hola {customer}, tu factura {invoice_uuid} está lista. La puedes descargar en tu panel.",
    "custom": "{custom_message}",
}


@register_action("send_whatsapp")
async def send_whatsapp(ctx: ActionContext) -> ActionResult:
    """Send a WhatsApp message to the customer."""
    template_key = ctx.action_config.get("template", "order_confirmation")
    custom_msg = ctx.action_config.get("custom_message", "")

    # Merge trigger data + previous action output for template variables
    variables = {**ctx.trigger_data, **ctx.previous_output}
    variables["custom_message"] = custom_msg

    template = TEMPLATES.get(template_key, TEMPLATES["order_confirmation"])

    try:
        message = template.format(**{k: variables.get(k, "") for k in _extract_keys(template)})
    except (KeyError, IndexError):
        message = template

    phone = ctx.trigger_data.get("customer_phone", "")

    # TODO: Replace with real WhatsApp Cloud API call
    # POST https://graph.facebook.com/v18.0/{phone_id}/messages
    # Headers: Authorization: Bearer {access_token}
    # Body: {"messaging_product":"whatsapp","to":phone,"type":"text","text":{"body":message}}

    return ActionResult(
        success=True,
        output={
            "whatsapp_sent": True,
            "phone": phone,
            "message": message,
            "template": template_key,
        },
    )


def _extract_keys(template: str) -> list[str]:
    """Extract {key} placeholders from a template string."""
    import re
    return re.findall(r'\{(\w+)\}', template)
