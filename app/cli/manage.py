"""
Management CLI for GNONE platform operations.
"""

import argparse
import asyncio
import sys


async def cmd_health(args):
    from app.infrastructure.cache import cache
    from app.infrastructure.db import db
    from app.infrastructure.health import health_registry

    health_registry.register("database", db.health)
    health_registry.register("cache", cache.health)

    results = await health_registry.check_all()
    all_ok = True
    for r in results:
        status = "OK" if r.healthy else "FAIL"
        all_ok = all_ok and r.healthy
        print(f"  [{status}] {r.service} ({r.latency_ms}ms)")
    return 0 if all_ok else 1


async def cmd_seed(args):
    from app.infrastructure.db import db
    await db.connect()
    print(f"Seeding {args.count} records...")
    await db.disconnect()
    return 0


async def cmd_encrypt_key(args):
    from app.services.encryption import generate_key
    key = generate_key()
    print(key)
    return 0


def main():
    parser = argparse.ArgumentParser(description="GNONE Platform Management CLI")
    subparsers = parser.add_subparsers(dest="command")

    health_parser = subparsers.add_parser("health", help="Run health checks")

    seed_parser = subparsers.add_parser("seed", help="Seed test data")
    seed_parser.add_argument("--count", type=int, default=10)

    subparsers.add_parser("encrypt-key", help="Generate a new AES-256-GCM encryption key")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "health": cmd_health,
        "seed": cmd_seed,
        "encrypt-key": cmd_encrypt_key,
    }

    return asyncio.run(commands[args.command](args))


if __name__ == "__main__":
    sys.exit(main())
