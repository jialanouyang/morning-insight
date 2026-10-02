"""后端接口与核心链路测试。

覆盖：
- 认证与多用户隔离
- 配置读写与密钥掩码
- 元信息 / 能力自检
- 晨报生成（无 AI 兜底 / Mock AI 全链路）、导出、推送渠道测试
- 知识库问答与检索
- 动态追踪、关键词预警、周报月报
- 插件系统（发现、启用、执行）
- 管理后台

运行：
    cd backend
    pip install -r requirements-dev.txt
    pytest -v
"""
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 必须在导入 app 之前指定测试库，避免污染开发数据
_TMP_DIR = Path(tempfile.mkdtemp(prefix="mi-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP_DIR / 'test.db').as_posix()}"
os.environ["DATA_DIR"] = (_TMP_DIR / "data").as_posix()

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import uvicorn  # noqa: E402

from app.main import app  # noqa: E402

MOCK_PORT = 8010
MOCK_MD = "# 晨析晨报 测试\n\n## 行业动态\n- 这是一条来自 Mock AI 的测试条目。\n\n## 今日建议\n1. 保持关注。"

mock_app = FastAPI()


@mock_app.post("/v1/chat/completions")
def mock_chat(payload: dict):  # noqa: ARG001
    return {"choices": [{"message": {"content": MOCK_MD}}]}


@mock_app.post("/v1/embeddings")
def mock_embeddings(payload: dict):  # noqa: ARG001
    data = payload.get("input") or []
    if isinstance(data, str):
        data = [data]
    return {"data": [{"embedding": [0.1] * 64, "index": i} for i, _ in enumerate(data)]}


@pytest.fixture(scope="session", autouse=True)
def mock_ai_server():
    server = uvicorn.Server(
        uvicorn.Config(mock_app, host="127.0.0.1", port=MOCK_PORT, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    yield
    server.should_exit = True


@pytest.fixture(scope="session")
def client():
    # 使用上下文管理器以触发 lifespan：建表 + 迁移 + 插件同步
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth(client):
    resp = client.post(
        "/api/auth/register", json={"email": "owner@example.com", "password": "owner123"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return {"headers": {"Authorization": f"Bearer {data['token']}"}, "user": data["user"]}


@pytest.fixture(scope="session")
def other(client):
    resp = client.post(
        "/api/auth/register", json={"email": "other@example.com", "password": "other123"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return {"headers": {"Authorization": f"Bearer {data['token']}"}, "user": data["user"]}


# =========================================================================== #
# 系统
# =========================================================================== #
def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_features_lists_capabilities(client):
    data = client.get("/api/features").json()
    assert set(data["capabilities"]["source_types"]) == {"rss", "api", "web", "plugin"}
    assert data["capabilities"]["push_channels"] >= 13
    assert "playwright" in data["optional"]


def test_meta_returns_all_catalogs(client, auth):
    meta = client.get("/api/meta", headers=auth["headers"]).json()
    for key in (
        "focus_points", "roles", "templates", "industries", "ai_providers",
        "embedding_providers", "vector_stores", "tts_providers", "ui_languages",
        "report_languages", "report_lengths", "channels", "default_sources",
        "source_catalog", "source_templates", "plugin_types", "plugin_permissions",
    ):
        assert key in meta, f"缺少 {key}"
    assert len(meta["focus_points"]) == 8          # 文档要求 8 个内置关注点
    assert len(meta["roles"]) == 7                 # 7 个内置角色模板
    assert len(meta["templates"]) == 6             # 6 套晨报模板
    assert len(meta["ui_languages"]) == 2          # 中英
    assert meta["report_lengths"][0]["id"] == "brief"


# =========================================================================== #
# 认证
# =========================================================================== #
def test_first_user_is_admin(auth):
    assert auth["user"]["role"] == "admin"


def test_auth_status(client, auth):
    data = client.get("/api/auth/status").json()
    assert data["has_user"] is True
    assert data["allow_registration"] is True


def test_duplicate_register_rejected(client, auth):
    resp = client.post(
        "/api/auth/register", json={"email": "owner@example.com", "password": "owner123"}
    )
    assert resp.status_code == 400


def test_invalid_email_rejected(client):
    resp = client.post("/api/auth/register", json={"email": "not-an-email", "password": "abc123"})
    assert resp.status_code == 422


def test_short_password_rejected(client):
    resp = client.post("/api/auth/register", json={"email": "short@example.com", "password": "123"})
    assert resp.status_code == 400


def test_login_and_wrong_password(client, auth):
    ok = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "owner123"})
    assert ok.status_code == 200
    assert "token" in ok.json()
    bad = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "wrong"})
    assert bad.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/reports").status_code in (401, 403)
    assert client.get("/api/config").status_code in (401, 403)


def test_change_password(client, auth):
    # 用错误原密码
    bad = client.post(
        "/api/auth/password",
        headers=auth["headers"],
        json={"old_password": "nope", "new_password": "abcdef"},
    )
    assert bad.status_code == 400


# =========================================================================== #
# 配置
# =========================================================================== #
def test_default_config(client, auth):
    cfg = client.get("/api/config", headers=auth["headers"]).json()
    assert len(cfg["sources"]) > 0
    assert len(cfg["focus_points"]) == 8
    assert len(cfg["roles"]) == 7
    assert cfg["ai_config"]["model"]
    assert cfg["ai_config"]["api_key"] == ""
    assert cfg["schedule"]["enabled"] is False
    assert cfg["fetch_config"]["since_hours"] == 24
    assert cfg["knowledge_config"]["enabled"] is True
    assert "email" in cfg["push_config"] and "wecom" in cfg["push_config"]


def test_secret_masking_and_preservation(client, auth):
    headers = auth["headers"]
    client.put(
        "/api/config",
        headers=headers,
        json={
            "ai_config": {"api_key": "sk-test-secret", "base_url": "https://example.com/v1"},
            "push_config": {"email": {"enabled": True, "smtp_pass": "smtp-secret", "smtp_host": "smtp.qq.com"}},
        },
    )

    masked = client.get("/api/config", headers=headers).json()
    assert masked["ai_config"]["api_key"] == "***"
    assert masked["push_config"]["email"]["smtp_pass"] == "***"
    assert masked["push_config"]["email"]["smtp_host"] == "smtp.qq.com"  # 非密钥字段不掩码

    # 回传掩码应保持原值，且不报错
    assert client.put("/api/config", headers=headers, json=masked).status_code == 200
    again = client.get("/api/config", headers=headers).json()
    assert again["ai_config"]["api_key"] == "***"
    assert again["push_config"]["email"]["smtp_pass"] == "***"


def test_config_sections_roundtrip(client, auth):
    headers = auth["headers"]
    payload = {
        "industries": ["半导体与集成电路", "人工智能"],
        "keywords": ["先进封装", "EDA"],
        "template": "magazine",
        "report_language": "bilingual",
        "translate_enabled": True,
        "tts_config": {"enabled": True, "provider": "edge", "voice": "zh-CN-YunxiNeural"},
        "knowledge_config": {"enabled": True, "auto_ingest": True, "top_k": 8, "vector_store": "builtin"},
        "fetch_config": {"since_hours": 48, "limit_per_source": 30},
        "template_config": {"custom_html": "<article>{{title}}{{content}}</article>", "custom_css": "body{font-size:15px}"},
    }
    assert client.put("/api/config", headers=headers, json=payload).status_code == 200
    cfg = client.get("/api/config", headers=headers).json()
    assert cfg["keywords"] == ["先进封装", "EDA"]
    assert cfg["template"] == "magazine"
    assert cfg["translate_enabled"] is True
    assert cfg["tts_config"]["voice"] == "zh-CN-YunxiNeural"
    assert cfg["knowledge_config"]["top_k"] == 8
    assert cfg["fetch_config"]["since_hours"] == 48
    assert "custom_html" in cfg["template_config"]


def test_channel_test_returns_error_without_config(client, auth):
    """未配置 SMTP 时应返回明确失败原因，而不是 500。"""
    resp = client.post(
        "/api/config/channels/test", headers=auth["headers"], json={"channel": "email"}
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is False
    assert "SMTP" in resp.json()["detail"]


def test_channel_test_unknown_channel(client, auth):
    resp = client.post(
        "/api/config/channels/test", headers=auth["headers"], json={"channel": "nope"}
    )
    assert resp.status_code == 404


def test_ai_test_requires_config(client, auth):
    headers = auth["headers"]
    before = client.get("/api/config", headers=headers).json()["ai_config"]
    # 清空 base_url 后应提示先配置
    client.put("/api/config", headers=headers, json={"ai_config": {"base_url": ""}})
    resp = client.post("/api/config/ai/test", headers=headers)
    assert resp.status_code == 400
    # 还原
    client.put("/api/config", headers=headers, json={"ai_config": before})


def test_source_test_invalid_url(client, auth):
    resp = client.post(
        "/api/config/sources/test",
        headers=auth["headers"],
        json={"source": {"name": "坏源", "type": "rss", "url": "http://127.0.0.1:1/x.xml"}},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is False


def test_reset_focus_points(client, auth):
    headers = auth["headers"]
    client.put(
        "/api/config",
        headers=headers,
        json={"focus_points": [{"id": "x", "name": "临时", "description": "", "enabled": True}]},
    )
    assert client.post("/api/config/reset?section=focus_points", headers=headers).status_code == 200
    assert len(client.get("/api/config", headers=headers).json()["focus_points"]) == 8


# =========================================================================== #
# 晨报
# =========================================================================== #
def test_generate_without_ai_falls_back_to_material(client, auth):
    """未配置 AI 时不应失败，而应生成「素材版」晨报。"""
    headers = auth["headers"]
    resp = client.post(
        "/api/reports/generate", headers=headers, json={"push": False, "use_ai": False, "tracking": False, "alerts": False}
    )
    assert resp.status_code == 200, resp.text
    report_id = resp.json()["report_id"]
    detail = client.get(f"/api/reports/{report_id}", headers=headers).json()
    assert detail["content_md"]
    assert detail["meta"]["error"]  # 记录了「AI 配置不完整」


def test_generate_with_mock_ai_full_pipeline(client, auth):
    """完整链路：配置 Mock AI → 生成 → 入库 → 列表 → 详情 → 导出。

    注意：sources 置为 [] 会被后端自动补回默认源（保证新用户开箱有内容），
    因此这里改用一个本地不可达源，让测试不依赖外网、也不受该补齐逻辑影响。
    """
    headers = auth["headers"]
    assert client.put(
        "/api/config",
        headers=headers,
        json={
            "sources": [
                {
                    "name": "测试空源",
                    "type": "rss",
                    "url": "http://127.0.0.1:1/empty.xml",
                    "enabled": True,
                    "priority": 1,
                }
            ],
            "ai_config": {
                "base_url": f"http://127.0.0.1:{MOCK_PORT}/v1",
                "api_key": "sk-mock",
                "model": "mock-model",
            },
        },
    ).status_code == 200

    resp = client.post(
        "/api/reports/generate",
        headers=headers,
        json={"push": False, "tracking": False, "alerts": False},
    )
    assert resp.status_code == 200, resp.text
    report_id = resp.json()["report_id"]

    detail = client.get(f"/api/reports/{report_id}", headers=headers).json()
    assert "Mock AI" in detail["content_md"], detail["content_md"][:200]
    assert detail["title"].startswith("晨析晨报")
    assert detail["content_html"].startswith("<!DOCTYPE html>")
    assert detail["meta"]["model"] == "mock-model"

    listing = client.get("/api/reports", headers=headers).json()
    assert any(r["id"] == report_id for r in listing)


def test_report_search_and_export(client, auth):
    headers = auth["headers"]
    listing = client.get("/api/reports?q=晨报", headers=headers).json()
    assert listing

    rid = listing[0]["id"]
    assert "title" in client.get(f"/api/reports/{rid}", headers=headers).json()
    assert client.get(f"/api/reports/{rid}/preview", headers=headers).status_code == 200

    for fmt in ("md", "html"):
        resp = client.get(f"/api/reports/{rid}/export?fmt={fmt}", headers=headers)
        assert resp.status_code == 200, resp.text
        assert len(resp.content) > 0

    resp = client.get(f"/api/reports/{rid}/export?fmt=pdf", headers=headers)
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_date_filter(client, auth):
    headers = auth["headers"]
    future = "2099-01-01"
    assert client.get(f"/api/reports?date_from={future}", headers=headers).json() == []

def test_report_tts_requires_available_engine(client, auth):
    headers = auth["headers"]
    rid = client.get("/api/reports", headers=headers).json()[0]["id"]
    resp = client.get(f"/api/reports/{rid}/tts", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_push_report_without_channels_returns_400(client, auth):
    headers = auth["headers"]
    runtime = client.get("/api/reports", headers=headers).json()
    rid = runtime[0]["id"]
    resp = client.post(f"/api/reports/{rid}/push", headers=headers)
    assert resp.status_code in (200, 400)


def test_report_not_found(client, auth):
    assert client.get("/api/reports/999999", headers=auth["headers"]).status_code == 404


# =========================================================================== #
# 知识库
# =========================================================================== #
def test_knowledge_openapi_paths(client, auth):
    headers = auth["headers"]
    assert client.get("/api/knowledge/stats", headers=headers).status_code == 200

    client.post("/api/knowledge/ingest?limit=10", headers=headers)
    stats = client.get("/api/knowledge/stats", headers=headers).json()
    assert "chunks" in stats and "by_type" in stats and "providers" in stats

    ask = client.post(
        "/api/knowledge/ask",
        headers=headers,
        json={"question": "最近有哪些值得关注的行业动态？", "top_k": 3},
    )
    assert ask.status_code == 200, ask.text
    assert "answer" in ask.json()

    s = client.post("/api/knowledge/search", headers=headers, json={"query": "晨报", "top_k": 3})
    assert s.status_code == 200
    assert "items" in s.json()

    assert client.post("/api/knowledge/reindex?limit=20", headers=headers).status_code == 200


# =========================================================================== #
# 动态追踪
# =========================================================================== #
def test_competitor_crud_and_scan(client, auth):
    headers = auth["headers"]
    assert client.get("/api/competitors", headers=headers).status_code == 200

    created = client.post(
        "/api/competitors",
        headers=headers,
        json={"name": "测试公司", "type": "company", "keywords": ["测试"], "level": "high"},
    )
    assert created.status_code == 200, created.text
    cid = created.json()["id"]

    # 重名拒绝
    assert client.post(
        "/api/competitors", headers=headers, json={"name": "测试公司"}
    ).status_code == 400

    assert client.get("/api/competitors/compare?days=30", headers=headers).status_code == 200
    assert client.get(f"/api/competitors/{cid}/timeline", headers=headers).status_code == 200

    assert client.post("/api/competitors/scan?limit=20&use_ai=false", headers=headers).status_code == 200

    upd = client.put(
        f"/api/competitors/{cid}",
        headers=headers,
        json={"name": "测试公司", "level": "normal", "enabled": False},
    )
    assert upd.status_code == 200
    assert client.delete(f"/api/competitors/{cid}", headers=headers).status_code == 200


# =========================================================================== #
# 关键词预警
# =========================================================================== #
def test_alert_crud_scan_and_history(client, auth):
    headers = auth["headers"]
    assert client.get("/api/alerts", headers=headers).status_code == 200

    bad = client.post("/api/alerts", headers=headers, json={"keyword": "测试", "match_type": "wat"})
    assert bad.status_code == 400

    created = client.post(
        "/api/alerts",
        headers=headers,
        json={"keyword": "融资", "match_type": "fuzzy", "condition": "always", "cooldown_minutes": 60},
    )
    assert created.status_code == 200, created.text
    aid = created.json()["id"]

    scan = client.post("/api/alerts/scan?limit=20&use_ai=false", headers=headers)
    assert scan.status_code == 200
    assert "fired" in scan.json()

    assert client.get("/api/alerts/history", headers=headers).status_code == 200

    upd = client.put(
        f"/api/alerts/{aid}",
        headers=headers,
        json={"keyword": "融资", "condition": "frequency", "condition_value": 2},
    )
    assert upd.status_code == 200
    assert client.delete(f"/api/alerts/{aid}", headers=headers).status_code == 200


# =========================================================================== #
# 周报 / 月报
# =========================================================================== #
def test_periodical_generate_export_delete(client, auth):
    headers = auth["headers"]
    assert client.get("/api/periodicals", headers=headers).status_code == 200

    bad = client.post("/api/periodicals/generate", headers=headers, json={"period_type": "yearly"})
    assert bad.status_code == 400

    gen = client.post(
        "/api/periodicals/generate",
        headers=headers,
        json={"period_type": "weekly", "push": False},
    )
    assert gen.status_code == 200, gen.text
    pid = gen.json()["id"]

    detail = client.get(f"/api/periodicals/{pid}", headers=headers).json()
    assert detail["content_md"]
    assert detail["period_type"] == "weekly"

    assert client.get(f"/api/periodicals/{pid}/preview", headers=headers).status_code == 200
    exp = client.get(f"/api/periodicals/{pid}/export?fmt=md", headers=headers)
    assert exp.status_code == 200

    assert client.get("/api/periodicals?period_type=weekly", headers=headers).status_code == 200
    assert client.delete(f"/api/periodicals/{pid}", headers=headers).status_code == 200


# =========================================================================== #
# 插件
# =========================================================================== #
def test_plugins_discovered_and_toggleable(client, auth):
    headers = auth["headers"]
    data = client.get("/api/plugins", headers=headers).json()
    assert "plugins" in data and "root" in data
    names = {p["name"] for p in data["plugins"]}
    assert {"source-example", "push-example", "ai-example"} <= names

    sample = next(p for p in data["plugins"] if p["name"] == "source-example")
    assert sample["type"] == "source"
    assert sample["valid"] is True

    on = client.post(f"/api/plugins/{sample['id']}/enable", headers=headers, json={"enabled": True})
    assert on.status_code == 200 and on.json()["enabled"] is True

    off = client.post(f"/api/plugins/{sample['id']}/enable", headers=headers, json={"enabled": False})
    assert off.status_code == 200 and off.json()["enabled"] is False


def test_plugin_marketplace(client, auth):
    data = client.get("/api/plugins/marketplace/catalog", headers=auth["headers"]).json()
    assert len(data["items"]) >= 3
    assert all("slug" in it and "type" in it for it in data["items"])


# =========================================================================== #
# 管理后台
# =========================================================================== #
def test_admin_stats_and_jobs(client, auth):
    headers = auth["headers"]
    stats = client.get("/api/admin/stats", headers=headers).json()
    for key in ("users", "reports", "articles", "knowledge_chunks", "push_logs", "llm_calls"):
        assert key in stats

    jobs = client.get("/api/admin/jobs", headers=headers)
    assert jobs.status_code == 200
    assert isinstance(jobs.json()["jobs"], list)

    assert client.get("/api/admin/users", headers=headers).status_code == 200
    log = client.get("/api/admin/push-logs?limit=10", headers=headers)
    assert log.status_code == 200 and isinstance(log.json(), list)
    assert client.get("/api/admin/usage?days=30", headers=headers).status_code == 200


def test_admin_requires_admin_role(client, auth, other):
    assert client.get("/api/admin/stats", headers=other["headers"]).status_code == 403
    assert client.post("/api/plugins/sync", headers=other["headers"]).status_code == 403


def test_admin_cannot_remove_last_admin(client, auth):
    me = client.get("/api/admin/users", headers=auth["headers"]).json()[0]
    resp = client.put(
        f"/api/admin/users/{me['id']}", headers=auth["headers"], json={"role": "user"}
    )
    assert resp.status_code == 400


# =========================================================================== #
# 多用户隔离
# =========================================================================== #
def test_multi_user_isolation(client, auth, other):
    assert other["user"]["role"] == "user"

    # 新用户看不到别人的晨报
    assert client.get("/api/reports", headers=other["headers"]).json() == []

    owner_reports = client.get("/api/reports", headers=auth["headers"]).json()
    foreign_id = owner_reports[0]["id"]
    assert client.get(f"/api/reports/{foreign_id}", headers=other["headers"]).status_code == 404
    assert client.get(f"/api/periodicals/1", headers=other["headers"]).status_code == 404

    # 配置互不影响
    other_cfg = client.get("/api/config", headers=other["headers"]).json()
    owner_cfg = client.get("/api/config", headers=auth["headers"]).json()
    assert other_cfg["template"] != owner_cfg["template"]


# =========================================================================== #
# 微信排版（wechat_style）
# =========================================================================== #
def test_wechat_wecom_chunks_respect_byte_limit():
    """企业微信机器人单条上限 4096 字节（UTF-8），切块必须按字节且不切断条目。"""
    from app.push.wechat_style import format_wecom

    md = "# 2026-10-01 晨报\n\n## 今日要点\n" + "\n".join(
        f"- [标题{i}](https://example.com/{i})（来源{i}）：这是一条比较长的摘要内容，用于撑大字节数。" * 2
        for i in range(30)
    )
    msgs = format_wecom(md, "2026-10-01 晨报")
    assert len(msgs) > 1
    for m in msgs:
        assert len(m.encode("utf-8")) <= 3800
    # 栏目头使用 warning 橙色
    assert '<font color="warning">▎今日要点</font>' in msgs[0]


def test_wechat_card_html_brand_style():
    """公众号卡片风 HTML：品牌橙/蓝、inline style、来源标签。"""
    from app.push.wechat_style import render_wechat_card_html

    md = ("# 2026-10-01 行业分析晨报\n\n## 今日要点\n"
          "1. 第一点结论\n\n## 其他动态\n"
          "- [某标题](https://example.com/a)（第一财经）：摘要文字")
    html = render_wechat_card_html(md)
    assert "#F6A821" in html and "#2B9CD8" in html
    assert 'href="https://example.com/a"' in html
    assert "第一财经" in html
    assert "<html" not in html  # 片段式输出，可直接内嵌
    # 无新动态弱化
    html2 = render_wechat_card_html("# t\n\n## 行业动态\n（无新动态）")
    assert "（无新动态）" in html2


def test_wechat_wecom_report_push_channel_registered():
    """wecom 渠道存在且 send 引用了新排版。"""
    from app.push.base import CHANNEL_MAP

    spec = CHANNEL_MAP.get("wecom")
    assert spec is not None
    import inspect

    src = inspect.getsource(spec.send)
    assert "format_wecom" in src


# =========================================================================== #
# 关注点补齐（老配置只存了部分项时自动补回内置清单）
# =========================================================================== #
def test_merge_focus_points_upgrades_legacy_subset():
    """早期保存的配置只有 3 条无 id 的项 → 读取时应补齐全部内置关注点。"""
    from app.ai.catalog import BUILTIN_FOCUS_POINTS, merge_focus_points

    legacy = [
        {"name": "行业动态", "description": "行业层面的动态"},
        {"name": "融资事件"},
        {"name": "政策监管", "enabled": False},
    ]
    merged = merge_focus_points(legacy)
    names = [f["name"] for f in merged]
    # 8 个内置项全部在场（融资事件/政策监管被升级，其余 6 个补齐）
    for b in BUILTIN_FOCUS_POINTS:
        assert b["name"] in names
    # 老的自定义项保留
    assert "行业动态" in names
    # 命中内置的项拿到 id 与 builtin 标记；用户的 enabled 覆盖被保留
    by_name = {f["name"]: f for f in merged}
    assert by_name["融资事件"]["id"] == "funding"
    assert by_name["融资事件"]["builtin"] is True
    assert by_name["政策监管"]["enabled"] is False
    assert by_name["技术突破"]["ai_hint"]  # 补齐项带完整 AI 提示


def test_merge_focus_points_keeps_user_edits():
    """用户改过的 ai_hint / enabled 不被补齐逻辑覆盖。"""
    from app.ai.catalog import merge_focus_points

    edited = [
        {"id": "tech", "name": "技术突破", "enabled": True, "ai_hint": "只看大模型"},
    ]
    merged = merge_focus_points(edited)
    tech = next(f for f in merged if f["id"] == "tech")
    assert tech["ai_hint"] == "只看大模型"
    assert len(merged) == len({f["name"] for f in merged})  # 无重复


def test_get_config_backfills_focus_points(client, auth):
    """GET /api/config 会把老配置的关注点补齐并持久化。"""
    from app.ai.catalog import BUILTIN_FOCUS_POINTS

    data = client.get("/api/config", headers=auth["headers"]).json()
    names = {f["name"] for f in data["focus_points"]}
    for b in BUILTIN_FOCUS_POINTS:
        assert b["name"] in names
