#!/bin/bash
# START_MODULE_CONTRACT: M-012-ROLLBACK
# PURPOSE: Deploy rollback — backup and restore .env, SSL certs, AWG configs
# SCOPE: backup, restore, list commands with timestamped backups in /opt/KrotVPN/backups/
# INPUTS: Command (backup|restore|list), optional backup timestamp
# OUTPUTS: Timestamped backup archives or restored state
# DEPENDENCIES: M-012 (deploy-surface)
# VERIFICATION: V-M-021 — backup created and restore produces working state
# END_MODULE_CONTRACT: M-012-ROLLBACK
#
# KrotVPN Rollback Script
# Backs up and restores .env, SSL certs, and AWG configs
#
# Usage:
#   ./deploy/rollback.sh backup   — Create a timestamped backup
#   ./deploy/rollback.sh restore  — Restore from the latest backup
#   ./deploy/rollback.sh list     — List available backups
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BACKUP_DIR="/opt/KrotVPN/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

usage() {
    echo "Usage: $0 {backup|restore|list}"
    echo ""
    echo "  backup   — Create a timestamped backup of .env, SSL certs, and AWG configs"
    echo "  restore  — Restore from the latest backup"
    echo "  list     — List available backups"
    exit 1
}

create_backup() {
    local dest="${BACKUP_DIR}/${TIMESTAMP}"
    mkdir -p "${dest}"

    echo -e "${BLUE}[ROLLBACK] Creating backup at ${dest}${NC}"

    # Backup .env
    if [ -f /opt/KrotVPN/.env ]; then
        cp /opt/KrotVPN/.env "${dest}/.env"
        echo -e "${GREEN}  ✓ Backed up .env${NC}"
    else
        echo -e "${YELLOW}  ⚠ .env not found, skipping${NC}"
    fi

    # Backup SSL certs
    if [ -d /opt/KrotVPN/ssl ]; then
        mkdir -p "${dest}/ssl"
        cp -r /opt/KrotVPN/ssl/* "${dest}/ssl/" 2>/dev/null || true
        echo -e "${GREEN}  ✓ Backed up SSL certs${NC}"
    else
        echo -e "${YELLOW}  ⚠ SSL directory not found, skipping${NC}"
    fi

    # Backup AWG configs
    if [ -d /etc/amnezia/amneziawg ]; then
        mkdir -p "${dest}/amneziawg"
        cp -r /etc/amnezia/amneziawg/* "${dest}/amneziawg/" 2>/dev/null || true
        echo -e "${GREEN}  ✓ Backed up AWG configs${NC}"
    else
        echo -e "${YELLOW}  ⚠ AWG config directory not found, skipping${NC}"
    fi

    echo -e "${GREEN}[ROLLBACK] Backup complete: ${dest}${NC}"
}

restore_backup() {
    local latest
    latest=$(ls -1d "${BACKUP_DIR}"/*/ 2>/dev/null | sort -r | head -1)

    if [ -z "$latest" ]; then
        echo -e "${RED}[ROLLBACK] No backups found in ${BACKUP_DIR}${NC}"
        exit 1
    fi

    echo -e "${YELLOW}[ROLLBACK] Restoring from: ${latest}${NC}"

    # Create a pre-restore backup
    create_backup

    # Restore .env
    if [ -f "${latest}/.env" ]; then
        cp "${latest}/.env" /opt/KrotVPN/.env
        chmod 600 /opt/KrotVPN/.env
        echo -e "${GREEN}  ✓ Restored .env${NC}"
    fi

    # Restore SSL certs
    if [ -d "${latest}/ssl" ]; then
        mkdir -p /opt/KrotVPN/ssl
        cp -r "${latest}/ssl/"* /opt/KrotVPN/ssl/ 2>/dev/null || true
        echo -e "${GREEN}  ✓ Restored SSL certs${NC}"
    fi

    # Restore AWG configs
    if [ -d "${latest}/amneziawg" ]; then
        mkdir -p /etc/amnezia/amneziawg
        cp -r "${latest}/amneziawg/"* /etc/amnezia/amneziawg/ 2>/dev/null || true
        echo -e "${GREEN}  ✓ Restored AWG configs${NC}"
    fi

    echo -e "${GREEN}[ROLLBACK] Restore complete. Restart services to apply changes.${NC}"
    echo -e "${YELLOW}  docker compose -f /opt/KrotVPN/docker-compose.yml restart${NC}"
}

list_backups() {
    echo -e "${BLUE}[ROLLBACK] Available backups:${NC}"
    ls -1d "${BACKUP_DIR}"/*/ 2>/dev/null | sort -r | while read -r dir; do
        echo -e "  ${GREEN}${dir}${NC}"
    done

    local count
    count=$(ls -1d "${BACKUP_DIR}"/*/ 2>/dev/null | wc -l)
    if [ "$count" -eq 0 ]; then
        echo -e "${YELLOW}  No backups found${NC}"
    fi
}

case "${1:-}" in
    backup)
        create_backup
        ;;
    restore)
        restore_backup
        ;;
    list)
        list_backups
        ;;
    *)
        usage
        ;;
esac
