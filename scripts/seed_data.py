#!/usr/bin/env python3
"""
Seed script for populating the database with demo data.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from app.infrastructure.db import db


async def seed():
    await db.connect()

    client_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO clients (id, org_name, org_slug, billing_email, subscription_tier)
           VALUES ($1, 'Acme Corp', 'acme-corp', 'billing@acme.com', 'enterprise')""",
        client_id,
    )
    print(f"Created client: {client_id}")

    agent_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO agent_profiles (id, client_id, agent_name, system_prompt)
           VALUES ($1, $2, 'Executive Sales Agent', 'You are a professional B2B sales agent...')""",
        agent_id, client_id,
    )
    print(f"Created agent profile: {agent_id}")

    session_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO proxy_sessions (id, client_id, agent_profile_id, meeting_platform, status, revenue_closed)
           VALUES ($1, $2, $3, 'zoom', 'COMPLETED', 50000.00)""",
        session_id, client_id, agent_id,
    )
    print(f"Created session: {session_id}")

    await db.disconnect()
    print("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())
