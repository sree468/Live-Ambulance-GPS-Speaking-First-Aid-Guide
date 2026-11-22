import json
from PIL import Image
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from app.config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)


class TriageReport(BaseModel):
    injury_type: str = Field(description="Primary detected injury type, e.g., Deep Laceration, Fracture, Thermal Burn")
    severity: str = Field(description="Must be strictly one of: Low, Medium, Critical")
    visible_symptoms: list[str] = Field(description="List of observable clinical signs from the image")
    recommended_doctor_prep: str = Field(description="Concise trauma/ER preparation brief for the receiving medical team")


def analyze_injury_image(image_path: str) -> dict:
    try:
        img = Image.open(image_path)
        prompt = (
            "You are an emergency trauma triage AI assisting on-duty doctors in India. "
            "Analyze the uploaded accident injury image objectively. Do not fabricate details not visible in the image. "
            "Classify severity strictly as Low, Medium, or Critical, list visible clinical symptoms, "
            "and state the immediate trauma bay preparation required."
        )

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=[img, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=TriageReport,
                temperature=0.1,
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        return {
            "injury_type": "Unable to assess image",
            "severity": "Medium",
            "visible_symptoms": ["Image quality or processing error"],
            "recommended_doctor_prep": f"Manual visual assessment required upon arrival. Error: {str(e)}"
        }