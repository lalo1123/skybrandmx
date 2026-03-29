"""Pydantic schemas for automation API."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ConditionSchema(BaseModel):
    field: str
    op: str
    value: str | int | float | bool


class ActionSchema(BaseModel):
    type: str
    config: dict = {}


class AutomationRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_event: str
    trigger_config: Optional[dict] = None
    conditions: Optional[list[ConditionSchema]] = None
    actions: list[ActionSchema]
    is_active: bool = True
    execution_order: int = 0


class AutomationRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_event: Optional[str] = None
    trigger_config: Optional[dict] = None
    conditions: Optional[list[ConditionSchema]] = None
    actions: Optional[list[ActionSchema]] = None
    is_active: Optional[bool] = None
    execution_order: Optional[int] = None


class AutomationRuleResponse(BaseModel):
    id: int
    workspace_id: int
    name: str
    description: Optional[str]
    trigger_event: str
    trigger_config: Optional[str]
    conditions: Optional[str]
    actions: str
    is_active: bool
    execution_order: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AutomationStepLogResponse(BaseModel):
    id: int
    step_index: int
    action_type: str
    status: str
    input_data: Optional[str]
    output_data: Optional[str]
    error_message: Optional[str]
    started_at: datetime
    finished_at: Optional[datetime]

    class Config:
        from_attributes = True


class AutomationLogResponse(BaseModel):
    id: int
    rule_id: int
    trigger_event: str
    trigger_data: Optional[str]
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    error_message: Optional[str]
    steps: list[AutomationStepLogResponse] = []
    rule_name: Optional[str] = None

    class Config:
        from_attributes = True
