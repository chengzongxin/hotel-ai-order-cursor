"""Session ownership checks shared by graph entrypoints."""

from schemas.user import SessionAccessError, UserContext


def ensure_session_access(state: dict[str, object], user: UserContext) -> None:
    stored_user_id = state.get("user_id")
    if stored_user_id and stored_user_id != user.user_id:
        raise SessionAccessError("无权访问该会话")
