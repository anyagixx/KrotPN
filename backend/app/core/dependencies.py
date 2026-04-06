# FILE: backend/app/core/dependencies.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: FastAPI authentication and authorization dependency injection
#   SCOPE: JWT token verification, user/admin/superuser role checks, type aliases
#   DEPENDS: M-001 (config), M-001 (database), M-001 (security), M-002 (users models)
#   LINKS: M-001 (backend-core), M-002 (users), all protected API routers
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   get_current_user - Extract authenticated user from JWT, raise 401/403
#   get_current_user_optional - Return user if authenticated, None otherwise (no raise)
#   get_current_admin - Verify current user has ADMIN or SUPERADMIN role
#   get_current_superuser - Verify current user has SUPERADMIN role
#   CurrentUser, OptionalUser, CurrentAdmin, CurrentSuperuser, DBSession - Type aliases for Depends()
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""
FastAPI dependencies for authentication and authorization.
"""
# <!-- GRACE: module="M-001" contract="dependencies" -->

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.core.database import get_session
from app.core.security import verify_token
from app.users.models import User, UserRole

security = HTTPBearer(auto_error=False)


# START_BLOCK_AUTH_FUNCTIONS
async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """
    Get the current authenticated user from JWT token.
    Raises 401 if not authenticated.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = verify_token(credentials.credentials, expected_type="access")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await session.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


async def get_current_user_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User | None:
    """Get current user if authenticated, otherwise return None."""
    if credentials is None:
        return None

    user_id = verify_token(credentials.credentials, expected_type="access")
    if user_id is None:
        return None

    result = await session.execute(select(User).where(User.id == int(user_id)))
    return result.scalar_one_or_none()
# END_BLOCK_AUTH_FUNCTIONS


# START_BLOCK_ROLE_CHECKS
async def get_current_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Get current user and verify they have admin role.
    Raises 403 if not admin.
    """
    if user.role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def get_current_superuser(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Get current user and verify they have superadmin role.
    Raises 403 if not superadmin.
    """
    if user.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin access required",
        )
    return user


# Type aliases for dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
CurrentAdmin = Annotated[User, Depends(get_current_admin)]
CurrentSuperuser = Annotated[User, Depends(get_current_superuser)]
DBSession = Annotated[AsyncSession, Depends(get_session)]
# END_BLOCK_ROLE_CHECKS
