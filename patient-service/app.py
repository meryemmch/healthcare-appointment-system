from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, Date, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from pydantic import BaseModel
from typing import Optional, List
import requests
import os
from datetime import datetime, date

# ------------------------------
# FastAPI setup
# ------------------------------
app = FastAPI(title="Patient Management Service")

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
        return {"service": "patient", "frontend": False}

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
class PatientDB(Base):
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    address = Column(Text, nullable=True)
    blood_type = Column(String, nullable=True)
    allergies = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# ------------------------------
# Pydantic models
# ------------------------------
class Patient(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    gender: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    blood_type: Optional[str] = None
    allergies: Optional[str] = None

class PatientResponse(Patient):
    id: int
    user_id: int

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
    return {"status": "healthy", "service": "patient"}

@app.post("/patients", response_model=PatientResponse)
def create_patient(patient: Patient, user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    existing = db.query(PatientDB).filter(PatientDB.user_id == user["user_id"]).first()
    if existing:
        raise HTTPException(status_code=400, detail="Patient already exists for this user")
    
    # accept either a date or a string for date_of_birth
    if isinstance(patient.date_of_birth, str):
        dob = datetime.strptime(patient.date_of_birth, "%Y-%m-%d").date()
    else:
        dob = patient.date_of_birth
    new_patient = PatientDB(
        user_id=user["user_id"],
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=dob,
        gender=patient.gender,
        phone=patient.phone,
        address=patient.address,
        blood_type=patient.blood_type,
        allergies=patient.allergies
    )
    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)
    return new_patient

@app.get("/patients/me", response_model=PatientResponse)
def get_my_patient(user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    patient = db.query(PatientDB).filter(PatientDB.user_id == user["user_id"]).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return patient

@app.get("/patients/{patient_id}", response_model=PatientResponse)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(PatientDB).filter(PatientDB.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient

@app.get("/patients", response_model=List[PatientResponse])
def list_patients(user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    if user["role"] not in ["admin", "doctor"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return db.query(PatientDB).all()

@app.put("/patients/{patient_id}", response_model=PatientResponse)
def update_patient(patient_id: int, patient: Patient, user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    db_patient = db.query(PatientDB).filter(PatientDB.id == patient_id).first()
    if not db_patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    if db_patient.user_id != user["user_id"] and user["role"] not in ["admin", "doctor"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    db_patient.first_name = patient.first_name
    db_patient.last_name = patient.last_name
    if isinstance(patient.date_of_birth, str):
        db_patient.date_of_birth = datetime.strptime(patient.date_of_birth, "%Y-%m-%d").date()
    else:
        db_patient.date_of_birth = patient.date_of_birth
    db_patient.gender = patient.gender
    db_patient.phone = patient.phone
    db_patient.address = patient.address
    db_patient.blood_type = patient.blood_type
    db_patient.allergies = patient.allergies
    
    db.commit()
    db.refresh(db_patient)
    return db_patient

"""
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
"""
