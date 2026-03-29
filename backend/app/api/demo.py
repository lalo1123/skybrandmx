"""Demo data and store simulator endpoints."""
import json
import random
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.deps import get_current_user
from ..models.base import User
from ..models.automation import AutomationRule
from ..models.crm import Contact

router = APIRouter()

# ===== DEMO SEED DATA =====

DEMO_PRODUCTS = [
    {"sku": "SKU-001", "name": "Camiseta Básica Negra", "price": 299, "stock": 45, "category": "ropa", "image": "👕"},
    {"sku": "SKU-002", "name": "Sudadera Premium Gris", "price": 799, "stock": 23, "category": "ropa", "image": "🧥"},
    {"sku": "SKU-003", "name": "Tenis Running Pro", "price": 1499, "stock": 12, "category": "calzado", "image": "👟"},
    {"sku": "SKU-004", "name": "Mochila Urbana 25L", "price": 599, "stock": 34, "category": "accesorios", "image": "🎒"},
    {"sku": "SKU-005", "name": "Gorra Snapback Logo", "price": 349, "stock": 67, "category": "accesorios", "image": "🧢"},
    {"sku": "SKU-006", "name": "Pantalón Jogger Slim", "price": 649, "stock": 28, "category": "ropa", "image": "👖"},
    {"sku": "SKU-007", "name": "Reloj Digital Sport", "price": 1199, "stock": 8, "category": "accesorios", "image": "⌚"},
    {"sku": "SKU-008", "name": "Lentes de Sol UV400", "price": 499, "stock": 41, "category": "accesorios", "image": "🕶️"},
    {"sku": "SKU-009", "name": "Playera Oversize White", "price": 399, "stock": 52, "category": "ropa", "image": "👕"},
    {"sku": "SKU-010", "name": "Botella Térmica 750ml", "price": 249, "stock": 89, "category": "accesorios", "image": "🧴"},
]

DEMO_CUSTOMERS = [
    {"name": "María García López", "email": "maria.garcia@gmail.com", "phone": "5512345678", "state": "CDMX"},
    {"name": "Carlos Rodríguez Pérez", "email": "carlos.rdz@hotmail.com", "phone": "8112345678", "state": "Nuevo León"},
    {"name": "Ana Martínez Flores", "email": "ana.mf@outlook.com", "phone": "3312345678", "state": "Jalisco"},
    {"name": "Roberto Hernández Díaz", "email": "roberto.hd@gmail.com", "phone": "2212345678", "state": "Puebla"},
    {"name": "Laura Sánchez Torres", "email": "laura.st@yahoo.com", "phone": "6622345678", "state": "Sonora"},
    {"name": "Diego Ramírez Vargas", "email": "diego.rv@gmail.com", "phone": "9981234567", "state": "Quintana Roo"},
    {"name": "Sofía López Cruz", "email": "sofia.lc@hotmail.com", "phone": "4421234567", "state": "Querétaro"},
    {"name": "Fernando Morales Ruiz", "email": "fer.mr@gmail.com", "phone": "2281234567", "state": "Veracruz"},
    {"name": "Valentina Castillo Ríos", "email": "vale.cr@outlook.com", "phone": "6141234567", "state": "Chihuahua"},
    {"name": "Alejandro Jiménez Luna", "email": "alex.jl@gmail.com", "phone": "7771234567", "state": "Morelos"},
]

CARRIERS = ["DHL", "Estafeta", "FedEx", "Redpack", "99Minutos"]
PAYMENT_METHODS = ["Tarjeta Visa ****4521", "Tarjeta MC ****8876", "Mercado Pago", "Transferencia SPEI", "PayPal", "Oxxo Pay"]
STORES = ["Shopify", "Mercado Libre", "WooCommerce"]
STATUSES = ["pending", "paid", "shipped", "delivered", "cancelled"]


def _generate_demo_orders(count: int = 25):
    """Generate realistic demo orders."""
    orders = []
    now = datetime.utcnow()

    for i in range(count):
        customer = random.choice(DEMO_CUSTOMERS)
        num_items = random.randint(1, 3)
        items = random.sample(DEMO_PRODUCTS, num_items)
        total = sum(p["price"] * random.randint(1, 2) for p in items)
        status = random.choices(STATUSES, weights=[10, 20, 30, 25, 5])[0]
        days_ago = random.randint(0, 30)
        order_date = now - timedelta(days=days_ago, hours=random.randint(0, 23), minutes=random.randint(0, 59))

        order = {
            "order_id": f"ORD-{1000 + i}",
            "store": random.choice(STORES),
            "customer": customer,
            "items": [
                {"sku": p["sku"], "name": p["name"], "price": p["price"], "qty": random.randint(1, 2), "image": p["image"]}
                for p in items
            ],
            "total_amount": total,
            "currency": "MXN",
            "payment_method": random.choice(PAYMENT_METHODS),
            "payment_status": "paid" if status != "pending" else "pending",
            "fulfillment_status": status,
            "shipping": None,
            "invoice": None,
            "order_date": order_date.isoformat(),
            "days_ago": days_ago,
        }

        # Add shipping info for shipped/delivered
        if status in ("shipped", "delivered"):
            carrier = random.choice(CARRIERS)
            order["shipping"] = {
                "carrier": carrier,
                "tracking_id": f"TRACK-{carrier[:3].upper()}-{uuid.uuid4().hex[:8].upper()}",
                "shipped_date": (order_date + timedelta(days=1)).isoformat(),
                "delivered_date": (order_date + timedelta(days=random.randint(2, 5))).isoformat() if status == "delivered" else None,
            }

        # Add invoice for paid/shipped/delivered
        if status in ("paid", "shipped", "delivered") and random.random() > 0.3:
            order["invoice"] = {
                "uuid": f"CFDI-{uuid.uuid4().hex[:12].upper()}",
                "status": "timbrado",
                "created_at": (order_date + timedelta(hours=1)).isoformat(),
            }

        orders.append(order)

    # Sort by date, most recent first
    orders.sort(key=lambda x: x["order_date"], reverse=True)
    return orders


def _generate_demo_stats(orders: list):
    """Generate dashboard stats from demo orders."""
    total_revenue = sum(o["total_amount"] for o in orders if o["payment_status"] == "paid")
    total_orders = len(orders)
    shipped = sum(1 for o in orders if o["fulfillment_status"] in ("shipped", "delivered"))
    invoiced = sum(1 for o in orders if o["invoice"])
    customers = len(set(o["customer"]["email"] for o in orders))

    # Weekly breakdown
    now = datetime.utcnow()
    weekly = []
    for week in range(8):
        week_start = now - timedelta(weeks=week + 1)
        week_end = now - timedelta(weeks=week)
        week_orders = [o for o in orders if week_start.isoformat() <= o["order_date"] <= week_end.isoformat()]
        weekly.append({
            "week": f"S{8 - week}",
            "revenue": sum(o["total_amount"] for o in week_orders if o["payment_status"] == "paid"),
            "orders": len(week_orders),
        })
    weekly.reverse()

    return {
        "revenue": total_revenue,
        "revenue_change": round(random.uniform(8, 28), 1),
        "orders": total_orders,
        "orders_change": round(random.uniform(5, 20), 1),
        "customers": customers,
        "customers_change": round(random.uniform(10, 35), 1),
        "invoices": invoiced,
        "invoices_change": round(random.uniform(5, 25), 1),
        "shipped": shipped,
        "weekly": weekly,
    }


@router.post("/seed")
def seed_demo_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate demo data for the dashboard."""
    orders = _generate_demo_orders(25)
    stats = _generate_demo_stats(orders)

    # Create some default automation rules if none exist
    existing = db.query(AutomationRule).filter(
        AutomationRule.workspace_id == current_user.workspace_id
    ).count()

    templates = []
    if existing == 0:
        default_rules = [
            {
                "name": "Auto-facturar pedidos nuevos",
                "description": "Genera CFDI automáticamente cuando entra un pedido pagado",
                "trigger_event": "order.paid",
                "actions": json.dumps([
                    {"type": "create_invoice", "config": {}},
                    {"type": "send_email", "config": {"template": "invoice_ready", "subject": "Tu factura está lista"}},
                ]),
            },
            {
                "name": "Notificar envío por WhatsApp",
                "description": "Envía WhatsApp con guía de rastreo cuando el pedido se envía",
                "trigger_event": "order.shipped",
                "actions": json.dumps([
                    {"type": "send_whatsapp", "config": {"template": "shipping_update"}},
                    {"type": "send_email", "config": {"template": "shipping_update", "subject": "Tu pedido está en camino"}},
                ]),
            },
            {
                "name": "Recuperar carrito abandonado",
                "description": "Envía recordatorio cuando un cliente abandona su carrito",
                "trigger_event": "cart.abandoned",
                "actions": json.dumps([
                    {"type": "wait", "config": {"duration": 30, "unit": "minutes"}},
                    {"type": "send_whatsapp", "config": {"template": "cart_reminder"}},
                    {"type": "apply_discount", "config": {"discount_type": "percentage", "amount": 10, "expires_days": 3}},
                ]),
            },
            {
                "name": "Gestionar cancelación",
                "description": "Nota de crédito + reembolso + notificación cuando se cancela un pedido",
                "trigger_event": "order.cancelled",
                "actions": json.dumps([
                    {"type": "create_credit_note", "config": {"reason": "cancellation"}},
                    {"type": "process_refund", "config": {"amount_type": "full"}},
                    {"type": "send_whatsapp", "config": {"template": "cancellation_notice"}},
                    {"type": "send_email", "config": {"template": "cancellation_notice", "subject": "Tu pedido fue cancelado"}},
                ]),
            },
            {
                "name": "Alerta stock bajo",
                "description": "Notifica al admin cuando un producto baja del mínimo",
                "trigger_event": "inventory.low",
                "actions": json.dumps([
                    {"type": "notify_admin", "config": {"channel": "whatsapp", "message": "⚠️ Stock bajo: {product_name} ({current_stock} unidades)"}},
                ]),
            },
            {
                "name": "Pedir review post-entrega",
                "description": "Pide reseña al cliente cuando recibe su pedido",
                "trigger_event": "order.delivered",
                "actions": json.dumps([
                    {"type": "wait", "config": {"duration": 2, "unit": "days"}},
                    {"type": "send_whatsapp", "config": {"template": "review_request"}},
                    {"type": "update_crm", "config": {"tag": "comprador-recurrente"}},
                ]),
            },
        ]

        for rule_data in default_rules:
            rule = AutomationRule(
                workspace_id=current_user.workspace_id,
                is_active=True,
                **rule_data,
            )
            db.add(rule)
            templates.append(rule_data["name"])

        db.commit()

    # Seed CRM contacts if none exist
    contacts_created = 0
    existing_contacts = db.query(Contact).filter(Contact.workspace_id == current_user.workspace_id).count()
    if existing_contacts == 0:
        tags_pool = ["lead", "cliente", "vip", "newsletter", "shopify", "mercadolibre", "recurrente", "nuevo"]
        sources_pool = ["shopify", "mercadolibre", "woocommerce", "manual", "import"]
        now = datetime.utcnow()

        for cust in DEMO_CUSTOMERS:
            days_ago = random.randint(1, 90)
            num_orders = random.randint(0, 12)
            spent = round(random.uniform(0, 15000), 2) if num_orders > 0 else 0
            cust_tags = random.sample(tags_pool, random.randint(1, 3))

            contact = Contact(
                workspace_id=current_user.workspace_id,
                email=cust["email"],
                phone=cust["phone"],
                first_name=cust["name"].split()[0],
                last_name=" ".join(cust["name"].split()[1:]),
                company=random.choice([None, f"Empresa de {cust['name'].split()[0]}", None]),
                state=cust["state"],
                tags=json.dumps(cust_tags),
                source=random.choice(sources_pool),
                total_orders=num_orders,
                total_spent=spent,
                last_order_date=(now - timedelta(days=random.randint(1, 30))) if num_orders > 0 else None,
                notes=json.dumps([{"text": f"Contacto importado desde demo", "date": now.isoformat(), "by": "Sistema"}]),
                created_at=now - timedelta(days=days_ago),
            )
            db.add(contact)
            contacts_created += 1

        db.commit()

    return {
        "success": True,
        "orders": orders,
        "products": DEMO_PRODUCTS,
        "customers": DEMO_CUSTOMERS,
        "stats": stats,
        "automation_templates_created": templates,
        "contacts_created": contacts_created,
        "message": f"Demo data generated: {len(orders)} orders, {len(DEMO_PRODUCTS)} products, {len(DEMO_CUSTOMERS)} customers"
            + (f", {len(templates)} automation rules created" if templates else "")
            + (f", {contacts_created} CRM contacts created" if contacts_created else ""),
    }


# ===== STORE SIMULATOR =====

@router.post("/simulate/{event_type}")
async def simulate_event(
    event_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Simulate a store event and trigger automations in real-time."""
    from ..engine.runner import fire_event

    customer = random.choice(DEMO_CUSTOMERS)
    products = random.sample(DEMO_PRODUCTS, random.randint(1, 3))
    total = sum(p["price"] for p in products)
    order_id = f"SIM-{uuid.uuid4().hex[:6].upper()}"

    event_data_map = {
        "order.created": {
            "order_id": order_id,
            "customer_name": customer["name"],
            "customer_email": customer["email"],
            "customer_phone": customer["phone"],
            "total_amount": total,
            "currency": "MXN",
            "store": random.choice(STORES),
            "items": [{"name": p["name"], "price": p["price"], "qty": 1, "image": p["image"]} for p in products],
            "shipping_address": f"Calle Demo 123, {customer['state']}",
        },
        "order.paid": {
            "order_id": order_id,
            "customer_name": customer["name"],
            "customer_email": customer["email"],
            "customer_phone": customer["phone"],
            "total_amount": total,
            "payment_method": random.choice(PAYMENT_METHODS),
        },
        "order.shipped": {
            "order_id": order_id,
            "customer_name": customer["name"],
            "customer_email": customer["email"],
            "customer_phone": customer["phone"],
            "tracking_id": f"TRACK-{random.choice(CARRIERS)[:3].upper()}-{uuid.uuid4().hex[:8].upper()}",
            "carrier": random.choice(CARRIERS),
            "label_url": f"https://labels.skybrandmx.com/{uuid.uuid4().hex[:8]}.pdf",
        },
        "order.delivered": {
            "order_id": order_id,
            "customer_name": customer["name"],
            "customer_email": customer["email"],
            "customer_phone": customer["phone"],
            "tracking_id": f"TRACK-{uuid.uuid4().hex[:8].upper()}",
        },
        "order.cancelled": {
            "order_id": order_id,
            "customer_name": customer["name"],
            "customer_email": customer["email"],
            "customer_phone": customer["phone"],
            "total_amount": total,
            "cancel_reason": random.choice(["Cliente lo solicitó", "Sin stock", "Error en dirección"]),
            "invoice_uuid": f"CFDI-{uuid.uuid4().hex[:8].upper()}",
        },
        "cart.abandoned": {
            "customer_name": customer["name"],
            "customer_email": customer["email"],
            "customer_phone": customer["phone"],
            "cart_total": total,
            "items": [{"name": p["name"], "price": p["price"], "qty": 1, "image": p["image"]} for p in products],
            "abandoned_minutes": random.randint(15, 120),
        },
        "payment.failed": {
            "order_id": order_id,
            "customer_name": customer["name"],
            "customer_email": customer["email"],
            "customer_phone": customer["phone"],
            "total_amount": total,
            "error": random.choice(["Fondos insuficientes", "Tarjeta rechazada", "Error de red"]),
        },
        "inventory.low": {
            "product_name": products[0]["name"],
            "sku": products[0]["sku"],
            "current_stock": random.randint(1, 4),
            "min_stock": 5,
        },
        "customer.created": {
            "customer_name": customer["name"],
            "customer_email": customer["email"],
            "customer_phone": customer["phone"],
            "state": customer["state"],
        },
    }

    data = event_data_map.get(event_type, {"event": event_type, "test": True})

    # Fire the automation engine
    results = await fire_event(event_type, data, current_user.workspace_id, db)

    return {
        "event_type": event_type,
        "event_data": data,
        "automation_results": results,
        "rules_triggered": len(results),
        "all_success": all(r["status"] == "success" for r in results) if results else True,
    }
