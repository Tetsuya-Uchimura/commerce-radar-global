from types import SimpleNamespace
from unittest.mock import MagicMock
from backend.ai import explain, Explanation


def test_structured_ai_cache_and_fallback(db,monkeypatch):
    import backend.ai as ai
    monkeypatch.setenv('OPENAI_API_KEY','unit-test-key')
    monkeypatch.setenv('OPENAI_MODEL','unit-test-model')
    monkeypatch.setattr(ai,'_last_call',0)
    fake=MagicMock()
    fake.responses.parse.return_value=SimpleNamespace(output_parsed=Explanation(
        explanation='A measured 28-day cycle supports replenishment.',limitation='Synthetic data; heuristic score.'))
    monkeypatch.setattr(ai,'OpenAI',lambda **kwargs:fake)
    first=explain(db,'consumer:1','explain',{'interval':28},'Template')
    second=explain(db,'consumer:1','explain',{'interval':28},'Template')
    assert first['source']=='OpenAI-generated explanation'
    assert second['cached'] is True
    assert fake.responses.parse.call_count==1
    assert fake.responses.parse.call_args.kwargs['model']=='unit-test-model'
    assert fake.responses.parse.call_args.kwargs['store'] is False
    scoped=explain(db,'consumer:2','explain',{'interval':28},'Other template')
    assert scoped['source']=='Statistical template · no LLM'


def test_ai_api_failure(db,monkeypatch):
    import backend.ai as ai
    from openai import OpenAIError
    monkeypatch.setenv('OPENAI_API_KEY','unit-test-key')
    monkeypatch.setenv('OPENAI_MODEL','unit-test-model')
    monkeypatch.setattr(ai,'_last_call',0)
    fake=MagicMock()
    fake.responses.parse.side_effect=OpenAIError('Mock failure')
    monkeypatch.setattr(ai,'OpenAI',lambda **kwargs:fake)
    result=explain(db,'consumer:1','explain',{},'Fallback text')
    assert result['explanation']=='Fallback text'
    assert 'unavailable' in result['limitation']


def test_offer_explanation_is_scoped(client):
    answer=client.post('/api/offers/1/explanation',json={})
    assert answer.status_code==200
    assert answer.json()['source']=='Statistical template · no LLM'
    assert client.post('/api/countries/PT/explanation',json={}).status_code==200

def test_concurrent_same_explanation_uses_one_model_call(db,tmp_path,monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import create_engine,select,func
    from sqlalchemy.orm import Session
    from backend.models import Base,AICache
    import backend.ai as ai
    from backend.seed import seed
    engine=create_engine('sqlite:///'+str(tmp_path/'explanations.db'),connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    with Session(engine) as session:seed(session)
    monkeypatch.setenv('OPENAI_API_KEY','unit-test-key')
    monkeypatch.setattr(ai,'_last_call',0)
    entered=threading.Event();second_miss=threading.Event();release=threading.Event()
    fake=MagicMock()
    def parse(**kwargs):
        entered.set();assert release.wait(5)
        return SimpleNamespace(output_parsed=Explanation(explanation='A grounded strategy explanation.',limitation='Unknown costs.'))
    fake.responses.parse.side_effect=parse
    monkeypatch.setattr(ai,'OpenAI',lambda **kwargs:fake)
    def call(second=False):
        with Session(engine) as session:
            get=session.get
            def observed_get(entity,*args,**kwargs):
                value=get(entity,*args,**kwargs)
                if second and entity is AICache and value is None:second_miss.set()
                return value
            session.get=observed_get
            return ai.explain(session,'user:1','strategy',{'same_evidence':True},'Fallback')
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(call);assert entered.wait(5)
        b=pool.submit(call,True);assert second_miss.wait(5);release.set()
        first=a.result();second=b.result()
    assert first['source']=='OpenAI-generated explanation' and second['cached']
    assert fake.responses.parse.call_count==1
    with Session(engine) as session:assert session.scalar(select(func.count()).select_from(AICache))==1
    engine.dispose()
