import pytest
from unittest.mock import MagicMock
from app.services.bot_eviction import should_evict_bot

def test_should_evict_when_win_rate_below_70():
    performance = MagicMock()
    performance.win_rate = 65.0
    performance.monthly_return_pct = 5.0
    performance.max_drawdown_pct = 10.0
    assert should_evict_bot(performance, max_drawdown_limit=20.0) is True

def test_should_not_evict_good_bot():
    performance = MagicMock()
    performance.win_rate = 75.0
    performance.monthly_return_pct = 8.0
    performance.max_drawdown_pct = 10.0
    assert should_evict_bot(performance, max_drawdown_limit=20.0) is False

def test_should_evict_when_negative_return():
    performance = MagicMock()
    performance.win_rate = 80.0
    performance.monthly_return_pct = -2.0
    performance.max_drawdown_pct = 5.0
    assert should_evict_bot(performance, max_drawdown_limit=20.0) is True

def test_should_evict_when_mdd_exceeded():
    performance = MagicMock()
    performance.win_rate = 80.0
    performance.monthly_return_pct = 5.0
    performance.max_drawdown_pct = 25.0
    assert should_evict_bot(performance, max_drawdown_limit=20.0) is True
