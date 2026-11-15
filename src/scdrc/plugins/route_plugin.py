"""
Semantic Kernel Plugin: Route lookup and logistics lanes.
"""

from __future__ import annotations
import json
from semantic_kernel.functions import kernel_function
from scdrc.data.repositories import RouteRepository


class RoutePlugin:
    """Tools for querying transit lanes, alternative freight modes, and carrier capacity."""

    def __init__(self, repo: RouteRepository):
        self.repo = repo

    @kernel_function(description="Find alternative transit lanes between origin and destination sites.")
    def find_alternative_routes(self, origin: str, dest: str) -> str:
        routes = self.repo.find_routes(origin, dest)
        return json.dumps(routes, indent=2)

    @kernel_function(description="Find all incoming transit routes connected to a destination site.")
    def find_routes_to_site(self, site_id: str) -> str:
        routes = self.repo.find_routes_to_dest(site_id)
        return json.dumps(routes, indent=2)
