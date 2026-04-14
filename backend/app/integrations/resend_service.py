"""
Resend integration service — SkyBrandMX
Send emails, manage domains, track events
"""
import os
import logging
import httpx
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.base import ApiCredential
from app.core.security import decrypt_api_credential

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com"


class ResendClient:
    """HTTP client for Resend API"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    async def _request(self, method: str, endpoint: str, json: dict = None) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method=method,
                    url=f"{RESEND_API_URL}{endpoint}",
                    json=json,
                    headers=self.headers,
                )
                if response.status_code >= 400:
                    error = response.json() if 'json' in response.headers.get('content-type', '') else {"message": response.text}
                    logger.error(f"Resend error {response.status_code}: {error}")
                    return {"error": True, "status": response.status_code, "detail": error}
                return response.json()
        except httpx.TimeoutException:
            return {"error": True, "status": 408, "detail": {"message": "Timeout connecting to Resend"}}
        except Exception as e:
            return {"error": True, "status": 500, "detail": {"message": str(e)}}

    async def send_email(self, from_email: str, to: str, subject: str, html: str, reply_to: str = None, tags: list = None) -> Dict[str, Any]:
        """Send a single email"""
        payload = {
            "from": from_email,
            "to": [to] if isinstance(to, str) else to,
            "subject": subject,
            "html": html,
        }
        if reply_to:
            payload["reply_to"] = reply_to
        if tags:
            payload["tags"] = [{"name": t, "value": "true"} for t in tags]
        return await self._request("POST", "/emails", json=payload)

    async def send_batch(self, emails: List[dict]) -> Dict[str, Any]:
        """Send batch of emails (up to 100 per request)"""
        return await self._request("POST", "/emails/batch", json=emails)

    async def get_email(self, email_id: str) -> Dict[str, Any]:
        """Get email delivery status"""
        return await self._request("GET", f"/emails/{email_id}")

    async def list_domains(self) -> Dict[str, Any]:
        """List verified domains"""
        return await self._request("GET", "/domains")

    async def verify_domain(self, domain: str) -> Dict[str, Any]:
        """Add domain for verification"""
        return await self._request("POST", "/domains", json={"name": domain})

    async def get_domain(self, domain_id: str) -> Dict[str, Any]:
        """Get domain verification status"""
        return await self._request("GET", f"/domains/{domain_id}")


def get_resend_client(workspace_id: int, db: Session) -> ResendClient:
    """Get Resend client — dual mode"""
    cred = db.query(ApiCredential).filter(
        ApiCredential.workspace_id == workspace_id,
        ApiCredential.provider == "resend"
    ).first()

    if cred and cred.encrypted_api_key:
        try:
            api_key = decrypt_api_credential(cred.encrypted_api_key)
            logger.info(f"Using workspace {workspace_id} own Resend credentials")
            return ResendClient(api_key)
        except Exception as e:
            logger.error(f"Error decrypting Resend credentials: {e}")

    default_key = os.environ.get("RESEND_API_KEY", "")
    if not default_key:
        logger.warning("No RESEND_API_KEY configured — email sending will fail")
    return ResendClient(default_key)


def build_email_html(subject: str, body: str, unsubscribe_url: str = "#") -> str:
    """Build a simple responsive HTML email"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
    <body style="margin:0;padding:0;background:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background:#ffffff;">
        <tr><td style="padding:32px;text-align:center;background:#084D6E;">
          <h1 style="color:#fff;margin:0;font-size:20px;">SkyBrandMX</h1>
        </td></tr>
        <tr><td style="padding:32px;color:#333;font-size:15px;line-height:1.6;">
          {body}
        </td></tr>
        <tr><td style="padding:24px 32px;background:#f9fafb;text-align:center;font-size:12px;color:#999;">
          <p>Enviado desde SkyBrandMX</p>
          <a href="{unsubscribe_url}" style="color:#999;text-decoration:underline;">Dejar de recibir emails</a>
        </td></tr>
      </table>
    </body>
    </html>
    """
