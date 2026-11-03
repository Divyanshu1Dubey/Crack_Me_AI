"""Model calls that can look at a question's figure (2026-11, docs/audit/MEDICAL_ACCURACY_DESIGN.md).

Every other AI path is text-only. ``call_vision`` sends a prompt plus up to ``MAX_IMAGES`` figures
to a provider that accepts images, in this order: Gemini (``inline_data``), GitHub Models
(gpt-4o-mini, OpenAI-style ``image_url`` data URI), OmniRoute (openai/gpt-4o-mini).

It never guesses about a figure it could not send. Under ``AI_OFFLINE_MODE``, with no vision
provider configured, with no image bytes on this server, or when every provider fails, it returns
an abstention::

    {'abstained': True, 'reason': 'image_context_missing', 'detail': 'offline_mode' |
     'no_vision_provider' | 'no_image_bytes' | 'providers_failed', 'text': '', ...}

Provider error text is logged by status code only and never returned or stored. What a model says
about a figure is a review signal / draft for an admin, never a source of medical facts, a
citation or a caption shown to students.
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Iterable, Optional

from django.conf import settings

from .offline import ai_offline_mode, is_unusable_text

logger = logging.getLogger(__name__)

ABSTAIN_REASON = 'image_context_missing'
DETAIL_OFFLINE = 'offline_mode'
DETAIL_NO_PROVIDER = 'no_vision_provider'
DETAIL_NO_IMAGE = 'no_image_bytes'
DETAIL_FAILED = 'providers_failed'

MAX_IMAGES = 4
MAX_IMAGE_BYTES = 4 * 1024 * 1024
GEMINI_VISION_MODEL = 'gemini-2.0-flash'
GITHUB_MODELS_URL = 'https://models.inference.ai.azure.com/chat/completions'
GITHUB_VISION_MODEL = 'gpt-4o-mini'
OMNIROUTE_VISION_MODEL = 'openai/gpt-4o-mini'
DEFAULT_TIMEOUT = 30.0

_SIGNATURES = (
    (b'\x89PNG\r\n\x1a\n', 'image/png'),
    (b'\xff\xd8\xff', 'image/jpeg'),
    (b'GIF87a', 'image/gif'),
    (b'GIF89a', 'image/gif'),
)


def _key(name: str) -> str:
    return (getattr(settings, name, '') or os.getenv(name, '') or '').strip()


def _omniroute_base() -> str:
    return (getattr(settings, 'OMNIROUTE_BASE_URL', '') or os.getenv('OMNIROUTE_BASE_URL', '') or '').strip().rstrip('/')


def vision_providers() -> list[str]:
    """Configured providers that accept images, in call order ([] under AI_OFFLINE_MODE)."""
    if ai_offline_mode():
        return []
    names = []
    if _key('GEMINI_API_KEY'):
        names.append('gemini')
    if _key('GITHUB_TOKEN'):
        names.append('github_models')
    if (_key('OMNIROUTE_API_KEY') or _key('OMNIROUTEAPI')) and _omniroute_base():
        names.append('omniroute')
    return names


def vision_available() -> bool:
    return bool(vision_providers())


def sniff_mime(data: bytes) -> Optional[str]:
    head = (data or b'')[:16]
    for signature, mime in _SIGNATURES:
        if head.startswith(signature):
            return mime
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'image/webp'
    return None


def _abstain(detail: str, **extra) -> dict:
    result = {'abstained': True, 'reason': ABSTAIN_REASON, 'detail': detail, 'text': '',
              'provider': '', 'model': '', 'images_sent': 0}
    result.update(extra)
    return result


def _prepare_images(images: Iterable) -> list[tuple[str, str]]:
    """[(mime, base64)] for raster bytes or QuestionImage rows (read from local storage only)."""
    prepared = []
    for item in images or ():
        if len(prepared) >= MAX_IMAGES:
            break
        data = item
        if not isinstance(item, (bytes, bytearray)):
            from questions.image_context import figure_bytes
            data = figure_bytes(item)
        if not data or len(data) > MAX_IMAGE_BYTES:
            continue
        mime = sniff_mime(bytes(data))
        if not mime:
            continue
        prepared.append((mime, base64.b64encode(bytes(data)).decode('ascii')))
    return prepared


def _post(url: str, *, headers: dict, payload: dict, timeout: float):
    """One HTTP POST (patched in tests; no other network access in this module)."""
    import requests
    return requests.post(url, headers=headers, json=payload, timeout=timeout)


def _call_gemini(prompt, system, images, temperature, max_tokens, timeout):
    parts = [{'text': f'{system}\n\n{prompt}' if system else prompt}]
    parts += [{'inline_data': {'mime_type': mime, 'data': data}} for mime, data in images]
    response = _post(
        f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_VISION_MODEL}:generateContent',
        headers={'Content-Type': 'application/json', 'x-goog-api-key': _key('GEMINI_API_KEY')},
        payload={'contents': [{'parts': parts}],
                 'generationConfig': {'temperature': temperature, 'maxOutputTokens': max_tokens}},
        timeout=timeout,
    )
    if response.status_code != 200:
        logger.warning('vision: gemini HTTP %s', response.status_code)
        return None, GEMINI_VISION_MODEL
    try:
        return response.json()['candidates'][0]['content']['parts'][0]['text'], GEMINI_VISION_MODEL
    except (KeyError, IndexError, TypeError, ValueError):
        logger.warning('vision: gemini returned an unexpected structure')
        return None, GEMINI_VISION_MODEL


def _openai_messages(prompt, system, images):
    content = [{'type': 'text', 'text': prompt}]
    content += [{'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{data}'}} for mime, data in images]
    messages = [{'role': 'system', 'content': system}] if system else []
    messages.append({'role': 'user', 'content': content})
    return messages


def _call_openai_style(url, key, model, prompt, system, images, temperature, max_tokens, timeout, name):
    response = _post(
        url,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'},
        payload={'model': model, 'messages': _openai_messages(prompt, system, images),
                 'temperature': temperature, 'max_tokens': max_tokens},
        timeout=timeout,
    )
    if response.status_code != 200:
        logger.warning('vision: %s HTTP %s', name, response.status_code)
        return None, model
    try:
        return response.json()['choices'][0]['message']['content'], model
    except (KeyError, IndexError, TypeError, ValueError):
        logger.warning('vision: %s returned an unexpected structure', name)
        return None, model


def _call_provider(name, prompt, system, images, temperature, max_tokens, timeout):
    if name == 'gemini':
        return _call_gemini(prompt, system, images, temperature, max_tokens, timeout)
    if name == 'github_models':
        return _call_openai_style(GITHUB_MODELS_URL, _key('GITHUB_TOKEN'), GITHUB_VISION_MODEL, prompt, system,
                                  images, temperature, max_tokens, timeout, name)
    if name == 'omniroute':
        key = _key('OMNIROUTE_API_KEY') or _key('OMNIROUTEAPI')
        return _call_openai_style(f'{_omniroute_base()}/chat/completions', key, OMNIROUTE_VISION_MODEL, prompt,
                                  system, images, temperature, max_tokens, timeout, name)
    return None, ''


def call_vision(prompt: str, images: Iterable, *, system: str = '', temperature: float = 0.2,
                max_tokens: int = 800, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Ask a vision-capable provider about ``images`` (raster bytes or QuestionImage rows).

    Returns ``{'abstained': False, 'text', 'provider', 'model', 'images_sent'}`` or an abstention
    (see the module docstring). Never raises for unavailability.
    """
    if ai_offline_mode():
        return _abstain(DETAIL_OFFLINE)
    providers = vision_providers()
    if not providers:
        return _abstain(DETAIL_NO_PROVIDER)
    prepared = _prepare_images(images)
    if not prepared:
        return _abstain(DETAIL_NO_IMAGE)
    for name in providers:
        try:
            text, model = _call_provider(name, prompt, system, prepared, temperature, max_tokens, timeout)
        except Exception as exc:  # noqa: BLE001 - try the next provider
            logger.warning('vision: %s failed (%s)', name, type(exc).__name__)
            continue
        if text and not is_unusable_text(text):
            return {'abstained': False, 'reason': '', 'detail': '', 'text': text.strip(), 'provider': name,
                    'model': model, 'images_sent': len(prepared)}
    return _abstain(DETAIL_FAILED, images_sent=len(prepared))


def call_vision_for_question(question, prompt: str, *, system: str = '', include_explanation_figures: bool = False,
                             **kwargs) -> dict:
    """``call_vision`` with the question's own figures: stem / option figures only, unless an
    admin path asks for explanation figures too (never when checking a key)."""
    from questions.image_context import active_images, stem_figures

    figures = active_images(question) if include_explanation_figures else stem_figures(question)
    if not figures:
        return _abstain(DETAIL_NO_IMAGE)
    return call_vision(prompt, figures, system=system, **kwargs)
