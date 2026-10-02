# -*- coding: utf-8 -*-
"""本地演示数据准备脚本（仅供开发/截图验证使用，不会进入产品交付）。

用法：
    python scripts/seed_demo.py

做什么：
1. 注册（或复用）演示账号 demo@example.com（与 backend/scripts/seed_demo.py 保持一致）
2. 为演示账号配置 AI（若本机数据库中已存在可用的 ai_config，则直接复用其 base_url/model，
   API Key 留空则走「素材版」兜底；如需真实 AI 生成，请在设置页填写自己的 Key）
3. 添加 2 个动态追踪对象、2 条关键词预警
4. 触发一次晨报生成与一次预警扫描
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000/api")
EMAIL = os.environ.get("DEMO_EMAIL", "demo@example.com")
PASSWORD = os.environ.get("DEMO_PASSWORD", "demo1234")
NAME = "Demo"


def call(method: str, path: str, token: str | None = None, body: dict | None = None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def main() -> int:
    status, register = call("POST", "/auth/register", body={
        "email": EMAIL, "password": PASSWORD, "display_name": NAME,
    })
    if status == 400:  # 已存在则直接登录
        status, register = call("POST", "/auth/login", body={"email": EMAIL, "password": PASSWORD})
    if status != 200:
        print("注册/登录失败:", status, register)
        return 1
    token = register.get("access_token") or register.get("token")
    print("登录 OK")

    # 动态追踪对象
    call("POST", "/competitors", token=token, body={
        "name": "DeepSeek", "kind": "company", "level": "core",
        "keywords": ["DeepSeek", "深度求索"], "note": "大模型厂商",
    })
    call("POST", "/competitors", token=token, body={
        "name": "智谱 GLM", "kind": "company", "level": "watch",
        "keywords": ["智谱", "GLM"], "note": "大模型厂商",
    })
    print("动态追踪 OK")

    # 关键词预警（字段以 OpenAPI 的 AlertIn 为准：keyword 必填，condition 取值 always 等）
    call("POST", "/alerts", token=token, body={
        "keyword": "开源", "match_type": "fuzzy", "condition": "always",
        "condition_value": 1, "cooldown_minutes": 1440, "channels": ["email"],
    })
    call("POST", "/alerts", token=token, body={
        "keyword": "融资", "match_type": "fuzzy", "condition": "always",
        "condition_value": 1, "cooldown_minutes": 1440, "channels": ["email"],
    })
    print("预警 OK")

    # 触发预警扫描 + 晨报生成
    status, res = call("POST", "/alerts/scan", token=token)
    print("预警扫描:", status, json.dumps(res, ensure_ascii=False)[:200])
    status, res = call("POST", "/reports/generate", token=token, body={"use_ai": True})
    print("晨报生成:", status, json.dumps(res, ensure_ascii=False)[:400])
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
