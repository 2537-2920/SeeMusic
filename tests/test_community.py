from backend.api.api_routes import (
    download_community_score,
    get_community_score_detail,
    list_community_score_comments,
    list_community_tags,
    post_community_score_comment,
    publish_community_score,
)
from backend.api.schemas import CommunityCommentCreateRequest, CommunityScorePublishRequest


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
