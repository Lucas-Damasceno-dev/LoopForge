from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.routes import appointments, auth, notifications, professionals, services
from app.core.security import create_access_token, verify_password
from app.db.init_db import init_db
from app.db.session import get_db
from app.models import User


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Booking System", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(professionals.router)
app.include_router(services.router)
app.include_router(appointments.router)
app.include_router(notifications.router)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse(url="/login")


@app.get("/login", include_in_schema=False)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/htmx/login", include_in_schema=False)
def htmx_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Credenciais inválidas"},
            status_code=400,
        )

    token = create_access_token(subject=user.id, role=user.role)
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    return response


@app.get("/professionals-page", include_in_schema=False)
def professionals_page(request: Request, db: Session = Depends(get_db)):
    users = db.query(User).filter(User.role == "professional").order_by(User.name).all()
    return templates.TemplateResponse(
        "professionals.html",
        {"request": request, "professionals": users},
    )


@app.get("/appointments/new", include_in_schema=False)
def new_appointment_page(request: Request):
    return templates.TemplateResponse("appointment_form.html", {"request": request})


@app.get("/dashboard", include_in_schema=False)
def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})