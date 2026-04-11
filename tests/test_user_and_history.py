import pytest
from fastapi import HTTPException

from backend.user.history_manager import delete_history, list_history, save_history
from backend.user.user_system import get_current_user, get_user_by_token, login_user, register_user


def test_user_registration_login_and_token_lookup():
    registered = register_user("alice", "password123", "alice@example.com")
    login_result = login_user("alice", "password123")
    current_user = get_current_user(f"Bearer {login_result['token']}")

    assert registered["user_id"].startswith("u_")
    assert login_result["user"]["username"] == "alice"
    assert get_user_by_token(login_result["token"])["user_id"] == current_user["user_id"]
    assert current_user["email"] == "alice@example.com"


def test_user_system_rejects_duplicates_and_bad_credentials():
    register_user("bob", "password123", "bob@example.com")
    with pytest.raises(HTTPException) as duplicate_exc:
        register_user("bob", "another", "bob2@example.com")
    assert duplicate_exc.value.status_code == 400

    with pytest.raises(HTTPException) as login_exc:
        login_user("bob", "wrong-password")
    assert login_exc.value.status_code == 401


def test_history_manager_save_list_and_delete():
    item = save_history("u_001", {"type": "score", "resource_id": "score_001", "title": "demo"})
    listed = list_history("u_001")
    deleted = delete_history("u_001", item["history_id"])

    assert len(listed["items"]) == 1
    assert listed["items"][0]["resource_id"] == "score_001"
    assert deleted["deleted"] is True
    assert list_history("u_001")["items"] == []

