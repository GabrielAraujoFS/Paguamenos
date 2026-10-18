import copy
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import create_app,local_origins
from app.models import PieceModel,ReviewModel
from app.services.catalog import load_rules,Catalog
from app.services.validation import validate_content

BRIEF=dict(campaign_name='Demo',product_id='syn-001',objective='Divulgar',target_audience='Adultos',channels=['feed','story','banner'])
@pytest.fixture
def env(tmp_path):
    url='sqlite:///'+(tmp_path/'test.db').as_posix()
    rules=load_rules()
    app=create_app(database_url=url,rules_loader=lambda:copy.deepcopy(rules))
    with TestClient(app) as client:
        yield client,app,rules,url

def generate(client,**changes):
    return client.post('/campaigns/generate',json=BRIEF|changes)
def review(client,piece,decision='approved'):
    return client.post(f'/pieces/{piece}/review',json=dict(decision=decision,reviewer_id='demo'))
def mutate(app,piece,**changes):
    with app.state.sessions.begin() as db:
        record=db.get(PieceModel,piece)
        record.content=record.content|changes

def test_health(env):
    assert env[0].get('/health').json()==dict(status='ok',generation_provider='mock')
def test_catalog(env):
    client=env[0]
    products=client.get('/products').json()
    assert len(products)==5
    assert products[0]['price']=='8.90'
    assert client.get('/products/syn-001').json()==products[0]
    assert client.get('/products/missing').status_code==404

def test_generation(env):
    response=generate(env[0])
    assert response.status_code==201
    campaign=response.json()
    assert len(campaign['pieces'])==3
    assert all(p['state']=='draft' and p['price']=='8.90' for p in campaign['pieces'])
    assert env[0].get(f'/campaigns/{campaign["id"]}').json()==campaign

def test_unknown_product(env):
    assert generate(env[0],product_id='missing').status_code==404

@pytest.mark.parametrize('changes,code',[
    ({'price':'0.01'},'PRICE_MATCH'),({'title':''},'REQUIRED_FIELD'),
    ({'title':'x'*100},'CHARACTER_LIMIT'),({'disclaimer':''},'REQUIRED_INFORMATION'),
    ({'authorized_offer':'inventada'},'OFFER_MATCH'),({'product_name':'outro'},'PRODUCT_NAME_MATCH'),
    ({'price':'NaN'},'PRICE_MATCH'),({'product_id':'missing'},'PRODUCT_EXISTS')])
def test_critical_blocks(env,changes,code):
    client,app,*_=env
    campaign=generate(client).json()
    piece=campaign['pieces'][0]['id']
    mutate(app,piece,**changes)
    # Non-finite prices cannot be represented by the public response contract.
    if changes.get('price')=='NaN':
        content=campaign['pieces'][0]|changes
        assert any(r.rule_code==code and not r.passed for r in validate_content(content,Catalog().get('syn-001'),load_rules()))
    else:
        result=client.post(f'/campaigns/{campaign["id"]}/validate')
        assert result.status_code==200
        assert any(r['rule_code']==code and not r['passed'] for r in result.json()['pieces'][0]['validations'][-1]['results'])
    assert review(client,piece).status_code==409

def test_invalid_channel(env):
    content=generate(env[0]).json()['pieces'][0]|{'channel':'invalid'}
    assert any(r.rule_code=='CHANNEL_ALLOWED' and not r.passed for r in validate_content(content,Catalog().get('syn-001'),load_rules()))

def test_requires_validation(env):
    assert review(env[0],generate(env[0]).json()['pieces'][0]['id']).status_code==409

def test_approval_persistence_restart(env):
    client,app,_,url=env
    campaign=generate(client).json()
    result=client.post(f'/campaigns/{campaign["id"]}/validate')
    assert all(p['state']=='validated' for p in result.json()['pieces'])
    piece=campaign['pieces'][0]['id']
    result=review(client,piece)
    assert result.status_code==200
    assert result.json()['state']=='approved'
    assert result.json()['reviews'][0]['created_at'].endswith('Z')
    with app.state.sessions() as db:
        assert db.scalars(select(ReviewModel)).one().reviewer_id=='demo'
    with TestClient(create_app(database_url=url)) as restarted:
        saved=restarted.get(f'/campaigns/{campaign["id"]}').json()['pieces'][0]
        assert saved['state']=='approved'
        assert len(saved['reviews'])==1

@pytest.mark.parametrize('approved',[False,True])
def test_content_invalidates(env,approved):
    client,app,*_=env
    campaign=generate(client).json()
    piece=campaign['pieces'][0]['id']
    client.post(f'/campaigns/{campaign["id"]}/validate')
    if approved:
        assert review(client,piece).status_code==200
    mutate(app,piece,title='Alterado')
    assert review(client,piece).status_code==409
    assert client.get(f'/campaigns/{campaign["id"]}').json()['pieces'][0]['state']=='draft'

def test_rules_invalidates(env):
    client,_,rules,_=env
    campaign=generate(client).json()
    client.post(f'/campaigns/{campaign["id"]}/validate')
    rules['version']='synthetic-2'
    assert review(client,campaign['pieces'][0]['id']).status_code==409

def test_rejection(env):
    client=env[0]
    campaign=generate(client).json()
    piece=campaign['pieces'][0]['id']
    assert review(client,piece,'rejected').json()['state']=='rejected'
    assert review(client,piece).status_code==409
    client.post(f'/campaigns/{campaign["id"]}/validate')
    assert review(client,piece).status_code==200

@pytest.mark.parametrize('changes',[{'channels':['feed','feed']},{'channels':[]},{'channels':['email']},{'objective':' '},{'extra':'x'}])
def test_invalid_request(env,changes):
    result=generate(env[0],**changes)
    assert result.status_code==422
    assert result.json()['error']['code']=='INVALID_REQUEST'

def test_cors_missing_openapi(env):
    client=env[0]
    headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'POST'}
    assert client.options('/campaigns/generate',headers=headers).headers['access-control-allow-origin']==headers['Origin']
    headers['Origin']='https://example.com'
    assert client.options('/campaigns/generate',headers=headers).status_code==400
    assert client.get('/campaigns/missing').status_code==404
    assert client.post('/campaigns/missing/validate').status_code==404
    assert review(client,'missing').status_code==404
    assert 'ErrorResponse' in client.get('/openapi.json').json()['components']['schemas']
    with pytest.raises(ValueError):
        local_origins('*')


def test_catalog_change_invalidates(env,tmp_path):
    import json
    client,app,*_=env
    path=tmp_path/'catalog.json'
    products=[p.model_dump(mode='json') for p in Catalog().all()]
    path.write_text(json.dumps(products),encoding='utf-8')
    app.state.catalog=Catalog(path)
    campaign=generate(client).json()
    client.post(f'/campaigns/{campaign["id"]}/validate')
    products[0]['price']='9.00'
    path.write_text(json.dumps(products),encoding='utf-8')
    assert review(client,campaign['pieces'][0]['id']).status_code==409

def test_bad_generator_channels(env):
    client,app,*_=env
    class BadGenerator:
        def generate(self,briefing,product):
            return []
    app.state.generator=BadGenerator()
    assert generate(client).status_code==502
