"""三级去重：URL 精确 → 标题哈希 → 内容相似度。"""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Article
from ..utils.text import content_hash, is_duplicate, normalize, title_hash

DEFAULT_SIM_THRESHOLD = 0.82


class DedupIndex:
    """内存去重索引：装载近期已有条目 + 本轮已接受条目，逐条判定。"""

    def __init__(self, threshold: float = DEFAULT_SIM_THRESHOLD, fuzzy_window: int = 400):
        self.threshold = threshold
        self.fuzzy_window = fuzzy_window
        self.urls: set[str] = set()
        self.title_hashes: set[str] = set()
        self.content_hashes: set[str] = set()
        self._recent: list[tuple[str, str]] = []  # (normalized_title, normalized_text)

    def load(self, rows: list[Article]) -> "DedupIndex":
        for a in rows:
            self.urls.add(a.url)
            self.title_hashes.add(a.title_hash or title_hash(a.title))
            if a.content_hash:
                self.content_hashes.add(a.content_hash)
            self._push(a.title, f"{a.title} {a.summary or ''}")
        return self

    def _push(self, title: str, text: str) -> None:
        self._recent.append((normalize(title), normalize(text)))
        if len(self._recent) > self.fuzzy_window:
            self._recent = self._recent[-self.fuzzy_window :]

    def check(self, item: dict) -> str:
        """返回重复原因，未重复返回空串。"""
        url = item.get("url") or ""
        if url and url in self.urls:
            return "url"
        th = item.get("title_hash") or title_hash(item.get("title") or "")
        if th in self.title_hashes:
            return "title_hash"
        ch = item.get("content_hash") or content_hash(f"{item.get('title','')}\n{item.get('summary','')}")
        if ch in self.content_hashes:
            return "content_hash"

        norm_title = normalize(item.get("title") or "")
        if len(norm_title) >= 8:
            text = f"{item.get('title','')} {item.get('summary','')}"
            for prev_title, prev_text in reversed(self._recent[-120:]):
                if is_duplicate(norm_title, prev_title, self.threshold):
                    return "title_similar"
                if len(text) > 60 and is_duplicate(text, prev_text, self.threshold + 0.04):
                    return "content_similar"
        return ""

    def accept(self, item: dict) -> bool:
        if self.check(item):
            return False
        self.urls.add(item.get("url") or "")
        self.title_hashes.add(item.get("title_hash") or title_hash(item.get("title") or ""))
        self.content_hashes.add(
            item.get("content_hash") or content_hash(f"{item.get('title','')}\n{item.get('summary','')}")
        )
        self._push(item.get("title") or "", f"{item.get('title','')} {item.get('summary','')}")
        return True


def load_index(db: Session, user_id: int, hours: int = 168) -> DedupIndex:
    """装载近 N 小时（默认 7 天）的文章作为去重基线。"""
    from .core import now_utc

    cutoff = now_utc() - timedelta(hours=max(hours, 1))
    rows = db.scalars(
        select(Article)
        .where(Article.user_id == user_id, Article.fetched_at >= cutoff)
        .order_by(Article.fetched_at.desc())
        .limit(2000)
    ).all()
    if not rows:  # 时间窗内无数据时退化为全量（老库首启场景）
        rows = db.scalars(
            select(Article).where(Article.user_id == user_id).order_by(Article.id.desc()).limit(1000)
        ).all()
    return DedupIndex().load(list(rows))
