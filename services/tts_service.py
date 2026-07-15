"""Small in-memory adapter for cloud text-to-speech generation."""

from __future__ import annotations

import asyncio

import edge_tts


VOICE_BY_LANGUAGE = {
    "zh-CN": "zh-CN-XiaoxiaoNeural",
    "zh-HK": "zh-HK-HiuMaanNeural",
    "en-US": "en-US-JennyNeural",
}


class UnsupportedTTSLanguage(ValueError):
    """Raised when the API receives a language outside the supported set."""


async def _synthesize(text: str, language: str) -> bytes:
    voice = VOICE_BY_LANGUAGE.get(language)
    if voice is None:
        raise UnsupportedTTSLanguage(language)

    audio_parts: list[bytes] = []
    communicate = edge_tts.Communicate(text, voice, rate="-5%")
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio" and chunk.get("data"):
            audio_parts.append(chunk["data"])

    audio = b"".join(audio_parts)
    if not audio:
        raise RuntimeError("edge-tts returned no audio data")
    return audio


def synthesize_speech(text: str, language: str) -> bytes:
    """Generate MP3 bytes without writing a temporary file."""

    return asyncio.run(_synthesize(text, language))
