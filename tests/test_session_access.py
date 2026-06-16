import pytest

from workflow.session_access import ensure_session_access
from schemas.user import SessionAccessError, UserContext


USER = UserContext(user_id="user-1")


def test_session_access_allows_empty_or_matching_owner():
    ensure_session_access({}, USER)
    ensure_session_access({"user_id": "user-1"}, USER)


def test_session_access_rejects_mismatched_owner():
    with pytest.raises(SessionAccessError, match="无权访问该会话"):
        ensure_session_access({"user_id": "user-2"}, USER)
