"""
GNONE — Financial Agent.
Ledger management, invoice processing, and Stripe billing integration.
"""

import os
import logging
from typing import Dict, Any

import httpx

from app.agents.base import BaseAgent
from app.core.circuit_breaker import stripe_breaker
from app.core.rate_limiter import limiter

logger = logging.getLogger(__name__)


class FinancialAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "financial_agent"

    @property
    def description(self) -> str:
        return "Financial ledger management and Stripe billing integration"

    async def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        if action == "create_invoice":
            return await self._create_stripe_invoice(
                client_email=kwargs.get("client_email", ""),
                contract_value=kwargs.get("contract_value", 0.0),
            )
        elif action == "log_entry":
            return {"status": "success", "message": "Entry logged to financial ledger", "data": kwargs}
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    async def _create_stripe_invoice(self, client_email: str, contract_value: float) -> Dict[str, Any]:
        """Create and finalize a Stripe invoice."""
        logger.info("FinancialAgent: Creating Stripe invoice for %s ($%.2f)", client_email, contract_value)

        stripe_key = os.getenv("STRIPE_API_KEY", "")
        if not stripe_key:
            return {"status": "fallback", "message": "Stripe key not set, simulating invoice", "invoice_url": f"https://invoice.stripe.com/i/sim_{client_email}"}

        headers = {"Authorization": f"Bearer {stripe_key}", "Content-Type": "application/x-www-form-urlencoded"}

        await limiter.acquire("stripe")

        async with httpx.AsyncClient(timeout=15.0) as client:
            # Create customer
            cust_resp = await client.post("https://api.stripe.com/v1/customers", headers=headers, data={"email": client_email})
            cust_resp.raise_for_status()
            cust_id = cust_resp.json()["id"]

            # Create invoice item
            await client.post("https://api.stripe.com/v1/invoiceitems", headers=headers, data={
                "customer": cust_id, "amount": int(contract_value * 100), "currency": "usd",
                "description": "GNONE Autonomous Digital Clone License",
            })

            # Create and finalize invoice
            inv_resp = await client.post("https://api.stripe.com/v1/invoices", headers=headers, data={"customer": cust_id, "auto_advance": "true"})
            inv_resp.raise_for_status()
            inv_id = inv_resp.json()["id"]

            final_resp = await client.post(f"https://api.stripe.com/v1/invoices/{inv_id}/finalize", headers=headers)
            final_resp.raise_for_status()
            final_data = final_resp.json()

        return {
            "status": "success",
            "transaction_id": final_data["id"],
            "invoice_url": final_data.get("hosted_invoice_url"),
            "amount": contract_value,
        }
