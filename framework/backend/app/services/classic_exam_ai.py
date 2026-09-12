"""Constrained explanation planning with bounded retries and explicit fallback.

Only validated identifiers and presentation choices are accepted from the model.
No unverified model prose (or reasoning text) is ever published as railway facts.
"""
from collections import OrderedDict
from concurrent.futures import Future, TimeoutError as FutureTimeout
from copy import deepcopy
import hashlib
import json
import logging
import threading
import time
from typing import Literal
from uuid import uuid4

import httpx
from openai import OpenAI, APIConnectionError, APITimeoutError, APIStatusError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger('uvicorn.error')
MAX_ATTEMPTS = 2
CALL_TIMEOUT = 25.0
TOTAL_BUDGET = 58.0
CACHE_TTL = 120.0
MAX_CACHE = 128
_lock = threading.Lock()
_slots = threading.BoundedSemaphore(3)
_cache = OrderedDict()
_inflight = {}


class PlanItem(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    error_id: str = Field(min_length=1, max_length=120)
    detail: Literal['concise', 'detailed']


class ExplanationPlan(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    version: Literal[1]
    include_route: Literal[True]
    items: list[PlanItem] = Field(min_length=1, max_length=80)


class InvalidOutput(Exception):
    def __init__(self, reason):
        self.reason = reason


def validate_plan(content, cards):
    if not isinstance(content, str) or not content.strip():
        raise InvalidOutput('empty_response')
    if len(content) > 40000:
        raise InvalidOutput('invalid_output')
    try:
        plan = ExplanationPlan.model_validate_json(content)
    except (ValidationError, ValueError):
        raise InvalidOutput('invalid_output') from None
    wanted = {card['id'] for card in cards}
    received = [item.error_id for item in plan.items]
    if len(received) != len(wanted) or set(received) != wanted:
        raise InvalidOutput('invalid_output')
    return plan


def local_plan(cards):
    return ExplanationPlan(version=1, include_route=True, items=[PlanItem(error_id=c['id'], detail='detailed') for c in cards])


MESSAGES = {
    'empty_response': '模型未返回有效解析，已显示依据本题规则整理的解释，可重新尝试AI解析。',
    'truncated': '模型回复未完整生成，已显示规则解析，可重新尝试。',
    'invalid_output': '模型回复未通过本题内容核验，已显示规则解析，可重新尝试。',
    'timeout': '模型响应超时，已显示规则解析；本次判分和答案仍保留。',
    'network': '暂时无法连接模型服务，已显示规则解析，可稍后重试。',
    'rate_limit': '模型服务请求过多，已显示规则解析，请稍后重试。',
    'configuration': '模型服务配置或授权不可用，已显示规则解析，请联系教师检查配置。',
    'provider_error': '模型服务暂时异常，已显示规则解析，可稍后重试。',
    'busy': '当前解析请求较多，已显示规则解析，可稍后重试。',
}


def render(plan, cards, route, source, request_id, reason=None):
    by_id = {card['id']: card for card in cards}
    items = []
    for choice in plan.items:
        card = by_id[choice.error_id]
        items.append({key: card[key] for key in ('id', 'category', 'code', 'error_type', 'title', 'diagnosis', 'correction', 'consequence')}
                     | {'reason': card['reasons'][choice.detail]})
    route_text = route if plan.include_route else ''
    paragraphs = [route_text] if route_text else []
    for index, item in enumerate(items, 1):
        paragraphs.append(f"{index}. {item['title']}\n错在哪里：{item['diagnosis']}\n为什么：{item['reason']}\n如何纠正：{item['correction']}\n不纠正的影响：{item['consequence']}")
    return {'ai_explanation': '\n\n'.join(paragraphs), 'source': source, 'items': items,
            'route_summary': route_text, 'request_id': request_id, 'reason_code': reason,
            'message': MESSAGES.get(reason, '模型已按本次错误组织讲解，专业内容经本题规则核验。'),
            'retryable': source == 'rules_fallback' and reason != 'configuration', 'cached': False}


SYSTEM_PROMPT = '''你是铁路联锁教学讲解编排助手。判断、走行事实、错误列表、纠正措施和解释片段均已由服务器依据本站既有规则与联锁表确定。
你的职责只是在本次错误范围内安排讲解顺序、选择解释的详略。不能新增、删去或改写专业事实，不能重新判分。
区分列车实际走行道岔、防护道岔、带动道岔和题设固定条件。防护或带动道岔不能说成列车实际经过的道岔。
根据错误选择适合学生的顺序：先处理影响走行方向的错误，再处理检查与防护；相关错误可相邻讲解。错误少时选detailed；重复背景可选concise。
只返回json对象，不要输出Markdown、解释正文、思考过程或额外键。
格式示例：{"version":1,"include_route":true,"items":[{"error_id":"switches:missing:9/11","detail":"detailed"}]}
include_route必须为true，先陈述走行事实。items必须逐一包含输入错误的全部error_id，每项恰好一次。detail只能为concise或detailed。只能使用本次输入给出的error_id；示例编号不是答案。'''


def _safe_log(request_id, model, attempt, started, reason, response=None):
    choice = response.choices[0] if response and response.choices else None
    usage = getattr(response, 'usage', None)
    logger.info('classic_exam_ai %s', json.dumps({
        'request_id': request_id, 'model': model[:80], 'attempt': attempt,
        'response_model': getattr(response, 'model', None),
        'elapsed_ms': round((time.monotonic() - started) * 1000), 'outcome': reason,
        'finish_reason': getattr(choice, 'finish_reason', None),
        'prompt_tokens': getattr(usage, 'prompt_tokens', None), 'completion_tokens': getattr(usage, 'completion_tokens', None),
    }, ensure_ascii=True))


def _generate(cards, route, model, base_url, key_loader, request_id):
    fallback = lambda reason: render(local_plan(cards), cards, route, 'rules_fallback', request_id, reason)
    try:
        key = key_loader()
        if not key or key.startswith('sk-xxxx'):
            return fallback('configuration')
    except (OSError, ValueError, RuntimeError):
        return fallback('configuration')
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': json.dumps({
        'route': route,
        'errors': [{'error_id': c['id']} | {k: c[k] for k in ('diagnosis', 'correction', 'reasons', 'consequence')} for c in cards],
    }, ensure_ascii=False)}]
    started = time.monotonic()
    last_reason = 'provider_error'
    # SDK retries are disabled: all retry decisions and their total budget are here.
    with OpenAI(api_key=key, base_url=base_url, max_retries=0,
                timeout=httpx.Timeout(CALL_TIMEOUT, connect=5, write=10, pool=5)) as client:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            remaining = TOTAL_BUDGET - (time.monotonic() - started)
            if remaining <= 1:
                last_reason = 'timeout'
                break
            response = None
            retry = True
            try:
                response = client.chat.completions.create(
                    model=model, messages=messages, stream=False,
                    extra_body={'thinking': {'type': 'disabled'}}, temperature=0,
                    response_format={'type': 'json_object'},
                    max_tokens=min(8192, max(2048, 160 * len(cards))) * attempt,
                    timeout=httpx.Timeout(min(CALL_TIMEOUT, remaining), connect=5, write=10, pool=5),
                )
                if not response.choices:
                    raise InvalidOutput('empty_response')
                choice = response.choices[0]
                if choice.finish_reason == 'length':
                    raise InvalidOutput('truncated')
                if choice.finish_reason != 'stop':
                    raise InvalidOutput('invalid_output')
                plan = validate_plan(choice.message.content, cards)
                _safe_log(request_id, model, attempt, started, 'accepted', response)
                return render(plan, cards, route, 'ai', request_id)
            except InvalidOutput as exc:
                last_reason = exc.reason
                if attempt < MAX_ATTEMPTS:
                    # Do not replay malformed prose or model reasoning into the next prompt.
                    messages = messages[:2] + [{'role': 'user', 'content': '上一轮返回为空、截断或未通过核验。请完整输出规定的json，每个输入id恰好一次，不添加字段或文字。'}]
            except APITimeoutError:
                last_reason = 'timeout'
            except APIConnectionError:
                last_reason = 'network'
            except APIStatusError as exc:
                status = exc.status_code
                last_reason = 'configuration' if status in (400, 401, 402, 403, 404, 422) else 'rate_limit' if status == 429 else 'provider_error'
                retry = status >= 500
            except (ValueError, TypeError, AttributeError):
                last_reason = 'invalid_output'
            _safe_log(request_id, model, attempt, started, last_reason, response)
            if not retry:
                break
    return fallback(last_reason)


def explain(cards, route, model, base_url, key_loader, cache_scope, fingerprint):
    request_id = uuid4().hex[:16]
    if not cards:
        return {'ai_explanation': '本次答案与预设答案一致，没有需要解释的错误。', 'source': 'no_errors',
                'items': [], 'route_summary': '', 'message': '本次答案全部正确。', 'retryable': False,
                'reason_code': None, 'request_id': request_id, 'cached': False}
    try:
        api_key = key_loader()
        if not api_key or api_key.startswith('sk-xxxx'):
            raise ValueError('missing key')
    except (OSError, ValueError, RuntimeError):
        return render(local_plan(cards), cards, route, 'rules_fallback', request_id, 'configuration')
    credential_version = hashlib.sha256(api_key.encode()).hexdigest()
    # No raw credentials, student identity or answers are logged or persisted here.
    cache_key = hashlib.sha256(json.dumps([cache_scope, credential_version, model, base_url, fingerprint, cards, route], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    with _lock:
        for key in list(_cache):
            if time.monotonic() - _cache[key][0] >= CACHE_TTL:
                del _cache[key]
        if cache_key in _cache:
            result = deepcopy(_cache[cache_key][1])
            result['cached'] = True
            _cache.move_to_end(cache_key)
            return result
        future = _inflight.get(cache_key)
        owner = future is None
        if owner:
            future = Future()
            _inflight[cache_key] = future
    if not owner:
        try:
            return deepcopy(future.result(timeout=TOTAL_BUDGET + 5))
        except FutureTimeout:
            return render(local_plan(cards), cards, route, 'rules_fallback', request_id, 'busy')
    acquired = _slots.acquire(blocking=False)
    try:
        if acquired:
            try:
                result = _generate(cards, route, model, base_url, lambda: api_key, request_id)
            except Exception:
                # Keep SDK initialization or unexpected failures from leaking secret-bearing errors.
                logger.warning('classic_exam_ai unexpected_failure request_id=%s', request_id)
                result = render(local_plan(cards), cards, route, 'rules_fallback', request_id, 'provider_error')
        else:
            result = render(local_plan(cards), cards, route, 'rules_fallback', request_id, 'busy')
        with _lock:
            if result['source'] == 'ai':
                _cache[cache_key] = (time.monotonic(), deepcopy(result))
                while len(_cache) > MAX_CACHE:
                    _cache.popitem(last=False)
        future.set_result(result)
        return result
    finally:
        if acquired:
            _slots.release()
        with _lock:
            _inflight.pop(cache_key, None)
