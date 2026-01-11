#!/bin/bash
# Alexandria Database Restore Script
#
# Restores a database backup from R2 storage.
#
# Usage: ./restore.sh <backup_filename>
# Example: ./restore.sh alexandria_backup_20240115_030000.sql.gz

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_filename>"
    echo ""
    echo "Available backups:"
    aws s3 ls "s3://$R2_BUCKET_NAME/backups/" --endpoint-url "$R2_ENDPOINT"
    exit 1
fi

BACKUP_FILE="$1"
RESTORE_DIR="/tmp/restore"

echo "Starting restore of $BACKUP_FILE at $(date)"

# Create restore directory
mkdir -p "$RESTORE_DIR"

# Download from R2
echo "Downloading backup from R2..."
export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"

aws s3 cp \
    "s3://$R2_BUCKET_NAME/backups/$BACKUP_FILE" \
    "$RESTORE_DIR/$BACKUP_FILE" \
    --endpoint-url "$R2_ENDPOINT"

# Extract database connection details
DB_URL="${DATABASE_URL/postgresql+asyncpg/postgresql}"

# Confirm before proceeding
echo ""
echo "WARNING: This will DROP and recreate the database!"
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

# Restore
echo "Restoring database..."
gunzip -c "$RESTORE_DIR/$BACKUP_FILE" | psql "$DB_URL"

# Clean up
rm -rf "$RESTORE_DIR"

echo "Restore completed successfully at $(date)"
