"""In-memory community score browsing and interaction helpers."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable
from uuid import uuid4


COMMUNITY_TZ = timezone(timedelta(hours=8))
COMMUNITY_SCORES: dict[str, dict[str, Any]] = {}
COMMUNITY_COMMENTS: dict[str, list[dict[str, Any]]] = {}
COMMUNITY_LIKES: dict[str, set[str]] = {}
COMMUNITY_FAVORITES: dict[str, set[str]] = {}

COMMUNITY_TAGS = ["精选", "流行", "古典", "爵士", "ACG", "指弹吉他"]
DEFAULT_AUTHOR = "社区用户"


def _now() -> datetime:
    return datetime.now(COMMUNITY_TZ)


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds")


def _compact_count(value: int) -> str:
    if value >= 10000:
        return f"{value / 10000:.1f}w"
    if value >= 1000:
        return f"{value / 1000:.1f}k"
    return str(value)


def _format_price(price: float) -> str:
    return "免费" if price <= 0 else f"¥{price:.2f}"


def _relative_time(timestamp: str) -> str:
    created_at = datetime.fromisoformat(timestamp)
    delta = _now() - created_at
    if delta < timedelta(minutes=1):
        return "刚刚"
    if delta < timedelta(hours=1):
        return f"{max(int(delta.total_seconds() // 60), 1)}分钟前"
    if delta < timedelta(days=1):
        return f"{int(delta.total_seconds() // 3600)}小时前"
    if delta < timedelta(days=2):
        return "昨天"
    return created_at.strftime("%m-%d")


def _dedupe_tags(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if normalized and normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)
    return deduped


def _default_subtitle(entry: dict[str, Any]) -> str:
    author = str(entry.get("author") or DEFAULT_AUTHOR)
    instrument = str(entry.get("instrument") or entry.get("style") or "乐谱")
    return f"{author} · {instrument}"


def _seed_score(entry: dict[str, Any], comments: list[dict[str, Any]]) -> None:
    score_id = str(entry["score_id"])
    COMMUNITY_SCORES[score_id] = deepcopy(entry)
    COMMUNITY_COMMENTS[score_id] = deepcopy(comments)
    COMMUNITY_LIKES.setdefault(score_id, set())
    COMMUNITY_FAVORITES.setdefault(score_id, set())


def _ensure_seeded() -> None:
    if COMMUNITY_SCORES:
        return

    _seed_score(
        {
            "community_score_id": "cmt_score_qt",
            "score_id": "score_qt",
            "title": "晴天",
            "author": "周杰伦",
            "subtitle": "周杰伦 · 钢琴版",
            "description": "适合中级演奏者的流行钢琴改编版，包含前奏与副歌段落。",
            "style": "流行",
            "instrument": "钢琴版",
            "price": 6.0,
            "cover_url": "https://api.dicebear.com/7.x/initials/svg?seed=QT",
            "downloads": 1200,
            "likes_base": 86,
            "favorites_base": 24,
            "tags": ["精选", "流行", "钢琴"],
            "is_public": True,
            "published_at": "2026-04-09T11:20:00+08:00",
            "source_file_name": "sunny-day.pdf",
            "download_url": "/api/v1/community/scores/score_qt/download",
        },
        [
            {
                "comment_id": "c_qt_1",
                "username": "路德维希",
                "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Ludwig",
                "content": "这首谱子转调处理得非常巧妙，值得学习！",
                "created_at": "2026-04-13T18:10:00+08:00",
            },
            {
                "comment_id": "c_qt_2",
                "username": "琴心剑胆",
                "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Piano",
                "content": "感谢分享，找了好久这个版本的钢琴谱。",
                "created_at": "2026-04-12T12:00:00+08:00",
            },
        ],
    )
    _seed_score(
        {
            "community_score_id": "cmt_score_bach",
            "score_id": "score_bach",
            "title": "G线上的咏叹调",
            "author": "巴赫",
            "subtitle": "巴赫 · 小提琴",
            "description": "适合弦乐与钢琴伴奏的古典社区版本，免费开放下载。",
            "style": "古典",
            "instrument": "小提琴",
            "price": 0.0,
            "cover_url": "https://api.dicebear.com/7.x/initials/svg?seed=Bach",
            "downloads": 856,
            "likes_base": 42,
            "favorites_base": 18,
            "tags": ["精选", "古典", "小提琴"],
            "is_public": True,
            "published_at": "2026-04-10T09:00:00+08:00",
            "source_file_name": "bach-air.pdf",
            "download_url": "/api/v1/community/scores/score_bach/download",
        },
        [],
    )
    _seed_score(
        {
            "community_score_id": "cmt_score_nxy",
            "score_id": "score_nxy",
            "title": "那些年",
            "author": "胡夏",
            "subtitle": "胡夏 · 简易钢琴",
            "description": "保留主旋律的简易版谱面，适合入门演奏者练习。",
            "style": "流行",
            "instrument": "简易钢琴",
            "price": 5.0,
            "cover_url": "https://api.dicebear.com/7.x/initials/svg?seed=TY",
            "downloads": 2300,
            "likes_base": 120,
            "favorites_base": 63,
            "tags": ["流行", "钢琴"],
            "is_public": True,
            "published_at": "2026-04-08T20:30:00+08:00",
            "source_file_name": "those-years.pdf",
            "download_url": "/api/v1/community/scores/score_nxy/download",
        },
        [],
    )
    _seed_score(
        {
            "community_score_id": "cmt_score_dream",
            "score_id": "score_dream",
            "title": "梦中的婚礼",
            "author": "理查德",
            "subtitle": "理查德 · 钢琴经典",
            "description": "社区高热度钢琴经典版本，保留了常见装饰音写法。",
            "style": "古典",
            "instrument": "钢琴经典",
            "price": 8.0,
            "cover_url": "https://api.dicebear.com/7.x/initials/svg?seed=Dream",
            "downloads": 4100,
            "likes_base": 205,
            "favorites_base": 88,
            "tags": ["精选", "古典", "钢琴"],
            "is_public": True,
            "published_at": "2026-04-07T16:45:00+08:00",
            "source_file_name": "dream-wedding.pdf",
            "download_url": "/api/v1/community/scores/score_dream/download",
        },
        [],
    )
    _seed_score(
        {
            "community_score_id": "cmt_score_croatia",
            "score_id": "score_croatia",
            "title": "克罗地亚狂想曲",
            "author": "理查德",
            "subtitle": "理查德 · 钢琴经典",
            "description": "节奏密集的演奏级版本，适合进阶演奏者挑战。",
            "style": "古典",
            "instrument": "钢琴经典",
            "price": 6.5,
            "cover_url": "https://api.dicebear.com/7.x/initials/svg?seed=Croatia",
            "downloads": 3800,
            "likes_base": 188,
            "favorites_base": 74,
            "tags": ["古典", "钢琴"],
            "is_public": True,
            "published_at": "2026-04-06T13:10:00+08:00",
            "source_file_name": "croatia-rhapsody.pdf",
            "download_url": "/api/v1/community/scores/score_croatia/download",
        },
        [],
    )
    _seed_score(
        {
            "community_score_id": "cmt_score_1001",
            "score_id": "score_1001",
            "title": "夜曲",
            "author": "user_01",
            "subtitle": "user_01 · 钢琴改编",
            "description": "根据音频自动扒谱后整理的社区共享版本。",
            "style": "流行",
            "instrument": "钢琴改编",
            "price": 0.0,
            "cover_url": "https://api.dicebear.com/7.x/initials/svg?seed=Nocturne",
            "downloads": 980,
            "likes_base": 56,
            "favorites_base": 24,
            "tags": ["流行", "钢琴"],
            "is_public": True,
            "published_at": "2026-04-11T10:30:00+08:00",
            "source_file_name": "nocturne.pdf",
            "download_url": "/api/v1/community/scores/score_1001/download",
        },
        [],
    )


def _get_score(score_id: str) -> dict[str, Any]:
    _ensure_seeded()
    if score_id not in COMMUNITY_SCORES:
        raise KeyError(f"community score {score_id} not found")
    return COMMUNITY_SCORES[score_id]


def _viewer_id(current_user: dict[str, Any] | None) -> str:
    if current_user and current_user.get("user_id"):
        return str(current_user["user_id"])
    return "guest"


def _serialize_comment(comment: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(comment)
    payload["relative_time"] = _relative_time(payload["created_at"])
    return payload


def _serialize_score(entry: dict[str, Any], current_user: dict[str, Any] | None = None) -> dict[str, Any]:
    score_id = str(entry["score_id"])
    viewer_id = _viewer_id(current_user)
    likes = int(entry.get("likes_base", 0)) + len(COMMUNITY_LIKES.get(score_id, set()))
    favorites = int(entry.get("favorites_base", 0)) + len(COMMUNITY_FAVORITES.get(score_id, set()))
    downloads = int(entry.get("downloads", 0))
    comments = COMMUNITY_COMMENTS.get(score_id, [])
    payload = deepcopy(entry)
    payload["subtitle"] = payload.get("subtitle") or _default_subtitle(payload)
    payload["price_label"] = _format_price(float(payload.get("price", 0.0)))
    payload["downloads"] = downloads
    payload["download_count_display"] = _compact_count(downloads)
    payload["likes"] = likes
    payload["favorites"] = favorites
    payload["comments_count"] = len(comments)
    payload["liked"] = viewer_id in COMMUNITY_LIKES.get(score_id, set())
    payload["favorited"] = viewer_id in COMMUNITY_FAVORITES.get(score_id, set())
    payload["download_url"] = payload.get("download_url") or f"/api/v1/community/scores/{score_id}/download"
    return payload


def list_community_scores(
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    tag: str | None = None,
    current_user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ensure_seeded()
    normalized_keyword = (keyword or "").strip().lower()
    normalized_tag = (tag or "").strip()

    items = [entry for entry in COMMUNITY_SCORES.values() if entry.get("is_public", True)]
    if normalized_keyword:
        items = [
            entry
            for entry in items
            if normalized_keyword in " ".join(
                [
                    str(entry.get("title", "")),
                    str(entry.get("author", "")),
                    str(entry.get("description", "")),
                    str(entry.get("style", "")),
                    str(entry.get("instrument", "")),
                    " ".join(entry.get("tags", [])),
                ]
            ).lower()
        ]
    if normalized_tag:
        items = [
            entry
            for entry in items
            if normalized_tag == entry.get("style")
            or normalized_tag == entry.get("instrument")
            or normalized_tag in entry.get("tags", [])
        ]

    items.sort(
        key=lambda entry: (
            "精选" in entry.get("tags", []),
            entry.get("downloads", 0),
            entry.get("likes_base", 0),
            entry.get("published_at", ""),
        ),
        reverse=True,
    )

    total = len(items)
    start = (page - 1) * page_size
    paged = items[start : start + page_size]
    return {
        "total": total,
        "items": [_serialize_score(entry, current_user=current_user) for entry in paged],
        "page": page,
        "page_size": page_size,
        "has_more": start + page_size < total,
        "filters": {
            "keyword": keyword,
            "tag": tag,
            "available_tags": COMMUNITY_TAGS,
        },
    }


def get_community_score_detail(score_id: str, current_user: dict[str, Any] | None = None) -> dict[str, Any]:
    entry = _get_score(score_id)
    return {
        "score": _serialize_score(entry, current_user=current_user),
        "comments": [_serialize_comment(comment) for comment in COMMUNITY_COMMENTS.get(score_id, [])[:20]],
    }


def list_community_tags() -> dict[str, Any]:
    _ensure_seeded()
    items = []
    for tag in COMMUNITY_TAGS:
        count = len(
            [
                entry
                for entry in COMMUNITY_SCORES.values()
                if tag == entry.get("style") or tag == entry.get("instrument") or tag in entry.get("tags", [])
            ]
        )
        items.append({"name": tag, "count": count})
    return {"items": items}


def publish_community_score(payload: dict[str, Any], current_user: dict[str, Any] | None = None) -> dict[str, Any]:
    _ensure_seeded()
    score_id = str(payload.get("score_id") or f"score_{uuid4().hex[:8]}")
    now = _now_iso()
    existing = deepcopy(COMMUNITY_SCORES.get(score_id, {}))

    style = str(payload.get("style") or (payload.get("tags") or ["精选"])[0] or "精选")
    instrument = str(payload.get("instrument") or "乐谱")
    author = str(payload.get("author_name") or (current_user or {}).get("username") or DEFAULT_AUTHOR)
    price = float(payload.get("price") or 0.0)
    tags = _dedupe_tags([style, instrument, *(payload.get("tags") or [])])

    entry = {
        "community_score_id": existing.get("community_score_id") or f"cmt_{score_id}",
        "score_id": score_id,
        "title": str(payload.get("title") or existing.get("title") or "未命名作品"),
        "author": author,
        "subtitle": str(payload.get("subtitle") or f"{author} · {instrument}"),
        "description": str(payload.get("description") or existing.get("description") or ""),
        "style": style,
        "instrument": instrument,
        "price": price,
        "cover_url": str(
            payload.get("cover_url")
            or existing.get("cover_url")
            or f"https://api.dicebear.com/7.x/initials/svg?seed={score_id}"
        ),
        "downloads": int(existing.get("downloads", 0)),
        "likes_base": int(existing.get("likes_base", 0)),
        "favorites_base": int(existing.get("favorites_base", 0)),
        "tags": tags,
        "is_public": bool(payload.get("is_public", True)),
        "published_at": existing.get("published_at") or now,
        "updated_at": now,
        "source_file_name": str(payload.get("source_file_name") or existing.get("source_file_name") or ""),
        "download_url": existing.get("download_url") or f"/api/v1/community/scores/{score_id}/download",
    }
    COMMUNITY_SCORES[score_id] = entry
    COMMUNITY_COMMENTS.setdefault(score_id, [])
    COMMUNITY_LIKES.setdefault(score_id, set())
    COMMUNITY_FAVORITES.setdefault(score_id, set())

    return {
        "community_score_id": entry["community_score_id"],
        "score_id": score_id,
        "published_at": entry["published_at"],
        "item": _serialize_score(entry, current_user=current_user),
    }


def list_community_comments(score_id: str, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    _get_score(score_id)
    comments = list(reversed(COMMUNITY_COMMENTS.get(score_id, [])))
    total = len(comments)
    start = (page - 1) * page_size
    paged = comments[start : start + page_size]
    return {
        "score_id": score_id,
        "total": total,
        "items": [_serialize_comment(comment) for comment in paged],
        "page": page,
        "page_size": page_size,
    }


def add_community_comment(score_id: str, payload: dict[str, Any], current_user: dict[str, Any] | None = None) -> dict[str, Any]:
    _get_score(score_id)
    content = str(payload.get("content") or "").strip()
    if not content:
        raise ValueError("comment content cannot be empty")

    author = str(payload.get("username") or (current_user or {}).get("username") or DEFAULT_AUTHOR)
    comment = {
        "comment_id": f"cc_{uuid4().hex[:8]}",
        "username": author,
        "avatar_url": str(
            payload.get("avatar_url")
            or f"https://api.dicebear.com/7.x/avataaars/svg?seed={author}"
        ),
        "content": content,
        "created_at": _now_iso(),
    }
    COMMUNITY_COMMENTS.setdefault(score_id, []).append(comment)
    return {
        "score_id": score_id,
        "comment": _serialize_comment(comment),
        "comments_count": len(COMMUNITY_COMMENTS[score_id]),
    }


def set_score_like(score_id: str, liked: bool, current_user: dict[str, Any] | None = None) -> dict[str, Any]:
    entry = _get_score(score_id)
    viewer_id = _viewer_id(current_user)
    likes = COMMUNITY_LIKES.setdefault(score_id, set())
    if liked:
        likes.add(viewer_id)
    else:
        likes.discard(viewer_id)
    payload = _serialize_score(entry, current_user=current_user)
    return {"score_id": score_id, "liked": liked, "likes": payload["likes"]}


def set_score_favorite(score_id: str, favorited: bool, current_user: dict[str, Any] | None = None) -> dict[str, Any]:
    entry = _get_score(score_id)
    viewer_id = _viewer_id(current_user)
    favorites = COMMUNITY_FAVORITES.setdefault(score_id, set())
    if favorited:
        favorites.add(viewer_id)
    else:
        favorites.discard(viewer_id)
    payload = _serialize_score(entry, current_user=current_user)
    return {"score_id": score_id, "favorited": favorited, "favorites": payload["favorites"]}


def register_score_download(score_id: str) -> dict[str, Any]:
    entry = _get_score(score_id)
    entry["downloads"] = int(entry.get("downloads", 0)) + 1
    return {
        "score_id": score_id,
        "downloaded": True,
        "downloads": entry["downloads"],
        "download_count_display": _compact_count(entry["downloads"]),
        "download_url": entry.get("download_url") or f"/api/v1/community/scores/{score_id}/download",
        "file_name": entry.get("source_file_name") or f"{score_id}.pdf",
    }
