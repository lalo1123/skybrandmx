"""Invoice action — generates CFDI 4.0 via SAT integration."""
from ..registry import register_action, ActionContext, ActionResult


@register_action("create_invoice")
async def create_invoice(ctx: ActionContext) -> ActionResult:
    """Create a CFDI 4.0 invoice for the order."""
    order_data = ctx.trigger_data
    customer = order_data.get("customer_name", "Público en General")
    total = order_data.get("total_amount", 0)
    email = order_data.get("customer_email", "")

    # TODO: Replace with real Facturama/SAT API call
    # For now, generate a mock invoice UUID
    import uuid
    invoice_uuid = f"CFDI-{uuid.uuid4().hex[:12].upper()}"

    return ActionResult(
        success=True,
        output={
            "invoice_uuid": invoice_uuid,
            "customer": customer,
            "total": total,
            "email": email,
            "status": "timbrado",
            "message": f"Factura {invoice_uuid} generada para {customer} por ${total}",
        },
    )
