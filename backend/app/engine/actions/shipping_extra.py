"""Extra shipping actions — cancel labels and return labels."""
import uuid
from ..registry import register_action, ActionContext, ActionResult


@register_action("cancel_shipping_label")
async def cancel_shipping_label(ctx: ActionContext) -> ActionResult:
    """Cancel a shipping label if order hasn't been sent yet."""
    tracking_id = ctx.previous_output.get("tracking_id") or ctx.trigger_data.get("tracking_id", "")

    # TODO: Connect to Skydropx/carrier API to cancel
    return ActionResult(
        success=True,
        output={
            "cancelled": True,
            "tracking_id": tracking_id,
            "message": f"Guía {tracking_id} cancelada exitosamente",
        },
    )


@register_action("create_return_label")
async def create_return_label(ctx: ActionContext) -> ActionResult:
    """Create a return shipping label for the customer."""
    carrier = ctx.action_config.get("carrier", "auto")
    customer = ctx.trigger_data.get("customer_name", "")
    address = ctx.trigger_data.get("shipping_address", "")

    # TODO: Connect to carrier API for real return label
    return_tracking = f"RET-{carrier.upper()}-{uuid.uuid4().hex[:8].upper()}"

    return ActionResult(
        success=True,
        output={
            "return_tracking_id": return_tracking,
            "carrier": carrier,
            "customer": customer,
            "label_url": f"https://labels.skybrandmx.com/return/{return_tracking}.pdf",
            "message": f"Guía de devolución {return_tracking} generada para {customer}",
        },
    )
