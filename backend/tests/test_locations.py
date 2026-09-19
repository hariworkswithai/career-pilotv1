"""Tests for India location parsing and eligibility."""

from __future__ import annotations

import pytest

from app.schemas.common import Eligibility, RemoteScope, WorkplaceType
from app.schemas.opportunities import NormalizedLocation
from app.services.locations import (
    determine_eligibility,
    location_from_text,
    parse_workplace,
)


class TestParseWorkplace:
    @pytest.mark.parametrize(
        "text,expected_type,expected_scope",
        [
            ("Bengaluru, Karnataka, India", WorkplaceType.ON_SITE, RemoteScope.NONE),
            ("Remote - India", WorkplaceType.REMOTE, RemoteScope.INDIA),
            ("Remote", WorkplaceType.REMOTE, RemoteScope.WORLDWIDE),
            ("Hybrid - Bengaluru", WorkplaceType.HYBRID, RemoteScope.NONE),
            ("New York, NY", WorkplaceType.ON_SITE, RemoteScope.NONE),
        ],
    )
    def test_parse(self, text, expected_type, expected_scope):
        wtype, scope = parse_workplace(text)
        assert wtype == expected_type
        assert scope == expected_scope


class TestLocationFromText:
    def test_city_and_state(self):
        loc = location_from_text("Bengaluru, Karnataka, India")
        assert loc.city == "bengaluru"
        assert loc.state == "karnataka"
        assert loc.country == "india"

    def test_remote_india(self):
        loc = location_from_text("Remote - India")
        assert loc.workplace_type == WorkplaceType.REMOTE
        assert loc.remote_scope == RemoteScope.INDIA

    def test_empty(self):
        loc = location_from_text("")
        assert loc.raw == ""


class TestEligibility:
    @pytest.mark.parametrize(
        "location,expected",
        [
            (location_from_text("Bengaluru, India"), Eligibility.ELIGIBLE),
            (location_from_text("Remote - India"), Eligibility.ELIGIBLE),
            (location_from_text("Mumbai, Maharashtra"), Eligibility.ELIGIBLE),
            (location_from_text("New York, USA"), Eligibility.NOT_ELIGIBLE),
            (location_from_text("Remote - US"), Eligibility.NOT_ELIGIBLE),
            (location_from_text("London, UK"), Eligibility.NOT_ELIGIBLE),
            (location_from_text(""), Eligibility.AMBIGUOUS),
            (location_from_text("Remote"), Eligibility.AMBIGUOUS),
            (location_from_text("Hybrid"), Eligibility.AMBIGUOUS),
        ],
    )
    def test_determine(self, location: NormalizedLocation, expected):
        eligibility, reason = determine_eligibility(location, "")
        assert eligibility == expected, reason
        assert reason

    def test_worldwide_remote_without_geo_hint_is_ambiguous(self):
        eligibility, _ = determine_eligibility(location_from_text("Remote"), "")
        assert eligibility == Eligibility.AMBIGUOUS
