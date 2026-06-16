"""Provider helpers for OAuth flows (skeleton implementations).

Provides authorize URL builders and code exchange helpers for common providers.
This file contains minimal, well-documented helpers intended for extension.
"""
import logging
import os
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)


def build_authorize_url(provider: str, redirect_uri: str, state: str = "state", scopes: list[str] | None = None) -> str:
    provider = provider.lower()
    scopes = scopes or ["openid", "profile"]
    if provider == "google":
        base = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "response_type": "code",
            "scope": " ".join(scopes),
            "redirect_uri": redirect_uri,
            "access_type": "offline",
            "state": state,
            "prompt": "consent",
        }
        return f"{base}?{urlencode(params)}"
    if provider == "linkedin":
        base = "https://www.linkedin.com/oauth/v2/authorization"
        params = {
            "response_type": "code",
            "client_id": os.getenv("LINKEDIN_CLIENT_ID", ""),
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
        }
        return f"{base}?{urlencode(params)}"
    if provider == "twitter":
        # Twitter uses OAuth 2.0 PKCE or OAuth 1.0a; here we use a simplified flow placeholder
        base = "https://twitter.com/i/oauth2/authorize"
        params = {
            "response_type": "code",
            "client_id": os.getenv("TWITTER_CLIENT_ID", ""),
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
            "code_challenge": "challenge",
            "code_challenge_method": "plain",
        }
        return f"{base}?{urlencode(params)}"

    raise ValueError(f"Unsupported provider: {provider}")


async def exchange_code_for_token(provider: str, code: str, redirect_uri: str, code_verifier: str | None = None) -> dict[str, str]:
    """Exchange authorization code for access token (with PKCE support for Twitter)."""
    provider = provider.lower()
    async with httpx.AsyncClient(timeout=15.0) as client:
        if provider == "google":
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "code": code,
                "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }
            resp = await client.post(token_url, data=data)
            resp.raise_for_status()
            return resp.json()

        if provider == "linkedin":
            token_url = "https://www.linkedin.com/oauth/v2/accessToken"
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": os.getenv("LINKEDIN_CLIENT_ID", ""),
                "client_secret": os.getenv("LINKEDIN_CLIENT_SECRET", ""),
            }
            resp = await client.post(token_url, data=data)
            resp.raise_for_status()
            return resp.json()

        if provider == "twitter":
            token_url = "https://api.twitter.com/2/oauth2/token"
            data = {
                "code": code,
                "grant_type": "authorization_code",
                "client_id": os.getenv("TWITTER_CLIENT_ID", ""),
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier or "challenge",
            }
            resp = await client.post(token_url, data=data, auth=(os.getenv("TWITTER_CLIENT_ID", ""), os.getenv("TWITTER_CLIENT_SECRET", "")))
            resp.raise_for_status()
            return resp.json()

        raise ValueError(f"Unsupported provider: {provider}")


async def refresh_access_token(provider: str, refresh_token: str) -> dict[str, str]:
    """Refresh an expired access token using a refresh token."""
    provider = provider.lower()
    async with httpx.AsyncClient(timeout=15.0) as client:
        if provider == "google":
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "refresh_token": refresh_token,
                "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
                "grant_type": "refresh_token",
            }
            resp = await client.post(token_url, data=data)
            resp.raise_for_status()
            return resp.json()
        if provider == "linkedin":
            token_url = "https://www.linkedin.com/oauth/v2/accessToken"
            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": os.getenv("LINKEDIN_CLIENT_ID", ""),
                "client_secret": os.getenv("LINKEDIN_CLIENT_SECRET", ""),
            }
            resp = await client.post(token_url, data=data)
            resp.raise_for_status()
            return resp.json()
        raise ValueError(f"Refresh token not supported for: {provider}")
