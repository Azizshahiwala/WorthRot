from app import create_app


def test_health_endpoint_returns_ok():
    response = create_app().test_client().get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_analyze_endpoint_is_an_explicit_placeholder():
    response = create_app().test_client().post("/analyze", json={})

    assert response.status_code == 501
    assert response.get_json() == {
        "message": "Video analysis has not been implemented yet."
    }


def test_home_explains_when_frontend_has_not_been_built(tmp_path):
    response = create_app(frontend_dist=tmp_path / "dist").test_client().get("/")

    assert response.status_code == 503
    assert "npm run build" in response.get_json()["message"]
