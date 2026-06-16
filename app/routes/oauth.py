import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.services import oauth_providers
from app.services.encryption import encrypt_token
from database.connection import get_session
from database.models import OAuthVault

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/oauth", tags=["OAuth"])


@router.get("/authorize")
async def authorize(platform: str, client_id: str | None = None, redirect_uri: str | None = None):
    redirect_uri = redirect_uri or "/oauth/callback"
    try:
        url = oauth_providers.build_authorize_url(platform, redirect_uri, state="state123")
        return JSONResponse({"authorize_url": url})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/callback")
async def callback(request: Request, platform: str, code: str | None = None, client_id: str | None = None, redirect_uri: str | None = None):
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    redirect_uri = redirect_uri or str(request.url.replace(path="/oauth/callback"))
    try:
        token_response = await oauth_providers.exchange_code_for_token(platform, code, redirect_uri)
    except Exception as exc:
        logger.exception("Token exchange failed: %s", exc)
        token_response = {"access_token": code}

    access_token = token_response.get("access_token")
    if not access_token:
        raise HTTPException(status_code=500, detail="No access token received from provider")

    try:
        ct, iv, tag = encrypt_token(access_token)
    except Exception as exc:
        logger.exception("Encryption failed: %s", exc)
        raise HTTPException(status_code=500, detail="Encryption failed")

    try:
        db_session = await anext(get_session())
        vault = OAuthVault(
            client_id=client_id,
            platform=platform.lower(),
            platform_label=f"{platform.title()}",
            encrypted_token=ct,
            encrypted_iv=iv,
            encrypted_tag=tag,
            token_type=token_response.get("token_type", "bearer"),
            token_expires_at=None,
            refresh_token_hash=token_response.get("refresh_token"),
            scopes=[],
            is_revoked=False,
        )
        db_session.add(vault)
        await db_session.flush()
    except Exception as exc:
        logger.exception("Failed to store oauth token: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to store token")

    return RedirectResponse(url=f"/dashboard?oauth_success=1&platform={platform}")
