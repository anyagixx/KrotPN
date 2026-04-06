#!/bin/bash
# FILE: deploy/backup-db.sh
# VERSION: 1.0.0
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Automated PostgreSQL backup via pg_dump from docker container
#   SCOPE: pg_dump execution, gzipped backup storage, 7-backup retention
#   DEPENDS: M-012 (deploy-surface), PostgreSQL container running
#   LINKS: M-012 (deploy-surface), V-M-012
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   pg_dump pipeline - Dump DB to gzipped .sql.gz file in /opt/KrotVPN/backups/db/
#   retention_cleanup - Remove old backups keeping only last 7
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Converted to full GRACE MODULE_CONTRACT/MAP format, removed duplicate contract block
# END_CHANGE_SUMMARY
#
# KrotVPN Database Backup Script
# Runs pg_dump from the postgres container, saves timestamped backups,
# keeps only the last 7 backups. Suitable for cron.
#
# Usage:
#   ./deploy/backup-db.sh
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BACKUP_DIR="/opt/KrotVPN/backups/db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/krotvpn_${TIMESTAMP}.sql.gz"
KEEP=7

# Load .env for DB credentials if present
ENV_FILE="/opt/KrotVPN/.env"
if [ -f "$ENV_FILE" ]; then
    export $(grep -E '^[A-Z]' "$ENV_FILE" | xargs 2>/dev/null || true)
fi

DB_USER="${DB_USER:-krotvpn}"
DB_NAME="${DB_NAME:-krotvpn}"

mkdir -p "$BACKUP_DIR"

echo -e "${BLUE}[DB-BACKUP] Starting backup of ${DB_NAME}...${NC}"

docker exec krotvpn-db pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-acl | gzip > "$BACKUP_FILE"

if [ -f "$BACKUP_FILE" ] && [ -s "$BACKUP_FILE" ]; then
    FILESIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo -e "${GREEN}[DB-BACKUP] Backup complete: ${BACKUP_FILE} (${FILESIZE})${NC}"
else
    echo -e "${RED}[DB-BACKUP] Backup failed or empty!${NC}"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Cleanup old backups, keep only last $KEEP
echo -e "${BLUE}[DB-BACKUP] Cleaning up old backups (keeping last ${KEEP})...${NC}"
ls -1t "${BACKUP_DIR}"/krotvpn_*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
    rm -f "$old"
    echo -e "${YELLOW}  Removed: ${old}${NC}"
done

echo -e "${GREEN}[DB-BACKUP] Done. Total backups: $(ls -1 "${BACKUP_DIR}"/krotvpn_*.sql.gz 2>/dev/null | wc -l)${NC}"
