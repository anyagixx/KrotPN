# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0] - 2026-03-21

### Added
- Full commercial VPN service platform
- User registration with email and Telegram OAuth
- Subscription system (trial, 1/3/6/12 months)
- YooKassa payment integration
- Referral program (+7 days bonus for referrals)
- Telegram bot for user management
- Admin panel (separate React frontend)
- Split-tunneling (Russian traffic bypass via ipset)
- PWA support for mobile installation
- Internationalization (Russian/English)
- Background tasks scheduler
- Security analysis report
- Auto-deployment scripts for RU/DE servers

### Security
- bcrypt password hashing via passlib
- JWT tokens (15min access + 7days refresh)
- Rate limiting with slowapi
- CORS whitelist configuration
- No hardcoded secrets (all via env vars)
- XSS protection (React auto-escaping)
- Shell injection protection (subprocess_exec)

### Infrastructure
- Docker Compose with 6 services
- PostgreSQL 15 + Redis 7
- AmneziaWG protocol with obfuscation params
- Two-server architecture (RU Entry + DE Exit)
- Health checks for all containers
- Systemd services for VPN routing

### Documentation
- README.md with project overview
- QUICKSTART.md for fast deployment
- DEPLOYMENT_GUIDE.md for production setup
- ANALYSIS_REPORT.md with security audit

## [1.0.0] - 2026-03-20

### Added
- Initial release
- Basic VPN management functionality
- AmneziaWG integration
- Deployment scripts
