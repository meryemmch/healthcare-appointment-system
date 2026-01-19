from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, DateTime, or_
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import hashlib
import jwt
from datetime import datetime, timedelta
import os

# ------------------------------
# FastAPI setup
# ------------------------------
app = FastAPI(title="Authentication Service")

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
        return {"service": "auth", "frontend": False}

# ------------------------------
# Security
# ------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
security = HTTPBearer()

# ------------------------------
# Database setup
# ------------------------------
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
# Models
# ------------------------------
class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    role = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# ------------------------------
# Pydantic models
# ------------------------------
class UserRegister(BaseModel):
    username: str
    password: str
    email: str
    role: str = "patient"

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    role: str

# ------------------------------
# Dependencies
# ------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ------------------------------
# Routes
# ------------------------------
@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "auth"}

@app.post("/register", response_model=Token)
def register(user: UserRegister, db: Session = Depends(get_db)):
    existing_user = db.query(UserDB).filter(
        (UserDB.username == user.username) | (UserDB.email == user.email)
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already exists")

    hashed_pw = hash_password(user.password)
    new_user = UserDB(
        username=user.username,
        password=hashed_pw,
        email=user.email,
        role=user.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_token(new_user.id, new_user.username, new_user.role)
    return Token(
        access_token=token,
        token_type="bearer",
        user_id=new_user.id,
        role=new_user.role
    )

@app.post("/login", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    hashed_pw = hash_password(user.password)
    # allow login by username OR email (frontend sends email as username when registering)
    db_user = db.query(UserDB).filter(
        UserDB.password == hashed_pw
    ).filter(
        or_(UserDB.username == user.username, UserDB.email == user.username)
    ).first()

    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(db_user.id, db_user.username, db_user.role)
    return Token(
        access_token=token,
        token_type="bearer",
        user_id=db_user.id,
        role=db_user.role
    )

@app.get("/verify")
def verify(payload: dict = Depends(verify_token)):
    return {"valid": True, "user": payload}


@app.get("/debug/users")
def debug_users(db: Session = Depends(get_db)):
    """Development-only: list users to help debug registration/login issues."""
    users = db.query(UserDB).all()
    return [{"id": u.id, "username": u.username, "email": u.email, "role": u.role} for u in users]


@app.get("/users/by-username/{username}")
def get_user_by_username(username: str, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_id": user.id, "username": user.username, "email": user.email, "role": user.role}

# ------------------------------
# Run server
# ------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
