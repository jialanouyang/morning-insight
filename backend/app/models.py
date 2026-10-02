"""数据模型（对应产品需求文档 v1.1 第八章「数据结构」，并做工程化补全）。

表清单：
- users                用户（邮箱 / 密码 / 角色）
- user_configs         用户配置（行业、关键词、关注点、角色、信息源、AI、推送、调度、模板、语言、TTS）
- reports              晨报存档
- articles             原始信息（去重与溯源）
- report_translations  晨报译文缓存（按目标语言存一份）
- push_logs            推送记录
- knowledge_chunks     知库切片（含向量，用于 RAG）
- competitors          动态追踪对象
- alerts               关键词预警规则
- alert_logs           预警历史
- periodical_reports   周报 / 月报
- plugins              插件
- marketplace_items    市场分享（模板 / 角色 / 信息源 / 插件）
- tts_assets           语音晨报音频文件
- llm_usage            大模型调用记录（成本控制）

命名统一约定（全项目一致）：
- UserConfig.focus_points  关注点 [{id, name, description, builtin, enabled}]
- UserConfig.roles         角色   [{id, name, description, system_prompt, enabled}]
- UserConfig.sources       信息源 [{name, type, url, enabled, priority, tags, ...}]
- UserConfig.ai_config     AI 配置 {base_url, api_key, model, models, embedding_model, prompt, language, length}
- UserConfig.push_config   推送渠道 {email: {...}, wecom: {...}, ...}
- UserConfig.schedule      调度 {enabled, time, days, cron, timezone, periodical}
- Report.content_md / Report.content_html / Report.template / Report.sources_used / Report.report_date
"""
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# 用户与配置
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")  # admin / user
    display_name: Mapped[str] = mapped_column(String(100), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserConfig(Base):
    __tablename__ = "user_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)

    # 行业 / 赛道：多选 + 自定义关键词
    industry: Mapped[str] = mapped_column(String(200), default="")
    industries: Mapped[list] = mapped_column(JSON, default=list)
    keywords: Mapped[list] = mapped_column(JSON, default=list)

    # 关注点决定晨报板块结构（三层设计：内置 / 改内置 / 完全自定义）
    focus_points: Mapped[list] = mapped_column(JSON, default=list)
    # 角色决定建议视角（内置模板 Prompt 可见可编辑 / 完全自定义）
    roles: Mapped[list] = mapped_column(JSON, default=list)

    # 信息源（RSS / API / 网页），支持标签与优先级
    sources: Mapped[list] = mapped_column(JSON, default=list)

    # AI 配置（多模型可选、Prompt 模板可编辑）
    ai_config: Mapped[dict] = mapped_column(JSON, default=dict)

    # 推送渠道配置（多渠道独立）
    push_config: Mapped[dict] = mapped_column(JSON, default=dict)
    # 兼容字段：v0.1 的邮件配置，读取时合并进 push_config["email"]
    push_email: Mapped[dict] = mapped_column(JSON, default=dict)

    # 调度：每天 / 工作日 / 每周 / 自定义 cron
    schedule: Mapped[dict] = mapped_column(JSON, default=dict)

    # 晨报模板（简报版 / 杂志版 / 数据版 / 卡片版 / 终端版 / 打印版 / 自定义 HTML）
    template: Mapped[str] = mapped_column(String(50), default="brief")
    template_config: Mapped[dict] = mapped_column(JSON, default=dict)

    # 语言：界面语言 / 晨报语言 / 翻译开关
    ui_language: Mapped[str] = mapped_column(String(10), default="zh")
    report_language: Mapped[str] = mapped_column(String(20), default="zh")
    translate_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # 语音晨报
    tts_config: Mapped[dict] = mapped_column(JSON, default=dict)

    # 知库（RAG）
    knowledge_config: Mapped[dict] = mapped_column(JSON, default=dict)

    # 时间窗（小时）等抓取参数
    fetch_config: Mapped[dict] = mapped_column(JSON, default=dict)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# --------------------------------------------------------------------------- #
# 晨报与原始信息
# --------------------------------------------------------------------------- #
class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    report_date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    industry: Mapped[str] = mapped_column(String(200), default="")
    title: Mapped[str] = mapped_column(String(500), default="")
    template: Mapped[str] = mapped_column(String(50), default="brief")
    content_md: Mapped[str] = mapped_column(Text, default="")
    content_html: Mapped[str] = mapped_column(Text, default="")
    sources_used: Mapped[list] = mapped_column(JSON, default=list)  # 引用文章 URL 列表
    meta: Mapped[dict] = mapped_column(JSON, default=dict)  # 统计信息（条数/耗时/模型）
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Article(Base):
    """已抓取文章：用于 URL / 标题 / 内容相似度去重与引用溯源。"""

    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("user_id", "url", name="uq_user_article_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    url: Mapped[str] = mapped_column(String(1000))
    source: Mapped[str] = mapped_column(String(200), default="")
    published_at: Mapped[str] = mapped_column(String(50), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    raw_content: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(100), default="")
    focus_point: Mapped[str] = mapped_column(String(100), default="")
    language: Mapped[str] = mapped_column(String(10), default="")
    region: Mapped[str] = mapped_column(String(20), default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    title_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    content_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReportTranslation(Base):
    """晨报译文缓存：一份晨报 × 一个目标语言只存一份，避免重复调用大模型。"""

    __tablename__ = "report_translations"
    __table_args__ = (UniqueConstraint("report_id", "target_lang", name="uq_report_translation"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), index=True)
    target_lang: Mapped[str] = mapped_column(String(10))  # zh / en
    source_lang: Mapped[str] = mapped_column(String(10), default="")
    title: Mapped[str] = mapped_column(String(500), default="")
    content_md: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- #
# 推送
# --------------------------------------------------------------------------- #
class PushLog(Base):
    __tablename__ = "push_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    report_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id"), nullable=True)
    periodical_id: Mapped[int | None] = mapped_column(ForeignKey("periodical_reports.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default="report")  # report / periodical / alert / test
    channel: Mapped[str] = mapped_column(String(50), default="")
    status: Mapped[str] = mapped_column(String(20), default="success")  # success / failed
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- #
# 知库（RAG）
# --------------------------------------------------------------------------- #
class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    report_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id"), nullable=True)
    periodical_id: Mapped[int | None] = mapped_column(ForeignKey("periodical_reports.id"), nullable=True)
    article_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(20), default="report")  # report / periodical / article
    title: Mapped[str] = mapped_column(String(500), default="")
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    chunk_text: Mapped[str] = mapped_column(Text, default="")
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 向量（本地检索用）
    embedding_provider: Mapped[str] = mapped_column(String(50), default="")
    doc_date: Mapped[str] = mapped_column(String(20), default="", index=True)
    industry: Mapped[str] = mapped_column(String(200), default="")
    chunk_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- #
# 动态追踪
# --------------------------------------------------------------------------- #
class Competitor(Base):
    __tablename__ = "competitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20), default="company")  # company / product
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    level: Mapped[str] = mapped_column(String(20), default="normal")  # high / normal
    notes: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CompetitorEvent(Base):
    """动态追踪到的动作记录：新闻 / 公告 / 融资 / 产品更新 / 高管变动。"""

    __tablename__ = "competitor_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id"), index=True)
    article_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(30), default="news")
    title: Mapped[str] = mapped_column(String(500), default="")
    url: Mapped[str] = mapped_column(String(1000), default="")
    source: Mapped[str] = mapped_column(String(200), default="")
    is_highlight: Mapped[bool] = mapped_column(Boolean, default=False)
    event_date: Mapped[str] = mapped_column(String(20), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- #
# 关键词预警
# --------------------------------------------------------------------------- #
class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    keyword: Mapped[str] = mapped_column(String(200))
    match_type: Mapped[str] = mapped_column(String(20), default="exact")  # exact / fuzzy
    condition: Mapped[str] = mapped_column(String(20), default="always")  # always / frequency / source
    condition_value: Mapped[int] = mapped_column(Integer, default=1)
    channels: Mapped[list] = mapped_column(JSON, default=list)  # 复用的推送渠道
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=180)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AlertLog(Base):
    __tablename__ = "alert_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"), index=True)
    article_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id"), nullable=True)
    keyword: Mapped[str] = mapped_column(String(200), default="")
    title: Mapped[str] = mapped_column(String(500), default="")
    url: Mapped[str] = mapped_column(String(1000), default="")
    pushed: Mapped[bool] = mapped_column(Boolean, default=False)
    detail: Mapped[str] = mapped_column(Text, default="")
    pushed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- #
# 周报 / 月报
# --------------------------------------------------------------------------- #
class PeriodicalReport(Base):
    __tablename__ = "periodical_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    period_type: Mapped[str] = mapped_column(String(20), default="weekly")  # weekly / monthly
    period_start: Mapped[str] = mapped_column(String(20), default="")
    period_end: Mapped[str] = mapped_column(String(20), default="")
    title: Mapped[str] = mapped_column(String(500), default="")
    content_md: Mapped[str] = mapped_column(Text, default="")
    content_html: Mapped[str] = mapped_column(Text, default="")
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    sources_used: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- #
# 插件与市场
# --------------------------------------------------------------------------- #
class Plugin(Base):
    __tablename__ = "plugins"
    __table_args__ = (UniqueConstraint("name", "type", name="uq_plugin_name_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20), default="source")  # source / push / ai
    version: Mapped[str] = mapped_column(String(50), default="0.1.0")
    author: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    entry_point: Mapped[str] = mapped_column(String(200), default="plugin.py")
    path: Mapped[str] = mapped_column(String(1000), default="")
    config_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MarketplaceItem(Base):
    __tablename__ = "marketplace_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(20), default="template")  # template / role / source / plugin
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(200), default="", index=True)
    author: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[str] = mapped_column(String(50), default="0.1.0")
    content: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    downloads: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- #
# 语音晨报 / 大模型用量
# --------------------------------------------------------------------------- #
class TTSAsset(Base):
    __tablename__ = "tts_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    report_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id"), nullable=True)
    periodical_id: Mapped[int | None] = mapped_column(ForeignKey("periodical_reports.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(50), default="edge")
    voice: Mapped[str] = mapped_column(String(100), default="")
    fmt: Mapped[str] = mapped_column(String(10), default="mp3")
    path: Mapped[str] = mapped_column(String(1000), default="")
    script_text: Mapped[str] = mapped_column(Text, default="")
    duration_sec: Mapped[float] = mapped_column(Float, default=0.0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LLMUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    scene: Mapped[str] = mapped_column(String(50), default="report")  # report / periodical / knowledge / summary / tts
    provider: Mapped[str] = mapped_column(String(200), default="")
    model: Mapped[str] = mapped_column(String(200), default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
