"""Tests for the discovery data model.

The discovery module manages iterative competitor finding: candidates
are presented in batches, users toggle accept/reject, and the state
tracks everything across rounds with deduplication by URL domain.
"""

from __future__ import annotations

import pytest

from recon.discovery import CompetitorTier, DiscoveryCandidate, DiscoveryState


class TestDiscoveryCandidate:
    def test_candidate_defaults_to_accepted(self) -> None:
        candidate = DiscoveryCandidate(
            name="Cursor",
            url="https://cursor.com",
            blurb="AI-first code editor",
            provenance="G2 category leader",
            suggested_tier=CompetitorTier.ESTABLISHED,
        )

        assert candidate.accepted is True

    def test_candidate_fields(self) -> None:
        candidate = DiscoveryCandidate(
            name="Linear",
            url="https://linear.app",
            blurb="Project tracking for high-performance teams",
            provenance="YC batch, HN front page 3x",
            suggested_tier=CompetitorTier.EMERGING,
        )

        assert candidate.name == "Linear"
        assert candidate.url == "https://linear.app"
        assert candidate.blurb == "Project tracking for high-performance teams"
        assert candidate.provenance == "YC batch, HN front page 3x"
        assert candidate.suggested_tier == CompetitorTier.EMERGING


class TestDiscoveryState:
    def test_empty_state(self) -> None:
        state = DiscoveryState()

        assert state.all_candidates == []
        assert state.round_count == 0

    def test_add_round_of_candidates(self) -> None:
        state = DiscoveryState()
        candidates = [
            DiscoveryCandidate(
                name="Cursor", url="https://cursor.com",
                blurb="AI editor", provenance="G2",
                suggested_tier=CompetitorTier.ESTABLISHED,
            ),
            DiscoveryCandidate(
                name="Linear", url="https://linear.app",
                blurb="Project tracking", provenance="HN",
                suggested_tier=CompetitorTier.EMERGING,
            ),
        ]

        state.add_round(candidates)

        assert len(state.all_candidates) == 2
        assert state.round_count == 1

    def test_toggle_candidate(self) -> None:
        state = DiscoveryState()
        state.add_round([
            DiscoveryCandidate(
                name="Cursor", url="https://cursor.com",
                blurb="AI editor", provenance="G2",
                suggested_tier=CompetitorTier.ESTABLISHED,
            ),
        ])

        state.toggle(0)

        assert state.all_candidates[0].accepted is False

    def test_toggle_twice_restores(self) -> None:
        state = DiscoveryState()
        state.add_round([
            DiscoveryCandidate(
                name="Cursor", url="https://cursor.com",
                blurb="AI editor", provenance="G2",
                suggested_tier=CompetitorTier.ESTABLISHED,
            ),
        ])

        state.toggle(0)
        state.toggle(0)

        assert state.all_candidates[0].accepted is True

    def test_accepted_candidates(self) -> None:
        state = DiscoveryState()
        state.add_round([
            DiscoveryCandidate(
                name="Cursor", url="https://cursor.com",
                blurb="AI editor", provenance="G2",
                suggested_tier=CompetitorTier.ESTABLISHED,
            ),
            DiscoveryCandidate(
                name="Linear", url="https://linear.app",
                blurb="Tracking", provenance="HN",
                suggested_tier=CompetitorTier.EMERGING,
            ),
        ])
        state.toggle(1)

        accepted = state.accepted_candidates

        assert len(accepted) == 1
        assert accepted[0].name == "Cursor"

    def test_rejected_candidates(self) -> None:
        state = DiscoveryState()
        state.add_round([
            DiscoveryCandidate(
                name="Cursor", url="https://cursor.com",
                blurb="AI editor", provenance="G2",
                suggested_tier=CompetitorTier.ESTABLISHED,
            ),
            DiscoveryCandidate(
                name="Linear", url="https://linear.app",
                blurb="Tracking", provenance="HN",
                suggested_tier=CompetitorTier.EMERGING,
            ),
        ])
        state.toggle(1)

        rejected = state.rejected_candidates

        assert len(rejected) == 1
        assert rejected[0].name == "Linear"

    def test_deduplicates_by_url_domain(self) -> None:
        state = DiscoveryState()
        state.add_round([
            DiscoveryCandidate(
                name="GitHub Actions", url="https://github.com/features/actions",
                blurb="CI/CD for GitHub", provenance="G2",
                suggested_tier=CompetitorTier.ESTABLISHED,
            ),
        ])

        state.add_round([
            DiscoveryCandidate(
                name="GitHub Workflows", url="https://github.com/features/workflows",
                blurb="Workflow automation", provenance="HN",
                suggested_tier=CompetitorTier.ESTABLISHED,
            ),
            DiscoveryCandidate(
                name="Linear", url="https://linear.app",
                blurb="Tracking", provenance="HN",
                suggested_tier=CompetitorTier.EMERGING,
            ),
        ])

        assert len(state.all_candidates) == 2
        assert state.round_count == 2

    def test_accept_all(self) -> None:
        state = DiscoveryState()
        state.add_round([
            DiscoveryCandidate(
                name="A", url="https://a.com", blurb="a",
                provenance="G2", suggested_tier=CompetitorTier.ESTABLISHED,
            ),
            DiscoveryCandidate(
                name="B", url="https://b.com", blurb="b",
                provenance="G2", suggested_tier=CompetitorTier.EMERGING,
            ),
        ])
        state.toggle(0)
        state.toggle(1)

        state.accept_all()

        assert all(c.accepted for c in state.all_candidates)

    def test_reject_all(self) -> None:
        state = DiscoveryState()
        state.add_round([
            DiscoveryCandidate(
                name="A", url="https://a.com", blurb="a",
                provenance="G2", suggested_tier=CompetitorTier.ESTABLISHED,
            ),
            DiscoveryCandidate(
                name="B", url="https://b.com", blurb="b",
                provenance="G2", suggested_tier=CompetitorTier.EMERGING,
            ),
        ])

        state.reject_all()

        assert not any(c.accepted for c in state.all_candidates)

    def test_add_manual_candidate(self) -> None:
        state = DiscoveryState()

        state.add_manual(
            name="Custom Tool",
            url="https://customtool.dev",
            blurb="User-added competitor",
        )

        assert len(state.all_candidates) == 1
        assert state.all_candidates[0].provenance == "manually added"
        assert state.all_candidates[0].suggested_tier == CompetitorTier.UNKNOWN

    def test_manual_candidate_deduplicates(self) -> None:
        state = DiscoveryState()
        state.add_round([
            DiscoveryCandidate(
                name="Linear", url="https://linear.app",
                blurb="Tracking", provenance="HN",
                suggested_tier=CompetitorTier.EMERGING,
            ),
        ])

        state.add_manual(
            name="Linear (duplicate)",
            url="https://linear.app/features",
            blurb="Duplicate",
        )

        assert len(state.all_candidates) == 1

    def test_toggle_out_of_range_raises(self) -> None:
        state = DiscoveryState()

        with pytest.raises(IndexError):
            state.toggle(0)

    def test_pattern_summary_with_mixed_decisions(self) -> None:
        state = DiscoveryState()
        state.add_round([
            DiscoveryCandidate(
                name="Enterprise Tool", url="https://enterprise.com",
                blurb="Enterprise CI", provenance="Gartner",
                suggested_tier=CompetitorTier.ESTABLISHED,
            ),
            DiscoveryCandidate(
                name="Tiny Script", url="https://tiny.sh",
                blurb="Build script", provenance="GitHub trending",
                suggested_tier=CompetitorTier.EXPERIMENTAL,
            ),
        ])
        state.toggle(1)

        summary = state.pattern_summary()

        assert "accepted" in summary.lower()
        assert "rejected" in summary.lower()
        assert "1" in summary

    def test_multiple_rounds_accumulate(self) -> None:
        state = DiscoveryState()
        state.add_round([
            DiscoveryCandidate(
                name="A", url="https://a.com", blurb="a",
                provenance="G2", suggested_tier=CompetitorTier.ESTABLISHED,
            ),
        ])
        state.add_round([
            DiscoveryCandidate(
                name="B", url="https://b.com", blurb="b",
                provenance="HN", suggested_tier=CompetitorTier.EMERGING,
            ),
        ])

        assert len(state.all_candidates) == 2
        assert state.round_count == 2


class TestDiscoveryStateRemove:
    def test_remove_candidate_by_index(self) -> None:
        state = DiscoveryState()
        state.add_round([
            DiscoveryCandidate(
                name="Alpha", url="https://alpha.com", blurb="a",
                provenance="web", suggested_tier=CompetitorTier.ESTABLISHED,
            ),
            DiscoveryCandidate(
                name="Beta", url="https://beta.com", blurb="b",
                provenance="web", suggested_tier=CompetitorTier.EMERGING,
            ),
            DiscoveryCandidate(
                name="Gamma", url="https://gamma.com", blurb="g",
                provenance="web", suggested_tier=CompetitorTier.EMERGING,
            ),
        ])

        state.remove(1)

        assert len(state.all_candidates) == 2
        names = [c.name for c in state.all_candidates]
        assert "Beta" not in names

    def test_remove_frees_domain_for_readd(self) -> None:
        state = DiscoveryState()
        state.add_round([
            DiscoveryCandidate(
                name="Alpha", url="https://alpha.com", blurb="a",
                provenance="web", suggested_tier=CompetitorTier.ESTABLISHED,
            ),
        ])

        state.remove(0)

        state.add_round([
            DiscoveryCandidate(
                name="Alpha v2", url="https://alpha.com", blurb="a2",
                provenance="web", suggested_tier=CompetitorTier.ESTABLISHED,
            ),
        ])

        assert len(state.all_candidates) == 1
        assert state.all_candidates[0].name == "Alpha v2"
