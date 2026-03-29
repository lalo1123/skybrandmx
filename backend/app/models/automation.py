"""Automation engine database models."""
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship


class AutomationRule(SQLModel, table=True):
    """User-defined automation rule: trigger + conditions + action chain."""
    __tablename__ = "automation_rules"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(index=True, foreign_key="workspace.id")
    name: str = Field(index=True)
    description: Optional[str] = None
    trigger_event: str = Field(index=True)  # e.g. "order.created"
    trigger_config: Optional[str] = None    # JSON: cron expression, webhook filters
    conditions: Optional[str] = None        # JSON: [{"field":"total","op":"gt","value":500}]
    actions: str                            # JSON: [{"type":"create_invoice","config":{}}]
    is_active: bool = Field(default=True)
    execution_order: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    logs: list["AutomationLog"] = Relationship(back_populates="rule")


class AutomationLog(SQLModel, table=True):
    """Tracks each execution of a rule."""
    __tablename__ = "automation_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    rule_id: int = Field(foreign_key="automation_rules.id", index=True)
    workspace_id: int = Field(index=True, foreign_key="workspace.id")
    trigger_event: str
    trigger_data: Optional[str] = None      # JSON snapshot of event payload
    status: str = Field(default="running")  # running, success, partial_failure, failed
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None

    rule: Optional[AutomationRule] = Relationship(back_populates="logs")
    steps: list["AutomationStepLog"] = Relationship(back_populates="log")


class AutomationStepLog(SQLModel, table=True):
    """Tracks each action step within a rule execution."""
    __tablename__ = "automation_step_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    log_id: int = Field(foreign_key="automation_logs.id", index=True)
    step_index: int
    action_type: str
    status: str = Field(default="pending")  # pending, running, success, failed, skipped
    input_data: Optional[str] = None        # JSON
    output_data: Optional[str] = None       # JSON
    error_message: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None

    log: Optional[AutomationLog] = Relationship(back_populates="steps")
