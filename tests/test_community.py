from backend.api.api_routes import (
    download_community_score,
    get_community_score_detail,
    list_community_score_comments,
    list_community_tags,
    post_community_score_comment,
    publish_community_score,
)
from backend.api.schemas import CommunityCommentCreateRequest, CommunityScorePublishRequest
from backend.db.models import CommunityComment, CommunityFavorite, CommunityLike, CommunityPost
from backend.db.session import session_scope


def test_community_detail_returns_frontend_fields():
    result = get_community_score_detail("score_qt")

    assert result["data"]["score"]["title"] == "晴天"
    assert result["data"]["score"]["cover_url"]
    assert result["data"]["score"]["price_label"] == "¥6.00"
    assert result["data"]["comments"]


def test_community_publish_comment_and_download_flow():
    published = publish_community_score(
        CommunityScorePublishRequest(
            title="测试社区曲谱",
            description="给社区页面联调使用",
            tags=["流行", "钢琴"],
            style="流行",
            instrument="钢琴",
            price=0,
            is_public=True,
        )
    )
    score_id = published["data"]["score_id"]

    comment_result = post_community_score_comment(
        score_id,
        CommunityCommentCreateRequest(content="这首整理得很清楚", username="测试用户"),
    )
    comments_result = list_community_score_comments(score_id)
    download_before = published["data"]["item"]["downloads"]
    download_result = download_community_score(score_id)

    assert score_id.startswith("score_")
    assert comment_result["data"]["comment"]["content"] == "这首整理得很清楚"
    assert comments_result["data"]["total"] == 1
    assert download_result["data"]["downloads"] == download_before + 1


def test_community_tags_endpoint_returns_frontend_tabs():
    result = list_community_tags()
    names = [item["name"] for item in result["data"]["items"]]

    assert "精选" in names
    assert "流行" in names
    assert "古典" in names


def test_community_flows_persist_when_db_enabled(user_database):
    published = publish_community_score(
        CommunityScorePublishRequest(
            score_id="score_db_case",
            title="数据库社区曲谱",
            description="数据库持久化验证",
            tags=["流行", "钢琴"],
            style="流行",
            instrument="钢琴",
            price=3.5,
            is_public=True,
        )
    )
    score_id = published["data"]["score_id"]
    post_community_score_comment(
        score_id,
        CommunityCommentCreateRequest(content="持久化评论", username="数据库用户"),
    )

    from backend.api.api_routes import favorite_score, like_score

    like_score(score_id)
    favorite_score(score_id)
    download_community_score(score_id)

    with session_scope() as session:
        post = session.query(CommunityPost).filter_by(score_id=score_id).one()
        comments = session.query(CommunityComment).filter_by(post_id=post.id).all()
        likes = session.query(CommunityLike).filter_by(post_id=post.id).all()
        favorites = session.query(CommunityFavorite).filter_by(post_id=post.id).all()

    assert post.community_score_id == "cmt_score_db_case"
    assert post.like_count == 1
    assert post.favorite_count == 1
    assert post.download_count == 1
    assert len(comments) == 1
    assert comments[0].content == "持久化评论"
    assert len(likes) == 1
    assert len(favorites) == 1
