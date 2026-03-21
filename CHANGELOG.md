# Changelog

All notable changes to this project will be documented in this file.

## [2.1.3] - 2026-03-21

### Changed
- **MAJOR**: Complete rewrite - now deploys directly to servers via SSH
  - Nothing is installed locally on your laptop
  - All installation happens on RU and DE servers
  - Single script handles everything remotely

### Architecture
```
Before (v2.1.2):
  Laptop → clone locally → deploy to servers

After (v2.1.3):
  Laptop → SSH to RU server → clone on RU → deploy to both servers
```

### Benefits
- No local disk space needed
- No sudo required on laptop
- Cleaner deployment process
- All files stored on the server

## [2.1.2] - 2026-03-21

### Changed
- **MAJOR**: Simplified installation - now uses SSH password authentication instead of SSH keys
  - No more manual SSH key setup required
  - Script asks for username/password for each server
  - Password input shows asterisks for security
- Removed complex ASCII art banner - replaced with simple "KROTVPN" text
- Default SSH username is `root`

### Fixed
- Interactive input now works correctly when running via `curl | bash`
- All `read` commands use `/dev/tty` for terminal input

## [2.1.1] - 2026-03-21

### Fixed
- **CRITICAL**: Fixed interactive input when running via `curl | bash`
  - Changed `read` to `read < /dev/tty` to read from terminal instead of pipe
- Fixed ASCII art banner - now correctly shows "KROTVPN" instead of garbled text

## [2.1.0] - 2026-03-21

### Added
- **Interactive Installer** - one-line installation via curl/wget
- **HTTPS Support** - self-signed SSL certificates for all services
- **Nginx SSL Proxy** - new Docker container for SSL termination
- **HTTP to HTTPS redirect** - automatic redirect from HTTP to HTTPS
- **Security headers** - X-Frame-Options, X-Content-Type-Options, X-XSS-Protection

## [2.0.1] - 2026-03-21

### Fixed
- **CRITICAL**: Fixed deployment scripts dependency order (RU must be deployed before DE)

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

## [1.0.0] - 2026-03-20

### Added
- Initial release
