import pytest
from fastapi import HTTPException

from backend.user.history_manager import delete_history, list_history, save_history
from backend.user.user_system import get_current_user, get_user_by_token, login_user, register_user


# =========================================================================
# In-memory mode tests (no database needed, runs fast in CI)
# =========================================================================

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
    item = save_history("u_001", {"type": "score", "resource_id": "score_001", "title": "demo", "metadata": {"from": "memory"}})
    listed = list_history("u_001")
    deleted = delete_history("u_001", item["history_id"])

    assert len(listed["items"]) == 1
    assert listed["items"][0]["resource_id"] == "score_001"
    assert listed["items"][0]["metadata"]["from"] == "memory"
    assert deleted["deleted"] is True
    assert list_history("u_001")["items"] == []


# =========================================================================
# Database mode tests (uses SQLite via user_database fixture)
# =========================================================================

def test_db_user_registration_login_and_token_lookup(user_database):
    registered = register_user("alice_db", "password123", "alice_db@example.com")
    login_result = login_user("alice_db", "password123")
    current_user = get_current_user(f"Bearer {login_result['token']}")

    assert registered["user_id"]
    assert login_result["user"]["username"] == "alice_db"
    assert get_user_by_token(login_result["token"])["user_id"] == current_user["user_id"]
    assert current_user["email"] == "alice_db@example.com"


def test_db_user_system_rejects_duplicates_and_bad_credentials(user_database):
    register_user("bob_db", "password123", "bob_db@example.com")
    with pytest.raises(HTTPException) as duplicate_exc:
        register_user("bob_db", "another", "bob_db2@example.com")
    assert duplicate_exc.value.status_code == 400

    with pytest.raises(HTTPException) as login_exc:
        login_user("bob_db", "wrong-password")
    assert login_exc.value.status_code == 401


def test_db_history_manager_save_list_and_delete(user_database):
    # First register a user so we have a valid user_id in the DB
    registered = register_user("history_tester", "pass123")
    user_id = registered["user_id"]

    item = save_history(user_id, {"type": "score", "resource_id": "score_001", "title": "demo", "metadata": {"from": "db"}})
    listed = list_history(user_id)
    deleted = delete_history(user_id, item["history_id"])

    assert len(listed["items"]) == 1
    assert listed["items"][0]["resource_id"] == "score_001"
    assert listed["items"][0]["metadata"]["from"] == "db"
    assert deleted["deleted"] is True
    assert list_history(user_id)["items"] == []


def test_db_history_manager_rejects_invalid_user_id(user_database):
    with pytest.raises(HTTPException) as exc:
        save_history("u_001", {"type": "score", "resource_id": "score_001", "title": "demo"})
    assert exc.value.status_code == 400


def test_db_history_manager_delete_respects_user_ownership(user_database):
    owner = register_user("owner_user", "pass123")
    other = register_user("other_user", "pass123")

    item = save_history(owner["user_id"], {"type": "score", "resource_id": "score_001", "title": "owner item"})

    # Another user deleting the same history_id should have no effect.
    delete_history(other["user_id"], item["history_id"])

    owner_items = list_history(owner["user_id"])["items"]
    assert len(owner_items) == 1
    assert owner_items[0]["history_id"] == item["history_id"]
