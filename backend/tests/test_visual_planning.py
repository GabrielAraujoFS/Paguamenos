import json
from copy import deepcopy

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import PieceModel
from app.schemas import Briefing
from app.schemas.configuration import parse_rules
from app.services.catalog import Catalog, load_rules
from app.services.composition import PillowComposer, default_template
from app.services.gemini import GeminiGenerationService
from app.services.generation import GenerationError, MockGenerationService
from app.settings import GenerationConfig


BRIEF = Briefing(campaign_name="Demo", product_id="syn-001", objective="Apresentar",
                 target_audience="Adultos", channels=["feed"])
COPY = {"channel": "feed", "title": "Conheça", "subtitle": "Cuidado diário.", "cta": "Confira"}
PLAN = {"channel": "feed", "art_direction": "Fundo claro e equilibrado",
        "background_prompt": "Fundo abstrato em tons suaves com espaço livre",
        "layout": "produto_direita", "palette": ["#DDEEFF"], "concept": "Clareza",
        "visual_style": "Minimalista", "scenario": "Estúdio abstrato",
        "lighting": "Difusa", "decorative_elements": ["formas suaves"]}


def envelope(data, *, tokens=True):
    body = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(data)}]}}]}
    if tokens:
        body["usageMetadata"] = {"promptTokenCount": 100, "candidatesTokenCount": 40, "totalTokenCount": 140}
    return body


def service(handler, attempts=2):
    return GeminiGenerationService(GenerationConfig(provider="gemini", api_key="test-secret",
        visual_max_attempts=attempts), load_rules, httpx.MockTransport(handler))


def invoke(generator):
    return generator.generate_package(BRIEF, Catalog().get("syn-001"))


def test_valid_plan_and_single_structured_request():
    requests = []
    def handler(request):
        requests.append(request)
        payload = json.loads(request.content)
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        assert "visual_plans" in payload["generationConfig"]["responseJsonSchema"]["properties"]
        return httpx.Response(200, json=envelope({"pieces": [COPY], "visual_plans": [PLAN]}))
    package = invoke(service(handler))
    assert len(requests) == 1
    assert package.pieces[0].title == COPY["title"]
    assert package.visual_plans[0].layout == "produto_direita"
    assert "Não gerar preços" in package.visual_plans[0].background_prompt
    assert package.metadata.model == "gemini-3.5-flash-lite"
    assert (package.metadata.prompt_tokens, package.metadata.response_tokens, package.metadata.total_tokens) == (100, 40, 140)
    assert package.metadata.attempts == 1
    assert PillowComposer._layout(default_template(package.visual_plans[0].layout, package.visual_plans[0].channel))["product"].width > 0


@pytest.mark.parametrize('parsed', [False, True])
def test_package_preserves_creativity_and_rules_without_mock_templates(parsed):
    source = load_rules()
    original = parse_rules(source) if parsed else source
    snapshot = deepcopy(original)
    product = Catalog().get('syn-001')
    expected = parse_rules(original).model_dump(mode='json')
    del expected['generation']['templates']
    mock = MockGenerationService(lambda: original)
    before = mock.generate(BRIEF, product)

    def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload['contents'][0]['parts'][0]['text'])
        assert context['brand_rules'] == expected
        assert context['authorized_product'] == product.model_dump(mode='json')
        assert context['briefing'] == BRIEF.model_dump(mode='json')
        instructions = payload['systemInstruction']['parts'][0]['text']
        assert 'títulos e subtítulos originais' in instructions
        assert 'prioridade sobre a criatividade' in instructions
        assert 'disclaimer também será inserido pelo backend' in instructions
        return httpx.Response(200, json=envelope({'pieces': [COPY], 'visual_plans': [PLAN]}))

    generator = GeminiGenerationService(GenerationConfig(provider='gemini', api_key='test-secret'),
        lambda: original, httpx.MockTransport(handler))
    package = generator.generate_package(BRIEF, product)
    assert len(package.visual_plans) == 1
    assert original == snapshot
    assert mock.generate(BRIEF, product) == before


@pytest.mark.parametrize("visual,code", [
    (PLAN | {"layout": "inventado"}, "VISUAL_PLAN_CONTRACT_ERROR"),
    ({key: value for key, value in PLAN.items() if key != "scenario"}, "VISUAL_PLAN_CONTRACT_ERROR"),
    (PLAN | {"background_prompt": "Produto com preço R$ 1,00"}, "VISUAL_PLAN_CONTRACT_ERROR"),
])
def test_invalid_visual_plans_are_rejected(visual, code):
    with pytest.raises(GenerationError) as error:
        invoke(service(lambda request: httpx.Response(200, json=envelope({"pieces": [COPY], "visual_plans": [visual]})), attempts=1))
    assert error.value.code == code


def test_invalid_json_exhausts_bounded_attempts():
    calls = 0
    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP",
            "content": {"parts": [{"text": "{invalid"}]}}]})
    with pytest.raises(GenerationError) as error:
        invoke(service(handler))
    assert error.value.code == "VISUAL_PLAN_CONTRACT_ERROR"
    assert calls == 2


def test_api_failure_retries_then_reports_unavailable():
    calls = 0
    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(503)
    with pytest.raises(GenerationError) as error:
        invoke(service(handler))
    assert error.value.code == "GENERATION_UNAVAILABLE"
    assert calls == 2


def test_timeout_is_bounded():
    calls = 0
    def handler(request):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("timeout", request=request)
    with pytest.raises(GenerationError) as error:
        invoke(service(handler, attempts=2))
    assert error.value.code == "GENERATION_TIMEOUT"
    assert calls == 2


def test_auth_failure_does_not_retry():
    calls = 0
    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(403)
    with pytest.raises(GenerationError) as error:
        invoke(service(handler))
    assert error.value.code == "GENERATION_AUTH_ERROR"
    assert calls == 1


def test_mock_visual_plan_and_text_generation_stay_compatible():
    mock = MockGenerationService()
    package = invoke(mock)
    assert package.pieces == mock.generate(BRIEF, Catalog().get("syn-001"))
    assert package.visual_plans[0].layout == "produto_direita"
    assert package.metadata.provider == "mock"
    assert "Não gerar preços" in package.visual_plans[0].background_prompt
    banner = Briefing(campaign_name="Demo", product_id="syn-001", objective="Apresentar",
                      target_audience="Adultos", channels=["banner"])
    banner_package = mock.generate_package(banner, Catalog().get("syn-001"))
    assert len(banner_package.pieces) == 1 and banner_package.visual_plans == []


def test_campaign_persists_plan_without_changing_commercial_fields(tmp_path):
    app = create_app(database_url="sqlite:///" + (tmp_path / "visual.db").as_posix(),
                     generator=service(lambda request: httpx.Response(200,
                         json=envelope({"pieces": [COPY], "visual_plans": [PLAN]}))))
    with TestClient(app) as client:
        response = client.post("/campaigns/generate", json=BRIEF.model_dump(mode="json"))
        assert response.status_code == 201
        public_piece = response.json()["pieces"][0]
        assert public_piece["price"] == "8.90"
        assert public_piece["product_id"] == "syn-001"
        assert "visual" not in public_piece
        with app.state.sessions() as db:
            saved = db.get(PieceModel, public_piece["id"])
            assert saved.content["visual"]["plan"]["layout"] == "produto_direita"
            assert saved.content["visual"]["template"]["width"] == 1080
            assert saved.content["visual"]["generation"]["prompt_tokens"] == 100
        assert client.post(f"/campaigns/{response.json()['id']}/validate").status_code == 200
