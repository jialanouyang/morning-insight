"""认证路由：注册 / 登录 / 当前用户 / 修改资料。首个注册用户自动成为管理员。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import create_token, get_current_user, hash_password, verify_password
from ..services.pipeline import ensure_default_config
from ..settings import ALLOW_REGISTRATION

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _norm_ui_language(value) -> str:
    """归一化界面语言：仅支持 zh / en。"""
    return "en" if str(value or "").lower().startswith("en") else "zh"


def _apply_login_language(db: Session, user: User, ui_language) -> None:
    """登录 / 注册时应用所选语言：界面语言与晨报语言同步切换（用户需求：
    中文登录看到的都是中文，英文登录看到的都是英文）。"""
    if not ui_language:
        return
    lang = _norm_ui_language(ui_language)
    cfg = ensure_default_config(db, user.id)
    if cfg.ui_language != lang or cfg.report_language != lang:
        cfg.ui_language = lang
        cfg.report_language = lang
        db.commit()


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    display_name: str = ""
    ui_language: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    ui_language: str | None = None


class ProfileIn(BaseModel):
    display_name: str | None = None
    ui_language: str | None = None


class PasswordIn(BaseModel):
    old_password: str
    new_password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str
    display_name: str
    is_active: bool = True


class TokenOut(BaseModel):
    token: str
    user: UserOut


@router.get("/status")
def status(db: Session = Depends(get_db)):
    """前端登录页用：是否需要引导创建首个管理员。"""
    has_user = db.scalar(select(User).limit(1)) is not None
    return {"has_user": has_user, "allow_registration": ALLOW_REGISTRATION}


@router.post("/register", response_model=TokenOut)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    is_first = db.scalar(select(User).limit(1)) is None
    if not is_first and not ALLOW_REGISTRATION:
        raise HTTPException(status_code=403, detail="本站已关闭自助注册，请联系管理员开通账号")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    if db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(status_code=400, detail="该邮箱已注册")
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        role="admin" if is_first else "user",
        display_name=data.display_name or data.email.split("@")[0],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _apply_login_language(db, user, data.ui_language)
    return TokenOut(token=create_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被停用")
    _apply_login_language(db, user, data.ui_language)
    return TokenOut(token=create_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


@router.put("/me", response_model=UserOut)
def update_me(data: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.display_name is not None:
        user.display_name = data.display_name
    db.commit()
    db.refresh(user)
    if data.ui_language is not None:
        cfg = ensure_default_config(db, user.id)
        cfg.ui_language = _norm_ui_language(data.ui_language)
        db.commit()
    return UserOut.model_validate(user)


@router.post("/password")
def change_password(data: PasswordIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"ok": True}
