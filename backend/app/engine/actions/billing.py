"""Billing actions — credit notes and refunds."""
import uuid
from ..registry import register_action, ActionContext, ActionResult


@register_action("create_credit_note")
async def create_credit_note(ctx: ActionContext) -> ActionResult:
    """Create a credit note to cancel/adjust an invoice."""
    reason = ctx.action_config.get("reason", "cancellation")
    invoice_uuid = ctx.previous_output.get("invoice_uuid") or ctx.trigger_data.get("invoice_uuid", "")
    total = ctx.trigger_data.get("total_amount", 0)

    # TODO: Connect to Facturama API for real credit note
    credit_note_uuid = f"NC-{uuid.uuid4().hex[:12].upper()}"

    reason_labels = {
        "cancellation": "Cancelación de pedido",
        "return": "Devolución de producto",
        "discount": "Ajuste de precio",
        "error": "Error en facturación",
    }

    return ActionResult(
        success=True,
        output={
            "credit_note_uuid": credit_note_uuid,
            "original_invoice": invoice_uuid,
            "reason": reason_labels.get(reason, reason),
            "amount": total,
            "message": f"Nota de crédito {credit_note_uuid} generada por {reason_labels.get(reason, reason)}",
        },
    )


@register_action("process_refund")
async def process_refund(ctx: ActionContext) -> ActionResult:
    """Process a refund via payment gateway."""
    amount_type = ctx.action_config.get("amount_type", "full")
    total = ctx.trigger_data.get("total_amount", 0)
    partial = ctx.action_config.get("partial_amount", 0)
    amount = total if amount_type == "full" else float(partial)
    customer = ctx.trigger_data.get("customer_name", "")

    # TODO: Connect to Stripe/Mercado Pago API for real refund
    refund_id = f"REF-{uuid.uuid4().hex[:8].upper()}"

    return ActionResult(
        success=True,
        output={
            "refund_id": refund_id,
            "amount": amount,
            "amount_type": amount_type,
            "customer": customer,
            "message": f"Reembolso {refund_id} de ${amount} procesado para {customer}",
        },
    )
