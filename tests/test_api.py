"""Tests for dashboard page routes and JSON API endpoints.

The dashboard lazily trains the World Model once (lru_cache), so these tests
share that cached pipeline and stay fast after the first call.
"""

from pathlib import Path

import pytest

from netwatch.dashboard.app import app

FRONTEND_INDEX = (
    Path(__file__).resolve().parent.parent / "frontend" / "dist" / "index.html"
)

PAGE_ROUTES = [
    "/", "/overview", "/analyze", "/network-state", "/forecast",
    "/graph", "/mitre", "/explainability", "/counterfactual",
    "/model-test", "/evaluation", "/scenarios", "/system",
    "/history", "/report",
]

API_ROUTES = [
    "/api/health", "/api/forecast", "/api/graph", "/api/counterfactual",
    "/api/evaluation", "/api/ensemble", "/api/mitre", "/api/topology",
    "/api/entities", "/api/models/status", "/api/network-state",
    "/api/scenarios", "/api/history", "/api/report", "/api/test-modules",
]


@pytest.fixture(scope="module")
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.mark.parametrize("path", PAGE_ROUTES)
def test_page_route_returns_200(client, path):
    if not FRONTEND_INDEX.is_file():
        pytest.skip("frontend/dist not built in this environment; run npm run build")
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


def test_upload_model_zip(client):
    import io
    import zipfile

    # Create in-memory test zip containing dummy model file
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("test_dummy.pkl", b"dummy model content")
    zip_buffer.seek(0)

    resp = client.post("/api/upload",
                       data={"file": (zip_buffer, "test_models.zip")},
                       content_type="multipart/form-data")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["type"] == "model_package"


def test_unknown_api_route_returns_json_404(client):
    resp = client.get("/api/definitely-not-a-route")
    assert resp.status_code == 404
    assert resp.is_json


def test_spa_route_serves_index_html(client):
    resp = client.get("/some/client/route")
    assert resp.status_code == 200
    assert "text/html" in resp.content_type
    assert b"<div id=\"root\">" in resp.data or b"root" in resp.data


def test_zip_inspect(client):
    import io
    import zipfile

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("recon.pcap", b"\xd4\xc3\xb2\xa1 fake pcap bytes")
        zf.writestr("normal.pcapng", b"fake pcapng bytes")
    zip_buffer.seek(0)

    resp = client.post("/api/zip/inspect",
                       data={"file": (zip_buffer, "capture.zip")},
                       content_type="multipart/form-data")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["has_traffic"] is True
    names = [m["name"] for m in data["traffic_members"]]
    assert "recon.pcap" in names and "normal.pcapng" in names
