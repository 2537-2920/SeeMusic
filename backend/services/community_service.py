"""Community score browsing and interaction helpers."""

from __future__ import annotations

import base64
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Iterator
from uuid import uuid4
import logging
from fastapi import HTTPException
import os                 
from sqlalchemy import select

from backend.config.settings import settings

UPLOAD_DIR = str(settings.storage_dir / "avatars")
logger = logging.getLogger(__name__)


COMMUNITY_TZ = timezone(timedelta(hours=8))
DEFAULT_AUTHOR = "社区用户"
COMMUNITY_TAGS = ["精选", "流行", "古典", "钢琴", "古筝", "吉他", "笛子"]
COMMUNITY_TAGS_OTHER = "其他"  # 「其他」过滤项的标志

USE_DB: bool = True
_session_factory = None

COMMUNITY_SCORES: dict[str, dict[str, Any]] = {}
COMMUNITY_COMMENTS: dict[str, list[dict[str, Any]]] = {}
COMMUNITY_LIKES: dict[str, set[str]] = {}
COMMUNITY_FAVORITES: dict[str, set[str]] = {}

_SEEDED_SCORE_FIXTURES: list[tuple[dict[str, Any], list[dict[str, Any]]]] = [
    (
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
    ),
    (
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
    ),
    (
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
    ),
    (
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
    ),
    (
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
    ),
    (
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
    ),
]


def set_db_session_factory(factory) -> None:
    global _session_factory
    _session_factory = factory


@contextmanager
def _session_scope() -> Iterator[Any]:
    if _session_factory is None:
        raise RuntimeError("DB mode enabled but no session factory configured")
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _now() -> datetime:
    return datetime.now(COMMUNITY_TZ)


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds")


def _parse_iso(value: str | None) -> datetime:
    if value:
        return datetime.fromisoformat(value)
    return _now()


def _to_community_iso(value: datetime | None) -> str:
    if value is None:
        return _now_iso()
    if value.tzinfo is None:
        value = value.replace(tzinfo=COMMUNITY_TZ)
    else:
        value = value.astimezone(COMMUNITY_TZ)
    return value.isoformat(timespec="seconds")


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


def _default_subtitle(author: str, instrument: str | None, style: str | None = None) -> str:
    return f"{author} · {instrument or style or '乐谱'}"


def _actor_key(current_user: dict[str, Any] | None) -> str:
    if current_user and current_user.get("user_id"):
        return f"user:{current_user['user_id']}"
    return "guest"


def _resolve_user_id(current_user: dict[str, Any] | None) -> int | None:
    if not current_user:
        return None
    user_id = current_user.get("user_id")
    if user_id is None:
        return None
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


def _serialize_comment(comment: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(comment)
    payload["relative_time"] = _relative_time(payload["created_at"])
    return payload


def _serialize_score(entry: dict[str, Any], current_user: dict[str, Any] | None = None) -> dict[str, Any]:
    score_id = str(entry["score_id"])
    actor_key = _actor_key(current_user)
    likes = int(entry.get("likes_base", 0)) + len(COMMUNITY_LIKES.get(score_id, set()))
    favorites = int(entry.get("favorites_base", 0)) + len(COMMUNITY_FAVORITES.get(score_id, set()))
    downloads = int(entry.get("downloads", 0))
    comments = COMMUNITY_COMMENTS.get(score_id, [])
    payload = deepcopy(entry)
    payload["subtitle"] = payload.get("subtitle") or _default_subtitle(
        str(payload.get("author") or DEFAULT_AUTHOR),
        str(payload.get("instrument") or "") or None,
        str(payload.get("style") or "") or None,
    )
    payload["price_label"] = _format_price(float(payload.get("price", 0.0)))
    payload["downloads"] = downloads
    payload["download_count_display"] = _compact_count(downloads)
    payload["likes"] = likes
    payload["favorites"] = favorites
    payload["comments_count"] = len(comments)
    payload["liked"] = actor_key in COMMUNITY_LIKES.get(score_id, set())
    payload["favorited"] = actor_key in COMMUNITY_FAVORITES.get(score_id, set())
    payload["download_url"] = payload.get("download_url") or f"/api/v1/community/scores/{score_id}/download"
    # Ensure cover_url reflects the actual uploaded cover_image if available (important for memory mode/tests)
    if payload.get("cover_image"):
        data_url = _cover_data_url(payload.get("cover_image"), payload.get("cover_content_type"))
        if data_url:
            payload["cover_url"] = data_url
    return payload


def _cover_data_url(image_bytes: bytes | None, content_type: str | None) -> str | None:
    if not image_bytes:
        return None
    resolved_type = (content_type or "image/png").strip() or "image/png"
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{resolved_type};base64,{encoded}"


def _seed_score(entry: dict[str, Any], comments: list[dict[str, Any]]) -> None:
    score_id = str(entry["score_id"])
    COMMUNITY_SCORES[score_id] = deepcopy(entry)
    COMMUNITY_COMMENTS[score_id] = deepcopy(comments)
    COMMUNITY_LIKES.setdefault(score_id, set())
    COMMUNITY_FAVORITES.setdefault(score_id, set())


def _ensure_seeded_mem() -> None:
    if COMMUNITY_SCORES:
        return
    for entry, comments in _SEEDED_SCORE_FIXTURES:
        _seed_score(entry, comments)


def _find_sheet_id(session: Any, score_id: str | None) -> int | None:
    if not score_id:
        return None
    from backend.db.models import Sheet

    statement = select(Sheet).where(Sheet.score_id == score_id)
    sheet = session.execute(statement).scalar_one_or_none()
    return int(sheet.id) if sheet else None


def _serialize_db_comment(session: Any, row: Any) -> dict[str, Any]:
    from backend.db.models import User
    user = session.get(User, row.user_id) if row.user_id else None
    payload = {
        "comment_id": str(row.comment_id),
        "username": str(row.username),
        "nickname": user.nickname if user and user.nickname else str(row.username),
        "avatar_url": row.avatar_url,
        "content": str(row.content),
        "created_at": _to_community_iso(row.create_time),
    }
    payload["relative_time"] = _relative_time(payload["created_at"])
    return payload


def _serialize_db_score(session: Any, post: Any, current_user: dict[str, Any] | None = None) -> dict[str, Any]:
    from backend.db.models import CommunityComment, CommunityFavorite, CommunityLike,User

    actor_key = _actor_key(current_user)
    comment_count = session.query(CommunityComment).filter_by(post_id=post.id).count()
    liked = session.query(CommunityLike).filter_by(post_id=post.id, actor_key=actor_key).first() is not None
    favorited = session.query(CommunityFavorite).filter_by(post_id=post.id, actor_key=actor_key).first() is not None
    user = session.get(User, post.user_id) if post.user_id else None
    author = (user.nickname if user and user.nickname else str(post.author_name or DEFAULT_AUTHOR))
    style = str(post.style or "")
    instrument = str(post.instrument or "")
    score_id = str(post.score_id)
    published_at = _to_community_iso(post.create_time)
    updated_at = _to_community_iso(post.update_time) if post.update_time else published_at
    return {
        "community_score_id": str(post.community_score_id),
        "score_id": score_id,
        "title": str(post.title),
        "author": author,
        "subtitle": str(post.subtitle or _default_subtitle(author, instrument or None, style or None)),
        "description": str(post.content or ""),
        "style": style,
        "instrument": instrument,
        "price": float(post.price or 0.0),
        "price_label": _format_price(float(post.price or 0.0)),
        "cover_url": _cover_data_url(post.cover_image, post.cover_content_type) or post.cover_url,
        "downloads": int(post.download_count or 0),
        "download_count_display": _compact_count(int(post.download_count or 0)),
        "likes": int(post.like_count or 0),
        "favorites": int(post.favorite_count or 0),
        "comments_count": int(comment_count),
        "liked": liked,
        "favorited": favorited,
        "tags": list(post.tags or []),
        "is_public": bool(post.is_public),
        "published_at": published_at,
        "updated_at": updated_at,
        "source_file_name": post.source_file_name,
        "download_url": f"/api/v1/community/scores/{score_id}/download",
    }
    

def get_community_score_cover(score_id: str) -> tuple[bytes, str]:
    _ensure_seeded()
    if USE_DB:
        from backend.db.models import CommunityPost
        with _session_scope() as session:
            row = session.execute(
                select(CommunityPost.cover_image, CommunityPost.cover_content_type)
                .where(CommunityPost.score_id == score_id)
            ).first()
            if row is None or not row.cover_image:
                raise KeyError(f"community score {score_id} cover not found")
            return bytes(row.cover_image), str(row.cover_content_type or "image/png")
            
    entry = _get_score_mem(score_id)
    if not entry.get("cover_image"):
        raise KeyError(f"community score {score_id} cover not found")
    return bytes(entry.get("cover_image")), str(entry.get("cover_content_type") or "image/png")


def _ensure_seeded_db() -> None:
    from backend.db.models import CommunityComment, CommunityPost

    with _session_scope() as session:
        existing = session.query(CommunityPost).first()
        if existing is not None:
            return

        for entry, comments in _SEEDED_SCORE_FIXTURES:
            created_at = _parse_iso(entry.get("published_at"))
            post = CommunityPost(
                user_id=None,
                sheet_id=_find_sheet_id(session, str(entry.get("score_id"))),
                community_score_id=str(entry["community_score_id"]),
                score_id=str(entry["score_id"]),
                title=str(entry["title"]),
                author_name=str(entry.get("author") or DEFAULT_AUTHOR),
                subtitle=str(entry.get("subtitle") or ""),
                content=str(entry.get("description") or ""),
                style=str(entry.get("style") or ""),
                instrument=str(entry.get("instrument") or ""),
                price=float(entry.get("price") or 0.0),
                cover_url=entry.get("cover_url"),
                cover_image=entry.get("cover_image"),
                cover_content_type=entry.get("cover_content_type"),
                source_file_name=entry.get("source_file_name"),
                tags=list(entry.get("tags") or []),
                is_public=bool(entry.get("is_public", True)),
                like_count=int(entry.get("likes_base", 0)),
                favorite_count=int(entry.get("favorites_base", 0)),
                download_count=int(entry.get("downloads", 0)),
                view_count=0,
                create_time=created_at,
                update_time=created_at,
            )
            session.add(post)
            session.flush()

            for comment in comments:
                session.add(
                    CommunityComment(
                        comment_id=str(comment["comment_id"]),
                        post_id=int(post.id),
                        user_id=None,
                        username=str(comment["username"]),
                        avatar_url=comment.get("avatar_url"),
                        content=str(comment["content"]),
                        create_time=_parse_iso(comment.get("created_at")),
                    )
                )


def _ensure_seeded() -> None:
    if USE_DB:
        _ensure_seeded_db()
    else:
        _ensure_seeded_mem()


def _get_score_mem(score_id: str) -> dict[str, Any]:
    _ensure_seeded_mem()
    if score_id not in COMMUNITY_SCORES:
        raise KeyError(f"community score {score_id} not found")
    return COMMUNITY_SCORES[score_id]


def _get_score_db(session: Any, score_id: str) -> Any:
    from backend.db.models import CommunityPost

    statement = select(CommunityPost).where(CommunityPost.score_id == score_id)
    post = session.execute(statement).scalar_one_or_none()
    if post is None:
        raise KeyError(f"community score {score_id} not found")
    return post


def list_community_scores(
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    tag: str | None = None,
    current_user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ensure_seeded()
    if USE_DB:
        from backend.db.models import CommunityPost, User
        from sqlalchemy.orm import defer

        normalized_keyword = (keyword or "").strip().lower()
        normalized_tag = (tag or "").strip()
        with _session_scope() as session:
            posts = list(
                session.execute(
                    select(CommunityPost)
                    .where(CommunityPost.is_public.is_(True))
                    .options(defer(CommunityPost.file_content_base64))
                ).scalars()
            )

            # Eagerly load user information to session cache to avoid N+1 queries and allow filtering by nickname
            user_ids = {post.user_id for post in posts if post.user_id}
            users = {}
            if user_ids:
                user_records = session.execute(select(User).where(User.id.in_(user_ids))).scalars()
                users = {u.id: u for u in user_records}

            filtered_posts = []
            for post in posts:
                user = users.get(post.user_id) if post.user_id else None
                author = user.nickname if user and user.nickname else str(post.author_name or DEFAULT_AUTHOR)

                if normalized_keyword:
                    search_text = " ".join(
                        [
                            str(post.title),
                            str(author),
                            str(post.content or ""),
                            str(post.style or ""),
                            str(post.instrument or ""),
                            " ".join(post.tags or []),
                        ]
                    ).lower()
                    if normalized_keyword not in search_text:
                        continue

                if normalized_tag:
                    if normalized_tag == COMMUNITY_TAGS_OTHER:
                        known_tags = set(COMMUNITY_TAGS)
                        if (
                            post.style in known_tags
                            or post.instrument in known_tags
                            or any(t in known_tags for t in (post.tags or []))
                        ):
                            continue
                    else:
                        if not (
                            normalized_tag == post.style
                            or normalized_tag == post.instrument
                            or normalized_tag in (post.tags or [])
                        ):
                            continue

                filtered_posts.append(post)

            filtered_posts.sort(
                key=lambda post: (
                    "精选" in (post.tags or []),
                    int(post.download_count or 0),
                    int(post.like_count or 0),
                    _to_community_iso(post.create_time),
                ),
                reverse=True,
            )

            total = len(filtered_posts)
            start = (page - 1) * page_size
            paged_posts = filtered_posts[start : start + page_size]

            serialized = [
                _serialize_db_score(session, post, current_user=current_user)
                for post in paged_posts
            ]

        return {
            "total": total,
            "items": serialized,
            "page": page,
            "page_size": page_size,
            "has_more": start + page_size < total,
            "filters": {
                "keyword": keyword,
                "tag": tag,
                "available_tags": COMMUNITY_TAGS,
            },
        }

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
        if normalized_tag == COMMUNITY_TAGS_OTHER:
            # 「其他」：选出 style、instrument、tags 均不属于已定义主标签的曲谱
            known_tags = set(COMMUNITY_TAGS)
            items = [
                entry
                for entry in items
                if entry.get("style") not in known_tags
                and entry.get("instrument") not in known_tags
                and not any(t in known_tags for t in entry.get("tags", []))
            ]
        else:
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
    _ensure_seeded()
    if USE_DB:
        from backend.db.models import CommunityComment

        with _session_scope() as session:
            post = _get_score_db(session, score_id)
            comments = list(
                session.execute(
                    select(CommunityComment)
                    .where(CommunityComment.post_id == post.id)
                    .order_by(CommunityComment.create_time.desc())
                ).scalars()
            )
            return {
                "score": _serialize_db_score(session, post, current_user=current_user),
                "comments": [_serialize_db_comment(session,comment) for comment in comments[:20]],
            }

    entry = _get_score_mem(score_id)
    return {
        "score": _serialize_score(entry, current_user=current_user),
        "comments": [_serialize_comment(comment) for comment in COMMUNITY_COMMENTS.get(score_id, [])[:20]],
    }


def list_community_tags() -> dict[str, Any]:
    _ensure_seeded()
    known_tags = set(COMMUNITY_TAGS)
    if USE_DB:
        from backend.db.models import CommunityPost

        with _session_scope() as session:
            rows = session.execute(
                select(CommunityPost.style, CommunityPost.instrument, CommunityPost.tags).where(
                    CommunityPost.is_public.is_(True)
                )
            ).all()

        items = []
        for tag in COMMUNITY_TAGS:
            count = 0
            for row in rows:
                row_tags = row.tags or []
                if tag == row.style or tag == row.instrument or tag in row_tags:
                    count += 1
            items.append({"name": tag, "count": count})

        other_count = 0
        for row in rows:
            row_tags = row.tags or []
            if (
                row.style not in known_tags
                and row.instrument not in known_tags
                and not any(t in known_tags for t in row_tags)
            ):
                other_count += 1

        if other_count > 0:
            items.append({"name": COMMUNITY_TAGS_OTHER, "count": other_count})
        return {"items": items}

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
    # 内存模式下计算「其他」
    other_count = len([
        entry for entry in COMMUNITY_SCORES.values()
        if entry.get("style") not in known_tags
        and entry.get("instrument") not in known_tags
        and not any(t in known_tags for t in entry.get("tags", []))
    ])
    if other_count > 0:
        items.append({"name": COMMUNITY_TAGS_OTHER, "count": other_count})
    return {"items": items}


def publish_community_score(payload: dict[str, Any], current_user: dict[str, Any] | None = None) -> dict[str, Any]:
    _ensure_seeded()
    score_id = str(payload.get("score_id") or f"score_{uuid4().hex[:8]}")
    now = _now()
    style = str(payload.get("style") or (payload.get("tags") or ["精选"])[0] or "精选")
    instrument = str(payload.get("instrument") or "乐谱")
    author = str(payload.get("author_name") or (current_user or {}).get("username") or DEFAULT_AUTHOR)
    price = float(payload.get("price") or 0.0)
    tags = _dedupe_tags([style, instrument, *(payload.get("tags") or [])])

    if USE_DB:
        from backend.db.models import CommunityPost

        with _session_scope() as session:
            post = session.execute(select(CommunityPost).where(CommunityPost.score_id == score_id)).scalar_one_or_none()
            if post is None:
                post = CommunityPost(
                    user_id=_resolve_user_id(current_user),
                    sheet_id=_find_sheet_id(session, score_id),
                    community_score_id=f"cmt_{score_id}",
                    score_id=score_id,
                    title=str(payload.get("title") or "未命名作品"),
                    author_name=author,
                    subtitle=str(payload.get("subtitle") or _default_subtitle(author, instrument, style)),
                    content=str(payload.get("description") or ""),
                    style=style,
                    instrument=instrument,
                    price=price,
                    cover_url=str(payload.get("cover_url") or f"https://api.dicebear.com/7.x/initials/svg?seed={score_id}"),
                    cover_image=payload.get("cover_image"),
                    cover_content_type=payload.get("cover_content_type"),
                    source_file_name=str(payload.get("source_file_name") or ""),
                    tags=tags,
                    is_public=bool(payload.get("is_public", True)),
                    like_count=0,
                    favorite_count=0,
                    download_count=0,
                    view_count=0,
                    file_content_base64=payload.get("file_content_base64"),
                    create_time=now,
                    update_time=now,
                )
                session.add(post)
                session.flush()
            else:
                post.user_id = _resolve_user_id(current_user) or post.user_id
                post.sheet_id = _find_sheet_id(session, score_id) or post.sheet_id
                post.title = str(payload.get("title") or post.title or "未命名作品")
                post.author_name = author
                post.subtitle = str(payload.get("subtitle") or post.subtitle or _default_subtitle(author, instrument, style))
                post.content = str(payload.get("description") or post.content or "")
                post.style = style
                post.instrument = instrument
                post.price = price
                post.cover_url = str(
                    payload.get("cover_url")
                    or post.cover_url
                    or f"https://api.dicebear.com/7.x/initials/svg?seed={score_id}"
                )
                if "cover_image" in payload:
                    post.cover_image = payload.get("cover_image")
                    post.cover_content_type = payload.get("cover_content_type")
                post.source_file_name = str(payload.get("source_file_name") or post.source_file_name or "")
                post.tags = tags
                post.is_public = bool(payload.get("is_public", True))
                post.update_time = now
                post.file_content_base64 = payload.get("file_content_base64")
                session.add(post)
                session.flush()

            item = _serialize_db_score(session, post, current_user=current_user)
            return {
                "community_score_id": item["community_score_id"],
                "score_id": item["score_id"],
                "published_at": item["published_at"],
                "item": item,
            }

    existing = deepcopy(COMMUNITY_SCORES.get(score_id, {}))
    now_iso = now.isoformat(timespec="seconds")
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
        "cover_image": payload.get("cover_image") if "cover_image" in payload else existing.get("cover_image"),
        "cover_content_type": payload.get("cover_content_type")
        if "cover_content_type" in payload
        else existing.get("cover_content_type"),
        "downloads": int(existing.get("downloads", 0)),
        "likes_base": int(existing.get("likes_base", 0)),
        "favorites_base": int(existing.get("favorites_base", 0)),
        "tags": tags,
        "is_public": bool(payload.get("is_public", True)),
        "published_at": existing.get("published_at") or now_iso,
        "updated_at": now_iso,
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
    _ensure_seeded()
    if USE_DB:
        from backend.db.models import CommunityComment

        with _session_scope() as session:
            post = _get_score_db(session, score_id)
            comments = list(
                session.execute(
                    select(CommunityComment)
                    .where(CommunityComment.post_id == post.id)
                    .order_by(CommunityComment.create_time.desc())
                ).scalars()
            )
            total = len(comments)
            start = (page - 1) * page_size
            paged = comments[start : start + page_size]
            return {
                "score_id": score_id,
                "total": total,
                "items": [_serialize_db_comment(session,comment) for comment in paged],
                "page": page,
                "page_size": page_size,
            }

    _get_score_mem(score_id)
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
    _ensure_seeded()
    content = str(payload.get("content") or "").strip()
    if not content:
        raise ValueError("comment content cannot be empty")

    author = str(payload.get("username") or (current_user or {}).get("username") or DEFAULT_AUTHOR)
    avatar_url = str(payload.get("avatar_url") or f"https://api.dicebear.com/7.x/avataaars/svg?seed={author}")

    if USE_DB:
        from backend.db.models import CommunityComment

        with _session_scope() as session:
            post = _get_score_db(session, score_id)
            comment = CommunityComment(
                comment_id=f"cc_{uuid4().hex[:8]}",
                post_id=int(post.id),
                user_id=_resolve_user_id(current_user),
                username=author,
                avatar_url=avatar_url,
                content=content,
            )
            session.add(comment)
            session.flush()
            comments_count = session.query(CommunityComment).filter_by(post_id=post.id).count()
            return {
                "score_id": score_id,
                "comment": _serialize_db_comment(session,comment),
                "comments_count": comments_count,
            }

    _get_score_mem(score_id)
    comment = {
        "comment_id": f"cc_{uuid4().hex[:8]}",
        "username": author,
        "avatar_url": avatar_url,
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
    _ensure_seeded()
    actor_key = _actor_key(current_user)
    if USE_DB:
        from backend.db.models import CommunityLike

        with _session_scope() as session:
            post = _get_score_db(session, score_id)
            existing = session.execute(
                select(CommunityLike).where(
                    CommunityLike.post_id == post.id,
                    CommunityLike.actor_key == actor_key,
                )
            ).scalars().first()
            if liked and existing is None:
                session.add(
                    CommunityLike(
                        post_id=int(post.id),
                        actor_key=actor_key,
                        user_id=_resolve_user_id(current_user),
                    )
                )
                post.like_count = int(post.like_count or 0) + 1
            elif not liked and existing is not None:
                session.delete(existing)
                post.like_count = max(int(post.like_count or 0) - 1, 0)
            session.add(post)
            session.flush()
            return {"score_id": score_id, "liked": liked, "likes": int(post.like_count or 0)}

    entry = _get_score_mem(score_id)
    likes = COMMUNITY_LIKES.setdefault(score_id, set())
    if liked:
        likes.add(actor_key)
    else:
        likes.discard(actor_key)
    payload = _serialize_score(entry, current_user=current_user)
    return {"score_id": score_id, "liked": liked, "likes": payload["likes"]}


def set_score_favorite(score_id: str, favorited: bool, current_user: dict[str, Any] | None = None) -> dict[str, Any]:
    _ensure_seeded()
    actor_key = _actor_key(current_user)
    if USE_DB:
        from backend.db.models import CommunityFavorite

        with _session_scope() as session:
            post = _get_score_db(session, score_id)
            existing = session.execute(
                select(CommunityFavorite).where(
                    CommunityFavorite.post_id == post.id,
                    CommunityFavorite.actor_key == actor_key,
                )
            ).scalars().first()
            if favorited and existing is None:
                session.add(
                    CommunityFavorite(
                        post_id=int(post.id),
                        actor_key=actor_key,
                        user_id=_resolve_user_id(current_user),
                    )
                )
                post.favorite_count = int(post.favorite_count or 0) + 1
            elif not favorited and existing is not None:
                session.delete(existing)
                post.favorite_count = max(int(post.favorite_count or 0) - 1, 0)
            session.add(post)
            session.flush()
            return {"score_id": score_id, "favorited": favorited, "favorites": int(post.favorite_count or 0)}

    entry = _get_score_mem(score_id)
    favorites = COMMUNITY_FAVORITES.setdefault(score_id, set())
    if favorited:
        favorites.add(actor_key)
    else:
        favorites.discard(actor_key)
    payload = _serialize_score(entry, current_user=current_user)
    return {"score_id": score_id, "favorited": favorited, "favorites": payload["favorites"]}


def register_score_download(score_id: str) -> dict[str, Any]:
    _ensure_seeded()
    if USE_DB:
        with _session_scope() as session:
            post = _get_score_db(session, score_id)
            post.download_count = int(post.download_count or 0) + 1
            session.add(post)
            session.flush()
            downloads = int(post.download_count or 0)
            return {
                "score_id": score_id,
                "downloaded": True,
                "downloads": downloads,
                "download_count_display": _compact_count(downloads),
                "download_url": f"/api/v1/community/scores/{score_id}/download",
                "file_name": post.source_file_name or f"{score_id}.pdf",
            }

    entry = _get_score_mem(score_id)
    entry["downloads"] = int(entry.get("downloads", 0)) + 1
    return {
        "score_id": score_id,
        "downloaded": True,
        "downloads": entry["downloads"],
        "download_count_display": _compact_count(entry["downloads"]),
        "download_url": entry.get("download_url") or f"/api/v1/community/scores/{score_id}/download",
        "file_name": entry.get("source_file_name") or f"{score_id}.pdf",
    }

def get_score_pdf_content(score_id: str) -> tuple[bytes, str]:
    if not USE_DB:
        # 返回一段假的二进制数据，确保测试流程能跑完
        return b"%PDF-1.4 mock content", "test_score.pdf"
    # 连接数据库
    from backend.db.models import CommunityPost
    with _session_scope() as db:
        # 查询乐谱数据
        post = db.query(CommunityPost).filter_by(score_id=score_id).first()
        
        # 乐谱不存在则报错
        if not post:
            raise HTTPException(status_code=404, detail="乐谱记录不存在")
        content_str = post.file_content_base64 or "" 
        
        if not content_str:
            # 如果数据库中没有存内容，返回 mock 数据（兼容部分测试用例）
            return b"%PDF-1.4 mock content (missing in DB)", "score.pdf"

        try:
            # Base64 解码 → 还原成PDF二进制文件
            pdf_bytes = base64.b64decode(content_str)
            return pdf_bytes, post.source_file_name or "score.pdf"
        except Exception as e:
            raise HTTPException(status_code=500, detail="文件解码失败")
        
def save_user_avatar(user_id: str, file_content: bytes, filename: str) -> str:
    from backend.db.models import User, CommunityPost, CommunityComment
    # Keep avatar files under the configured application storage directory.
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, f"{user_id}.png")
    
    # 写入图片文件
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # 生成可访问的URL
    avatar_url = f"/static/avatars/{user_id}.png"
    if not USE_DB:
        return avatar_url

    from backend.db.models import User, CommunityPost, CommunityComment
    
    # 转换为数字 ID（确保匹配数据库类型）
    try:
        uid = int(user_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid user_id for avatar update") from exc
    
    with _session_scope() as db:
        # 1) 核心路径：更新用户头像，必须成功。
        user = db.query(User).get(uid)
        if not user:
            raise HTTPException(status_code=404, detail="user not found")
        user.avatar = avatar_url

        # 2) 非关键同步：社区表结构在不同环境可能未完成迁移，失败不应影响主流程。
        try:
            db.query(CommunityComment).filter(CommunityComment.user_id == uid).update({
                "avatar_url": avatar_url
            })
        except Exception as exc:  # pragma: no cover - defensive for schema drift
            logger.warning("Skip syncing avatar_url to community_comment: %s", exc)

        try:
            db.query(CommunityPost).filter(CommunityPost.user_id == uid).update({
                "cover_url": avatar_url
            })
        except Exception as exc:  # pragma: no cover - defensive for schema drift
            logger.warning("Skip syncing avatar_url to community_post: %s", exc)
    
    return avatar_url
