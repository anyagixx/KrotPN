# FILE: backend/app/users/__init__.py
# VERSION: 1.0.0
# ROLE: BARREL
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: User authentication, profile management, Telegram-linked identity flows
#   SCOPE: Email/password auth, Telegram auth, JWT token handling, user profile CRUD
#   DEPENDS: M-001 (backend-core)
#   LINKS: M-002 (users), V-M-002
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   User, UserCreate, UserResponse - User models and schemas
#   UserService - Authentication, registration, profile management, Telegram auth
#   router, telegram_router - FastAPI routers for auth and profile endpoints
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""Users package."""
