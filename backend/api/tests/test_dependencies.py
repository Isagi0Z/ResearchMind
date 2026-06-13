import pytest
from fastapi import HTTPException
from backend.api.dependencies import get_current_user

def test_get_current_user_raises_not_implemented():
    with pytest.raises(HTTPException) as exc:
        get_current_user("any.token.string")
    assert exc.value.status_code == 501
