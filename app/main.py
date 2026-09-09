from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import telegram_bot
from app.config import PUBLIC_DIR
from app.db import get_db
from app.security import COOKIE_NAME, verify_session_token

from app.routers import auth as auth_router
from app.routers import orgs as orgs_router
from app.routers import push as push_router
from app.routers import stats as stats_router
from app.routers import tasks as tasks_router
from app.routers import users as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    telegram_bot.start()
    yield
    telegram_bot.stop()


app = FastAPI(title="Topshiriqlar nazorati tizimi", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    message = errors[0]["msg"] if errors else "Noto'g'ri so'rov"
    return JSONResponse({"error": message}, status_code=422)


app.include_router(auth_router.router)
app.include_router(tasks_router.router)
app.include_router(orgs_router.router)
app.include_router(users_router.router)
app.include_router(stats_router.router)
app.include_router(push_router.router)


@app.get("/admin/login")
def admin_login_page():
    return FileResponse(PUBLIC_DIR / "admin" / "login.html")


@app.middleware("http")
async def admin_guard(request: Request, call_next):
    path = request.url.path
    if path.startswith("/admin") and path not in ("/admin/login", "/admin/login.html"):
        token = request.cookies.get(COOKIE_NAME)
        role = None
        if token:
            user_id = verify_session_token(token)
            if user_id is not None:
                db = get_db()
                row = db.execute("SELECT role FROM users WHERE id = ? AND is_active = 1", (user_id,)).fetchone()
                role = row["role"] if row else None
        if role != "admin":
            return RedirectResponse("/admin/login")
    return await call_next(request)


app.mount("/admin", StaticFiles(directory=PUBLIC_DIR / "admin", html=True), name="admin-static")


@app.get("/login")
def login_page():
    return FileResponse(PUBLIC_DIR / "login.html")


app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="static")


@app.exception_handler(404)
async def spa_fallback(request: Request, exc: HTTPException):
    if request.method == "GET" and not request.url.path.startswith("/api"):
        return FileResponse(PUBLIC_DIR / "index.html")
    return JSONResponse({"error": "Topilmadi"}, status_code=404)
