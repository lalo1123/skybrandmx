"""Core automation engine runner — fires events and executes action chains."""
import json
import logging
from datetime import datetime
from ..models.automation import AutomationRule, AutomationLog, AutomationStepLog
from .conditions import evaluate_conditions
from .registry import ACTION_REGISTRY, ActionContext, ActionResult

logger = logging.getLogger("skybrand.engine")


async def fire_event(
    event_type: str,
    event_data: dict,
    workspace_id: int,
    db: Session,
) -> list[dict]:
    """Fire an event and execute all matching automation rules.

    Returns a list of execution summaries.
    """
    # Find all active rules for this workspace and trigger
    rules = (
        db.query(AutomationRule)
        .filter(AutomationRule.workspace_id == workspace_id)
        .filter(AutomationRule.trigger_event == event_type)
        .filter(AutomationRule.is_active == True)
        .order_by(AutomationRule.execution_order)
        .all()
    )

    results = []

    for rule in rules:
        # Evaluate conditions
        if not evaluate_conditions(rule.conditions, event_data):
            logger.info(f"Rule '{rule.name}' skipped: conditions not met")
            continue

        # Create execution log
        log = AutomationLog(
            rule_id=rule.id,
            workspace_id=workspace_id,
            trigger_event=event_type,
            trigger_data=json.dumps(event_data, default=str),
            status="running",
            started_at=datetime.utcnow(),
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        # Parse actions
        try:
            actions = json.loads(rule.actions)
        except (json.JSONDecodeError, TypeError):
            log.status = "failed"
            log.error_message = "Invalid actions JSON"
            log.finished_at = datetime.utcnow()
            db.commit()
            continue

        # Execute action chain
        previous_output = {}
        all_success = True
        step_results = []

        for i, action in enumerate(actions):
            action_type = action.get("type", "")
            action_config = action.get("config", {})

            # Create step log
            step = AutomationStepLog(
                log_id=log.id,
                step_index=i,
                action_type=action_type,
                status="running",
                input_data=json.dumps({"trigger_data": event_data, "previous_output": previous_output, "config": action_config}, default=str),
                started_at=datetime.utcnow(),
            )
            db.add(step)
            db.commit()
            db.refresh(step)

            # Look up handler
            handler = ACTION_REGISTRY.get(action_type)
            if not handler:
                step.status = "failed"
                step.error_message = f"Unknown action type: {action_type}"
                step.finished_at = datetime.utcnow()
                db.commit()
                all_success = False
                step_results.append({"action": action_type, "status": "failed", "error": step.error_message})
                break

            # Build context
            ctx = ActionContext(
                workspace_id=workspace_id,
                trigger_event=event_type,
                trigger_data=event_data,
                previous_output=previous_output,
                action_config=action_config,
                db=db,
            )

            # Execute
            try:
                result: ActionResult = await handler(ctx)
            except Exception as e:
                result = ActionResult(success=False, error=str(e))
                logger.error(f"Action '{action_type}' failed: {e}")

            # Update step log
            step.status = "success" if result.success else "failed"
            step.output_data = json.dumps(result.output, default=str)
            step.error_message = result.error
            step.finished_at = datetime.utcnow()
            db.commit()

            step_results.append({
                "action": action_type,
                "status": step.status,
                "output": result.output,
                "error": result.error,
            })

            if result.success:
                previous_output = result.output
            else:
                all_success = False
                # Mark remaining steps as skipped
                for j in range(i + 1, len(actions)):
                    skip_step = AutomationStepLog(
                        log_id=log.id,
                        step_index=j,
                        action_type=actions[j].get("type", "unknown"),
                        status="skipped",
                        started_at=datetime.utcnow(),
                        finished_at=datetime.utcnow(),
                    )
                    db.add(skip_step)
                db.commit()
                break

        # Update log
        log.status = "success" if all_success else "partial_failure"
        log.finished_at = datetime.utcnow()
        db.commit()

        results.append({
            "rule_id": rule.id,
            "rule_name": rule.name,
            "status": log.status,
            "steps": step_results,
        })

    return results
