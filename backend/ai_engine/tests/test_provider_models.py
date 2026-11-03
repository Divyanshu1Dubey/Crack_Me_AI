"""Provider model lists: env overrides and fallback across retired / busy models (no network)."""
import os
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from ai_engine import services
from ai_engine.services import (
    CEREBRAS_DEFAULT_MODELS,
    GROQ_DEFAULT_MODELS,
    OPENROUTER_DEFAULT_FREE_MODELS,
    AIService,
    _models_from_env,
)


def _reply(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class ModelsFromEnvTests(SimpleTestCase):
    def test_default_when_unset(self):
        with mock.patch.dict(os.environ, {'GROQ_MODELS': ''}):
            self.assertEqual(_models_from_env('GROQ_MODELS', GROQ_DEFAULT_MODELS), list(GROQ_DEFAULT_MODELS))

    def test_comma_separated_override(self):
        with mock.patch.dict(os.environ, {'GROQ_MODELS': ' a/b , c ,, '}):
            self.assertEqual(_models_from_env('GROQ_MODELS', GROQ_DEFAULT_MODELS), ['a/b', 'c'])

    def test_retired_ids_are_gone_from_defaults(self):
        retired = {'llama-3.3-70b-versatile', 'llama-3.1-8b', 'llama3.1-8b',
                   'meta-llama/llama-3.3-70b-instruct:free', 'google/gemma-2-9b-it:free'}
        defaults = set(GROQ_DEFAULT_MODELS) | set(CEREBRAS_DEFAULT_MODELS) | set(OPENROUTER_DEFAULT_FREE_MODELS)
        self.assertFalse(retired & defaults)


class ProviderFallbackTests(SimpleTestCase):
    def _service(self):
        service = AIService.__new__(AIService)  # skip client initialisation
        service._attempt_timeout = lambda cap: cap
        return service

    def test_groq_falls_back_to_next_model_and_uses_low_reasoning(self):
        service = self._service()
        create = mock.Mock(side_effect=[Exception('Error code: 503 - over capacity'), _reply('NAC')])
        service.groq = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with mock.patch.dict(os.environ, {'GROQ_MODELS': 'openai/gpt-oss-120b,qwen/qwen3.8-27b'}):
            self.assertEqual(service._call_groq('q', 'sys', 0.2, 50), 'NAC')
        first, second = create.call_args_list
        self.assertEqual(first.kwargs['model'], 'openai/gpt-oss-120b')
        self.assertEqual(first.kwargs['extra_body'], {'reasoning_effort': 'low'})
        self.assertEqual(second.kwargs['model'], 'qwen/qwen3.8-27b')
        self.assertNotIn('extra_body', second.kwargs)

    def test_groq_invalid_key_disables_provider(self):
        service = self._service()
        create = mock.Mock(side_effect=Exception('Error code: 401 - invalid_api_key'))
        service.groq = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        self.assertIsNone(service._call_groq('q', '', 0.2, 50))
        self.assertIsNone(service.groq)
        self.assertEqual(create.call_count, 1)

    def test_cerebras_payment_required_skips_quickly(self):
        service = self._service()
        create = mock.Mock(side_effect=Exception("Error code: 402 - {'code': 'payment_required'}"))
        service.cerebras = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        self.assertIsNone(service._call_cerebras('q', '', 0.2, 50))
        self.assertIsNone(service.cerebras)
        self.assertEqual(create.call_count, 1)

    def test_openrouter_skips_rate_limited_free_model(self):
        service = self._service()
        create = mock.Mock(side_effect=[Exception('Error code: 429 - rate-limited upstream'), _reply('answer')])
        service.openrouter = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with mock.patch.dict(os.environ, {'OPENROUTER_FREE_MODELS': ''}):
            self.assertEqual(service._call_openrouter('q', '', 0.2, 50), 'answer')
        self.assertEqual(create.call_args_list[0].kwargs['model'], OPENROUTER_DEFAULT_FREE_MODELS[0])
        self.assertEqual(create.call_args_list[1].kwargs['model'], OPENROUTER_DEFAULT_FREE_MODELS[1])

    def test_module_exports(self):
        self.assertTrue(callable(services._models_from_env))
