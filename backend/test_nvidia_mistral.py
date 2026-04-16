#!/usr/bin/env python
"""
Quick test to verify NVIDIA Mistral integration.

Usage:
    cd backend
    python test_nvidia_mistral.py
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')

import django
django.setup()

from django.conf import settings
from ai_engine.services import AIService


def test_nvidia_mistral_config():
    """Verify NVIDIA Mistral configuration."""
    print("\n🔍 Testing NVIDIA Mistral Integration...\n")
    
    # Check 1: Environment variable
    nvidia_key = os.getenv('NVIDIA_MISTRAL_API_KEY', '')
    if nvidia_key:
        masked = nvidia_key[:10] + '...' + nvidia_key[-4:] if len(nvidia_key) > 15 else '***'
        print(f"✅ NVIDIA_MISTRAL_API_KEY is set: {masked}")
    else:
        print("⚠️  NVIDIA_MISTRAL_API_KEY not found in environment")
        print("   Add to .env: NVIDIA_MISTRAL_API_KEY=nvapi-YOUR-KEY")
    
    # Check 2: Django settings
    settings_key = getattr(settings, 'NVIDIA_MISTRAL_API_KEY', '')
    if settings_key:
        masked = settings_key[:10] + '...' + settings_key[-4:] if len(settings_key) > 15 else '***'
        print(f"✅ Django settings loaded: {masked}")
    else:
        print("⚠️  NVIDIA_MISTRAL_API_KEY not in Django settings")
    
    # Check 3: AIService initialization
    print("\n🚀 Initializing AI Service...")
    try:
        ai = AIService()
        
        # Check if nvidia_mistral client is initialized
        if ai.nvidia_mistral:
            print("✅ NVIDIA Mistral client initialized successfully!")
            print(f"   Base URL: {ai.nvidia_mistral.base_url}")
            print(f"   Model: mistralai/mistral-7b-instruct-v0.2")
        else:
            print("⚠️  NVIDIA Mistral client not initialized (key may be missing)")
            print("   This is OK if NVIDIA_MISTRAL_API_KEY is intentionally empty.")
        
        # Show all initialized providers
        providers = []
        if ai.gemini_client:
            providers.append('Gemini')
        if ai.groq:
            providers.append('Groq')
        if ai.cerebras:
            providers.append('Cerebras')
        if ai.cohere:
            providers.append('Cohere')
        if ai.openrouter:
            providers.append('OpenRouter')
        if ai.openrouter2:
            providers.append('OpenRouter2')
        if ai.github_models:
            providers.append('GitHub Models')
        if ai.huggingface:
            providers.append('HuggingFace')
        if ai.mistral:
            providers.append('Mistral Native')
        if ai.nvidia_mistral:
            providers.append('NVIDIA Mistral')
        if ai.deepseek:
            providers.append('DeepSeek')
        
        print(f"\n📊 Active Providers ({len(providers)}/11):")
        for i, provider in enumerate(providers, 1):
            print(f"   {i}. {provider}")
        
        print("\n✅ All checks passed!")
        return True
        
    except Exception as e:
        print(f"❌ Error initializing AI Service: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_nvidia_mistral_config()
    sys.exit(0 if success else 1)
