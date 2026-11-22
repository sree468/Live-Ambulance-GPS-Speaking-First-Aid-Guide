# 108 PulseAI: Live Ambulance Tracking & Multi-Language Voice First-Aid App

An end-to-end real-time emergency response system modeled after India's 108 ambulance service, designed for accessibility by non-literate or panicked bystanders during road accidents.

## Core Features
- **One-Tap SOS & Live WebSocket GPS Tracking:** Captures exact accident coordinates, dispatches the nearest 108 ambulance, and streams live GPS telemetry with dynamic distance and ETA updates on a Leaflet map.
- **Two-Way Multilingual Voice First-Aid Assistant:** Powered by **Faster-Whisper (STT)**, **FAISS RAG** (Red Cross & WHO protocols), **Gemini 2.5 Flash**, and **Edge-TTS** (`te-IN`, `hi-IN`, `en-IN`) for calm, single-step voice guidance in Telugu, Hindi, and English.
- **Vision AI Injury Triage:** Analyzes uploaded accident photos via **Gemini Vision** using structured Pydantic JSON schemas to alert ER doctors of injury type, severity, and trauma bay prep.
- **ER Doctor Command & Override Dashboard:** Live view of incoming SOS emergencies, wound photos, voice transcripts, and real-time doctor instruction injection into the AI voice dispatcher.
- **Nearby Hospital & Pharmacy Finder:** Uses OpenStreetMap Overpass & Nominatim APIs with Haversine distance sorting and one-tap Google Maps navigation.
