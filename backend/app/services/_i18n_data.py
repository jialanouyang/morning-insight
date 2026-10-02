"""后端多语言词条表（zh / en）。"""

SUPPORTED_LANGUAGES = ["zh", "en"]

MESSAGES: dict[str, dict[str, str]] = {
    # 语言名
    "lang.zh": {"zh": "简体中文", "en": "Simplified Chinese"},
    "lang.en": {"zh": "英文", "en": "English"},
    "lang.bilingual": {"zh": "中英双语", "en": "Chinese + English"},

    # 通用
    "common.ok": {"zh": "操作成功", "en": "Success"},
    "common.not_found": {"zh": "资源不存在", "en": "Not found"},
    "common.unauthorized": {"zh": "未登录或凭证已失效", "en": "Not signed in or session expired"},
    "common.forbidden": {"zh": "没有权限执行该操作", "en": "Permission denied"},
    "common.bad_request": {"zh": "请求参数有误", "en": "Invalid request"},

    # 认证
    "auth.email_exists": {"zh": "该邮箱已注册", "en": "Email already registered"},
    "auth.bad_credentials": {"zh": "邮箱或密码错误", "en": "Incorrect email or password"},
    "auth.registered": {"zh": "注册成功", "en": "Registered"},
    "auth.last_admin": {"zh": "不能删除最后一个管理员", "en": "Cannot remove the last admin"},

    # 晨报
    "report.generating": {"zh": "正在生成晨报…", "en": "Generating report…"},
    "report.no_material": {"zh": "本轮没有抓取到新素材", "en": "No new material fetched this round"},
    "report.ai_incomplete": {"zh": "AI 配置不完整", "en": "AI configuration is incomplete"},
    "report.not_found": {"zh": "晨报不存在", "en": "Report not found"},

    # 推送
    "push.sent": {"zh": "已推送", "en": "Sent"},
    "push.failed": {"zh": "推送失败", "en": "Push failed"},
    "push.no_channel": {"zh": "未启用任何推送渠道", "en": "No push channel enabled"},

    # 知识库
    "knowledge.empty": {"zh": "知识库中还没有相关内容", "en": "Nothing relevant in the knowledge base"},
    "knowledge.reindexed": {"zh": "索引重建完成", "en": "Reindex finished"},

    # 预警 / 追踪 / 周月报
    "alert.triggered": {"zh": "关键词预警已触发", "en": "Keyword alert triggered"},
    "tracking.section": {"zh": "动态追踪", "en": "Tracking"},
    "periodical.weekly": {"zh": "周报", "en": "Weekly"},
    "periodical.monthly": {"zh": "月报", "en": "Monthly"},
    "tts.ready": {"zh": "语音晨报已生成", "en": "Audio report generated"},
}
