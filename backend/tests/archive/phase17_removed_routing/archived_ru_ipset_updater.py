# FILE: backend/tests/test_ru_ipset_updater.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Unit tests for RuIpsetUpdater — multi-source fetch, validation, snapshot, diff computation.
#   SCOPE: Mocked HTTP sources, CIDR parsing, validation, snapshot persistence, diff computation.
#   DEPENDS: M-017 (ru_ipset_updater), pytest, httpx (mocked), tmp_path
#   LINKS: V-M-017, M-017
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_fetch_single_json — parses ipverse JSON format
#   test_fetch_single_text — parses antizapret/ipgeobase text format
#   test_fetch_all_sources — merges multiple sources
#   test_parse_cidrs — valid and invalid CIDR handling
#   test_validate_cidrs — sanity check pass/fail
#   test_compute_diff — add/remove computation
#   test_persist_and_load_snapshot — roundtrip
#   test_update_ru_ipset_all_sources_fail — fallback behavior
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.5 - Created unit tests for RuIpsetUpdater (Phase-15)
# END_CHANGE_SUMMARY
#
"""Unit tests for RuIpsetUpdater."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routing.ru_ipset_updater import (
    RuIpsetUpdater,
    RuIpsetStats,
    MIN_ENTRIES,
)


# --- Fixtures ---

@pytest.fixture
def sample_cidrs():
    """Generate a set of valid CIDRs."""
    return {f"10.{i}.0.0/16" for i in range(1100)}


@pytest.fixture
def updater(tmp_path):
    """Create RuIpsetUpdater with temp snapshot dir."""
    return RuIpsetUpdater(snapshot_dir=tmp_path)


# --- fetch_single tests ---

@pytest.mark.asyncio
async def test_fetch_single_json(updater):
    """Parse ipverse JSON format correctly."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "ip_list": ["10.0.0.0/8", "192.168.0.0/16"]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    cidrs = await updater._fetch_single(mock_client, {
        "name": "test",
        "url": "http://test",
        "format": "json",
        "key": "ip_list",
    })

    assert "10.0.0.0/8" in cidrs
    assert "192.168.0.0/16" in cidrs


@pytest.mark.asyncio
async def test_fetch_single_text(updater):
    """Parse text CIDR list correctly."""
    mock_response = MagicMock()
    mock_response.text = "10.0.0.0/8\n192.168.0.0/16\n# comment\n\ninvalid"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    cidrs = await updater._fetch_single(mock_client, {
        "name": "test",
        "url": "http://test",
        "format": "text",
    })

    assert "10.0.0.0/8" in cidrs
    assert "192.168.0.0/16" in cidrs
    assert "invalid" not in cidrs


# --- parse_cidrs tests ---

def test_parse_cidrs_valid_only(updater):
    """Only valid CIDRs are kept."""
    lines = ["10.0.0.0/8", "not-an-ip", "192.168.1.0/24", "# comment", ""]
    cidrs = updater._parse_cidrs(lines)
    assert cidrs == {"10.0.0.0/8", "192.168.1.0/24"}


def test_parse_cidrs_normalizes(updater):
    """CIDRs are normalized (e.g. 10.0.0.1/24 → 10.0.0.0/24)."""
    lines = ["10.0.0.1/24"]
    cidrs = updater._parse_cidrs(lines)
    assert "10.0.0.0/24" in cidrs


# --- validate tests ---

def test_validate_passes(updater, sample_cidrs):
    """Validation passes with enough entries."""
    assert updater.validate_cidrs(sample_cidrs) is True


def test_validate_fails_too_few(updater):
    """Validation fails with too few entries."""
    assert updater.validate_cidrs({"10.0.0.0/8"}) is False


# --- compute_diff tests ---

def test_compute_diff_add_and_remove():
    """Diff correctly identifies additions and removals."""
    current = {"10.0.0.0/8", "192.168.0.0/16"}
    desired = {"10.0.0.0/8", "172.16.0.0/12"}

    to_add, to_remove, added, removed = RuIpsetUpdater.compute_diff(current, desired)

    assert to_add == {"172.16.0.0/12"}
    assert to_remove == {"192.168.0.0/16"}
    assert added == 1
    assert removed == 1


def test_compute_diff_no_changes():
    """Diff is empty when sets are equal."""
    current = {"10.0.0.0/8"}
    desired = {"10.0.0.0/8"}

    to_add, to_remove, added, removed = RuIpsetUpdater.compute_diff(current, desired)

    assert to_add == set()
    assert to_remove == set()
    assert added == 0
    assert removed == 0


# --- Snapshot tests ---

def test_persist_and_load_snapshot(updater, sample_cidrs):
    """Snapshot roundtrip preserves data."""
    sources = ["ipverse", "antizapret"]
    updater.persist_snapshot(sample_cidrs, sources)

    loaded = updater.load_snapshot()
    assert loaded is not None
    assert loaded == sample_cidrs


def test_load_snapshot_missing(updater):
    """Returns None when no snapshot file exists."""
    assert updater.load_snapshot() is None


# --- fetch_all_sources tests ---

@pytest.mark.asyncio
async def test_fetch_all_sources_partial_fail(updater):
    """Continues with remaining sources when one fails."""
    async def mock_get(url):
        if "fail" in url:
            raise Exception("Connection refused")
        resp = MagicMock()
        resp.text = "\n".join(f"10.{i}.0.0/16" for i in range(600))
        resp.raise_for_status = MagicMock()
        return resp

    mock_client = AsyncMock()
    mock_client.get = mock_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    updater.sources = [
        {"name": "good", "url": "http://good", "format": "text"},
        {"name": "bad", "url": "http://fail", "format": "text"},
    ]

    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value = mock_client
        cidrs, sources_used = await updater.fetch_all_sources()

    assert len(cidrs) == 600
    assert "good" in sources_used
    assert "bad" not in sources_used


# --- update_ru_ipset tests ---

@pytest.mark.asyncio
async def test_update_ru_ipset_no_changes(updater, sample_cidrs):
    """Returns success with 0 added/removed when ipset is empty."""
    # Mock _get_current_entries to return empty set
    updater._get_current_entries = AsyncMock(return_value=set())
    # Mock apply_incremental to not actually call ipset
    updater.apply_incremental = AsyncMock(return_value=True)

    # Mock fetch to return valid data
    updater.fetch_all_sources = AsyncMock(return_value=(sample_cidrs, ["mock"]))

    stats = await updater.update_ru_ipset("test_ipset")

    assert stats.entries == len(sample_cidrs)
    assert stats.last_error is None
    assert stats.sources_used == ["mock"]
    assert updater.snapshot_file.exists()


@pytest.mark.asyncio
async def test_update_ru_ipset_all_sources_fail_no_snapshot(updater):
    """Returns error when all sources fail and no snapshot exists."""
    updater.fetch_all_sources = AsyncMock(return_value=(set(), []))

    stats = await updater.update_ru_ipset("test_ipset")

    assert stats.last_error is not None
    assert stats.entries == 0
