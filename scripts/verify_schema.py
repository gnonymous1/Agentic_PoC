"""
GNONE — Schema Verification Script

Connects to PostgreSQL and verifies all tables, indexes, constraints,
and extensions exist as expected.

Usage:
    python scripts/verify_schema.py
"""

import os
import sys
import logging
from typing import Optional

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("schema_verifier")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://gnone:gnone@localhost:5432/gnone")

EXPECTED_EXTENSIONS = ["pgcrypto", "vector", "plpgsql"]

EXPECTED_TABLES = [
    "clients",
    "oauth_vault",
    "agent_profiles",
    "proxy_sessions",
    "corporate_knowledge_vectors",
    "analytics_events",
    "analytics_daily_rollups",
    "audit_log",
    "key_versions",
    "content_cache",
    "approved_content",
    "content_versions",
    "content_diffs",
    "content_review_log",
    "content_branches",
    "webhook_subscriptions",
    "webhook_deliveries",
    "webhook_event_types",
    "schema_migrations",
]

EXPECTED_TYPES = [
    "session_status",
    "platform_enum",
]

EXPECTED_FUNCTIONS = [
    "update_updated_at_column",
    "semantic_search",
    "semantic_search_all_clients",
    "batch_semantic_search",
    "generate_and_store_embedding",
    "update_knowledge_embedding",
    "delete_client_knowledge",
    "knowledge_similarity_stats",
    "top_knowledge_by_source",
    "compute_content_hash",
    "get_version_chain",
    "get_latest_content_versions",
    "get_pending_webhook_deliveries",
    "create_webhook_delivery",
    "update_webhook_delivery_status",
    "find_subscriptions_for_event",
]

EXPECTED_INDEXES = [
    "idx_clients_org_slug",
    "idx_clients_is_active",
    "idx_oauth_vault_client",
    "idx_oauth_vault_expiry",
    "idx_agent_profiles_client",
    "idx_proxy_sessions_client",
    "idx_proxy_sessions_status",
    "idx_proxy_sessions_revenue",
    "idx_corporate_knowledge_hnsw",
    "idx_ckv_client_source",
    "idx_content_versions_client",
    "idx_content_versions_parent",
    "idx_content_versions_hash",
    "idx_content_versions_status",
    "idx_content_diffs_version",
    "idx_webhook_subs_client",
    "idx_webhook_subs_events",
    "idx_webhook_deliveries_sub",
    "idx_webhook_deliveries_event",
    "idx_schema_migrations_filename",
]


async def verify_extensions(conn: asyncpg.Connection) -> list[str]:
    logger.info("Checking extensions...")
    rows = await conn.fetch(
        "SELECT extname FROM pg_extension ORDER BY extname"
    )
    installed = {row["extname"] for row in rows}
    missing = []
    for ext in EXPECTED_EXTENSIONS:
        if ext in installed:
            logger.info("  [OK] Extension: %s", ext)
        else:
            logger.error("  [MISSING] Extension: %s", ext)
            missing.append(ext)
    return missing


async def verify_tables(conn: asyncpg.Connection) -> list[str]:
    logger.info("Checking tables...")
    rows = await conn.fetch(
        """
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
        """
    )
    installed = {row["tablename"] for row in rows}
    missing = []
    for table in EXPECTED_TABLES:
        if table in installed:
            row_count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            logger.info("  [OK] Table: %s (%d rows)", table, row_count)
        else:
            logger.error("  [MISSING] Table: %s", table)
            missing.append(table)
    return missing


async def verify_types(conn: asyncpg.Connection) -> list[str]:
    logger.info("Checking custom types...")
    rows = await conn.fetch(
        """
        SELECT typname FROM pg_type
        WHERE typtype = 'e' AND typnamespace = 'public'::regnamespace
        ORDER BY typname
        """
    )
    installed = {row["typname"] for row in rows}
    missing = []
    for typ in EXPECTED_TYPES:
        if typ in installed:
            logger.info("  [OK] Type: %s", typ)
        else:
            logger.error("  [MISSING] Type: %s", typ)
            missing.append(typ)
    return missing


async def verify_functions(conn: asyncpg.Connection) -> list[str]:
    logger.info("Checking functions...")
    rows = await conn.fetch(
        """
        SELECT proname FROM pg_proc
        WHERE pronamespace = 'public'::regnamespace
        ORDER BY proname
        """
    )
    installed = {row["proname"] for row in rows}
    missing = []
    for func in EXPECTED_FUNCTIONS:
        if func in installed:
            logger.info("  [OK] Function: %s", func)
        else:
            logger.error("  [MISSING] Function: %s", func)
            missing.append(func)
    return missing


async def verify_indexes(conn: asyncpg.Connection) -> list[str]:
    logger.info("Checking indexes...")
    rows = await conn.fetch(
        """
        SELECT indexname FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY indexname
        """
    )
    installed = {row["indexname"] for row in rows}
    missing = []
    for idx in EXPECTED_INDEXES:
        if idx in installed:
            logger.info("  [OK] Index: %s", idx)
        else:
            logger.error("  [MISSING] Index: %s", idx)
            missing.append(idx)
    return missing


async def verify_constraints(conn: asyncpg.Connection) -> list[str]:
    logger.info("Checking foreign key constraints...")
    rows = await conn.fetch(
        """
        SELECT
            tc.constraint_name,
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
        ORDER BY tc.table_name, tc.constraint_name
        """
    )
    fk_count = len(rows)
    logger.info("  Found %d foreign key constraints", fk_count)

    logger.info("Checking check constraints...")
    rows = await conn.fetch(
        """
        SELECT tc.table_name, tc.constraint_name, cc.check_clause
        FROM information_schema.table_constraints tc
        JOIN information_schema.check_constraints cc
            ON tc.constraint_name = cc.constraint_name
        WHERE tc.constraint_type = 'CHECK'
          AND tc.table_schema = 'public'
        ORDER BY tc.table_name
        """
    )
    check_count = len(rows)
    logger.info("  Found %d check constraints", check_count)

    return []


async def verify_triggers(conn: asyncpg.Connection) -> list[str]:
    logger.info("Checking triggers...")
    rows = await conn.fetch(
        """
        SELECT trigger_name, event_object_table, action_timing, event_manipulation
        FROM information_schema.triggers
        WHERE trigger_schema = 'public'
        ORDER BY event_object_table, trigger_name
        """
    )
    for row in rows:
        logger.info(
            "  [OK] Trigger: %s on %s (%s %s)",
            row["trigger_name"],
            row["event_object_table"],
            row["action_timing"],
            row["event_manipulation"],
        )
    return []


async def main() -> None:
    logger.info("=" * 70)
    logger.info("GNONE Schema Verification")
    logger.info("Database: %s", DATABASE_URL)
    logger.info("=" * 70)

    try:
        conn = await asyncpg.connect(dsn=DATABASE_URL)
    except Exception as exc:
        logger.error("Failed to connect to database: %s", exc)
        sys.exit(1)

    all_missing = []

    try:
        all_missing.extend(await verify_extensions(conn))
        all_missing.extend(await verify_tables(conn))
        all_missing.extend(await verify_types(conn))
        all_missing.extend(await verify_functions(conn))
        all_missing.extend(await verify_indexes(conn))
        all_missing.extend(await verify_constraints(conn))
        all_missing.extend(await verify_triggers(conn))
    finally:
        await conn.close()

    logger.info("=" * 70)
    if all_missing:
        logger.error("VERIFICATION FAILED — %d items missing", len(all_missing))
        for item in all_missing:
            logger.error("  - %s", item)
        sys.exit(1)
    else:
        logger.info("VERIFICATION PASSED — All schema objects present")
        sys.exit(0)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
