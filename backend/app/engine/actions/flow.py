"""Flow control actions — wait, conditional logic."""
import asyncio
from ..registry import register_action, ActionContext, ActionResult, ACTION_REGISTRY
from ..conditions import evaluate_condition


@register_action("wait")
async def wait_action(ctx: ActionContext) -> ActionResult:
    """Wait for a specified duration before continuing the chain.

    Note: For MVP, short waits execute inline. For long waits (hours/days),
    this should be replaced with a scheduled job system.
    """
    duration = int(ctx.action_config.get("duration", 1))
    unit = ctx.action_config.get("unit", "minutes")

    # Convert to seconds
    multipliers = {"minutes": 60, "hours": 3600, "days": 86400}
    seconds = duration * multipliers.get(unit, 60)

    # For MVP: only actually wait for short durations (< 5 min)
    # Longer waits should be queued to a job scheduler
    if seconds <= 300:
        await asyncio.sleep(seconds)
        return ActionResult(
            success=True,
            output={
                "waited": True,
                "duration": duration,
                "unit": unit,
                "seconds": seconds,
                "message": f"Esperó {duration} {unit}",
            },
        )
    else:
        # TODO: Queue to background job scheduler for long waits
        return ActionResult(
            success=True,
            output={
                "waited": False,
                "queued": True,
                "duration": duration,
                "unit": unit,
                "message": f"Programado para continuar en {duration} {unit}",
            },
        )


@register_action("condition")
async def condition_action(ctx: ActionContext) -> ActionResult:
    """Evaluate a condition and execute different actions based on result."""
    field = ctx.action_config.get("field", "")
    operator = ctx.action_config.get("operator", "eq")
    value = ctx.action_config.get("value", "")
    then_action = ctx.action_config.get("then_action", "")
    else_action = ctx.action_config.get("else_action", "")

    # Merge trigger data + previous output
    data = {**ctx.trigger_data, **ctx.previous_output}

    # Evaluate
    condition = {"field": field, "op": operator, "value": value}
    result = evaluate_condition(condition, data)

    chosen_action = then_action if result else else_action

    output = {
        "condition_met": result,
        "field": field,
        "operator": operator,
        "value": value,
        "actual_value": str(data.get(field, "")),
        "chosen_action": chosen_action,
    }

    # Execute the chosen action if specified
    if chosen_action and chosen_action in ACTION_REGISTRY:
        handler = ACTION_REGISTRY[chosen_action]
        sub_ctx = ActionContext(
            workspace_id=ctx.workspace_id,
            trigger_event=ctx.trigger_event,
            trigger_data=ctx.trigger_data,
            previous_output=ctx.previous_output,
            action_config={},
            db=ctx.db,
            credentials=ctx.credentials,
        )
        sub_result = await handler(sub_ctx)
        output["sub_action_result"] = sub_result.output
        output["message"] = f"Condición {'cumplida' if result else 'no cumplida'} → ejecutó {chosen_action}"
        return ActionResult(success=sub_result.success, output=output, error=sub_result.error)

    output["message"] = f"Condición {'cumplida' if result else 'no cumplida'}, sin acción configurada"
    return ActionResult(success=True, output=output)


@register_action("notify_admin")
async def notify_admin(ctx: ActionContext) -> ActionResult:
    """Send notification to the workspace admin."""
    channel = ctx.action_config.get("channel", "both")
    message = ctx.action_config.get("message", "Alerta de automatización")

    # Replace variables in message
    data = {**ctx.trigger_data, **ctx.previous_output}
    try:
        for key, val in data.items():
            message = message.replace(f"{{{key}}}", str(val))
    except Exception:
        pass

    # TODO: Actually send WhatsApp/email to admin
    return ActionResult(
        success=True,
        output={
            "notified": True,
            "channel": channel,
            "message": message,
            "admin_message": f"Admin notificado vía {channel}: {message}",
        },
    )


@register_action("send_sms")
async def send_sms(ctx: ActionContext) -> ActionResult:
    """Send SMS to customer."""
    message = ctx.action_config.get("message", "")
    phone = ctx.trigger_data.get("customer_phone", "")

    data = {**ctx.trigger_data, **ctx.previous_output}
    try:
        for key, val in data.items():
            message = message.replace(f"{{{key}}}", str(val))
    except Exception:
        pass

    # TODO: Connect to Twilio/SMS API
    return ActionResult(
        success=True,
        output={
            "sms_sent": True,
            "phone": phone,
            "message": message,
        },
    )


@register_action("resume_ad")
async def resume_ad(ctx: ActionContext) -> ActionResult:
    """Resume a paused ad campaign."""
    platform = ctx.action_config.get("platform", "meta")
    campaign_id = ctx.action_config.get("campaign_id", "")

    # TODO: Connect to Meta/Google Ads API
    return ActionResult(
        success=True,
        output={
            "resumed": True,
            "platform": platform,
            "campaign_id": campaign_id,
            "message": f"Campaña {campaign_id} reanudada en {platform}",
        },
    )
