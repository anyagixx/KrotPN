# KrotVPN Agent Guide

This repository uses a practical GRACE-lite workflow for multi-agent development.

## Read Order

Every new agent should read files in this exact order before changing code:

1. `docs/current-status.xml`
2. `docs/knowledge-graph.xml`
3. `docs/development-plan.xml`
4. `docs/verification-plan.xml`
5. `README.md`

## Project Reality

- `KrotVPN` is not a greenfield project. It is an implemented MVP in hardening/stabilization.
- The main risks are currently in security, deployment, VPN topology migration, and verification discipline.
- Code is the source of truth when docs lag, but docs must be updated after meaningful changes.

## Main Subsystems

- `backend/app/core`: config, DB, security, bootstrap
- `backend/app/users`: auth, profile, Telegram auth
- `backend/app/vpn`: VPN clients, configs, AWG integration, nodes/routes
- `backend/app/billing`: plans, subscriptions, payments, YooKassa
- `backend/app/referrals`: referral codes and bonuses
- `backend/app/admin`: admin analytics/system endpoints
- `backend/app/routing`: split-tunneling and host routing logic
- `frontend`: user dashboard
- `frontend-admin`: admin panel
- `telegram-bot`: bot client over backend API
- `deploy`, `install.sh`, `nginx`, `docker-compose.yml`: operational surface

## Working Rules

- Do not assume deployment is safe by default.
- Treat VPN and routing code as host-coupled, not purely containerized.
- If you change API shape, module ownership, or system behavior, update the GRACE-lite docs.
- If verification cannot be run, say exactly why.
- Prefer targeted, truthful updates over broad aspirational docs.
