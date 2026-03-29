"""CRM actions — update contacts, apply discounts."""
import uuid
from ..registry import register_action, ActionContext, ActionResult


@register_action("update_crm")
async def update_crm(ctx: ActionContext) -> ActionResult:
    """Add or update a contact in the CRM."""
    tag = ctx.action_config.get("tag", "")
    customer = ctx.trigger_data.get("customer_name", "")
    email = ctx.trigger_data.get("customer_email", "")

    # TODO: Update actual CRM database record
    return ActionResult(
        success=True,
        output={
            "crm_updated": True,
            "customer": customer,
            "email": email,
            "tag": tag,
            "message": f"Contacto {customer} actualizado con tag '{tag}'",
        },
    )


@register_action("apply_discount")
async def apply_discount(ctx: ActionContext) -> ActionResult:
    """Generate a discount code for the customer."""
    discount_type = ctx.action_config.get("discount_type", "percentage")
    amount = ctx.action_config.get("amount", 10)
    expires_days = ctx.action_config.get("expires_days", 30)
    customer = ctx.trigger_data.get("customer_name", "")

    code = f"SKY-{uuid.uuid4().hex[:6].upper()}"
    label = f"{amount}%" if discount_type == "percentage" else f"${amount}"

    return ActionResult(
        success=True,
        output={
            "discount_code": code,
            "discount_type": discount_type,
            "amount": amount,
            "expires_days": expires_days,
            "customer": customer,
            "message": f"Cupón {code} de {label} generado para {customer}, vigencia {expires_days} días",
        },
    )
