from fastapi import APIRouter, Query
from app.dependencies import route_service

router = APIRouter(prefix="/api", tags=["Safe Routes"])


@router.get("/safe-places")
async def get_safe_places(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_m: int = Query(5000, description="Search radius in metres"),
):
    """Nearest safe shelter places from OpenStreetMap."""
    places = await route_service.get_safe_places(lat, lon, radius_m)
    return {"success": True, "count": len(places), "places": places}


@router.get("/safe-route")
async def get_safe_route(
    lat: float = Query(..., description="User latitude"),
    lon: float = Query(..., description="User longitude"),
    radius_m: int = Query(5000, description="Shelter search radius in metres"),
    profile: str = Query("driving-car", description="driving-car | foot-walking"),
):
    """Finds the nearest safe shelter and returns the route to it."""
    return await route_service.get_safe_route_to_shelter(
        lat=lat, lon=lon, radius_m=radius_m, profile=profile
    )


@router.get("/route")
async def get_direct_route(
    from_lat: float = Query(..., description="Origin latitude"),
    from_lon: float = Query(..., description="Origin longitude"),
    to_lat: float = Query(..., description="Destination latitude"),
    to_lon: float = Query(..., description="Destination longitude"),
    profile: str = Query("driving-car", description="driving-car | foot-walking"),
):
    """Point-to-point route between any two coordinates."""
    return await route_service.get_route(
        from_lat=from_lat, from_lon=from_lon,
        to_lat=to_lat,     to_lon=to_lon,
        profile=profile,
    )
