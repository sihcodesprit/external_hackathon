"""Tests for dashboard page routes and JSON API endpoints.

The dashboard lazily trains the World Model once (lru_cache), so these tests
share that cached pipeline and stay fast after the first call.
"""

import pytest

from netwatch.dashboard.app import app

PAGE_ROUTES = [
    "/dashboard", "/radar", "/graph", "/counterfactual",
    "/stages", "/explainability", "/evaluation", "/scenarios",
    "/ensemble",
]

API_ROUTES = [
    "/api/forecast", "/api/graph", "/api/counterfactual", "/api/evaluation",
    "/api/ensemble",
]


@pytest.fixture(scope="module")
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.mark.parametrize("path", PAGE_ROUTES)
def test_page_route_returns_200(client, path):
    resp = client.get(path)
    assert resp.status_code == 200


@pytest.mark.parametrize("path", API_ROUTES)
def test_api_route_returns_json(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.is_json


def test_api_forecast_structure(client):
    data = client.get("/api/forecast").get_json()
    assert data["status"] == "ok"
    assert "current" in data
    assert "future" in data
    assert "k" in data
    assert all("step" in s and "risk" in s and "stage" in s
               for s in data["future"])


def test_api_counterfactual_has_recommendation(client):
    data = client.get("/api/counterfactual").get_json()
    assert "results" in data
    assert "recommendation" in data
    assert "recommended_action" in data["recommendation"]
    # recommendation reflects actual model outputs, with a reason
    assert data["recommendation"]["reason"]


def test_api_evaluation_has_world_model_and_baselines(client):
    data = client.get("/api/evaluation").get_json()
    me = data.get("model_evaluation", {})
    assert "world_model" in me
    assert "baselines" in me


def test_api_graph_shape(client):
    data = client.get("/api/graph").get_json()
    assert "nodes" in data
    assert "edges" in data
    assert data["counts"]["nodes"] == len(data["nodes"])
    assert data["counts"]["edges"] == len(data["edges"])


def test_api_scenario_post(client):
    resp = client.post("/api/scenario",
                       json={"k": 3, "actions": ["isolate_host"]})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] in ("ok", "no_history")
    assert "recommendation" in data
    if data["status"] == "ok":
        assert set(data["results"]) == {"isolate_host"}


def test_unknown_page_returns_json_404(client):
    resp = client.get("/definitely-not-a-page")
    assert resp.status_code == 404
    assert resp.is_json