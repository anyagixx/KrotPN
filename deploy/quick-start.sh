#!/bin/bash
#
# KrotVPN Quick Start - One command deployment
# This is a wrapper for deploy-all.sh
#
# Usage: ./deploy/quick-start.sh
# Set RU_IP and DE_IP environment variables before running
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec "${SCRIPT_DIR}/deploy-all.sh" "$@"
