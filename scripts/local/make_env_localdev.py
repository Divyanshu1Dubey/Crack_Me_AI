"""Create backend/.env.localdev from backend/.env.localdev.example.

- Replaces every `__generated__` value with a fresh random secret.
- With --with-ai-keys, copies ONLY the AI provider keys from backend/.env
  (never SMTP, Razorpay, Supabase, Sentry or database credentials).
- Never prints secret values.

Usage:  python scripts/local/make_env_localdev.py [--with-ai-keys] [--force]
"""
from __future__ import annotations

import argparse
import secrets
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / 'backend'
EXAMPLE = BACKEND / '.env.localdev.example'
TARGET = BACKEND / '.env.localdev'
PROD_ENV = BACKEND / '.env'

AI_KEYS = (
    'GEMINI_API_KEY', 'GROQ_API_KEY', 'CEREBRAS_API_KEY', 'COHERE_API_KEY',
    'OPENROUTER_API_KEY', 'OPENROUTER_API_KEY2', 'TOGETHER_API_KEY', 'GITHUB_TOKEN',
    'HUGGINGFACE_API_KEY', 'AIML_API_KEY', 'MISTRAL_API_KEY', 'NVIDIA_MISTRAL_API_KEY',
    'DEEPSEEK_API_KEY', 'OMNIROUTE_API_KEY', 'OMNIROUTE_BASE_URL',
)


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--with-ai-keys', action='store_true')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()

    if TARGET.exists() and not args.force:
        print(f'{TARGET} already exists (use --force to regenerate).')
        return

    lines = []
    for raw in EXAMPLE.read_text(encoding='utf-8').splitlines():
        if '=__generated__' in raw:
            key = raw.split('=', 1)[0]
            raw = f'{key}={secrets.token_urlsafe(48)}'
        lines.append(raw)

    copied = []
    if args.with_ai_keys and PROD_ENV.exists():
        prod = parse_env(PROD_ENV)
        extra = [f'{k}={prod[k]}' for k in AI_KEYS if prod.get(k)]
        copied = [k for k in AI_KEYS if prod.get(k)]
        if extra:
            lines += ['', '# AI provider keys copied from backend/.env'] + extra

    TARGET.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'Wrote {TARGET} (secrets generated; AI keys copied: {len(copied)})')


if __name__ == '__main__':
    main()
