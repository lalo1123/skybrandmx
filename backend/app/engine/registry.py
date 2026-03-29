"""Action registry and trigger catalog for the automation engine."""
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class ActionContext:
    """Context passed to each action handler."""
    workspace_id: int
    trigger_event: str
    trigger_data: dict
    previous_output: dict
    action_config: dict
    db: Any  # SQLAlchemy Session
    credentials: dict = field(default_factory=dict)


@dataclass
class ActionResult:
    """Result returned by each action handler."""
    success: bool
    output: dict = field(default_factory=dict)
    error: Optional[str] = None


# Registry: maps action type string → handler function
ACTION_REGISTRY: dict[str, Callable] = {}


def register_action(action_type: str):
    """Decorator to register an action handler."""
    def decorator(func: Callable):
        ACTION_REGISTRY[action_type] = func
        return func
    return decorator


# ============================================================
# TRIGGER CATALOG — all events that can start an automation
# ============================================================
TRIGGER_CATALOG = {
    # --- Orders ---
    "order.created": {
        "label": "Nuevo pedido",
        "description": "Se activa cuando entra un pedido nuevo",
        "category": "orders",
        "icon": "📦",
    },
    "order.paid": {
        "label": "Pedido pagado",
        "description": "Se activa cuando se confirma el pago de un pedido",
        "category": "orders",
        "icon": "✅",
    },
    "order.shipped": {
        "label": "Pedido enviado",
        "description": "Se activa cuando un pedido se marca como enviado",
        "category": "orders",
        "icon": "🚚",
    },
    "order.delivered": {
        "label": "Pedido entregado",
        "description": "Se activa cuando la paquetería confirma entrega",
        "category": "orders",
        "icon": "📬",
    },
    "order.cancelled": {
        "label": "Pedido cancelado",
        "description": "Se activa cuando se cancela un pedido",
        "category": "orders",
        "icon": "❌",
    },
    "order.refunded": {
        "label": "Reembolso procesado",
        "description": "Se activa cuando se completa un reembolso",
        "category": "orders",
        "icon": "💸",
    },

    # --- Returns ---
    "return.requested": {
        "label": "Devolución solicitada",
        "description": "Se activa cuando un cliente solicita devolución",
        "category": "orders",
        "icon": "↩️",
    },
    "return.received": {
        "label": "Devolución recibida",
        "description": "Se activa cuando la devolución llega al almacén",
        "category": "orders",
        "icon": "📥",
    },

    # --- Payments ---
    "payment.received": {
        "label": "Pago recibido",
        "description": "Se activa cuando se confirma un pago",
        "category": "billing",
        "icon": "💰",
    },
    "payment.failed": {
        "label": "Pago fallido",
        "description": "Se activa cuando un pago es rechazado",
        "category": "billing",
        "icon": "🚫",
    },

    # --- Invoicing ---
    "invoice.created": {
        "label": "Factura generada",
        "description": "Se activa cuando se crea una factura",
        "category": "billing",
        "icon": "🧾",
    },

    # --- CRM ---
    "customer.created": {
        "label": "Nuevo cliente",
        "description": "Se activa cuando se registra un cliente nuevo",
        "category": "crm",
        "icon": "👤",
    },
    "customer.inactive": {
        "label": "Cliente inactivo",
        "description": "Se activa cuando un cliente no compra en X días",
        "category": "crm",
        "icon": "😴",
    },

    # --- Cart ---
    "cart.abandoned": {
        "label": "Carrito abandonado",
        "description": "Se activa cuando un cliente no completa su compra",
        "category": "orders",
        "icon": "🛒",
    },

    # --- Inventory ---
    "inventory.low": {
        "label": "Stock bajo",
        "description": "Se activa cuando un producto baja del mínimo",
        "category": "inventory",
        "icon": "📉",
    },
    "inventory.out": {
        "label": "Sin stock",
        "description": "Se activa cuando un producto se agota",
        "category": "inventory",
        "icon": "🚨",
    },

    # --- Ads ---
    "ads.budget_exceeded": {
        "label": "Presupuesto de ads excedido",
        "description": "Se activa cuando el gasto supera el límite diario",
        "category": "ads",
        "icon": "💳",
    },

    # --- Time ---
    "cron": {
        "label": "Programado",
        "description": "Se activa en un horario definido (diario, semanal, etc.)",
        "category": "time",
        "icon": "⏰",
    },
}


# ============================================================
# ACTION CATALOG — all actions that can be executed
# ============================================================
ACTION_CATALOG = {
    # --- Billing ---
    "create_invoice": {
        "label": "Crear factura",
        "description": "Genera CFDI 4.0 automáticamente",
        "category": "billing",
        "icon": "🧾",
        "config_fields": [],
    },
    "create_credit_note": {
        "label": "Crear nota de crédito",
        "description": "Genera nota de crédito para cancelar/ajustar factura",
        "category": "billing",
        "icon": "📝",
        "config_fields": [
            {"name": "reason", "label": "Motivo", "type": "select", "options": ["cancellation", "return", "discount", "error"]},
        ],
    },
    "process_refund": {
        "label": "Procesar reembolso",
        "description": "Devuelve el dinero al cliente vía pasarela de pago",
        "category": "billing",
        "icon": "💸",
        "config_fields": [
            {"name": "amount_type", "label": "Monto", "type": "select", "options": ["full", "partial"]},
            {"name": "partial_amount", "label": "Monto parcial", "type": "number", "condition": "amount_type=partial"},
        ],
    },

    # --- Shipping ---
    "create_shipping_label": {
        "label": "Generar guía de envío",
        "description": "Crea guía con la paquetería más conveniente",
        "category": "shipping",
        "icon": "📮",
        "config_fields": [
            {"name": "carrier", "label": "Paquetería", "type": "select", "options": ["auto", "dhl", "estafeta", "fedex", "redpack", "99minutos"]},
        ],
    },
    "cancel_shipping_label": {
        "label": "Cancelar guía de envío",
        "description": "Cancela una guía si el pedido aún no fue enviado",
        "category": "shipping",
        "icon": "🚫",
        "config_fields": [],
    },
    "create_return_label": {
        "label": "Generar guía de devolución",
        "description": "Crea guía para que el cliente devuelva el producto",
        "category": "shipping",
        "icon": "↩️",
        "config_fields": [
            {"name": "carrier", "label": "Paquetería", "type": "select", "options": ["auto", "dhl", "estafeta", "fedex"]},
        ],
    },

    # --- Communication ---
    "send_whatsapp": {
        "label": "Enviar WhatsApp",
        "description": "Envía mensaje por WhatsApp al cliente",
        "category": "communication",
        "icon": "💬",
        "config_fields": [
            {"name": "template", "label": "Plantilla", "type": "select", "options": [
                "order_confirmation", "shipping_update", "delivery_confirmation",
                "cancellation_notice", "refund_notice", "return_instructions",
                "cart_reminder", "inactive_customer", "review_request",
                "payment_failed", "invoice_ready", "custom",
            ]},
            {"name": "custom_message", "label": "Mensaje personalizado", "type": "textarea", "condition": "template=custom"},
        ],
    },
    "send_email": {
        "label": "Enviar email",
        "description": "Envía email al cliente",
        "category": "communication",
        "icon": "📧",
        "config_fields": [
            {"name": "template", "label": "Plantilla", "type": "select", "options": [
                "order_confirmation", "shipping_update", "delivery_confirmation",
                "cancellation_notice", "refund_notice", "return_instructions",
                "cart_reminder", "inactive_offer", "review_request",
                "payment_failed", "invoice_ready", "welcome", "custom",
            ]},
            {"name": "subject", "label": "Asunto", "type": "text"},
        ],
    },
    "send_sms": {
        "label": "Enviar SMS",
        "description": "Envía SMS al cliente",
        "category": "communication",
        "icon": "📱",
        "config_fields": [
            {"name": "message", "label": "Mensaje", "type": "textarea"},
        ],
    },
    "notify_admin": {
        "label": "Notificar al admin",
        "description": "Envía alerta al administrador por WhatsApp o email",
        "category": "communication",
        "icon": "🔔",
        "config_fields": [
            {"name": "channel", "label": "Canal", "type": "select", "options": ["whatsapp", "email", "both"]},
            {"name": "message", "label": "Mensaje", "type": "textarea"},
        ],
    },

    # --- CRM ---
    "update_crm": {
        "label": "Actualizar CRM",
        "description": "Agrega o actualiza contacto en el CRM",
        "category": "crm",
        "icon": "👥",
        "config_fields": [
            {"name": "tag", "label": "Etiqueta", "type": "text"},
        ],
    },
    "apply_discount": {
        "label": "Aplicar descuento",
        "description": "Genera un código de descuento para el cliente",
        "category": "crm",
        "icon": "🏷️",
        "config_fields": [
            {"name": "discount_type", "label": "Tipo", "type": "select", "options": ["percentage", "fixed"]},
            {"name": "amount", "label": "Cantidad (% o $)", "type": "number"},
            {"name": "expires_days", "label": "Vigencia (días)", "type": "number"},
        ],
    },

    # --- Ads ---
    "pause_ad": {
        "label": "Pausar campaña",
        "description": "Pausa una campaña en Meta o Google Ads",
        "category": "ads",
        "icon": "⏸️",
        "config_fields": [
            {"name": "platform", "label": "Plataforma", "type": "select", "options": ["meta", "google"]},
            {"name": "campaign_id", "label": "ID de campaña", "type": "text"},
        ],
    },
    "resume_ad": {
        "label": "Reanudar campaña",
        "description": "Reactiva una campaña pausada",
        "category": "ads",
        "icon": "▶️",
        "config_fields": [
            {"name": "platform", "label": "Plataforma", "type": "select", "options": ["meta", "google"]},
            {"name": "campaign_id", "label": "ID de campaña", "type": "text"},
        ],
    },

    # --- Flow control ---
    "wait": {
        "label": "Esperar",
        "description": "Pausa la cadena X minutos/horas/días antes de continuar",
        "category": "flow",
        "icon": "⏳",
        "config_fields": [
            {"name": "duration", "label": "Duración", "type": "number"},
            {"name": "unit", "label": "Unidad", "type": "select", "options": ["minutes", "hours", "days"]},
        ],
    },
    "condition": {
        "label": "Si/Entonces",
        "description": "Evalúa una condición y ejecuta acciones diferentes según el resultado",
        "category": "flow",
        "icon": "🔀",
        "config_fields": [
            {"name": "field", "label": "Campo a evaluar", "type": "text"},
            {"name": "operator", "label": "Operador", "type": "select", "options": ["eq", "neq", "gt", "lt", "contains"]},
            {"name": "value", "label": "Valor", "type": "text"},
            {"name": "then_action", "label": "Si es verdadero → acción", "type": "select", "options": []},
            {"name": "else_action", "label": "Si es falso → acción", "type": "select", "options": []},
        ],
    },
}

# Condition operators
CONDITION_OPERATORS = {
    "eq": {"label": "es igual a", "type": "any"},
    "neq": {"label": "no es igual a", "type": "any"},
    "gt": {"label": "es mayor que", "type": "number"},
    "gte": {"label": "es mayor o igual que", "type": "number"},
    "lt": {"label": "es menor que", "type": "number"},
    "lte": {"label": "es menor o igual que", "type": "number"},
    "contains": {"label": "contiene", "type": "string"},
    "not_contains": {"label": "no contiene", "type": "string"},
    "is_empty": {"label": "está vacío", "type": "any"},
    "is_not_empty": {"label": "no está vacío", "type": "any"},
}
