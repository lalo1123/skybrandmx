"""
Skydropx integration service — SkyBrandMX
Cotizar, generar guías, rastrear, etiquetas
"""
import os
import logging
import httpx
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.base import ApiCredential
from app.core.security import decrypt_api_credential

logger = logging.getLogger(__name__)

SKYDROPX_API_URL = "https://api.skydropx.com/v1"
SKYDROPX_RADAR_URL = "https://radar-api.skydropx.com/v1"
MARGIN_PERCENTAGE = 0.25  # 25% markup on carrier cost


class SkydropxClient:
    """HTTP client for Skydropx API"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Token token={api_key}",
        }

    async def _request(self, method: str, url: str, json: dict = None, params: dict = None) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method=method, url=url, json=json, params=params, headers=self.headers,
                )
                if response.status_code >= 400:
                    error_data = response.json() if 'json' in response.headers.get('content-type', '') else {"message": response.text}
                    logger.error(f"Skydropx error {response.status_code}: {error_data}")
                    return {"error": True, "status": response.status_code, "detail": error_data}
                return response.json()
        except httpx.TimeoutException:
            return {"error": True, "status": 408, "detail": {"message": "Timeout al conectar con Skydropx"}}
        except Exception as e:
            return {"error": True, "status": 500, "detail": {"message": str(e)}}

    # ═══════ QUOTATION ═══════

    async def create_quotation(self, zip_from: str, zip_to: str, weight: float, length: float, width: float, height: float) -> Dict[str, Any]:
        """Get shipping rates from all carriers"""
        payload = {
            "zip_from": zip_from,
            "zip_to": zip_to,
            "parcel": {
                "weight": weight,
                "height": height,
                "width": width,
                "length": length,
            },
        }
        result = await self._request("POST", f"{SKYDROPX_API_URL}/quotations", json=payload)
        return result

    async def get_quotation(self, quotation_id: str) -> Dict[str, Any]:
        """Get quotation details with rates"""
        return await self._request("GET", f"{SKYDROPX_API_URL}/quotations/{quotation_id}")

    # ═══════ SHIPMENT ═══════

    async def create_shipment(self, address_from: dict, address_to: dict, parcel: dict) -> Dict[str, Any]:
        """Create a shipment"""
        payload = {
            "address_from": address_from,
            "address_to": address_to,
            "parcels": [parcel],
        }
        return await self._request("POST", f"{SKYDROPX_API_URL}/shipments", json=payload)

    # ═══════ LABEL ═══════

    async def create_label(self, rate_id: str, label_format: str = "pdf") -> Dict[str, Any]:
        """Generate shipping label from a rate"""
        payload = {
            "rate_id": rate_id,
            "label_format": label_format,
        }
        return await self._request("POST", f"{SKYDROPX_API_URL}/labels", json=payload)

    # ═══════ TRACKING ═══════

    async def track_shipment(self, carrier: str, tracking_number: str) -> Dict[str, Any]:
        """Track a shipment"""
        payload = {
            "tracking_numbers": [
                {"carrier": carrier, "tracking_number": tracking_number}
            ]
        }
        return await self._request("POST", f"{SKYDROPX_RADAR_URL}/tracking", json=payload)


def get_skydropx_client(workspace_id: int, db: Session) -> SkydropxClient:
    """Get Skydropx client — dual mode like Facturapi"""
    cred = db.query(ApiCredential).filter(
        ApiCredential.workspace_id == workspace_id,
        ApiCredential.provider == "skydropx"
    ).first()

    if cred and cred.encrypted_api_key:
        try:
            api_key = decrypt_api_credential(cred.encrypted_api_key)
            logger.info(f"Using workspace {workspace_id} own Skydropx credentials")
            return SkydropxClient(api_key)
        except Exception as e:
            logger.error(f"Error decrypting workspace Skydropx credentials: {e}")

    default_key = os.environ.get("SKYDROPX_API_KEY", "")
    if not default_key:
        logger.warning("No SKYDROPX_API_KEY configured — shipping will fail")
    return SkydropxClient(default_key)


def calculate_user_price(carrier_cost: float) -> dict:
    """Calculate user price with margin"""
    margin = round(carrier_cost * MARGIN_PERCENTAGE, 2)
    return {
        "cost": carrier_cost,
        "price": round(carrier_cost + margin, 2),
        "margin": margin,
    }


def calculate_volumetric_weight(length: float, width: float, height: float) -> float:
    """Calculate volumetric weight (factor 5000 standard)"""
    return round((length * width * height) / 5000, 2)
