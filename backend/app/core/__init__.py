# FILE: backend/app/core/__init__.py
# VERSION: 1.0.0
# ROLE: BARREL
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: Core module re-exports and circular dependency documentation
#   SCOPE: Aggregates config, database, security, dependencies for convenient imports
#   DEPENDS: M-001 submodules (config, database, security, dependencies)
#   LINKS: M-001 (backend-core), all modules importing from app.core
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   Settings, get_settings, settings - Configuration from config.py
#   engine, async_session_maker, get_session, get_db_context, init_db - Database from database.py
#   hash_password, verify_password, create_access_token, create_refresh_token, verify_token, encrypt_data, decrypt_data - Security from security.py
#   get_current_user, get_current_admin, get_current_superuser, CurrentUser, OptionalUser, CurrentAdmin, CurrentSuperuser, DBSession - Dependencies from dependencies.py
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""Core module exports.

KNOWN CIRCULAR DEPENDENCY CHAINS
=================================
This module and its submodules use lazy (deferred) imports inside functions
to avoid circular dependency errors at module load time. The main chains are:

1. app.core.database -> app.vpn.amneziawg -> app.vpn.models -> app.core.database
   Migration helpers in database.py import wg_manager, which imports models.
   Workaround: imports are deferred inside migration functions.

2. app.vpn.service -> app.billing.service -> app.core.database
   Billing service needs the session factory, which lives in database.py.
   Workaround: services import database objects at module level (safe because
   database.py does not import billing), but routers defer service imports.

3. app.vpn.router -> app.vpn.service -> app.routing.manager -> app.vpn.models
   Routing manager may reference VPN models, creating a triangle.
   Workaround: routing_manager is a singleton injected at module level in
   vpn/service.py; routers import services directly.

4. app.tasks.scheduler -> app.vpn.models / app.billing.models
   Scheduler imports models inside task functions to avoid boot-time cycles
   when the scheduler module is loaded before init_db() runs.

These lazy imports are a pragmatic stopgap. A proper fix would require
introducing a dependency-injection container or restructuring module
boundaries so that models, services, and infrastructure layers form a
strict DAG with no back-edges.
"""
from app.core.config import Settings, get_settings, settings
from app.core.database import (
    async_session_maker,
    engine,
    get_db_context,
    get_session,
    init_db,
)
from app.core.dependencies import (
    CurrentAdmin,
    CurrentSuperuser,
    CurrentUser,
    DBSession,
    OptionalUser,
    get_current_admin,
    get_current_superuser,
    get_current_user,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decrypt_data,
    encrypt_data,
    hash_password,
    verify_password,
    verify_token,
)

__all__ = [
    # Config
    "Settings",
    "get_settings",
    "settings",
    # Database
    "engine",
    "async_session_maker",
    "get_session",
    "get_db_context",
    "init_db",
    # Security
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "encrypt_data",
    "decrypt_data",
    # Dependencies
    "get_current_user",
    "get_current_admin",
    "get_current_superuser",
    "CurrentUser",
    "OptionalUser",
    "CurrentAdmin",
    "CurrentSuperuser",
    "DBSession",
]
