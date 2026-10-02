"""本地演示数据脚本：创建一个演示账号并写入一份示例晨报，方便快速预览界面。

用法：
    cd backend
    python scripts/seed_demo.py

演示账号：demo@example.com / demo1234
重复执行不会产生重复账号（已存在则跳过）。
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Report, User  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.pipeline import ensure_default_config  # noqa: E402

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo1234"

SAMPLE_REPORT = """# 晨析晨报 · 示例

> 这是一份示例晨报，用于本地预览界面效果。真实使用时由 AI 按你的信息源与关注点生成。

## 行业动态

- **头部厂商发布新一代推理模型**，长上下文与工具调用能力显著提升，API 价格下调约 40%。（示例来源）
- **开源社区活跃度走高**，本周新增两个万星项目，均聚焦于 Agent 工作流编排。（示例来源）
- **云厂商调整 GPU 实例定价**，推理型实例降幅明显，训练型保持不变。（示例来源）

## 融资事件

- A 轮：某智能体基础设施公司完成 3000 万美元融资，由产业资本领投。（示例来源）
- 战略投资：某数据服务商获头部云厂商入股，双方将在数据合规方向合作。（示例来源）

## 政策监管

- 监管部门就生成式 AI 服务备案发布补充说明，进一步明确数据来源与标识要求。（示例来源）
- 多地出台算力补贴细则，对中小企业调用大模型 API 给予最高 50% 补贴。（示例来源）

## 今日建议

1. **评估模型迁移成本**：新一代模型降价明显，建议本周内对现有调用链路做一次成本测算。
2. **关注备案合规**：若产品面向公众提供生成式服务，请对照最新备案说明检查数据标识链路。
3. **留意算力补贴窗口**：中小企业可核查本地补贴细则，降低推理成本。
"""


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if user is None:
            user = User(
                email=DEMO_EMAIL,
                password_hash=hash_password(DEMO_PASSWORD),
                role="admin",
                display_name="演示账号",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"已创建演示账号：{DEMO_EMAIL} / {DEMO_PASSWORD}")
        else:
            print(f"演示账号已存在：{DEMO_EMAIL}")

        ensure_default_config(db, user.id)

        today = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
        exists = (
            db.query(Report)
            .filter(Report.user_id == user.id, Report.report_date == today)
            .first()
        )
        if exists is None:
            db.add(
                Report(
                    user_id=user.id,
                    report_date=today,
                    title="晨析晨报 · 示例",
                    content_md=SAMPLE_REPORT,
                    sources_used=["https://sspai.com/feed", "https://hnrss.org/frontpage"],
                )
            )
            db.commit()
            print("已写入一份示例晨报")
        else:
            print("今日已有晨报，跳过写入")
    finally:
        db.close()


if __name__ == "__main__":
    main()
