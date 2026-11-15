from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Generator, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (Boolean, Date, DateTime, ForeignKey, Integer, String,
                        Text, UniqueConstraint, create_engine, func, select, update)
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'alm_events.db').as_posix()}")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
engine = create_engine(DATABASE_URL, **engine_kwargs)
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
COOKIE_NAME = "eo_session"
CSRF_COOKIE = "eo_csrf"
SESSION_DAYS = 14
PAIRING_MINUTES = 15
DAILY_LIMIT_SECONDS = 6 * 60 * 60
PASSWORD_ITERATIONS = 310_000
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() in {"1", "true", "yes"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(60))
    age_band: Mapped[str] = mapped_column(String(16))
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16), default="user")
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Slot(Base):
    __tablename__ = "slots"
    __table_args__ = (UniqueConstraint("reserved_by", name="uq_single_slot_per_user"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(Integer, index=True)
    reserved_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reserved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PairingCode(Base):
    __tablename__ = "pairing_codes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    redeemed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class PairedDevice(Base):
    __tablename__ = "paired_devices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    device_label: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class DailyUsage(Base):
    __tablename__ = "daily_usage"
    __table_args__ = (UniqueConstraint("user_id", "usage_day", name="uq_daily_usage_user_day"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    usage_day: Mapped[date] = mapped_column(Date, index=True)
    seconds: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = ()


class LoginFailure(Base):
    __tablename__ = "login_failures"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_key: Mapped[str] = mapped_column(String(64), index=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class AdminAudit(Base):
    __tablename__ = "admin_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(40))
    target_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RegisterInput(BaseModel):
    username: str = Field(min_length=3, max_length=24)
    display_name: str = Field(min_length=1, max_length=40)
    age_band: str
    password: str = Field(min_length=12, max_length=128)

    @field_validator("username")
    @classmethod
    def clean_username(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,23}", value):
            raise ValueError("اسم المستخدم: أحرف إنجليزية وأرقام و . _ - فقط")
        return value

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("الاسم المعروض مطلوب")
        return value

    @field_validator("age_band")
    @classmethod
    def valid_age_band(cls, value: str) -> str:
        if value not in {"under18", "18plus"}:
            raise ValueError("اختر الفئة العمرية")
        return value


class LoginInput(BaseModel):
    username: str = Field(min_length=3, max_length=24)
    password: str = Field(min_length=1, max_length=128)


class ReserveInput(BaseModel):
    pass


class PairingRedeemInput(BaseModel):
    code: str = Field(min_length=20, max_length=128)
    device_label: str = Field(min_length=1, max_length=60)

    @field_validator("device_label")
    @classmethod
    def clean_label(cls, value: str) -> str:
        return value.strip()[:60]


class BootstrapInput(RegisterInput):
    pass


class AdminStatusInput(BaseModel):
    status: str


class SlotStatusInput(BaseModel):
    active: bool


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${key.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        method, iterations, salt_hex, expected = encoded.split("$", 3)
        if method != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.scalar(select(func.count(Slot.id))) == 0:
            db.add_all([Slot(id=i, group_id=((i - 1) // 50) + 1, is_active=True) for i in range(1, 301)])
            db.commit()


@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="ALMANTHOMH EO CN API",
    version="2.0.0",
    docs_url="/api-docs",
    redoc_url=None,
    description="خادم حسابات وخانات وجلسات ALMANTHOMH EO CN. لا ينفذ التحكم الفعلي بشاشة Android.",
)


@app.middleware("http")
async def security_and_csrf(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        cookie_token = request.cookies.get(CSRF_COOKIE, "")
        header_token = request.headers.get("x-csrf-token", "")
        origin = request.headers.get("origin")
        host = request.headers.get("host", "")
        if origin:
            from urllib.parse import urlsplit
            if urlsplit(origin).netloc != host:
                return JSONResponse({"detail": "مصدر الطلب غير مسموح"}, status_code=403)
        if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
            return JSONResponse({"detail": "رمز حماية الطلب غير صالح؛ أعد تحميل الصفحة"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(func.count(Slot.id))).scalar_one()
    return {"ok": True, "service": "ALMANTHOMH EO CN", "version": "2.0.0", "database": "connected"}


@app.get("/api/config")
def public_config():
    return {
        "appName": "ALMANTHOMH EO CN", "brand": "ESKO", "releaseVersion": "2.0.0",
        "backendConfigured": True, "slots": 300, "groups": 6,
        "pairingLinkMinutes": PAIRING_MINUTES, "dailyUsageLimitHours": 6,
        "inactiveSessionDays": SESSION_DAYS,
        "phoneScreenStreaming": False,
        "note": "الحسابات والحجز والجلسات تعمل عبر الخادم. عرض شاشة الهاتف يحتاج تطبيق Android مستقلًا بموافقة صاحبه.",
    }


@app.get("/api/auth/csrf")
def csrf(response: Response, request: Request):
    token = request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(32)
    response.set_cookie(CSRF_COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=False,
                        secure=COOKIE_SECURE, samesite="strict", path="/")
    return {"csrfToken": token}


def create_auth_session(db: Session, user: User, response: Response) -> None:
    raw = secrets.token_urlsafe(48)
    now = utcnow()
    record = AuthSession(user_id=user.id, token_hash=token_digest(raw), created_at=now,
                         last_activity=now, expires_at=now + timedelta(days=SESSION_DAYS))
    db.add(record)
    db.commit()
    response.set_cookie(COOKIE_NAME, raw, max_age=SESSION_DAYS * 86400, httponly=True,
                        secure=COOKIE_SECURE, samesite="strict", path="/")


def auth_context(request: Request, db: Session = Depends(get_db)):
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        raise HTTPException(401, "سجّل الدخول أولًا")
    auth = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_digest(raw)))
    now = utcnow()
    if not auth or auth.revoked_at or auth.expires_at <= now:
        raise HTTPException(401, "انتهت الجلسة؛ سجّل الدخول مجددًا")
    if (now - auth.last_activity) > timedelta(days=SESSION_DAYS):
        auth.revoked_at = now
        db.commit()
        raise HTTPException(401, "انتهت الجلسة بسبب عدم النشاط")
    user = db.get(User, auth.user_id)
    if not user or user.status != "active":
        auth.revoked_at = now
        db.commit()
        raise HTTPException(403, "الحساب غير متاح؛ تواصل مع مسؤول المنظومة")
    return user, auth


def require_admin(context=Depends(auth_context)):
    user, auth = context
    if user.role != "admin":
        raise HTTPException(403, "هذه الوظيفة للمطور فقط")
    return user, auth


def local_today():
    return datetime.now(ZoneInfo("Africa/Cairo")).date()


def ensure_daily_limit(db: Session, user_id: int) -> int:
    account = db.get(User, user_id)
    if account and account.role == "admin":
        return 0
    today = local_today()
    usage = db.scalar(select(DailyUsage).where(DailyUsage.user_id == user_id, DailyUsage.usage_day == today))
    seconds = usage.seconds if usage else 0
    if seconds >= DAILY_LIMIT_SECONDS:
        raise HTTPException(429, "تم الوصول إلى حد الاستخدام اليومي البالغ 6 ساعات")
    return seconds


def audit(db: Session, admin_id: int, action: str, target_user_id: Optional[int] = None, details: str = "") -> None:
    db.add(AdminAudit(admin_id=admin_id, action=action, target_user_id=target_user_id, details=details[:500]))


@app.post("/api/auth/register", status_code=201)
def register(data: RegisterInput, db: Session = Depends(get_db)):
    exists = db.scalar(select(User.id).where(User.username == data.username))
    if exists:
        raise HTTPException(409, "اسم المستخدم مستخدم بالفعل")
    user = User(username=data.username, display_name=data.display_name,
                age_band=data.age_band, password_hash=hash_password(data.password), role="user", status="active")
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "اسم المستخدم مستخدم بالفعل")
    return {"ok": True, "message": "تم إنشاء الحساب. سجّل الدخول للمتابعة.", "userId": user.id}


@app.post("/api/auth/login")
def login(data: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    username = data.username.strip().lower()
    ip = request.client.host if request.client else "unknown"
    key = hashlib.sha256(f"{username}|{ip}".encode()).hexdigest()
    since = utcnow() - timedelta(minutes=15)
    attempts = db.scalar(select(func.count(LoginFailure.id)).where(LoginFailure.attempt_key == key, LoginFailure.attempted_at >= since)) or 0
    if attempts >= 10:
        raise HTTPException(429, "محاولات كثيرة. انتظر 15 دقيقة ثم حاول مجددًا")
    user = db.scalar(select(User).where(User.username == username))
    if not user or not verify_password(data.password, user.password_hash) or user.status != "active":
        db.add(LoginFailure(attempt_key=key, attempted_at=utcnow()))
        db.commit()
        raise HTTPException(401, "اسم المستخدم أو كلمة المرور غير صحيحة")
    db.query(LoginFailure).filter(LoginFailure.attempt_key == key).delete(synchronize_session=False)
    db.commit()
    create_auth_session(db, user, response)
    return {"ok": True, "message": "تم تسجيل الدخول"}


@app.post("/api/auth/logout")
def logout(response: Response, context=Depends(auth_context), db: Session = Depends(get_db)):
    user, auth = context
    auth.revoked_at = utcnow()
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/me")
def me(context=Depends(auth_context), db: Session = Depends(get_db)):
    user, auth = context
    age_days = max(0, (utcnow() - auth.last_activity).days)
    today = local_today()
    usage = db.scalar(select(DailyUsage).where(DailyUsage.user_id == user.id, DailyUsage.usage_day == today))
    slot = db.scalar(select(Slot).where(Slot.reserved_by == user.id))
    return {"id": user.id, "username": user.username, "displayName": user.display_name,
            "ageBand": user.age_band, "role": user.role, "inactiveDays": age_days,
            "warningDays": 10 if age_days >= 10 else 13 if age_days >= 13 else None,
            "dailyUsageSeconds": usage.seconds if usage else 0,
            "dailyLimitSeconds": DAILY_LIMIT_SECONDS,
            "reservedSlot": slot.id if slot else None}


@app.post("/api/usage/heartbeat")
def heartbeat(response: Response, request: Request, context=Depends(auth_context), db: Session = Depends(get_db)):
    user, auth = context
    now = utcnow()
    if user.role == "admin":
        auth.last_activity = now
        auth.expires_at = now + timedelta(days=SESSION_DAYS)
        raw_cookie = request.cookies.get(COOKIE_NAME)
        if raw_cookie:
            response.set_cookie(COOKIE_NAME, raw_cookie, max_age=SESSION_DAYS * 86400, httponly=True,
                                secure=COOKIE_SECURE, samesite="strict", path="/")
        db.commit()
        return {"ok": True, "usedSeconds": 0, "remainingSeconds": DAILY_LIMIT_SECONDS, "limitReached": False, "unlimited": True}
    today = local_today()
    row = db.scalar(select(DailyUsage).where(DailyUsage.user_id == user.id, DailyUsage.usage_day == today))
    if not row:
        row = DailyUsage(user_id=user.id, usage_day=today, seconds=0)
        db.add(row)
        db.flush()
    delta = int((now - auth.last_activity).total_seconds())
    if 0 < delta <= 120:
        row.seconds = min(DAILY_LIMIT_SECONDS, row.seconds + delta)
    auth.last_activity = now
    auth.expires_at = now + timedelta(days=SESSION_DAYS)
    raw_cookie = request.cookies.get(COOKIE_NAME)
    if raw_cookie:
        response.set_cookie(COOKIE_NAME, raw_cookie, max_age=SESSION_DAYS * 86400, httponly=True,
                            secure=COOKIE_SECURE, samesite="strict", path="/")
    db.commit()
    remaining = max(0, DAILY_LIMIT_SECONDS - row.seconds)
    return {"ok": True, "usedSeconds": row.seconds, "remainingSeconds": remaining,
            "limitReached": row.seconds >= DAILY_LIMIT_SECONDS}


@app.get("/api/slots")
def list_slots(group: int = 0, context=Depends(auth_context), db: Session = Depends(get_db)):
    user, _ = context
    if user.role != "admin":
        ensure_daily_limit(db, user.id)
    stmt = select(Slot).order_by(Slot.id)
    if group:
        if group < 1 or group > 6:
            raise HTTPException(400, "رقم المجموعة يجب أن يكون من 1 إلى 6")
        stmt = stmt.where(Slot.group_id == group)
    rows = db.scalars(stmt).all()
    return {"slots": [{"id": s.id, "group": s.group_id, "active": s.is_active,
                       "reserved": s.reserved_by is not None, "mine": s.reserved_by == user.id}
                      for s in rows]}


@app.post("/api/slots/{slot_id}/reserve")
def reserve_slot(slot_id: int, context=Depends(auth_context), db: Session = Depends(get_db)):
    user, _ = context
    ensure_daily_limit(db, user.id)
    slot = db.get(Slot, slot_id)
    if not slot or not slot.is_active:
        raise HTTPException(404, "الخانة غير متاحة")
    existing = db.scalar(select(Slot).where(Slot.reserved_by == user.id))
    if existing and existing.id != slot_id:
        raise HTTPException(409, f"لديك حجز قائم للخانة {existing.id}. حرره أولًا")
    if slot.reserved_by == user.id:
        return {"ok": True, "slotId": slot_id, "message": "الخانة محجوزة لحسابك بالفعل"}
    result = db.execute(update(Slot).where(Slot.id == slot_id, Slot.reserved_by.is_(None), Slot.is_active.is_(True))
                        .values(reserved_by=user.id, reserved_at=utcnow()))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "سبقك مستخدم آخر إلى هذه الخانة")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "الحساب لديه خانة محجوزة بالفعل أو سبقك مستخدم آخر")
    return {"ok": True, "slotId": slot_id, "message": "تم حجز الخانة لحسابك"}


@app.delete("/api/slots/{slot_id}/reserve")
def release_slot(slot_id: int, context=Depends(auth_context), db: Session = Depends(get_db)):
    user, _ = context
    result = db.execute(update(Slot).where(Slot.id == slot_id, Slot.reserved_by == user.id)
                        .values(reserved_by=None, reserved_at=None))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(404, "لا يوجد حجز لهذه الخانة في حسابك")
    db.query(PairingCode).filter(PairingCode.slot_id == slot_id, PairingCode.user_id == user.id,
                                PairingCode.redeemed_at.is_(None)).update({"redeemed_at": utcnow()}, synchronize_session=False)
    db.commit()
    return {"ok": True, "message": "تم تحرير الخانة وإلغاء روابط الربط غير المستخدمة"}


@app.post("/api/pairings")
def create_pairing(slot_id: int, context=Depends(auth_context), db: Session = Depends(get_db)):
    user, _ = context
    ensure_daily_limit(db, user.id)
    slot = db.get(Slot, slot_id)
    if not slot or slot.reserved_by != user.id or not slot.is_active:
        raise HTTPException(403, "يمكن إنشاء رابط ربط لخانتك المحجوزة فقط")
    raw = secrets.token_urlsafe(32)
    now = utcnow()
    # Issuing a fresh link rotates the previous unused link for this slot.
    db.query(PairingCode).filter(PairingCode.slot_id == slot_id, PairingCode.user_id == user.id,
                                 PairingCode.redeemed_at.is_(None)).update({"redeemed_at": now}, synchronize_session=False)
    db.add(PairingCode(slot_id=slot_id, user_id=user.id, token_hash=token_digest(raw),
                       created_at=now, expires_at=now + timedelta(minutes=PAIRING_MINUTES)))
    db.commit()
    return {"ok": True, "code": raw, "expiresAt": (now + timedelta(minutes=PAIRING_MINUTES)).isoformat() + "Z",
            "expiresInMinutes": PAIRING_MINUTES,
            "notice": "رمز ربط أحادي الاستخدام فقط؛ لا يفعّل تحكم الهاتف أو بث الشاشة."}


@app.post("/api/pairings/redeem", status_code=201)
def redeem_pairing(data: PairingRedeemInput, db: Session = Depends(get_db)):
    row = db.scalar(select(PairingCode).where(PairingCode.token_hash == token_digest(data.code)))
    now = utcnow()
    if not row or row.redeemed_at or row.expires_at <= now:
        raise HTTPException(400, "رمز الربط غير صالح أو منتهي أو سبق استخدامه")
    slot = db.get(Slot, row.slot_id)
    if not slot or slot.reserved_by != row.user_id or not slot.is_active:
        raise HTTPException(400, "لم يعد الحجز صالحًا")
    row.redeemed_at = now
    device = PairedDevice(slot_id=row.slot_id, user_id=row.user_id, device_label=data.device_label.strip())
    db.add(device)
    db.commit()
    return {"ok": True, "pairedDeviceId": device.id,
            "message": "تم تسجيل جهاز مقترن. لا يوجد بث شاشة أو تحكم عن بعد في هذا الإصدار."}


@app.post("/api/admin/bootstrap", status_code=201)
def bootstrap_admin(data: BootstrapInput, request: Request, db: Session = Depends(get_db),
                    x_bootstrap_key: Optional[str] = Header(default=None)):
    configured = os.getenv("ADMIN_BOOTSTRAP_KEY", "")
    if not configured:
        raise HTTPException(503, "لم يتم إعداد مفتاح تأسيس المدير في متغيرات الخادم")
    if not x_bootstrap_key or not hmac.compare_digest(x_bootstrap_key, configured):
        raise HTTPException(403, "مفتاح التأسيس غير صحيح")
    admins = db.scalar(select(func.count(User.id)).where(User.role == "admin")) or 0
    if admins:
        raise HTTPException(409, "يوجد مدير بالفعل؛ التأسيس الأولي مغلق")
    if db.scalar(select(User.id).where(User.username == data.username)):
        raise HTTPException(409, "اسم المستخدم مستخدم بالفعل")
    user = User(username=data.username, display_name=data.display_name, age_band=data.age_band,
                password_hash=hash_password(data.password), role="admin", status="active")
    db.add(user)
    db.commit()
    return {"ok": True, "message": "تم إنشاء حساب المدير. احذف ADMIN_BOOTSTRAP_KEY من إعدادات التشغيل بعد ذلك."}


@app.get("/api/admin/overview")
def admin_overview(context=Depends(require_admin), db: Session = Depends(get_db)):
    total_users = db.scalar(select(func.count(User.id))) or 0
    active_users = db.scalar(select(func.count(User.id)).where(User.status == "active")) or 0
    reserved_slots = db.scalar(select(func.count(Slot.id)).where(Slot.reserved_by.is_not(None))) or 0
    active_sessions = db.scalar(select(func.count(AuthSession.id)).where(AuthSession.revoked_at.is_(None), AuthSession.expires_at > utcnow())) or 0
    return {"users": total_users, "activeUsers": active_users, "reservedSlots": reserved_slots,
            "totalSlots": 300, "activeSessions": active_sessions}


@app.get("/api/admin/users")
def admin_search_users(q: str = "", context=Depends(require_admin), db: Session = Depends(get_db)):
    q = q.strip()[:60]
    stmt = select(User).order_by(User.id.desc()).limit(100)
    if q:
        stmt = select(User).where((User.username.ilike(f"%{q}%")) | (User.display_name.ilike(f"%{q}%"))).order_by(User.id.desc()).limit(100)
    users = db.scalars(stmt).all()
    return {"users": [{"id": u.id, "username": u.username, "displayName": u.display_name,
                       "role": u.role, "status": u.status, "createdAt": u.created_at.isoformat() + "Z"}
                      for u in users]}


@app.post("/api/admin/users/{user_id}/revoke-sessions")
def admin_revoke_sessions(user_id: int, context=Depends(require_admin), db: Session = Depends(get_db)):
    admin, _ = context
    if not db.get(User, user_id):
        raise HTTPException(404, "الحساب غير موجود")
    now = utcnow()
    db.query(AuthSession).filter(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)).update({"revoked_at": now}, synchronize_session=False)
    audit(db, admin.id, "revoke_sessions", user_id)
    db.commit()
    return {"ok": True, "message": "تم إنهاء جلسات الحساب"}


@app.post("/api/admin/users/{user_id}/status")
def admin_set_user_status(user_id: int, data: AdminStatusInput, context=Depends(require_admin), db: Session = Depends(get_db)):
    admin, _ = context
    if data.status not in {"active", "blocked"}:
        raise HTTPException(400, "الحالة يجب أن تكون active أو blocked")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "الحساب غير موجود")
    if target.role == "admin":
        raise HTTPException(403, "لا يمكن حظر حساب مدير من هذه الواجهة")
    target.status = data.status
    if data.status == "blocked":
        now = utcnow()
        db.query(AuthSession).filter(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)).update({"revoked_at": now}, synchronize_session=False)
        db.query(Slot).filter(Slot.reserved_by == user_id).update({"reserved_by": None, "reserved_at": None}, synchronize_session=False)
        db.query(PairingCode).filter(PairingCode.user_id == user_id, PairingCode.redeemed_at.is_(None)).update({"redeemed_at": now}, synchronize_session=False)
    audit(db, admin.id, "set_user_status", user_id, data.status)
    db.commit()
    return {"ok": True, "status": target.status}


@app.patch("/api/admin/slots/{slot_id}")
def admin_set_slot(slot_id: int, data: SlotStatusInput, context=Depends(require_admin), db: Session = Depends(get_db)):
    admin, _ = context
    slot = db.get(Slot, slot_id)
    if not slot:
        raise HTTPException(404, "الخانة غير موجودة")
    slot.is_active = data.active
    if not data.active:
        slot.reserved_by = None
        slot.reserved_at = None
    audit(db, admin.id, "set_slot_active", details=f"slot={slot_id};active={data.active}")
    db.commit()
    return {"ok": True, "slotId": slot_id, "active": slot.is_active}


# Static frontend is served by this same application, so cookies and CSRF tokens remain same-origin.
app.mount("/", StaticFiles(directory=str(DOCS_DIR), html=True), name="site")
