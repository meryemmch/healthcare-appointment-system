from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, Date, DateTime, func
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from typing import Optional, List
from datetime import datetime, date
import requests
import os

# ------------------------------
# FastAPI setup
# ------------------------------
app = FastAPI(title="Billing Service")

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
        return {"service": "billing", "frontend": False}

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
# Database models
# ------------------------------
class InvoiceDB(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, nullable=False)
    appointment_id = Column(Integer, nullable=True)
    amount = Column(Float, nullable=False)
    description = Column(Text)
    status = Column(String, default="pending")
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    paid_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=func.now())

Base.metadata.create_all(bind=engine)

# ------------------------------
# Pydantic models
# ------------------------------
class Invoice(BaseModel):
    patient_id: int
    appointment_id: Optional[int] = None
    amount: float
    description: Optional[str] = None
    invoice_date: date
    due_date: date

class InvoiceResponse(Invoice):
    id: int
    status: str
    paid_date: Optional[date]

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
    return {"status": "healthy", "service": "billing"}

@app.post("/invoices", response_model=InvoiceResponse)
def create_invoice(invoice: Invoice, user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    if user["role"] not in ["admin", "doctor"]:
        raise HTTPException(status_code=403, detail="Not authorized to create invoices")
    
    try:
        if isinstance(invoice.invoice_date, str):
            invoice_date = datetime.strptime(invoice.invoice_date, "%Y-%m-%d").date()
        else:
            invoice_date = invoice.invoice_date
        if isinstance(invoice.due_date, str):
            due_date = datetime.strptime(invoice.due_date, "%Y-%m-%d").date()
        else:
            due_date = invoice.due_date
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    new_invoice = InvoiceDB(
        patient_id=invoice.patient_id,
        appointment_id=invoice.appointment_id,
        amount=invoice.amount,
        description=invoice.description,
        invoice_date=invoice_date,
        due_date=due_date,
        status="pending"
    )
    db.add(new_invoice)
    db.commit()
    db.refresh(new_invoice)
    return new_invoice

@app.get("/invoices/my", response_model=List[InvoiceResponse])
def get_my_invoices(user: dict = Depends(verify_token), status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(InvoiceDB).filter(InvoiceDB.patient_id == user["user_id"])
    if status:
        query = query.filter(InvoiceDB.status == status)
    invoices = query.order_by(InvoiceDB.invoice_date.desc()).all()
    return invoices

@app.get("/invoices/patient/{patient_id}", response_model=List[InvoiceResponse])
def get_patient_invoices(patient_id: int, user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    if user["role"] not in ["admin", "doctor"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    invoices = db.query(InvoiceDB).filter(InvoiceDB.patient_id == patient_id).order_by(InvoiceDB.invoice_date.desc()).all()
    return invoices

@app.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(invoice_id: int, user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    invoice = db.query(InvoiceDB).filter(InvoiceDB.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.patient_id != user["user_id"] and user["role"] not in ["admin", "doctor"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return invoice

@app.put("/invoices/{invoice_id}/pay")
def pay_invoice(invoice_id: int, paid_date: str, user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    invoice = db.query(InvoiceDB).filter(InvoiceDB.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.patient_id != user["user_id"] and user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        invoice.paid_date = datetime.strptime(paid_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    invoice.status = "paid"
    db.commit()
    db.refresh(invoice)
    return {"message": "Invoice marked as paid"}

@app.get("/invoices/stats/summary")
def get_billing_summary(user: dict = Depends(verify_token), db: Session = Depends(get_db)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view billing summary")

    pending = db.query(func.count(InvoiceDB.id), func.sum(InvoiceDB.amount)).filter(InvoiceDB.status == "pending").first()
    paid = db.query(func.count(InvoiceDB.id), func.sum(InvoiceDB.amount)).filter(InvoiceDB.status == "paid").first()
    total = db.query(func.sum(InvoiceDB.amount)).first()

    return {
        "pending_invoices": pending[0] or 0,
        "pending_amount": pending[1] or 0.0,
        "paid_invoices": paid[0] or 0,
        "paid_amount": paid[1] or 0.0,
        "total_amount": total[0] or 0.0
    }

# ------------------------------
# Run server
# ------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
