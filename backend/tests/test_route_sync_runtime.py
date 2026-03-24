from app.routing.manager import RoutingManager


def test_build_route_sync_plan_tracks_incremental_adds_and_removals():
    manager = RoutingManager()

    plan = manager._build_route_sync_plan(
        current_direct={"1.1.1.1/32", "2.2.2.0/24"},
        current_vpn={"8.8.8.8/32"},
        desired_direct={"2.2.2.0/24", "3.3.3.3/32"},
        desired_vpn={"8.8.8.8/32", "9.9.9.9/32"},
    )

    assert plan.add_direct == {"3.3.3.3/32"}
    assert plan.remove_direct == {"1.1.1.1/32"}
    assert plan.add_vpn == {"9.9.9.9/32"}
    assert plan.remove_vpn == set()


async def test_collect_desired_route_sets_normalizes_ips_and_resolved_domains():
    manager = RoutingManager()

    async def fake_resolve(domain: str) -> str | None:
        mapping = {
            "portal.example.com": "4.4.4.4",
        }
        return mapping.get(domain)

    manager._resolve_domain_to_ipv4 = fake_resolve  # type: ignore[method-assign]

    direct, vpn = await manager._collect_desired_route_sets(
        [
            {"address": "10.0.0.5", "route_type": "direct"},
            {"address": "portal.example.com", "route_type": "vpn"},
        ]
    )

    assert direct == {"10.0.0.5/32"}
    assert vpn == {"4.4.4.4/32"}
