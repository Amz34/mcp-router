"""
mcp_router package initialization.
"""

from mcp_router.router import route_mcp_tools, detect_intent, RouteDecision

__version__ = "1.0.0"
__all__ = ["route_mcp_tools", "detect_intent", "RouteDecision"]
