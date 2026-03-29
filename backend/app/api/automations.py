"""Automation rules and logs API endpoints."""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.deps import get_current_user
from ..models.base import User
from ..models.automation import AutomationRule, AutomationLog, AutomationStepLog
from ..schemas.automation_schemas import (
    AutomationRuleCreate,
    AutomationRuleUpdate,
    AutomationRuleResponse,
    AutomationLogResponse,
    AutomationStepLogResponse,
)
from ..engine.registry import TRIGGER_CATALOG, ACTION_CATALOG, CONDITION_OPERATORS

router = APIRouter()


# ===== CATALOG =====

@router.get("/catalog")
def get_catalog(current_user: User = Depends(get_current_user)):
    """Get available triggers, actions, and condition operators."""
    return {
        "triggers": TRIGGER_CATALOG,
        "actions": ACTION_CATALOG,
        "condition_operators": CONDITION_OPERATORS,
    }


# ===== RULES CRUD =====

@router.get("/rules", response_model=list[AutomationRuleResponse])
def list_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all automation rules for the workspace."""
    rules = (
        db.query(AutomationRule)
        .filter(AutomationRule.workspace_id == current_user.workspace_id)
        .order_by(AutomationRule.execution_order, AutomationRule.created_at.desc())
        .all()
    )
    return rules


@router.post("/rules", response_model=AutomationRuleResponse)
def create_rule(
    data: AutomationRuleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new automation rule."""
    if data.trigger_event not in TRIGGER_CATALOG:
        raise HTTPException(400, f"Invalid trigger: {data.trigger_event}")

    for action in data.actions:
        if action.type not in ACTION_CATALOG:
            raise HTTPException(400, f"Invalid action: {action.type}")

    rule = AutomationRule(
        workspace_id=current_user.workspace_id,
        name=data.name,
        description=data.description,
        trigger_event=data.trigger_event,
        trigger_config=json.dumps(data.trigger_config) if data.trigger_config else None,
        conditions=json.dumps([c.model_dump() for c in data.conditions]) if data.conditions else None,
        actions=json.dumps([a.model_dump() for a in data.actions]),
        is_active=data.is_active,
        execution_order=data.execution_order,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/rules/{rule_id}", response_model=AutomationRuleResponse)
def get_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single rule."""
    rule = db.get(AutomationRule, rule_id)
    if not rule or rule.workspace_id != current_user.workspace_id:
        raise HTTPException(404, "Rule not found")
    return rule


@router.put("/rules/{rule_id}", response_model=AutomationRuleResponse)
def update_rule(
    rule_id: int,
    data: AutomationRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an automation rule."""
    rule = db.get(AutomationRule, rule_id)
    if not rule or rule.workspace_id != current_user.workspace_id:
        raise HTTPException(404, "Rule not found")

    update_data = data.model_dump(exclude_unset=True)

    if "conditions" in update_data and update_data["conditions"] is not None:
        update_data["conditions"] = json.dumps([c.model_dump() if hasattr(c, 'model_dump') else c for c in update_data["conditions"]])
    if "actions" in update_data and update_data["actions"] is not None:
        update_data["actions"] = json.dumps([a.model_dump() if hasattr(a, 'model_dump') else a for a in update_data["actions"]])
    if "trigger_config" in update_data and update_data["trigger_config"] is not None:
        update_data["trigger_config"] = json.dumps(update_data["trigger_config"])

    for key, value in update_data.items():
        setattr(rule, key, value)

    rule.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an automation rule."""
    rule = db.get(AutomationRule, rule_id)
    if not rule or rule.workspace_id != current_user.workspace_id:
        raise HTTPException(404, "Rule not found")
    db.delete(rule)
    db.commit()
    return {"ok": True, "message": f"Rule '{rule.name}' deleted"}


@router.patch("/rules/{rule_id}/toggle", response_model=AutomationRuleResponse)
def toggle_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle a rule's active state."""
    rule = db.get(AutomationRule, rule_id)
    if not rule or rule.workspace_id != current_user.workspace_id:
        raise HTTPException(404, "Rule not found")
    rule.is_active = not rule.is_active
    rule.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(rule)
    return rule


# ===== LOGS =====

@router.get("/logs", response_model=list[AutomationLogResponse])
def list_logs(
    rule_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List automation execution logs."""
    query = (
        db.query(AutomationLog)
        .filter(AutomationLog.workspace_id == current_user.workspace_id)
        .order_by(AutomationLog.started_at.desc())
        .limit(limit)
    )
    if rule_id:
        query = query.filter(AutomationLog.rule_id == rule_id)
    if status:
        query = query.filter(AutomationLog.status == status)

    logs = query.all()

    result = []
    for log in logs:
        steps = (
            db.query(AutomationStepLog)
            .filter(AutomationStepLog.log_id == log.id)
            .order_by(AutomationStepLog.step_index)
            .all()
        )

        rule = db.query(AutomationRule).get(log.rule_id)

        result.append(AutomationLogResponse(
            id=log.id,
            rule_id=log.rule_id,
            trigger_event=log.trigger_event,
            trigger_data=log.trigger_data,
            status=log.status,
            started_at=log.started_at,
            finished_at=log.finished_at,
            error_message=log.error_message,
            rule_name=rule.name if rule else None,
            steps=[AutomationStepLogResponse(
                id=s.id,
                step_index=s.step_index,
                action_type=s.action_type,
                status=s.status,
                input_data=s.input_data,
                output_data=s.output_data,
                error_message=s.error_message,
                started_at=s.started_at,
                finished_at=s.finished_at,
            ) for s in steps],
        ))

    return result


# ===== TEST EVENT =====

@router.post("/test")
async def test_event(
    event_type: str = "order.created",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fire a test event with mock data to test automation rules."""
    from ..engine.runner import fire_event

    base_customer = {
        "customer_name": "Cliente de Prueba",
        "customer_email": current_user.email,
        "customer_phone": "5525582310",
        "shipping_address": "Av. Reforma 123, CDMX",
    }
    mock_data = {
        "order.created": {**base_customer, "order_id": "TEST-001", "total_amount": 1500.00, "currency": "MXN", "items": [{"name": "Producto Demo", "qty": 1, "price": 1500}]},
        "order.paid": {**base_customer, "order_id": "TEST-001", "total_amount": 1500.00, "payment_method": "card"},
        "order.shipped": {**base_customer, "order_id": "TEST-001", "tracking_id": "TRACK-TEST-12345", "carrier": "dhl", "label_url": "https://labels.skybrandmx.com/TRACK-TEST-12345.pdf"},
        "order.delivered": {**base_customer, "order_id": "TEST-001", "tracking_id": "TRACK-TEST-12345", "delivered_at": "2026-03-28T14:00:00"},
        "order.cancelled": {**base_customer, "order_id": "TEST-001", "total_amount": 1500.00, "cancel_reason": "Cliente lo solicitó", "invoice_uuid": "CFDI-TEST123"},
        "order.refunded": {**base_customer, "order_id": "TEST-001", "total_amount": 1500.00, "refund_amount": 1500.00},
        "return.requested": {**base_customer, "order_id": "TEST-001", "return_reason": "Producto defectuoso", "items": [{"name": "Producto Demo", "qty": 1}]},
        "return.received": {**base_customer, "order_id": "TEST-001", "return_tracking": "RET-TEST-001"},
        "payment.received": {**base_customer, "order_id": "TEST-001", "total_amount": 1500.00, "payment_method": "transfer"},
        "payment.failed": {**base_customer, "order_id": "TEST-001", "total_amount": 1500.00, "error": "Fondos insuficientes"},
        "invoice.created": {**base_customer, "invoice_uuid": "CFDI-TEST123", "total_amount": 1500.00},
        "customer.created": {"customer_name": "Nuevo Cliente", "customer_email": "nuevo@ejemplo.com", "customer_phone": "5512345678"},
        "customer.inactive": {**base_customer, "days_inactive": 45, "last_purchase": "2026-02-10"},
        "cart.abandoned": {**base_customer, "cart_total": 2300.00, "items": [{"name": "Producto A", "qty": 2}, {"name": "Producto B", "qty": 1}], "abandoned_minutes": 35},
        "inventory.low": {"product_name": "Producto Demo", "sku": "SKU-001", "current_stock": 3, "min_stock": 5},
        "inventory.out": {"product_name": "Producto Demo", "sku": "SKU-001", "current_stock": 0},
        "ads.budget_exceeded": {"platform": "meta", "campaign_name": "Campaña Verano", "campaign_id": "123456", "daily_budget": 500, "spent_today": 520},
    }

    data = mock_data.get(event_type, {"test": True, "event": event_type})

    results = await fire_event(event_type, data, current_user.workspace_id, db)

    return {
        "event_type": event_type,
        "mock_data": data,
        "results": results,
        "rules_triggered": len(results),
    }
