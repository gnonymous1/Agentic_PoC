import logging

from fastapi import APIRouter, HTTPException

from database.connection import get_session
from database.models import OAuthVault

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/accounts", tags=["Accounts"])


@router.get("/connected")
async def list_connected_accounts(client_id: str):
    from sqlalchemy import select
    db_session = await anext(get_session())
    rows = await db_session.execute(select(OAuthVault).where(OAuthVault.client_id == client_id))
    vaults = rows.scalars().all()
    out = []
    for v in vaults:
        out.append({
            "id": str(v.id),
            "platform": v.platform,
            "platform_label": v.platform_label,
            "last_used_at": v.last_used_at.isoformat() if v.last_used_at else None,
            "is_revoked": v.is_revoked,
            "scopes": v.scopes or [],
        })
    return out


@router.post("/revoke")
async def revoke_account(vault_id: str):
    db_session = await anext(get_session())
    vault = await db_session.get(OAuthVault, vault_id)
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")
    vault.is_revoked = True
    await db_session.flush()
    return {"status": "revoked", "id": vault_id}
