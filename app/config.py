import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./emergency_108.db")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "first_aid_guidelines.txt")
FAISS_INDEX_PATH = os.path.join(BASE_DIR, "faiss_index")
AUDIO_OUTPUT_DIR = os.path.join(BASE_DIR, "static", "audio")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")

os.makedirs(FAISS_INDEX_PATH, exist_ok=True)
os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)