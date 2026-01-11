#!/bin/bash
# Alexandria Database Backup Script
#
# This script creates a backup of the PostgreSQL database and uploads it to R2.
# Set up as a Railway cron job or run manually.
#
# Required environment variables:
#   DATABASE_URL - PostgreSQL connection string
#   R2_ACCESS_KEY_ID - Cloudflare R2 access key
#   R2_SECRET_ACCESS_KEY - Cloudflare R2 secret key
#   R2_BUCKET_NAME - R2 bucket name
#   R2_ENDPOINT - R2 endpoint URL

set -e

# Configuration
BACKUP_DIR="/tmp/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="alexandria_backup_${DATE}.sql.gz"
RETENTION_DAYS=30

echo "Starting Alexandria backup at $(date)"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Extract database connection details from DATABASE_URL
# Format: postgresql+asyncpg://user:pass@host:port/dbname
DB_URL="${DATABASE_URL/postgresql+asyncpg/postgresql}"

echo "Creating database dump..."
pg_dump "$DB_URL" | gzip > "$BACKUP_DIR/$BACKUP_FILE"

BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
echo "Backup created: $BACKUP_FILE ($BACKUP_SIZE)"

# Upload to R2 using AWS CLI (R2 is S3-compatible)
if [ -n "$R2_ACCESS_KEY_ID" ] && [ -n "$R2_SECRET_ACCESS_KEY" ]; then
    echo "Uploading to Cloudflare R2..."

    export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
    export AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"

    aws s3 cp "$BACKUP_DIR/$BACKUP_FILE" \
        "s3://$R2_BUCKET_NAME/backups/$BACKUP_FILE" \
        --endpoint-url "$R2_ENDPOINT"

    echo "Upload complete"

    # Clean up old backups (keep last RETENTION_DAYS days)
    echo "Cleaning up old backups..."
    CUTOFF_DATE=$(date -d "-${RETENTION_DAYS} days" +%Y%m%d)

    aws s3 ls "s3://$R2_BUCKET_NAME/backups/" --endpoint-url "$R2_ENDPOINT" | while read -r line; do
        FILE=$(echo "$line" | awk '{print $4}')
        if [[ $FILE =~ alexandria_backup_([0-9]{8})_ ]]; then
            FILE_DATE="${BASH_REMATCH[1]}"
            if [[ "$FILE_DATE" < "$CUTOFF_DATE" ]]; then
                echo "Deleting old backup: $FILE"
                aws s3 rm "s3://$R2_BUCKET_NAME/backups/$FILE" --endpoint-url "$R2_ENDPOINT"
            fi
        fi
    done
else
    echo "R2 credentials not set, keeping backup locally"
fi

# Clean up local backup
rm -f "$BACKUP_DIR/$BACKUP_FILE"

echo "Backup completed successfully at $(date)"
