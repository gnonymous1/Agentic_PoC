#!/bin/bash
# GNONE Database Migration Runner
# Applies pending SQL migration files in lexicographic order.
# Supports rollback detection via .applied markers.
set -euo pipefail

MIGRATIONS_DIR="$(dirname "$0")/../migrations"
DB_URL="${DATABASE_URL:-postgresql://gnone:gnone@localhost:5432/gnone}"

echo "Running GNONE migrations against: $DB_URL"

for f in "$MIGRATIONS_DIR"/*.sql; do
    basename_f="$(basename "$f")"
    if [ -f "$MIGRATIONS_DIR/.applied/$basename_f" ]; then
        echo "  [SKIP] $basename_f (already applied)"
        continue
    fi
    echo "  [RUN]  $basename_f"
    psql "$DB_URL" -f "$f" -q
    mkdir -p "$MIGRATIONS_DIR/.applied"
    touch "$MIGRATIONS_DIR/.applied/$basename_f"
done

echo "All migrations applied."

# ── Rollback markers ──────────────────────────────────────────────────────────
# To rollback a specific migration, remove its .applied marker and run a
# corresponding down migration script (if available).  For example:
#
#   rm -f "$MIGRATIONS_DIR/.applied/003_audit_logging.sql"
#   psql "$DB_URL" -c "DROP TABLE IF EXISTS audit_log;"
#
# Then re-run this script to re-apply any remaining pending migrations.
