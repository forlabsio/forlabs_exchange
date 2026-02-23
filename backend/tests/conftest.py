import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from contextlib import asynccontextmanager

@pytest.fixture(autouse=True)
def mock_background_tasks(monkeypatch):
    """Prevent real Redis/market/bot connections during tests."""
    monkeypatch.setattr("app.main.market_data_loop", AsyncMock(return_value=None))
    monkeypatch.setattr("app.main.bot_runner_loop", AsyncMock(return_value=None))
