import copy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models import CampaignModel, PieceModel, ReviewModel, ValidationModel
from app.services.catalog import load_rules


@pytest.fixture
def environment(tmp_path):
    url = "sqlite:///" + (tmp_path / "campaign-list.db").as_posix()
    app = create_app(database_url=url, rules_loader=lambda: copy.deepcopy(load_rules()))
    with TestClient(app) as client:
        yield client, app, url


def generate(client, name, channels=("feed",), objective="Apresentar"):
    response = client.post("/campaigns/generate", json={
        "campaign_name": name, "product_id": "syn-001", "objective": objective,
        "target_audience": "Adultos", "channels": list(channels),
    })
    assert response.status_code == 201
    return response.json()


def test_empty_and_invalid_pagination(environment):
    client, _, _ = environment
    assert client.get("/campaigns").json() == {
        "items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0,
    }
    for query in ("page=0", "page_size=0", "page_size=101", "page=abc",
                  "status=unknown", "channel=email", "search="):
        response = client.get("/campaigns?" + query)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_single_campaign_and_detail(environment):
    client, _, _ = environment
    created = generate(client, "Primeira")
    listing = client.get("/campaigns").json()
    assert listing["total"] == listing["total_pages"] == 1
    assert listing["items"] == [created]
    assert client.get(f'/campaigns/{created["id"]}').json() == created
    missing = client.get("/campaigns/nonexistent")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "CAMPAIGN_NOT_FOUND"


def test_ordering_pagination_and_restart(environment):
    client, app, url = environment
    campaigns = [generate(client, f"Campanha {n}") for n in range(5)]
    with app.state.sessions.begin() as db:
        # Ties must be broken by the stable UUID, not insertion order.
        for index, campaign in enumerate(campaigns):
            record = db.get(CampaignModel, campaign["id"])
            record.created_at = ("2026-10-24T12:00:00+00:00" if index < 3
                                 else "2026-10-23T12:00:00+00:00")
    expected = sorted(campaigns, key=lambda item: (
        "2026-10-24" if item in campaigns[:3] else "2026-10-23", item["id"]), reverse=True)
    first = client.get("/campaigns?page=1&page_size=2").json()
    second = client.get("/campaigns?page=2&page_size=2").json()
    third = client.get("/campaigns?page=3&page_size=2").json()
    assert [item["id"] for item in first["items"] + second["items"] + third["items"]] == [
        item["id"] for item in expected]
    assert (first["total"], first["page"], first["page_size"], first["total_pages"]) == (5, 1, 2, 3)
    assert client.get("/campaigns?page=4&page_size=2").json() == {
        "items": [], "total": 5, "page": 4, "page_size": 2, "total_pages": 3,
    }
    with TestClient(create_app(database_url=url)) as restarted:
        assert [item["id"] for item in restarted.get("/campaigns?page_size=100").json()["items"]] == [
            item["id"] for item in expected]


def test_filters_are_independent_and_do_not_duplicate_campaigns(environment):
    client, _, _ = environment
    mixed = generate(client, "Promoção Aurora", ("feed", "story"), "Conhecer")
    other = generate(client, "Campanha simples", ("banner",), "Apresentar")
    piece = mixed["pieces"][0]["id"]
    assert client.post(f"/pieces/{piece}/review", json={
        "decision": "rejected", "reviewer_id": "teste"}).status_code == 200
    cases = {
        "status=rejected": [mixed["id"]],
        "status=draft": [mixed["id"], other["id"]],
        "channel=story": [mixed["id"]],
        "channel=banner": [other["id"]],
        "search=promo%C3%A7%C3%A3o": [mixed["id"]],
        "search=CONHECER": [mixed["id"]],
        "search=Adultos": [mixed["id"], other["id"]],
        "status=rejected&channel=story&search=Aurora": [mixed["id"]],
        "status=rejected&channel=banner": [],
        "search=%25": [],
    }
    for query, ids in cases.items():
        result = client.get("/campaigns?" + query).json()
        assert result["total"] == len(ids), query
        assert {item["id"] for item in result["items"]} == set(ids), query
        assert len(result["items"]) == len(ids), query


def test_complete_creatives_histories_and_read_only_listing(environment):
    client, app, _ = environment
    campaign = generate(client, "Histórico", ("feed", "story", "banner"))
    validated = client.post(f'/campaigns/{campaign["id"]}/validate').json()
    assert len(validated["pieces"]) == 3
    approved_id, rejected_id = [piece["id"] for piece in validated["pieces"][:2]]
    assert client.post(f"/pieces/{approved_id}/review", json={
        "decision": "approved", "reviewer_id": "revisor"}).status_code == 200
    assert client.post(f"/pieces/{rejected_id}/review", json={
        "decision": "rejected", "reviewer_id": "revisor", "comment": "Ajustar"}).status_code == 200

    def snapshot():
        with app.state.sessions() as db:
            campaigns = [(c.id, c.created_at, c.briefing) for c in db.scalars(select(CampaignModel))]
            pieces = [(p.id, p.state, p.content) for p in db.scalars(select(PieceModel))]
            validations = [(v.id, v.results) for v in db.scalars(select(ValidationModel))]
            reviews = [(r.id, r.decision, r.comment) for r in db.scalars(select(ReviewModel))]
            return campaigns, pieces, validations, reviews

    before = snapshot()
    listing = client.get("/campaigns?page_size=1").json()
    result = listing["items"][0]
    assert result == client.get(f'/campaigns/{campaign["id"]}').json()
    assert [piece["state"] for piece in result["pieces"]] == ["approved", "rejected", "validated"]
    assert all(piece["validations"][0]["results"] for piece in result["pieces"])
    assert [len(piece["reviews"]) for piece in result["pieces"]] == [1, 1, 0]
    assert result["pieces"][1]["reviews"][0]["comment"] == "Ajustar"
    assert snapshot() == before


def test_listing_does_not_invalidate_stale_validation(environment):
    client, app, _ = environment
    campaign = generate(client, "Regras variáveis")
    validated = client.post(f'/campaigns/{campaign["id"]}/validate').json()
    assert validated["pieces"][0]["state"] == "validated"
    changed_rules = load_rules()
    changed_rules["version"] = "nova-versao"
    app.state.rules_loader = lambda: changed_rules
    listed = client.get("/campaigns").json()["items"][0]
    assert listed["pieces"][0]["state"] == "validated"
    with app.state.sessions() as db:
        assert db.get(PieceModel, listed["pieces"][0]["id"]).state == "validated"
