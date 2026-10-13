"""Optional Claude API helpers (needs your own Anthropic API key, billed per use):
  - write_script: write a full Money Studio script (English narration + Vietnamese "vi" for every line)
  - translate_vi: fill in missing Vietnamese subtitle lines of an existing script

Uses the official `anthropic` Python SDK with streaming. Refusal fallback ("fallbacks": "default") is on,
so if the main model declines a request the API retries it on a fallback model automatically.
The free path needs no key: tab 2 > "Copy prompt", paste into Claude chat, paste the JSON back.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL = 'claude-opus-5-5'
FALLBACK_BETA = 'server-side-fallback-2026-07-01'


def prompt_doc():
    with open(os.path.join(ROOT, 'docs', 'PROMPT_FOR_CLAUDE.md'), 'r', encoding='utf-8') as f:
        return f.read()


def user_prompt(topic, pillar, minutes, mascot, extra=''):
    return (f'Write one complete Broke Ben episode as a single JSON object in the Money Studio format.\n'
            f'- Topic: {topic or "(you choose a strong topic for this pillar)"}\n'
            f'- Pillar: {pillar}\n- Target length: about {minutes} minutes of narration\n'
            f'- Mascot: {mascot}\n{extra}\n'
            'Every line needs both "text" (English narration) and "vi" (natural Vietnamese subtitle).\n'
            'Output ONLY the JSON object, no explanation, no markdown fence.')


def extract_json(text):
    t = text.strip()
    m = re.search(r'```(?:json)?\s*([\[{].*[\]}])\s*```', t, re.S)
    if m:
        t = m.group(1)
    starts = [i for i in (t.find('{'), t.find('[')) if i >= 0]
    if not starts:
        raise ValueError('Không thấy JSON trong câu trả lời')
    a = min(starts)
    b = max(t.rfind('}'), t.rfind(']'))
    return json.loads(t[a:b + 1])


def _stream(api_key, model, system, user, effort, on_text=None, cancelled=lambda: False, max_tokens=64000):
    try:
        import anthropic
    except ImportError:
        raise RuntimeError('Chưa cài thư viện anthropic. Chạy lại setup.bat.')
    client = anthropic.Anthropic(api_key=api_key.strip()) if api_key and api_key.strip() else anthropic.Anthropic()
    out = []
    try:
        with client.beta.messages.stream(
                model=model or DEFAULT_MODEL,
                max_tokens=max_tokens,
                betas=[FALLBACK_BETA],
                fallbacks='default',
                output_config={'effort': effort},
                system=system,
                messages=[{'role': 'user', 'content': user}]) as stream:
            for piece in stream.text_stream:
                if cancelled():
                    raise RuntimeError('Đã hủy')
                out.append(piece)
                if on_text:
                    on_text(piece)
            final = stream.get_final_message()
    except anthropic.AuthenticationError:
        raise RuntimeError('API key không đúng hoặc đã bị thu hồi.')
    except anthropic.PermissionDeniedError as e:
        raise RuntimeError(f'API key không có quyền dùng model này: {e.message}')
    except anthropic.NotFoundError:
        raise RuntimeError(f'Không tìm thấy model "{model}". Sửa "claude_model" trong config.json.')
    except anthropic.RateLimitError:
        raise RuntimeError('Claude API đang giới hạn tốc độ. Đợi một lúc rồi thử lại.')
    except anthropic.APIStatusError as e:
        raise RuntimeError(f'Claude API lỗi {e.status_code}: {e.message}')
    except anthropic.APIConnectionError:
        raise RuntimeError('Không kết nối được Claude API. Kiểm tra mạng.')
    if final.stop_reason == 'refusal':
        raise RuntimeError('Claude từ chối yêu cầu này. Thử đổi chủ đề hoặc cách diễn đạt.')
    if final.stop_reason == 'max_tokens':
        raise RuntimeError('Câu trả lời bị cắt vì quá dài. Giảm số phút rồi thử lại.')
    return ''.join(out)


def write_script(api_key, topic, pillar='Why You\'re Broke', minutes=10, mascot='ben', model=None, extra='',
                 on_text=None, cancelled=lambda: False):
    return _stream(api_key, model, prompt_doc(), user_prompt(topic, pillar, minutes, mascot, extra), 'high',
                   on_text, cancelled)


def translate_vi(api_key, script, model=None, on_text=None, cancelled=lambda: False):
    """Fills every empty "vi" field in place. Returns how many lines were translated."""
    todo = []
    for si, sc in enumerate(script.get('scenes', [])):
        for li, ln in enumerate(sc.get('lines', [])):
            if isinstance(ln, dict) and ln.get('text') and not ln.get('vi'):
                todo.append({'id': f'{si}.{li}', 'en': ln['text']})
    if not todo:
        return 0
    system = ('You translate English narration of an animated personal-finance YouTube video into natural, '
              'easy-to-read Vietnamese subtitles. Keep numbers and money amounts exact (write "$3,000" as '
              '"3.000 đô"). Keep each subtitle about as short as the English. Return only a JSON array of '
              '{"id": ..., "vi": ...} objects in the same order.')
    text = _stream(api_key, model, system, json.dumps(todo, ensure_ascii=False), 'low', on_text, cancelled,
                   max_tokens=32000)
    got = {str(x['id']): x['vi'] for x in extract_json(text) if isinstance(x, dict) and x.get('vi')}
    n = 0
    for si, sc in enumerate(script.get('scenes', [])):
        for li, ln in enumerate(sc.get('lines', [])):
            v = got.get(f'{si}.{li}')
            if v and isinstance(ln, dict) and not ln.get('vi'):
                ln['vi'] = v
                n += 1
    return n
