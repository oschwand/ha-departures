"""Tests for line selection."""

from unittest.mock import AsyncMock, patch

from custom_components.ha_departures.config_flow import (
    _extract_lines_from_stop_times,
    _fetch_lines,
)


def _stop_time(headsign, direction="1", route="rer-b", name="B"):
    return {
        "routeId": route,
        "directionId": direction,
        "routeShortName": name,
        "headsign": headsign,
        "mode": "REGIONAL_RAIL",
    }


def test_multiple_missions_are_one_line_per_direction():
    """A changing trip headsign must not label the whole line."""
    data = {
        "stopTimes": [
            _stop_time("LOVE"),
            _stop_time("PPIT"),
            _stop_time("EPOI", direction="0"),
            _stop_time("EPOI", direction="0"),
            _stop_time("Central", route="other", name="C"),
        ]
    }

    lines = _extract_lines_from_stop_times(data)
    labels = {(line.route_id, line.direction_id): line.head_sign for line in lines}

    assert labels == {
        ("rer-b", "1"): "Direction 1",
        ("rer-b", "0"): "EPOI",
        ("other", "1"): "Central",
    }
    assert [line.head_sign for line in _extract_lines_from_stop_times(data, False)] == [
        "LOVE", "PPIT", "EPOI", "EPOI", "Central"
    ]


async def test_missions_from_different_stops_are_grouped_together():
    """Grouping happens after all stop responses are collected."""
    responses = [
        {"stopTimes": [_stop_time("LOVE")]},
        {"stopTimes": [_stop_time("PPIT")]},
    ]
    with patch(
        "custom_components.ha_departures.config_flow._send_api_request",
        new_callable=AsyncMock,
        side_effect=responses,
    ):
        lines = await _fetch_lines(["stop-1", "stop-2"])

    assert len(lines) == 1
    assert lines[0].route_short_name == "B"
    assert lines[0].head_sign == "Direction 1"
