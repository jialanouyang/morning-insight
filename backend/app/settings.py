"""应用基础配置。优先读取环境变量，其次读取 backend/.env 文件。"""
import os
from pathlib import Path


# 简易 .env 加载，避免额外依赖
def _load_dotenv():
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
REPO_DIR = BASE_DIR.parent                                  # 仓库根目录

DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///./data/morning_insight.db")
SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-do-not-use-in-production")
TOKEN_EXPIRE_HOURS: int = int(os.environ.get("TOKEN_EXPIRE_HOURS", "72"))
TIMEZONE: str = os.environ.get("TIMEZONE", "Asia/Shanghai")
DATA_DIR: str = os.environ.get("DATA_DIR", "./data")

# 插件目录：默认仓库根的 plugins/
PLUGIN_DIR: str = os.environ.get("PLUGIN_DIR", str(REPO_DIR / "plugins"))

# 是否允许安装本地插件（安全开关，默认开启；可设为 false 关闭插件安装入口）
PLUGIN_INSTALL_ENABLED: bool = os.environ.get("PLUGIN_INSTALL_ENABLED", "true").lower() not in ("0", "false", "no")

# 允许自助注册（首个注册用户自动成为管理员）
ALLOW_REGISTRATION: bool = os.environ.get("ALLOW_REGISTRATION", "true").lower() not in ("0", "false", "no")

# 保证 SQLite 数据目录存在
if DATABASE_URL.startswith("sqlite"):
    db_path = DATABASE_URL.replace("sqlite:///", "", 1)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
