# Changelog

All notable changes to this project will be documented in this file.

## [2.1.5] - 2026-03-21

### Fixed
- **CRITICAL**: Fixed IPv6 detection - now forces IPv4 with multiple fallbacks
- **CRITICAL**: Fixed password passing - now uses config file instead of arguments
- Passwords with special characters ($, !, &, etc.) now work correctly
- Added connection testing before deployment starts

### Changed
- Configuration now passed via `/tmp/krotvpn_deploy.conf` file
- IPv4 detection uses multiple fallback services (api4.ipify.org, ipv4.icanhazip.com, v4.ident.me)
- Better error messages with helpful hints

### Architecture
```
install.sh (laptop)
    │
    ├─► Creates /tmp/krotvpn_deploy.conf on RU server
    │   (contains all credentials safely)
    │
    └─► Runs deploy-on-server.sh
            │
            └─► Reads config, sets up both servers
```

## [2.1.4] - 2026-03-21

### Fixed
- **CRITICAL**: Fixed deployment - created deploy-on-server.sh
- Simplified install.sh - passes credentials as script arguments

## [2.1.3] - 2026-03-21

### Changed
- **MAJOR**: Complete rewrite - now deploys directly to servers via SSH

## [2.1.2] - 2026-03-21

### Changed
- **MAJOR**: Simplified installation - now uses SSH password authentication

## [2.1.1] - 2026-03-21

### Fixed
- **CRITICAL**: Fixed interactive input when running via `curl | bash`

## [2.1.0] - 2026-03-21

### Added
- **Interactive Installer** - one-line installation via curl/wget
- **HTTPS Support** - self-signed SSL certificates for all services

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

## [1.0.0] - 2026-03-20

### Added
- Initial release
