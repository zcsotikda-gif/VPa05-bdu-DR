"""Время: ввод человека — местный, хранение — UTC."""

from datetime import UTC, datetime, timedelta

import pytest

from reminder.clock import local_to_utc, now_utc, utc_to_local


def test_now_utc_is_aware_and_in_utc():
    now = now_utc()

    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_local_input_survives_round_trip():
    entered = datetime(2026, 10, 12, 15, 30)

    assert utc_to_local(local_to_utc(entered)).replace(tzinfo=None) == entered


def test_local_to_utc_returns_utc():
    stored = local_to_utc(datetime(2026, 10, 12, 15, 30))

    assert stored.utcoffset() == timedelta(0)


def test_local_to_utc_refuses_aware_input():
    with pytest.raises(ValueError, match="местное"):
        local_to_utc(datetime(2026, 10, 12, 15, 30, tzinfo=UTC))
