from typing import Any, Dict
from ..integrations.sat.sat_service import SATIntegration
from ..integrations.shipping.shipping_service import ShippingIntegration
from ..core.security import decrypt_key

class AutomationEngine:
    """Orchestrates events and triggers. e.g. New Order -> Generate SAT Invoice."""
    
    @staticmethod
    async def process_event(event_type: str, data: Dict[str, Any], user_id: int, db: Any = None):
        print(f"DEBUG: [Orquestador] Processing {event_type} for user {user_id}")
        
        # 1. Logic for New Order
        if event_type == "order.created":
            # Logic: We fetch the user's SAT credentials from the vault
            # (In a real scenario, we'd query the DB here)
            # sat_creds = db.query(CredentialVault).filter(...)
            
            print(f"DEBUG: [Orquestador] Success! Triggering SAT Invoice for Order ID {data.get('id')}")
            sat_service = SATIntegration(api_key="SIMULATED_DECRYPTED_KEY")
            invoice_id = await sat_service.create_invoice(data)
            
            # 2. Logic: Trigger Shipping if it's a physical product
            print(f"DEBUG: [Orquestador] Generating multidestination shipping label for user {user_id}")
            shipping_service = ShippingIntegration(api_key="SIMULATED_DECRYPTED_KEY")
            tracking_id = await shipping_service.create_label(data)
            
            return {
                "status": "orchestration_complete",
                "actions": [
                    {"service": "SAT", "result": invoice_id},
                    {"service": "Shipping", "result": tracking_id}
                ]
            }
            
        return {"status": "event_ignored", "event": event_type}
