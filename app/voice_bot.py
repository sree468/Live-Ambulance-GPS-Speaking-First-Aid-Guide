import os
import uuid
from faster_whisper import WhisperModel
import edge_tts
from google import genai
from google.genai import types
from app.config import GEMINI_API_KEY, AUDIO_OUTPUT_DIR
from app.rag_setup import retrieve_first_aid_context

stt_model = WhisperModel("base", device="cpu", compute_type="int8")
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

VOICE_MAP = {
    "te": "te-IN-ShrutiNeural",
    "hi": "hi-IN-SwaraNeural",
    "en": "en-IN-NeerjaNeural",
}


def transcribe_audio(audio_file_path: str) -> tuple[str, str]:
    try:
        segments, info = stt_model.transcribe(audio_file_path)
        text = " ".join([seg.text.strip() for seg in segments]).strip()
        lang = info.language if info.language in VOICE_MAP else "en"
        return text, lang
    except Exception as e:
        print(f"[STT Error] {e}")
        return "", "en"


def generate_first_aid_reply(user_text: str, lang_code: str, history: list[dict], doctor_override: str | None = None) -> str:
    try:
        rag_context = retrieve_first_aid_context(user_text, k=2)
    except Exception:
        rag_context = "Apply firm direct pressure to bleeding wounds with a clean cloth. Keep the person still."

    system_instruction = f"""
You are a calm, empathetic 108 emergency medical dispatcher in India speaking with a non-literate bystander.
STRICT RULES:
1. Reply ONLY in the exact language requested (Language code: {lang_code} — 'te' for Telugu, 'hi' for Hindi, 'en' for English).
2. Maximum 20 to 25 words total.
3. Give ONLY ONE physical first-aid action per turn based on the Verified Protocol below.
4. Never diagnose or prescribe medicines.
5. End EVERY response with a simple yes/no or short-answer question.
6. Remind the user that the ambulance is on the way.
{f"7. URGENT DOCTOR OVERRIDE: {doctor_override}" if doctor_override else ""}

VERIFIED PROTOCOL:
{rag_context}
"""

    formatted_history = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history[-6:]])
    prompt = f"History:\n{formatted_history}\n\nBystander: {user_text}\nDispatcher:"

    try:
        response = gemini_client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2,
            ),
        )
        return response.text.strip()
    except Exception as e:
        print(f"[Gemini Error] {e}")
        return "Keep the injured person still and press a clean cloth on any bleeding. Ambulance is on the way. Are they conscious?"


async def synthesize_speech(text: str, lang_code: str) -> str:
    voice = VOICE_MAP.get(lang_code, "en-IN-NeerjaNeural")
    filename = f"reply_{uuid.uuid4().hex}.mp3"
    output_path = os.path.join(AUDIO_OUTPUT_DIR, filename)
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        return f"/static/audio/{filename}"
    except Exception as e:
        print(f"[TTS Error] {e}")
        return ""