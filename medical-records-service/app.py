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
app = FastAPI(title="Medical Records Service")

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
        return {"service": "medical-records", "frontend": False}

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
class MedicalRecordDB(Base):
    __tablename__ = "medical_records"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, nullable=False)
    doctor_id = Column(Integer, nullable=False)
    appointment_id = Column(Integer, nullable=True)
    diagnosis = Column(Text, nullable=False)
    prescription = Column(Text, nullable=True)
    lab_results = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    record_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# ------------------------------
# Pydantic models
# ------------------------------
class MedicalRecord(BaseModel):
    patient_id: int
    appointment_id: Optional[int] = None
    diagnosis: str
    prescription: Optional[str] = None
    lab_results: Optional[str] = None
    notes: Optional[str] = None
    record_date: date  # can be parsed into date

class MedicalRecordResponse(MedicalRecord):
    id: int
    doctor_id: int

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
    return {"status": "healthy", "service": "medical-records"}

@app.post("/records", response_model=MedicalRecordResponse)
def create_record(record: MedicalRecord, user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    if user["role"] not in ["doctor", "admin"]:
        raise HTTPException(status_code=403, detail="Only doctors or admins can create medical records")
    
    if isinstance(record.record_date, str):
        record_date = datetime.strptime(record.record_date, "%Y-%m-%d").date()
    else:
        record_date = record.record_date
    
    new_record = MedicalRecordDB(
        patient_id=record.patient_id,
        doctor_id=user["user_id"],
        appointment_id=record.appointment_id,
        diagnosis=record.diagnosis,
        prescription=record.prescription,
        lab_results=record.lab_results,
        notes=record.notes,
        record_date=record_date
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    return new_record

@app.get("/records/patient/{patient_id}", response_model=List[MedicalRecordResponse])
def get_patient_records(patient_id: int, user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    if user["user_id"] != patient_id and user["role"] not in ["doctor", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized to view these records")
    
    records = db.query(MedicalRecordDB).filter(MedicalRecordDB.patient_id == patient_id).order_by(MedicalRecordDB.record_date.desc()).all()
    return records

@app.get("/records/my", response_model=List[MedicalRecordResponse])
def get_my_records(user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    records = db.query(MedicalRecordDB).filter(MedicalRecordDB.patient_id == user["user_id"]).order_by(MedicalRecordDB.record_date.desc()).all()
    return records

@app.get("/records/{record_id}", response_model=MedicalRecordResponse)
def get_record(record_id: int, user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    record = db.query(MedicalRecordDB).filter(MedicalRecordDB.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    if record.patient_id != user["user_id"] and user["role"] not in ["doctor", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return record


@app.get("/records/doctor/my", response_model=List[MedicalRecordResponse])
def get_records_for_doctor(user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    # only doctors or admins can call this endpoint
    if user["role"] not in ["doctor", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    records = db.query(MedicalRecordDB).filter(MedicalRecordDB.doctor_id == user["user_id"]).order_by(MedicalRecordDB.record_date.desc()).all()
    return records

@app.put("/records/{record_id}", response_model=MedicalRecordResponse)
def update_record(record_id: int, record: MedicalRecord, user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    if user["role"] not in ["doctor", "admin"]:
        raise HTTPException(status_code=403, detail="Only doctors or admins can update records")
    
    db_record = db.query(MedicalRecordDB).filter(MedicalRecordDB.id == record_id).first()
    if not db_record:
        raise HTTPException(status_code=404, detail="Record not found")
    if db_record.doctor_id != user["user_id"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Can only update your own records")
    
    db_record.diagnosis = record.diagnosis
    db_record.prescription = record.prescription
    db_record.lab_results = record.lab_results
    db_record.notes = record.notes
    if isinstance(record.record_date, str):
        db_record.record_date = datetime.strptime(record.record_date, "%Y-%m-%d").date()
    else:
        db_record.record_date = record.record_date
    
    db.commit()
    db.refresh(db_record)
    return db_record

"""
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
"""
