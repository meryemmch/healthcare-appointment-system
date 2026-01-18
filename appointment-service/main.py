from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Text, Date, Time, TIMESTAMP, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import requests
import os
from datetime import datetime, date, time

# ------------------------------
# FastAPI setup
# ------------------------------
app = FastAPI(title="Appointment Scheduling Service")

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
        return {"service": "appointment", "frontend": False}

# ------------------------------
# Environment / DB setup
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
# Database models
# ------------------------------
class AppointmentModel(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, nullable=False)
    doctor_id = Column(Integer, nullable=False)
    appointment_date = Column(Date, nullable=False)
    appointment_time = Column(Time, nullable=False)
    status = Column(String, default="scheduled")
    reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

Base.metadata.create_all(bind=engine)

# ------------------------------
# Pydantic models
# ------------------------------
class Appointment(BaseModel):
    doctor_id: int
    appointment_date: date  # format: YYYY-MM-DD
    appointment_time: time  # format: HH:MM
    reason: Optional[str] = None

class AppointmentResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    appointment_date: date
    appointment_time: time
    status: str
    reason: Optional[str]
    notes: Optional[str]

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
    return {"status": "healthy", "service": "appointment"}

@app.post("/appointments", response_model=AppointmentResponse)
def create_appointment(appointment: Appointment, user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    # Parse date and time
    try:
        if isinstance(appointment.appointment_date, str):
            appointment_date = datetime.strptime(appointment.appointment_date, "%Y-%m-%d").date()
        else:
            appointment_date = appointment.appointment_date
        if isinstance(appointment.appointment_time, str):
            appointment_time = datetime.strptime(appointment.appointment_time, "%H:%M").time()
        else:
            appointment_time = appointment.appointment_time
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date/time format")

    # Check if time slot is available
    existing = db.query(AppointmentModel).filter(
        AppointmentModel.doctor_id == appointment.doctor_id,
        AppointmentModel.appointment_date == appointment_date,
        AppointmentModel.appointment_time == appointment_time,
        AppointmentModel.status != "cancelled"
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Time slot not available")

    # Create appointment
    new_appointment = AppointmentModel(
        patient_id=user["user_id"],
        doctor_id=appointment.doctor_id,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        reason=appointment.reason
    )
    db.add(new_appointment)
    db.commit()
    db.refresh(new_appointment)

    return new_appointment

@app.get("/appointments/my", response_model=List[AppointmentResponse])
def get_my_appointments(user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    query = db.query(AppointmentModel)
    if user["role"] == "doctor":
        query = query.filter(AppointmentModel.doctor_id == user["user_id"])
    else:
        query = query.filter(AppointmentModel.patient_id == user["user_id"])
    appointments = query.order_by(AppointmentModel.appointment_date.desc(), AppointmentModel.appointment_time.desc()).all()
    return appointments


@app.get("/appointments/user/{username}", response_model=List[AppointmentResponse])
def get_appointments_for_username(username: str, db: Session = Depends(get_db)):
    """Fetch appointments for a given username by resolving user_id via auth service."""
    # resolve username -> user_id via auth service
    try:
        r = requests.get(f"http://localhost:8000/users/by-username/{username}")
        if r.status_code != 200:
            raise HTTPException(status_code=404, detail="User not found")
        user_info = r.json()
        target_id = user_info.get('user_id')
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Auth service unavailable")

    query = db.query(AppointmentModel).filter(AppointmentModel.patient_id == int(target_id))
    appointments = query.order_by(AppointmentModel.appointment_date.desc(), AppointmentModel.appointment_time.desc()).all()
    return appointments

@app.get("/appointments/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(appointment_id: int, user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    appointment = db.query(AppointmentModel).filter(AppointmentModel.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.patient_id != user["user_id"] and user["role"] not in ["admin", "doctor"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return appointment

@app.put("/appointments/{appointment_id}/cancel")
def cancel_appointment(appointment_id: int, user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    appointment = db.query(AppointmentModel).filter(AppointmentModel.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.patient_id != user["user_id"] and user["role"] not in ["admin", "doctor"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    appointment.status = "cancelled"
    db.commit()
    return {"message": "Appointment cancelled successfully"}

@app.put("/appointments/{appointment_id}/complete")
def complete_appointment(appointment_id: int, notes: str = "", user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    if user["role"] not in ["doctor", "admin"]:
        raise HTTPException(status_code=403, detail="Only doctors can complete appointments")
    appointment = db.query(AppointmentModel).filter(AppointmentModel.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    appointment.status = "completed"
    appointment.notes = notes
    db.commit()
    return {"message": "Appointment marked as completed"}

@app.get("/appointments/doctor/{doctor_id}/available-slots")
def get_available_slots(doctor_id: int, date: str, db: Session = Depends(get_db)):
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    booked_slots = db.query(AppointmentModel.appointment_time).filter(
        AppointmentModel.doctor_id == doctor_id,
        AppointmentModel.appointment_date == target_date,
        AppointmentModel.status != "cancelled"
    ).all()
    booked_slots = [slot[0].strftime("%H:%M") for slot in booked_slots]

    all_slots = [f"{h:02d}:00" for h in range(9, 17)]
    available = [slot for slot in all_slots if slot not in booked_slots]
    return {"available_slots": available}

# ------------------------------
# Run server
# ------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
