from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class EmergencySession(Base):
    __tablename__ = "emergency_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)
    bystander_lat = Column(Float, nullable=False)
    bystander_lon = Column(Float, nullable=False)
    ambulance_lat = Column(Float, nullable=True)
    ambulance_lon = Column(Float, nullable=True)
    status = Column(String, default="DISPATCHED")  # DISPATCHED, EN_ROUTE, ARRIVED
    triage_json = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    chat_history = Column(Text, default="[]")
    doctor_override = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)