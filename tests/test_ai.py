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
