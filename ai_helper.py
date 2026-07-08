"""
Universal AI helper — replaces Gemini for text and image tasks.
Import this instead of calling Gemini directly.

Usage:
    from ai_helper import call_ai, call_ai_vision

    # Text tasks (Groq free, GPT fallback)
    result = call_ai("Translate this to Russian: Hello world")

    # Image analysis (GPT-4o-mini vision)
    result = call_ai_vision("Describe this image", image_base64)
"""
import os
import json
import requests

GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")


def call_ai(prompt: str, temperature: float = 0.1, max_tokens: int = 4096, system: str = "") -> str:
    """Call AI for text tasks. Chain: Groq (free) → GPT-4o-mini → OpenRouter."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # 1. Groq (free)
    if GROQ_KEY:
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                json={"model": "llama-3.3-70b-versatile", "messages": messages,
                      "temperature": temperature, "max_tokens": min(max_tokens, 8192)},
                timeout=30)
            if r.status_code == 200:
                text = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                if text:
                    return text
        except Exception:
            pass

    # 2. GPT-4o-mini (paid, reliable)
    if OPENAI_KEY:
        try:
            r = requests.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                json={"model": "gpt-4o-mini", "messages": messages,
                      "temperature": temperature, "max_tokens": max_tokens},
                timeout=30)
            if r.status_code == 200:
                text = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                if text:
                    return text
        except Exception:
            pass

    # 3. OpenRouter (free models)
    if OPENROUTER_KEY:
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
                json={"model": "meta-llama/llama-3.3-70b-instruct:free", "messages": messages,
                      "temperature": temperature, "max_tokens": max_tokens},
                timeout=60)
            if r.status_code == 200:
                text = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                if text:
                    return text
        except Exception:
            pass

    return ""


def call_ai_vision(prompt: str, image_base64: str, mime_type: str = "image/jpeg",
                    temperature: float = 0.1, max_tokens: int = 2048) -> str:
    """Call AI for image analysis. Uses GPT-4o-mini vision."""
    if not OPENAI_KEY:
        return ""

    messages = [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}},
    ]}]

    try:
        r = requests.post("https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini", "messages": messages,
                  "temperature": temperature, "max_tokens": max_tokens},
            timeout=30)
        if r.status_code == 200:
            return r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception:
        pass
    return ""
