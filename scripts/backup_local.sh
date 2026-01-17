#!/bin/bash
# Alexandria Local Database Backup Script
#
# Creates a local PostgreSQL dump for backup purposes.
# Run this script periodically to keep local backups.
#
# Usage:
#   ./scripts/backup_local.sh                    # Backup to default location
#   ./scripts/backup_local.sh /path/to/backups   # Backup to custom location
#
# Default connection uses local development settings.
# Override with environment variables if needed:
#   PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE

set -e

# Configuration - can be overridden with env vars
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGPASSWORD="${PGPASSWORD:-localdev}"
PGDATABASE="${PGDATABASE:-alexandria}"

# Backup location
BACKUP_DIR="${1:-$HOME/alexandria-backups}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="alexandria_backup_${DATE}.sql.gz"

echo "=================================="
echo "Alexandria Local Backup"
echo "=================================="
echo "Date: $(date)"
echo "Database: $PGDATABASE@$PGHOST:$PGPORT"
echo "Backup dir: $BACKUP_DIR"
echo ""

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Export password for pg_dump
export PGPASSWORD

echo "Creating database dump..."
pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" "$PGDATABASE" | gzip > "$BACKUP_DIR/$BACKUP_FILE"

BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
echo ""
echo "Backup created successfully!"
echo "  File: $BACKUP_DIR/$BACKUP_FILE"
echo "  Size: $BACKUP_SIZE"
echo ""

# Show recent backups
echo "Recent backups:"
ls -lht "$BACKUP_DIR"/alexandria_backup_*.sql.gz 2>/dev/null | head -5 || echo "  (none found)"
echo ""

# Optional: Clean up old backups (keep last 10)
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/alexandria_backup_*.sql.gz 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt 10 ]; then
    echo "Cleaning up old backups (keeping last 10)..."
    ls -1t "$BACKUP_DIR"/alexandria_backup_*.sql.gz | tail -n +11 | xargs rm -f
    echo "Done."
fi

echo ""
echo "To restore this backup, run:"
echo "  gunzip -c $BACKUP_DIR/$BACKUP_FILE | psql -h $PGHOST -p $PGPORT -U $PGUSER $PGDATABASE"
echo ""
echo "=================================="
