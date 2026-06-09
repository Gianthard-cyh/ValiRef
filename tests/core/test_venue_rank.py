"""Tests for venue rank lookup."""

import pytest
from src.core.venue_rank import VenueRankLookup, VenueRank


@pytest.fixture
def lookup():
    return VenueRankLookup()


class TestVenueRankLookup:
    def test_exact_match_abbreviation(self, lookup):
        result = lookup.lookup("NeurIPS")
        assert result is not None
        assert result.ccf_rank == "A"

    def test_exact_match_case_insensitive(self, lookup):
        result = lookup.lookup("neurips")
        assert result is not None
        assert result.ccf_rank == "A"

    def test_exact_match_full_name(self, lookup):
        result = lookup.lookup("AAAI Conference on Artificial Intelligence")
        assert result is not None
        assert result.ccf_rank == "A"

    def test_full_name_case_insensitive(self, lookup):
        result = lookup.lookup("aaai conference on artificial intelligence")
        assert result is not None
        assert result.ccf_rank == "A"

    def test_substring_match_abbreviation(self, lookup):
        result = lookup.lookup("Proceedings of NeurIPS 2023")
        assert result is not None
        assert result.ccf_rank == "A"

    def test_conference_b_rank(self, lookup):
        result = lookup.lookup("EMNLP")
        assert result is not None
        assert result.ccf_rank == "B"

    def test_conference_c_rank(self, lookup):
        result = lookup.lookup("CoNLL")
        assert result is not None
        assert result.ccf_rank == "C"

    def test_journal_a_rank(self, lookup):
        result = lookup.lookup("JMLR")
        assert result is not None
        assert result.ccf_rank == "A"

    def test_none_input(self, lookup):
        assert lookup.lookup(None) is None

    def test_empty_string(self, lookup):
        assert lookup.lookup("") is None

    def test_whitespace_only(self, lookup):
        assert lookup.lookup("   ") is None

    def test_unknown_venue(self, lookup):
        assert lookup.lookup("Some Unknown Venue XYZ") is None

    def test_nature_not_false_positive(self, lookup):
        """Nature (the journal) is not in CCF CS list, should not match."""
        assert lookup.lookup("Nature") is None

    def test_data_loaded(self, lookup):
        assert len(lookup._data) > 500

    def test_iclr_rank(self, lookup):
        result = lookup.lookup("ICLR")
        assert result is not None
        assert result.ccf_rank == "A"

    def test_cvpr_rank(self, lookup):
        result = lookup.lookup("CVPR")
        assert result is not None
        assert result.ccf_rank == "A"

    def test_emnlp_full_name(self, lookup):
        result = lookup.lookup("Conference on Empirical Methods in Natural Language Processing")
        assert result is not None
        assert result.ccf_rank == "B"

    def test_kdd_full_name(self, lookup):
        result = lookup.lookup("ACM SIGKDD Conference on Knowledge Discovery and Data Mining")
        assert result is not None
        assert result.ccf_rank == "A"

    def test_icml_full_name(self, lookup):
        result = lookup.lookup("International Conference on Machine Learning")
        assert result is not None
        assert result.ccf_rank == "A"
