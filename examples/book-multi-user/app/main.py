from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, professionals, services, appointments, notifications
from app.db.base import Base
from app.db.session import engine

# Create tables (in production use Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Booking System")

# Mount static/templates if needed
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(professionals.router, prefix="/professionals", tags=["professionals"])
app.include_router(services.router, prefix="/services", tags=["services"])
app.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])

# Root endpoint (optional)
from fastapi.responses import HTMLResponse
from fastapi import Request

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})