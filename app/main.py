import os
import json
import uuid
import shutil
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import AUDIO_OUTPUT_DIR, UPLOAD_DIR, BASE_DIR
from app.database import init_db, SessionLocal, EmergencySession
from app.voice_bot import transcribe_audio, generate_first_aid_reply, synthesize_speech
from app.vision_triage import analyze_injury_image
from app.location_service import find_nearby_medical_facilities

init_db()
app = FastAPI(title="108 Real-Time AI Emergency Response")

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(session_id, []).append(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket):
        if session_id in self.active_connections:
            self.active_connections[session_id].remove(websocket)

    async def broadcast(self, session_id: str, message: dict):
        for connection in self.active_connections.get(session_id, []):
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


class SOSRequest(BaseModel):
    lat: float
    lon: float


class OverrideRequest(BaseModel):
    instruction: str


async def simulate_ambulance_approach(session_id: str):
    """Automatically moves the dispatched ambulance toward the patient spot every 2 seconds."""
    await asyncio.sleep(1.5)  # Give browser WebSocket 1.5s to connect first
    step_size = 0.0008        # Constant ~90m movement per 2 seconds

    while True:
        await asyncio.sleep(2)
        db = SessionLocal()
        emergency = db.query(EmergencySession).filter(EmergencySession.session_id == session_id).first()
        if not emergency or emergency.status == "ARRIVED":
            db.close()
            break

        d_lat = emergency.bystander_lat - emergency.ambulance_lat
        d_lon = emergency.bystander_lon - emergency.ambulance_lon
        dist = (d_lat ** 2 + d_lon ** 2) ** 0.5

        if dist <= step_size:
            emergency.ambulance_lat = emergency.bystander_lat
            emergency.ambulance_lon = emergency.bystander_lon
            emergency.status = "ARRIVED"
            db.commit()
            db.close()
            await manager.broadcast(session_id, {
                "type": "AMBULANCE_GPS",
                "lat": emergency.bystander_lat,
                "lon": emergency.bystander_lon,
                "status": "ARRIVED"
            })
            break

        # Move along unit vector toward patient at steady speed
        new_lat = emergency.ambulance_lat + (d_lat / dist) * step_size
        new_lon = emergency.ambulance_lon + (d_lon / dist) * step_size
        emergency.ambulance_lat = new_lat
        emergency.ambulance_lon = new_lon
        emergency.status = "EN_ROUTE"
        db.commit()
        db.close()

        await manager.broadcast(session_id, {
            "type": "AMBULANCE_GPS",
            "lat": new_lat,
            "lon": new_lon,
            "status": "EN_ROUTE"
        })


@app.get("/")
def serve_bystander():
    return FileResponse(os.path.join(BASE_DIR, "static", "bystander.html"))


@app.get("/driver")
def serve_driver():
    return FileResponse(os.path.join(BASE_DIR, "static", "driver.html"))


@app.get("/doctor")
def serve_doctor():
    return FileResponse(os.path.join(BASE_DIR, "static", "doctor.html"))


@app.post("/api/sos")
async def trigger_sos(payload: SOSRequest):
    db = SessionLocal()
    session_id = f"SOS-{uuid.uuid4().hex[:6].upper()}"
    # Spawn simulated ambulance ~1.5 km away
    amb_lat = payload.lat + 0.010
    amb_lon = payload.lon + 0.010

    emergency = EmergencySession(
        session_id=session_id,
        bystander_lat=payload.lat,
        bystander_lon=payload.lon,
        ambulance_lat=amb_lat,
        ambulance_lon=amb_lon,
    )
    db.add(emergency)
    db.commit()
    db.close()

    facilities = await find_nearby_medical_facilities(payload.lat, payload.lon)
    asyncio.create_task(simulate_ambulance_approach(session_id))

    return {
        "session_id": session_id,
        "bystander": {"lat": payload.lat, "lon": payload.lon},
        "ambulance": {"lat": amb_lat, "lon": amb_lon},
        "facilities": facilities,
    }


@app.get("/api/session/{session_id}")
def get_single_session(session_id: str):
    db = SessionLocal()
    s = db.query(EmergencySession).filter(EmergencySession.session_id == session_id).first()
    db.close()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": s.session_id,
        "status": s.status,
        "bystander": {"lat": s.bystander_lat, "lon": s.bystander_lon},
        "ambulance": {"lat": s.ambulance_lat, "lon": s.ambulance_lon},
    }


@app.get("/api/sessions")
def list_active_sessions():
    db = SessionLocal()
    sessions = db.query(EmergencySession).order_by(EmergencySession.id.desc()).limit(10).all()
    db.close()
    return [
        {
            "session_id": s.session_id,
            "status": s.status,
            "bystander": {"lat": s.bystander_lat, "lon": s.bystander_lon},
            "ambulance": {"lat": s.ambulance_lat, "lon": s.ambulance_lon},
            "triage": json.loads(s.triage_json) if s.triage_json else None,
            "image_url": s.image_url,
            "chat_history": json.loads(s.chat_history),
            "doctor_override": s.doctor_override,
        }
        for s in sessions
    ]


@app.post("/api/voice/{session_id}")
async def process_voice_turn(session_id: str, audio: UploadFile = File(...), lang_hint: str = Form("auto")):
    db = SessionLocal()
    emergency = db.query(EmergencySession).filter(EmergencySession.session_id == session_id).first()
    if not emergency:
        db.close()
        raise HTTPException(status_code=404, detail="SOS Session not found")

    temp_audio_path = os.path.join(AUDIO_OUTPUT_DIR, f"in_{uuid.uuid4().hex}.webm")
    with open(temp_audio_path, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    user_text, detected_lang = transcribe_audio(temp_audio_path)
    if lang_hint in ("te", "hi", "en"):
        detected_lang = lang_hint

    if not user_text:
        user_text = "Help, someone is injured in an accident."

    history = json.loads(emergency.chat_history)
    bot_reply = generate_first_aid_reply(user_text, detected_lang, history, emergency.doctor_override)
    audio_url = await synthesize_speech(bot_reply, detected_lang)

    history.append({"role": "bystander", "content": user_text, "lang": detected_lang})
    history.append({"role": "dispatcher", "content": bot_reply, "lang": detected_lang})
    emergency.chat_history = json.dumps(history)
    db.commit()
    db.close()

    await manager.broadcast(session_id, {"type": "CHAT_UPDATE", "history": history})

    return {
        "user_text": user_text,
        "bot_reply": bot_reply,
        "language": detected_lang,
        "audio_url": audio_url,
    }


@app.post("/api/triage/{session_id}")
async def upload_injury_photo(session_id: str, image: UploadFile = File(...)):
    db = SessionLocal()
    emergency = db.query(EmergencySession).filter(EmergencySession.session_id == session_id).first()
    if not emergency:
        db.close()
        raise HTTPException(status_code=404, detail="SOS Session not found")

    filename = f"injury_{session_id}_{uuid.uuid4().hex[:6]}.jpg"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(image.file, f)

    triage_result = analyze_injury_image(file_path)
    image_url = f"/static/uploads/{filename}"

    emergency.triage_json = json.dumps(triage_result)
    emergency.image_url = image_url
    db.commit()
    db.close()

    await manager.broadcast(session_id, {
        "type": "TRIAGE_UPDATE",
        "triage": triage_result,
        "image_url": image_url
    })

    return {"triage": triage_result, "image_url": image_url}


@app.post("/api/doctor/override/{session_id}")
async def set_doctor_override(session_id: str, payload: OverrideRequest):
    db = SessionLocal()
    emergency = db.query(EmergencySession).filter(EmergencySession.session_id == session_id).first()
    if not emergency:
        db.close()
        raise HTTPException(status_code=404, detail="SOS Session not found")

    emergency.doctor_override = payload.instruction
    db.commit()
    db.close()

    await manager.broadcast(session_id, {
        "type": "DOCTOR_OVERRIDE",
        "instruction": payload.instruction
    })
    return {"status": "Override saved"}


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "AMBULANCE_GPS":
                lat, lon = data["lat"], data["lon"]
                db = SessionLocal()
                emergency = db.query(EmergencySession).filter(EmergencySession.session_id == session_id).first()
                if emergency:
                    emergency.ambulance_lat = lat
                    emergency.ambulance_lon = lon
                    emergency.status = "EN_ROUTE"
                    db.commit()
                db.close()
                await manager.broadcast(session_id, {
                    "type": "AMBULANCE_GPS",
                    "lat": lat,
                    "lon": lon,
                    "status": "EN_ROUTE"
                })
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)