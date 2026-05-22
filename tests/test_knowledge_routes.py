"""Tests for api/routes/knowledge.py."""


class TestKnowledgeRoutes:
    def test_router_registered(self):
        from api.routes.knowledge import router
        assert router is not None
        routes = [r.path for r in router.routes]
        assert "/knowledge/stats" in routes
        assert "/knowledge/search" in routes
        assert "/knowledge/fragments" in routes
        assert "/knowledge/snippets" in routes
        assert "/knowledge/generate-refs" in routes

    def test_router_included_in_app(self):
        from api.server import app
        found = any(
            hasattr(route, "path") and str(route.path).startswith("/knowledge")
            for route in app.routes
        )
        assert found, "knowledge router not found in app"
