"""
Unit test untuk bot/services/sports_api.py.

Semua test di sini memakai mock untuk requests.Session, jadi TIDAK ada
panggilan jaringan sungguhan ke TheSportsDB. Ini penting karena:
1. Test jadi cepat dan deterministik (tidak tergantung koneksi/rate limit).
2. Rate limit gratis TheSportsDB (30 req/menit) tidak ikut terpakai
   hanya untuk menjalankan test suite.

Jalankan dengan: python -m unittest tests/test_sports_api.py -v
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from services.sports_api import (
    Event,
    RateLimitExceededError,
    SportsAPIError,
    Team,
    TeamNotFoundError,
    TheSportsDBClient,
)


def make_response(status_code: int = 200, json_data: dict | None = None) -> MagicMock:
    """Helper untuk membuat objek response palsu ala `requests.Response`."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data or {}
    return response


class TheSportsDBClientTestCase(unittest.TestCase):
    """Test untuk operasi dasar client: search_team, get_next_event_for_team, dll."""

    def setUp(self) -> None:
        self.session = MagicMock()
        self.client = TheSportsDBClient(session=self.session, max_retries=1)

    def test_search_team_success_returns_team(self) -> None:
        raw_team = {
            "idTeam": "133602",
            "strTeam": "Arsenal",
            "strLeague": "English Premier League",
            "strSport": "Soccer",
        }
        self.session.get.return_value = make_response(json_data={"teams": [raw_team]})

        team = self.client.search_team("Arsenal")

        self.assertIsInstance(team, Team)
        self.assertEqual(team.id, "133602")
        self.assertEqual(team.name, "Arsenal")
        self.assertEqual(team.league, "English Premier League")

    def test_search_team_not_found_raises_team_not_found_error(self) -> None:
        self.session.get.return_value = make_response(json_data={"teams": None})

        with self.assertRaises(TeamNotFoundError):
            self.client.search_team("Tim Tidak Ada")

    def test_get_next_event_for_team_returns_event(self) -> None:
        raw_event = {
            "idEvent": "1001",
            "strEvent": "Arsenal vs Chelsea",
            "strLeague": "English Premier League",
            "strHomeTeam": "Arsenal",
            "strAwayTeam": "Chelsea",
            "dateEvent": "2026-08-15",
            "strTime": "14:00:00",
            "strVenue": "Emirates Stadium",
        }
        self.session.get.return_value = make_response(json_data={"events": [raw_event]})

        event = self.client.get_next_event_for_team("133602")

        self.assertIsInstance(event, Event)
        self.assertEqual(event.name, "Arsenal vs Chelsea")
        self.assertEqual(event.venue, "Emirates Stadium")

    def test_get_next_event_for_team_returns_none_when_empty(self) -> None:
        self.session.get.return_value = make_response(json_data={"events": None})

        event = self.client.get_next_event_for_team("133602")

        self.assertIsNone(event)

    def test_get_last_event_for_team_returns_event(self) -> None:
        raw_event = {
            "idEvent": "999",
            "strEvent": "Chelsea vs Arsenal",
            "dateEvent": "2026-05-01",
            "strTime": "16:30:00",
        }
        self.session.get.return_value = make_response(json_data={"results": [raw_event]})

        event = self.client.get_last_event_for_team("133602")

        self.assertIsInstance(event, Event)
        self.assertEqual(event.id, "999")


class TheSportsDBClientErrorHandlingTestCase(unittest.TestCase):
    """Test untuk penanganan error: rate limit, HTTP error, JSON tidak valid."""

    def setUp(self) -> None:
        self.session = MagicMock()

    def test_rate_limit_retries_then_succeeds(self) -> None:
        client = TheSportsDBClient(session=self.session, max_retries=1)
        rate_limited_response = make_response(status_code=429)
        success_response = make_response(json_data={"teams": [{
            "idTeam": "1", "strTeam": "Arsenal",
        }]})
        self.session.get.side_effect = [rate_limited_response, success_response]

        with patch("bot.services.sports_api.time.sleep") as mock_sleep:
            team = client.search_team("Arsenal")

        self.assertEqual(team.name, "Arsenal")
        mock_sleep.assert_called_once()

    def test_rate_limit_exceeded_raises_after_max_retries(self) -> None:
        client = TheSportsDBClient(session=self.session, max_retries=1)
        self.session.get.return_value = make_response(status_code=429)

        with patch("bot.services.sports_api.time.sleep"):
            with self.assertRaises(RateLimitExceededError):
                client.search_team("Arsenal")

    def test_http_error_raises_sports_api_error(self) -> None:
        client = TheSportsDBClient(session=self.session, max_retries=0)
        self.session.get.return_value = make_response(status_code=500)

        with self.assertRaises(SportsAPIError):
            client.search_team("Arsenal")

    def test_invalid_json_raises_sports_api_error(self) -> None:
        client = TheSportsDBClient(session=self.session, max_retries=0)
        bad_response = MagicMock()
        bad_response.status_code = 200
        bad_response.json.side_effect = ValueError("bukan json")
        self.session.get.return_value = bad_response

        with self.assertRaises(SportsAPIError):
            client.search_team("Arsenal")


class EventKickoffParsingTestCase(unittest.TestCase):
    """Test untuk properti Event.kickoff_utc."""

    def test_kickoff_utc_parses_valid_date_and_time(self) -> None:
        event = Event(
            id="1", name="Test", league=None, home_team=None, away_team=None,
            date="2026-08-15", time="14:00:00", venue=None,
        )

        kickoff = event.kickoff_utc

        self.assertIsNotNone(kickoff)
        self.assertEqual(kickoff.year, 2026)
        self.assertEqual(kickoff.hour, 14)

    def test_kickoff_utc_returns_none_when_date_missing(self) -> None:
        event = Event(
            id="1", name="Test", league=None, home_team=None, away_team=None,
            date=None, time="14:00:00", venue=None,
        )

        self.assertIsNone(event.kickoff_utc)

    def test_kickoff_utc_returns_none_on_malformed_value(self) -> None:
        event = Event(
            id="1", name="Test", league=None, home_team=None, away_team=None,
            date="tanggal-aneh", time="waktu-aneh", venue=None,
        )

        self.assertIsNone(event.kickoff_utc)


if __name__ == "__main__":
    unittest.main(verbosity=2)