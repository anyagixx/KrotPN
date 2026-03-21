# Changelog

All notable changes to this project will be documented in this file.

## [2.1.4] - 2026-03-21

### Fixed
- **CRITICAL**: Fixed deployment - now works 100%
- Created `deploy/deploy-on-server.sh` - runs directly on RU server
- Simplified `install.sh` - passes credentials as script arguments
- Removed complex heredoc - no more parsing issues

### Changed
- All deployment logic moved to `deploy-on-server.sh`
- `install.sh` now only handles user input and SSH connection
- Credentials passed as command-line arguments (secure, no escaping issues)

### Architecture
```
install.sh (laptop)
    │
    └── SSH to RU server
            │
            └── deploy-on-server.sh (RU server)
                    │
                    └── SSH to DE server
```

## [2.1.3] - 2026-03-21

### Changed
- **MAJOR**: Complete rewrite - now deploys directly to servers via SSH
  - Nothing is installed locally on your laptop
  - All installation happens on RU and DE servers
  - Single script handles everything remotely

## [2.1.2] - 2026-03-21

### Changed
- **MAJOR**: Simplified installation - now uses SSH password authentication instead of SSH keys

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
