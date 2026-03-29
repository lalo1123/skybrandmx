"""Shipping action — generates shipping labels via carrier APIs."""
from ..registry import register_action, ActionContext, ActionResult


@register_action("create_shipping_label")
async def create_shipping_label(ctx: ActionContext) -> ActionResult:
    """Create a shipping label for the order."""
    order_data = ctx.trigger_data
    carrier = ctx.action_config.get("carrier", "auto")
    customer = order_data.get("customer_name", "")
    address = order_data.get("shipping_address", "")

    # TODO: Replace with real Skydropx/DHL/Estafeta API call
    import uuid
    tracking_id = f"TRACK-{carrier.upper()}-{uuid.uuid4().hex[:8].upper()}"

    return ActionResult(
        success=True,
        output={
            "tracking_id": tracking_id,
            "carrier": carrier,
            "customer": customer,
            "address": address,
            "label_url": f"https://labels.skybrandmx.com/{tracking_id}.pdf",
            "message": f"Guía {tracking_id} generada vía {carrier}",
        },
    )
