"""
Routing API router.
"""
# <!-- GRACE: module="M-007" api-group="Routing API" -->

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core import CurrentAdmin, CurrentUser, DBSession
from app.routing.manager import routing_manager
from app.routing.models import (
    CustomRoute,
    CustomRouteCreate,
    CustomRouteResponse,
    RouteType,
    RoutingStatus,
)

router = APIRouter(prefix="/api/routing", tags=["routing"])

# Track last RU update time globally
_last_ru_update: datetime | None = None


@router.get("/status", response_model=RoutingStatus)
async def get_routing_status(
    admin: CurrentAdmin,
    session: DBSession,
):
    """Get routing system status."""
    global _last_ru_update
    
    ipset_stats = await routing_manager.get_ipset_stats()
    tunnel_status = await routing_manager.check_tunnel_status()
    
    # Count custom routes
    result = await session.execute(select(CustomRoute).where(CustomRoute.is_active == True))
    custom_routes = result.scalars().all()
    
    return RoutingStatus(
        ru_ipset_entries=ipset_stats.get(routing_manager.IPSET_RU, {}).get("entries", 0),
        ru_ipset_status=ipset_stats.get(routing_manager.IPSET_RU, {}).get("status", "unknown"),
        tunnel_status=tunnel_status.get("status", "unknown"),
        custom_routes_count=len(custom_routes),
        last_ru_update=_last_ru_update,
    )


@router.post("/update-ru")
async def update_ru_ips(
    admin: CurrentAdmin,
):
    """Update Russian IP set."""
    global _last_ru_update
    
    success = await routing_manager.update_ru_ipset()
    
    if success:
        _last_ru_update = datetime.now(timezone.utc)
        return {"status": "updated", "updated_at": _last_ru_update.isoformat()}
    
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to update RU IPset",
    )


@router.get("/custom", response_model=list[CustomRouteResponse])
async def list_custom_routes(
    admin: CurrentAdmin,
    session: DBSession,
):
    """List all custom routes."""
    result = await session.execute(
        select(CustomRoute).order_by(CustomRoute.created_at.desc())
    )
    routes = result.scalars().all()
    
    return [
        CustomRouteResponse(
            id=r.id,
            address=r.address,
            route_type=r.route_type,
            description=r.description,
            is_active=r.is_active,
            created_at=r.created_at,
        )
        for r in routes
    ]


@router.post("/custom", response_model=CustomRouteResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_route(
    data: CustomRouteCreate,
    admin: CurrentAdmin,
    session: DBSession,
):
    """Create a custom route."""
    # Check for duplicates
    result = await session.execute(
        select(CustomRoute).where(CustomRoute.address == data.address)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Route already exists",
        )
    
    route = CustomRoute(
        address=data.address.strip(),
        route_type=data.route_type,
        description=data.description,
    )
    
    session.add(route)
    await session.flush()
    await session.refresh(route)
    
    # Sync with ipset
    routes = await _get_all_routes(session)
    await routing_manager.sync_custom_routes(routes)
    
    return CustomRouteResponse(
        id=route.id,
        address=route.address,
        route_type=route.route_type,
        description=route.description,
        is_active=route.is_active,
        created_at=route.created_at,
    )


@router.delete("/custom/{route_id}")
async def delete_custom_route(
    route_id: int,
    admin: CurrentAdmin,
    session: DBSession,
):
    """Delete a custom route."""
    route = await session.get(CustomRoute, route_id)
    
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Route not found",
        )
    
    await session.delete(route)
    await session.flush()
    
    # Sync with ipset
    routes = await _get_all_routes(session)
    await routing_manager.sync_custom_routes(routes)
    
    return {"status": "deleted"}


async def _get_all_routes(session) -> list[dict]:
    """Get all active routes as dicts."""
    result = await session.execute(
        select(CustomRoute).where(CustomRoute.is_active == True)
    )
    routes = result.scalars().all()
    return [
        {"address": r.address, "route_type": r.route_type.value}
        for r in routes
    ]
