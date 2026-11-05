from app import create_app


def test_health_endpoint_returns_ok():
    response = create_app().test_client().get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_analyze_endpoint_validates_requests_instead_of_returning_placeholder():
    response = create_app().test_client().post("/analyze", json={})

    assert response.status_code == 400
    assert response.get_json() == {"message": "Add a question to continue."}


def test_home_explains_when_frontend_has_not_been_built(tmp_path):
    response = create_app(frontend_dist=tmp_path / "dist").test_client().get("/")

    assert response.status_code == 503
    assert "npm run build" in response.get_json()["message"]


def test_client_side_route_serves_frontend_for_refresh(tmp_path):
    frontend_dist = tmp_path / "dist"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("<main>WorthRot app</main>")

    response = create_app(frontend_dist=frontend_dist).test_client().get("/compare")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "<main>WorthRot app</main>"


def test_client_route_fallback_does_not_shadow_api(tmp_path):
    frontend_dist = tmp_path / "dist"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("<main>WorthRot app</main>")

    response = create_app(frontend_dist=frontend_dist).test_client().post(
        "/analyze", json={}
    )

    assert response.status_code == 400
    assert response.get_json() == {"message": "Add a question to continue."}
