"""Email inbox connector for Gmail and Outlook (IMAP/Office 365 API).

Polls email inboxes, detects mentions/replies, and enqueues auto-reply
opportunities for HITL approval.
"""
import asyncio
import email as email_parser
import imaplib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Represents a single email message."""
    message_id: str
    from_addr: str
    subject: str
    body: str
    received_at: datetime
    is_reply: bool = False


class EmailConnector:
    """Manages email inbox polling and message processing."""

    def __init__(self, email: str, password: str, provider: str = "gmail"):
        self.email = email
        self.password = password
        self.provider = provider.lower()
        self.imap_host = "imap.gmail.com" if provider == "gmail" else "outlook.office365.com"
        self.is_connected = False

    async def connect(self) -> bool:
        """Establish IMAP connection (async wrapper)."""
        try:
            # In async context, use run_in_executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._sync_connect
            )
            self.is_connected = result
            return result
        except Exception as exc:
            logger.error("Email connection failed: %s", exc)
            return False

    def _sync_connect(self) -> bool:
        """Sync IMAP connection helper."""
        try:
            self.imap = imaplib.IMAP4_SSL(self.imap_host)
            self.imap.login(self.email, self.password)
            logger.info("Connected to %s IMAP", self.provider)
            return True
        except Exception as exc:
            logger.error("IMAP login failed: %s", exc)
            return False

    async def fetch_unread_messages(self) -> list[EmailMessage]:
        """Fetch unread emails from inbox."""
        if not self.is_connected:
            await self.connect()
            if not self.is_connected:
                return []

        try:
            loop = asyncio.get_event_loop()
            messages = await loop.run_in_executor(
                None, self._sync_fetch_unread
            )
            return messages
        except Exception as exc:
            logger.error("Failed to fetch unread messages: %s", exc)
            return []

    def _sync_fetch_unread(self) -> list[EmailMessage]:
        """Sync fetch unread messages helper."""
        try:
            self.imap.select("INBOX")
            status, message_ids = self.imap.search(None, "UNSEEN")
            if status != "OK":
                return []

            messages = []
            for msg_id in message_ids[0].split():
                try:
                    status, msg_data = self.imap.fetch(msg_id, "(RFC822)")
                    if status != "OK":
                        continue

                    msg = email_parser.message_from_bytes(msg_data[0][1])
                    from_addr = msg.get("From", "unknown")
                    subject = msg.get("Subject", "(no subject)")
                    body = msg.get_payload()

                    messages.append(
                        EmailMessage(
                            message_id=msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
                            from_addr=from_addr,
                            subject=subject,
                            body=body or "",
                            received_at=datetime.now(UTC),
                            is_reply="Re:" in subject,
                        )
                    )
                except Exception as e:
                    logger.debug("Error parsing message %s: %s", msg_id, e)
                    continue

            logger.info("Fetched %d unread messages from %s", len(messages), self.email)
            return messages
        except Exception as exc:
            logger.error("Error in _sync_fetch_unread: %s", exc)
            return []

    async def disconnect(self) -> None:
        """Close IMAP connection."""
        if self.is_connected:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.imap.close)
                self.is_connected = False
            except Exception as exc:
                logger.error("Error closing IMAP: %s", exc)


async def poll_email_inbox(client_id: str, vault_id: str) -> dict[str, int]:
    """Poll a client's email inbox and enqueue unread messages for HITL."""
    from app.services.encryption import decrypt_token
    from database.connection import get_session
    from database.models import HitlAction, OAuthVault

    try:
        db_session = await anext(get_session())
        vault = await db_session.get(OAuthVault, vault_id)
        if not vault:
            logger.warning("Vault not found: %s", vault_id)
            return {"status": "error", "processed": 0}

        # For prototype, we use the decrypted token as email password
        # In production, use Gmail/Outlook API tokens properly
        token = decrypt_token(vault.encrypted_token, vault.encrypted_iv, vault.encrypted_tag, key_version=vault.key_version)

        # Placeholder: in real flow, extract email from token metadata
        email_account = vault.platform_label or "test@gmail.com"

        connector = EmailConnector(email_account, token, provider="gmail")
        connected = await connector.connect()
        if not connected:
            return {"status": "error", "processed": 0}

        messages = await connector.fetch_unread_messages()

        # Enqueue each unread message as a HITL action for auto-reply approval
        for msg in messages:
            hitl = HitlAction(
                client_id=client_id,
                action_type="email_reply",
                status="PENDING_HUMAN_SIGN_OFF",
                target_platform="email",
                payload={
                    "from": msg.from_addr,
                    "subject": msg.subject,
                    "body": msg.body,
                    "message_id": msg.message_id,
                },
            )
            db_session.add(hitl)

        await db_session.flush()
        await connector.disconnect()

        logger.info("Processed %d email messages from %s", len(messages), email_account)
        return {"status": "ok", "processed": len(messages)}

    except Exception as exc:
        logger.error("Email polling failed: %s", exc)
        return {"status": "error", "processed": 0}
