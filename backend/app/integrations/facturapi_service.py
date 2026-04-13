"""
Facturapi integration service — SkyBrandMX
Supports dual mode: SkyBrandMX PAC (default) or user's own PAC credentials
"""
import os
import logging
import httpx
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.base import ApiCredential
from app.core.security import decrypt_api_credential as decrypt_value

logger = logging.getLogger(__name__)

FACTURAPI_SANDBOX_URL = "https://www.facturapi.io/v2"
FACTURAPI_LIVE_URL = "https://www.facturapi.io/v2"


class FacturapiClient:
    """HTTP client for Facturapi API"""

    def __init__(self, api_key: str, is_sandbox: bool = True):
        self.api_key = api_key
        self.base_url = FACTURAPI_SANDBOX_URL if is_sandbox else FACTURAPI_LIVE_URL
        self.headers = {
            "Content-Type": "application/json",
        }
        self.auth = (api_key, "")  # Basic auth with API key as username

    async def _request(self, method: str, endpoint: str, json: dict = None, params: dict = None) -> Dict[str, Any]:
        """Make authenticated request to Facturapi"""
        url = f"{self.base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    auth=self.auth,
                    headers=self.headers,
                )

                if response.status_code >= 400:
                    error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {"message": response.text}
                    logger.error(f"Facturapi error {response.status_code}: {error_data}")
                    return {"error": True, "status": response.status_code, "detail": error_data}

                if response.headers.get('content-type', '').startswith('application/json'):
                    return response.json()
                return {"data": response.content, "content_type": response.headers.get('content-type')}

        except httpx.TimeoutException:
            logger.error(f"Facturapi timeout: {url}")
            return {"error": True, "status": 408, "detail": {"message": "Timeout al conectar con Facturapi"}}
        except Exception as e:
            logger.error(f"Facturapi exception: {e}")
            return {"error": True, "status": 500, "detail": {"message": str(e)}}

    # ═══════ INVOICES ═══════

    async def create_invoice(self, invoice_data: dict) -> Dict[str, Any]:
        """Create and stamp a CFDI 4.0 invoice"""
        return await self._request("POST", "/invoices", json=invoice_data)

    async def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Get invoice details"""
        return await self._request("GET", f"/invoices/{invoice_id}")

    async def cancel_invoice(self, invoice_id: str, motive: str, substitution: str = None) -> Dict[str, Any]:
        """Cancel invoice with SAT"""
        body = {"motive": motive}
        if substitution:
            body["substitution"] = substitution
        return await self._request("PUT", f"/invoices/{invoice_id}/cancel", json=body)

    async def download_pdf(self, invoice_id: str) -> bytes:
        """Download invoice PDF"""
        result = await self._request("GET", f"/invoices/{invoice_id}/pdf")
        if isinstance(result, dict) and "data" in result:
            return result["data"]
        return result

    async def download_xml(self, invoice_id: str) -> bytes:
        """Download invoice XML"""
        result = await self._request("GET", f"/invoices/{invoice_id}/xml")
        if isinstance(result, dict) and "data" in result:
            return result["data"]
        return result

    async def send_by_email(self, invoice_id: str, email: str) -> Dict[str, Any]:
        """Send invoice PDF+XML by email"""
        return await self._request("POST", f"/invoices/{invoice_id}/email", json={"email": email})

    # ═══════ CUSTOMERS ═══════

    async def create_customer(self, customer_data: dict) -> Dict[str, Any]:
        """Create a customer in Facturapi"""
        return await self._request("POST", "/customers", json=customer_data)

    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """Get customer details"""
        return await self._request("GET", f"/customers/{customer_id}")

    async def list_customers(self, search: str = None) -> Dict[str, Any]:
        """List customers"""
        params = {}
        if search:
            params["q"] = search
        return await self._request("GET", "/customers", params=params)

    # ═══════ PRODUCTS ═══════

    async def create_product(self, product_data: dict) -> Dict[str, Any]:
        """Create a product in Facturapi catalog"""
        return await self._request("POST", "/products", json=product_data)

    # ═══════ ORGANIZATION ═══════

    async def get_organization(self) -> Dict[str, Any]:
        """Get organization/issuer info"""
        return await self._request("GET", "/organizations")


def get_facturapi_client(workspace_id: int, db: Session) -> FacturapiClient:
    """
    Get Facturapi client — dual mode:
    1. If workspace has own credentials → use them
    2. Otherwise → use SkyBrandMX default credentials
    """
    # Check if workspace has own Facturapi credentials
    cred = db.query(ApiCredential).filter(
        ApiCredential.workspace_id == workspace_id,
        ApiCredential.provider == "facturapi"
    ).first()

    if cred and cred.encrypted_api_key:
        try:
            api_key = decrypt_value(cred.encrypted_api_key)
            is_sandbox = False  # User's own = production
            logger.info(f"Using workspace {workspace_id} own Facturapi credentials")
            return FacturapiClient(api_key, is_sandbox=is_sandbox)
        except Exception as e:
            logger.error(f"Error decrypting workspace credentials: {e}")

    # Fallback: SkyBrandMX default
    default_key = os.environ.get("FACTURAPI_KEY", "")
    if not default_key:
        logger.warning("No FACTURAPI_KEY configured — invoicing will fail")

    is_sandbox = os.environ.get("FACTURAPI_ENV", "sandbox") == "sandbox"
    logger.info(f"Using SkyBrandMX default Facturapi ({'sandbox' if is_sandbox else 'live'})")
    return FacturapiClient(default_key, is_sandbox=is_sandbox)


def build_facturapi_invoice_payload(invoice_data: dict, items: list, issuer: dict = None) -> dict:
    """
    Build the JSON payload for Facturapi API from our internal data
    """
    payload = {
        "type": invoice_data.get("cfdi_type", "I"),
        "customer": {
            "legal_name": invoice_data["receiver_name"],
            "tax_id": invoice_data["receiver_rfc"],
            "tax_system": invoice_data["receiver_regime"],
            "address": {
                "zip": invoice_data["receiver_zip"],
            },
        },
        "use": invoice_data.get("receiver_cfdi_use", "G03"),
        "payment_form": invoice_data.get("payment_form", "03"),
        "payment_method": invoice_data.get("payment_method", "PUE"),
        "currency": invoice_data.get("currency", "MXN"),
        "items": [],
    }

    if invoice_data.get("exchange_rate", 1.0) != 1.0:
        payload["exchange"] = invoice_data["exchange_rate"]

    # Add items
    for item in items:
        facturapi_item = {
            "quantity": item["quantity"],
            "product": {
                "description": item["description"],
                "product_key": item.get("product_code", "01010101"),
                "unit_key": item.get("unit_code", "E48"),
                "unit_name": item.get("unit_name", "Servicio"),
                "price": item["unit_price"],
                "tax_included": False,
                "taxes": [],
            },
        }

        # IVA
        if item.get("iva_rate", 0) > 0:
            facturapi_item["product"]["taxes"].append({
                "type": "IVA",
                "rate": item["iva_rate"],
            })

        # ISR retention
        if item.get("isr_rate", 0) > 0:
            facturapi_item["product"]["taxes"].append({
                "type": "ISR",
                "rate": item["isr_rate"],
                "withholding": True,
            })

        if item.get("discount", 0) > 0:
            facturapi_item["discount"] = item["discount"]

        payload["items"].append(facturapi_item)

    return payload
