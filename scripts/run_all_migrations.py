"""
GNONE — PostgreSQL Migration Runner

Applies all pending SQL migrations in order, tracks applied migrations
in a schema_migrations table, and supports rollback.

Usage:
    python scripts/run_all_migrations.py              # Apply all pending
    python scripts/run_all_migrations.py --rollback   # Rollback last
    python scripts/run_all_migrations.py --status     # Show status
"""

import os
import sys
import glob
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("migration_runner")

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://gnone:gnone@localhost:5432/gnone")


async def ensure_migrations_table(conn: asyncpg.Connection) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            filename    TEXT NOT NULL UNIQUE,
            checksum    TEXT NOT NULL,
            applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            execution_time_ms INTEGER
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_schema_migrations_filename
            ON schema_migrations (filename)
    """)


async def get_applied_migrations(conn: asyncpg.Connection) -> dict[str, dict]:
    rows = await conn.fetch(
        "SELECT filename, checksum, applied_at, execution_time_ms FROM schema_migrations ORDER BY filename"
    )
    return {row["filename"]: dict(row) for row in rows}


def get_migration_files() -> list[Path]:
    pattern = str(MIGRATIONS_DIR / "*.sql")
    files = sorted(glob.glob(pattern))
    return [Path(f) for f in files]


def compute_checksum(filepath: Path) -> str:
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


async def apply_migration(conn: asyncpg.Connection, filepath: Path) -> bool:
    filename = filepath.name
    checksum = compute_checksum(filepath)
    logger.info("Applying migration: %s", filename)

    sql = filepath.read_text(encoding="utf-8")

    start = datetime.now(timezone.utc)
    try:
        await conn.execute(sql)
        elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

        await conn.execute(
            """
            INSERT INTO schema_migrations (filename, checksum, execution_time_ms)
            VALUES ($1, $2, $3)
            """,
            filename,
            checksum,
            elapsed,
        )
        logger.info("Applied %s in %dms", filename, elapsed)
        return True
    except Exception as exc:
        elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        logger.error("Migration %s FAILED after %dms: %s", filename, elapsed, exc)
        raise


async def rollback_last_migration(conn: asyncpg.Connection) -> Optional[str]:
    applied = await get_applied_migrations(conn)
    if not applied:
        logger.info("No migrations to rollback")
        return None

    last_filename = sorted(applied.keys())[-1]
    logger.info("Rolling back migration: %s", last_filename)

    await conn.execute(
        "DELETE FROM schema_migrations WHERE filename = $1",
        last_filename,
    )

    migration_file = MIGRATIONS_DIR / last_filename
    if migration_file.exists():
        logger.warning(
            "Migration %s removed from tracking. Manual SQL rollback may be required.",
            last_filename,
        )

    return last_filename


async def show_status(conn: asyncpg.Connection) -> None:
    applied = await get_applied_migrations(conn)
    files = get_migration_files()

    logger.info("=" * 70)
    logger.info("Migration Status")
    logger.info("=" * 70)

    for filepath in files:
        filename = filepath.name
        if filename in applied:
            info = applied[filename]
            applied_time = info["applied_at"].strftime("%Y-%m-%d %H:%M:%S UTC")
            exec_time = info.get("execution_time_ms", "N/A")
            logger.info("  [APPLIED]  %s  (applied: %s, %sms)", filename, applied_time, exec_time)
        else:
            logger.info("  [PENDING]  %s", filename)

    logger.info("=" * 70)
    logger.info("Total: %d applied, %d pending", len(applied), len(files) - len(applied))


async def run_migrations() -> None:
    conn = await asyncpg.connect(dsn=DATABASE_URL)
    try:
        await ensure_migrations_table(conn)
        applied = await get_applied_migrations(conn)
        files = get_migration_files()

        pending = [f for f in files if f.name not in applied]

        if not pending:
            logger.info("All migrations are already applied")
            return

        logger.info("Found %d pending migrations", len(pending))

        for filepath in pending:
            await apply_migration(conn, filepath)

        logger.info("All migrations applied successfully")
    finally:
        await conn.close()


async def run_rollback() -> None:
    conn = await asyncpg.connect(dsn=DATABASE_URL)
    try:
        await ensure_migrations_table(conn)
        result = await rollback_last_migration(conn)
        if result:
            logger.info("Rolled back: %s", result)
    finally:
        await conn.close()


async def run_status() -> None:
    conn = await asyncpg.connect(dsn=DATABASE_URL)
    try:
        await ensure_migrations_table(conn)
        await show_status(conn)
    finally:
        await conn.close()


def main() -> None:
    import asyncio

    action = "migrate"
    if len(sys.argv) > 1:
        action = sys.argv[1].lstrip("-")

    if action in ("migrate", "run", "apply"):
        asyncio.run(run_migrations())
    elif action in ("rollback", "undo"):
        asyncio.run(run_rollback())
    elif action in ("status", "info"):
        asyncio.run(run_status())
    else:
        print(f"Unknown action: {action}")
        print("Usage: python run_all_migrations.py [migrate|rollback|status]")
        sys.exit(1)


if __name__ == "__main__":
    main()
