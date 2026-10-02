"""抓取层公共设施：HTTP 客户端、请求头、时间解析、条目归一化。"""
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx

from ..utils.text import content_hash, strip_html, title_hash, truncate

logger = logging.getLogger("morning_insight.fetcher")

FETCH_TIMEOUT = 20.0
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
HEADERS = {
    # 部分源会拦截无 UA 的请求，这里伪装为常见浏览器并附带产品标识
    "User-Agent": f"{BROWSER_UA} MorningInsight/0.2 (+https://github.com/morning-insight)",
    "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def http_get(url: str, *, headers: dict | None = None, params: dict | None = None, timeout: float = FETCH_TIMEOUT) -> httpx.Response:
    merged = dict(HEADERS)
    if headers:
        merged.update({k: v for k, v in headers.items() if v})
    try:
        resp = httpx.get(url, headers=merged, params=params, timeout=timeout, follow_redirects=True)
    except httpx.ProxyError:
        # 部分环境（系统代理/企业网关）会对个别站点返回 502，
        # 此时绕过代理直连重试一次，避免整个源直接失败
        logger.info("代理请求失败，尝试直连：%s", url)
        resp = httpx.get(url, headers=merged, params=params, timeout=timeout,
                         follow_redirects=True, trust_env=False)
    resp.raise_for_status()
    return resp


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# 中文站点常见日期写法：2026/07/31、2026.07.31、2026年7月31日、2026-7-31 10:30
_DATE_YMD_RE = re.compile(
    r"(\d{4})\s*[年./\-]\s*(\d{1,2})\s*[月./\-]\s*(\d{1,2})\s*日?"
    r"(?:\s*(\d{1,2})\s*[:：]\s*(\d{2})(?:\s*[:：]\s*(\d{2}))?)?"
)
# 无年份：07-31 / 7月31日 / 07/31
_DATE_MD_RE = re.compile(r"^(\d{1,2})\s*[月./\-]\s*(\d{1,2})\s*日?$")
# 相对时间：刚刚 / 3分钟前 / 2小时前 / 5天前 / 昨天 23:50 / 今天 08:30
_REL_MIN_RE = re.compile(r"(\d+)\s*分钟前")
_REL_HOUR_RE = re.compile(r"(\d+)\s*小时前")
_REL_DAY_RE = re.compile(r"(\d+)\s*天前")
_REL_CLOCK_RE = re.compile(r"(昨天|今天|今日|昨)\s*(\d{1,2})\s*[:：]\s*(\d{2})")


def _parse_relative_time(text: str) -> datetime | None:
    """解析中文相对时间（列表页常见），相对当前时间换算。"""
    text = (text or "").strip()
    if not text:
        return None
    now = now_utc()
    if "刚刚" in text or "刚才" in text or "秒前" in text:
        return now
    m = _REL_MIN_RE.search(text)
    if m:
        return now - timedelta(minutes=int(m.group(1)))
    m = _REL_HOUR_RE.search(text)
    if m:
        return now - timedelta(hours=int(m.group(1)))
    m = _REL_DAY_RE.search(text)
    if m:
        return now - timedelta(days=int(m.group(1)))
    m = _REL_CLOCK_RE.search(text)
    if m:
        day = now
        if m.group(1) in ("昨天", "昨"):
            day = now - timedelta(days=1)
        try:
            return day.replace(hour=int(m.group(2)), minute=int(m.group(3)),
                               second=0, microsecond=0)
        except ValueError:
            return None
    return None


# 链接里内嵌的日期（新华社 /20260929/、人民日报 /2026/1001/、财新 /2026-08-21/）
_URL_DATE_SEP_RE = re.compile(r"(?<!\d)(20\d{2})[-/](\d{1,2})[-/](\d{1,2})(?!\d)")
# 年 / 月日 连写：/2026/1001/
_URL_DATE_YMMDD_RE = re.compile(r"(?<!\d)(20\d{2})/(\d{2})(\d{2})(?!\d)")
_URL_DIGITS_RE = re.compile(r"\d{8,}")


def parse_date_from_url(url: str) -> datetime | None:
    """从链接中提取日期（很多站点只把日期放进 URL，列表页不给时间元素）。

    支持三种写法：
    - 带分隔符：/2026/10/01/、/2026-08-21/
    - 年/月日连写：/2026/1001/
    - 纯数字串：/20260929/、t20260731_xxx.html、/20260929171535.../（前 8 位为日期）
    """
    url = (url or "").strip()
    if not url:
        return None
    for m in _URL_DATE_SEP_RE.finditer(url):
        dt = _safe_date(*(int(g) for g in m.groups()))
        if dt is not None:
            return dt
    for m in _URL_DATE_YMMDD_RE.finditer(url):
        dt = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if dt is not None:
            return dt
    for m in _URL_DIGITS_RE.finditer(url):
        digits = m.group(0)
        dt = _safe_date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        if dt is not None:
            return dt
    return None


def _safe_date(year: int, month: int, day: int) -> datetime | None:
    if not (2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31):
        return None
    try:
        return datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_numeric_date(text: str) -> datetime | None:
    """解析数字型日期串（政府站点居多），无法识别时返回 None。

    支持：2026/07/31、2026.07.31、2026年7月31日、20260731、
    以及带时间的 2026/07/31 10:30:00；无年份的「7月31日」按当年推断。
    """
    text = (text or "").strip()
    if not text:
        return None
    has_year = True
    hour = minute = second = 0
    if re.fullmatch(r"\d{8}", text):
        year, month, day = int(text[:4]), int(text[4:6]), int(text[6:8])
    else:
        m = _DATE_YMD_RE.search(text)
        if m:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            hour = int(m.group(4) or 0)
            minute = int(m.group(5) or 0)
            second = int(m.group(6) or 0)
        else:
            m2 = _DATE_MD_RE.match(text)
            if not m2:
                return None
            has_year = False
            year = now_utc().year
            month, day = int(m2.group(1)), int(m2.group(2))
    if not (1 <= month <= 12 and 1 <= day <= 31 and 0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    try:
        dt = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    except ValueError:
        return None
    if not has_year and dt > now_utc() + timedelta(days=1):
        # 「12月31日」类写法在年初出现，实为去年
        try:
            dt = dt.replace(year=year - 1)
        except ValueError:
            return None
    return dt


def parse_datetime(value) -> datetime | None:
    """解析多种时间格式：struct_time / RFC822 / ISO8601 / 中文数字日期 / Unix 时间戳。

    注意：**解析失败返回 None**，调用方（时间窗过滤）应把 None 视为「该源未提供
    可信时间」而放行；因此这里要尽量覆盖真实站点的写法，否则旧文会漏进素材库。
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        # Unix 时间戳：10 位为秒、13 位为毫秒
        ts = float(value)
        if value >= 10**12:
            ts /= 1000
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, (tuple, list)) and len(value) >= 6:
        try:
            return datetime(*value[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        # 纯数字时间戳：10 位为秒、13 位为毫秒（如澎湃/36氪接口）
        if text.isdigit() and len(text) in (9, 10, 12, 13):
            ts = int(text)
            if len(text) in (12, 13):
                ts /= 1000
            try:
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                return None
        try:
            dt = parsedate_to_datetime(text)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(text.replace("Z", "+0000") if fmt.endswith("%z") else text, fmt)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        # 中文相对时间：刚刚 / 3分钟前 / 昨天 23:50
        rel = _parse_relative_time(text)
        if rel is not None:
            return rel
        # 中文站点数字日期：2026/07/31、2026.07.31、2026年7月31日、20260731
        return _parse_numeric_date(text)
    return None


def make_item(
    *,
    title: str,
    url: str,
    source: str,
    summary: str = "",
    published_at: str = "",
    raw_content: str = "",
    source_meta: dict | None = None,
) -> dict | None:
    """归一化一条抓取结果；缺标题或缺链接的条目丢弃。"""
    title = strip_html(title or "").strip()
    url = (url or "").strip()
    if not title or not url or not url.lower().startswith(("http://", "https://")):
        return None
    summary = truncate(strip_html(summary or ""), 800)
    raw = truncate(strip_html(raw_content or ""), 20000)
    meta = source_meta or {}
    tags = meta.get("tags") or {}
    return {
        "title": title[:500],
        "url": url[:1000],
        "source": (source or "")[:200],
        "summary": summary,
        "raw_content": raw,
        "published_at": (published_at or "")[:50],
        "language": tags.get("language") or meta.get("language") or "",
        "region": tags.get("region") or meta.get("region") or "",
        "category": meta.get("category") or "",
        "priority": int(meta.get("priority") or 0),
        "title_hash": title_hash(title),
        "content_hash": content_hash(f"{title}\n{summary}"),
    }


def sort_by_priority(items: list[dict]) -> list[dict]:
    """高优先级源的文章排在前面。"""
    return sorted(items, key=lambda x: -int(x.get("priority") or 0))
