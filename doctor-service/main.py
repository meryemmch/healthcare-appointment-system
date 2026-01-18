from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy import or_, func
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from typing import Optional, List
import requests
import os
from datetime import datetime

# ------------------------------
# FastAPI setup
# ------------------------------
app = FastAPI(title="Doctor Management Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = "frontend"
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(frontend_dir, "index.html"))
else:
    @app.get("/")
    def serve_index():
        return {"service": "doctor", "frontend": False}

# ------------------------------
# Environment variables
# ------------------------------
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")

DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# ------------------------------
# Database model
# ------------------------------
class DoctorDB(Base):
    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, nullable=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    specialization = Column(String, nullable=False)
    license_number = Column(String, unique=True, nullable=False)
    phone = Column(String)
    email = Column(String)
    consultation_fee = Column(Float, default=100.0)
    available_days = Column(String, default="Mon,Tue,Wed,Thu,Fri")
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# ------------------------------
# Pydantic models
# ------------------------------
class Doctor(BaseModel):
    first_name: str
    last_name: str
    specialization: str
    license_number: str
    phone: Optional[str] = None
    email: Optional[str] = None
    consultation_fee: Optional[float] = 100.0
    available_days: Optional[str] = "Mon,Tue,Wed,Thu,Fri"

class DoctorResponse(Doctor):
    id: int
    user_id: Optional[int]

    class Config:
        from_attributes = True

# ------------------------------
# Dependencies
# ------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    try:
        response = requests.get(
            f"{AUTH_SERVICE_URL}/verify",
            headers={"Authorization": authorization}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")
        return response.json()["user"]
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Auth service unavailable")

# ------------------------------
# Routes
# ------------------------------
@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "doctor"}

@app.post("/doctors", response_model=DoctorResponse)
def create_doctor(doctor: Doctor, db: Session = Depends(get_db)):
    """
    Create a doctor profile. Public endpoint: anyone can create a doctor profile.
    This endpoint no longer requires or checks Authorization — profiles are created unconditionally.
    """
    # Prevent duplicate license numbers
    existing = db.query(DoctorDB).filter(DoctorDB.license_number == doctor.license_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="License number already exists")

    new_doctor = DoctorDB(
        user_id=None,
        first_name=doctor.first_name,
        last_name=doctor.last_name,
        specialization=doctor.specialization,
        license_number=doctor.license_number,
        phone=doctor.phone,
        email=doctor.email,
        consultation_fee=doctor.consultation_fee,
        available_days=doctor.available_days
    )
    db.add(new_doctor)
    db.commit()
    db.refresh(new_doctor)
    return new_doctor

@app.get("/doctors", response_model=List[DoctorResponse])
def list_doctors(specialization: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(DoctorDB)
    if specialization:
        # case-insensitive partial match
        query = query.filter(func.lower(DoctorDB.specialization).like(f"%{specialization.lower()}%"))
    return query.all()

@app.get("/doctors/{doctor_id}", response_model=DoctorResponse)
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    doctor = db.query(DoctorDB).filter(DoctorDB.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor

@app.put("/doctors/{doctor_id}", response_model=DoctorResponse)
def update_doctor(doctor_id: int, doctor: Doctor, user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can update doctors")
    
    db_doctor = db.query(DoctorDB).filter(DoctorDB.id == doctor_id).first()
    if not db_doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    for field, value in doctor.dict().items():
        setattr(db_doctor, field, value)
    
    db.commit()
    db.refresh(db_doctor)
    return db_doctor

@app.get("/specializations")
def get_specializations(db: Session = Depends(get_db)):
    results = db.query(DoctorDB.specialization).distinct().all()
    return {"specializations": [r[0] for r in results]}

# ------------------------------
# Run server
# ------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
