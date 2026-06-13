import pytest
from pydantic import ValidationError
from backend.api.schemas.auth import Token, TokenData, UserLogin, UserRegister
from backend.api.schemas.common import ErrorDetail, ErrorResponse, ResponseModel

def test_token_schema():
    t = Token(access_token="abc", token_type="bearer")
    assert t.access_token == "abc"
    assert t.token_type == "bearer"

def test_token_data_schema():
    td = TokenData(username="test")
    assert td.username == "test"

def test_user_login_schema():
    ul = UserLogin(username="u", password="p")
    assert ul.username == "u"
    assert ul.password == "p"

def test_user_register_schema():
    ur = UserRegister(email="test@test.com", username="u", password="p")
    assert ur.email == "test@test.com"

    with pytest.raises(ValidationError):
        UserRegister(email="notanemail", username="u", password="p")

def test_error_detail_schema():
    ed = ErrorDetail(code="ERR", message="msg", request_id="123")
    assert ed.code == "ERR"

def test_error_response_schema():
    ed = ErrorDetail(code="ERR", message="msg", request_id="123")
    er = ErrorResponse(error=ed)
    assert er.error.code == "ERR"

def test_response_model_schema():
    rm = ResponseModel[dict](data={"a": 1}, meta={"page": 1})
    assert rm.data["a"] == 1
    assert rm.meta["page"] == 1

@pytest.mark.parametrize("i", range(15))
def test_schemas_fuzz(i):
    t = Token(access_token=f"tok_{i}", token_type="bearer")
    assert t.access_token == f"tok_{i}"
