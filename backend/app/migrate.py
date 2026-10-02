"""轻量数据库迁移：为已存在的表补齐新增列。

自托管场景下用户会沿用旧的 SQLite 文件，而 `create_all` 只会新建表、
不会给已有表加列。这里在启动时比对模型定义与实际库结构，自动 `ALTER TABLE ADD COLUMN`，
让升级过程无需手工操作（SQLite 支持加列，但要求不能是无默认值的 NOT NULL）。
"""
import logging

from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateIndex

from .database import Base, engine

logger = logging.getLogger("morning_insight.migrate")


def _sql_type(column) -> str:
    try:
        return column.type.compile(dialect=engine.dialect)
    except Exception:  # pragma: no cover - 极端类型的兜底
        return "TEXT"


def run_migrations() -> list[str]:
    """补齐缺失的表与列，返回执行过的变更描述列表。"""
    changes: list[str] = []
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            have = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in have:
                    continue
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {_sql_type(column)}'
                if column.default is not None and not column.default.is_callable:
                    ddl += f" DEFAULT {column.default.arg!r}"
                conn.execute(text(ddl))
                changes.append(f"{table.name}.{column.name}")

            # 为新增的索引列补索引（已存在的索引由 create_all 处理新表）
            existing_indexes = {i["name"] for i in inspector.get_indexes(table.name)}
            for index in table.indexes:
                if index.name in existing_indexes:
                    continue
                try:
                    conn.execute(CreateIndex(index))
                    changes.append(f"index:{index.name}")
                except Exception as exc:  # pragma: no cover
                    logger.warning("创建索引失败 %s: %s", index.name, exc)

    if changes:
        logger.info("数据库已补齐 %d 项变更：%s", len(changes), ", ".join(changes[:20]))
    return changes
