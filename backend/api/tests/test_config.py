import os
from unittest.mock import patch
from backend.api.config import Settings

VALID_KEY = "a" * 64  # meets minimum 32-char requirement

def test_config_defaults():
    with patch.dict(os.environ, {"SECRET_KEY": VALID_KEY}, clear=True):
        settings = Settings(SECRET_KEY=VALID_KEY)
        assert settings.PROJECT_NAME == "ResearchMind API"
        assert settings.VERSION == "1.0.0"
        assert settings.API_V1_STR == "/api/v1"
        assert settings.ALGORITHM == "HS256"
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 60

def test_config_overrides():
    with patch.dict(os.environ, {
        "SECRET_KEY": VALID_KEY,
        "PROJECT_NAME": "Custom Name",
        "API_V1_STR": "/custom",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "120"
    }, clear=True):
        settings = Settings()
        assert settings.PROJECT_NAME == "Custom Name"
        assert settings.API_V1_STR == "/custom"
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 120

import pytest
@pytest.mark.parametrize("i", range(10))
def test_config_fuzz(i):
    with patch.dict(os.environ, {"SECRET_KEY": VALID_KEY, "VERSION": f"1.0.{i}"}, clear=True):
        settings = Settings()
        assert settings.VERSION == f"1.0.{i}"
