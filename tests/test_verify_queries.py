import requests
import json
import pytest

API_URL = 'http://127.0.0.1:8000'

def _send_chat_query(msg, client_id='test', pending=None):
    headers = {'Content-Type': 'application/json', 'X-Client-Id': client_id}
    payload = {'message': msg}
    if pending:
        payload['pending_state'] = pending
    try:
        r = requests.post(f'{API_URL}/api/chat/stream', json=payload, headers=headers, timeout=2)
        assert r.status_code == 200, f'Status {r.status_code}'
        lines = r.iter_lines(decode_unicode=True)
    except Exception:
        from fastapi.testclient import TestClient
        from backend.main import app
        c = TestClient(app)
        r = c.post('/api/chat/stream', json=payload, headers=headers)
        assert r.status_code == 200, f'Status {r.status_code}'
        lines = r.text.splitlines()

    events = []
    current_ev = None
    for line in lines:
        if not line:
            continue
        if line.startswith('event:'):
            current_ev = line[6:].strip()
        elif line.startswith('data:'):
            d = json.loads(line[5:].strip())
            events.append((current_ev, d))
    return events


def test_five_queries_return_distinct_answers():
    questions = [
        'Which circuit hosts the Belgian GP?',
        'Who won Monza 2023?',
        'standings 2026 drivers',
        'alonso race strategy',
        'hello'
    ]
    responses = {}
    for idx, q in enumerate(questions):
        evs = _send_chat_query(q, client_id=f'client-{idx}')
        ans_ev = next((d for ev, d in evs if ev in ('answer', 'clarify')), {})
        text = ans_ev.get('markdown') or ans_ev.get('question')
        responses[q] = text

    unique_answers = set(responses.values())
    assert len(unique_answers) == len(questions), f'Expected 5 distinct answers, got {len(unique_answers)}'


def test_repeat_query_returns_cache_hit():
    q = 'Who won Monza 2023?'
    _send_chat_query(q, client_id='client-c1')
    evs2 = _send_chat_query(q, client_id='client-c2')
    done_ev = next((d for ev, d in evs2 if ev == 'done'), {})
    debug = done_ev.get('debug', {})
    assert debug.get('cache') == 'hit', f'Expected cache hit on repeat query, got {debug.get("cache")}'


def test_pending_clarification_dropped_on_new_question():
    evs1 = _send_chat_query('alonso race strategy', client_id='conv-pending-test')
    clarify_ev = next((d for ev, d in evs1 if ev == 'clarify'), {})
    pending = clarify_ev.get('pending_state')
    assert pending is not None, 'Expected pending state from alonso strategy'

    # Send completely new question with pending state
    evs2 = _send_chat_query('Who won Monza 2023?', client_id='conv-pending-test', pending=pending)
    ans_ev = next((d for ev, d in evs2 if ev == 'answer'), {})
    markdown = ans_ev.get('markdown', '')
    assert 'Verstappen' in markdown or 'Italian Grand Prix' in markdown
