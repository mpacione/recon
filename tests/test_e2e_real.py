"""Real end-to-end tests with actual Anthropic API calls.

These tests are SKIPPED unless ANTHROPIC_API_KEY is set in the
environment. They make real API calls and cost real money (a few
cents per run). Use them to verify the engine actually wires up to
the live API correctly.

Run explicitly:
    ANTHROPIC_API_KEY=sk-ant-... pytest tests/test_e2e_real.py -v

Scope is intentionally small:
- 1 competitor
- 1 section
- 1 research call
- Assert content is written to the profile
"""

from __future__ import annotations

import os
from pathlib import Path  # noqa: TCH003 -- used at runtime

import pytest
import yaml

from recon.client_factory import create_llm_client
from recon.discovery import DiscoveryAgent, DiscoveryState
from recon.research import ResearchOrchestrator
from recon.wizard import DecisionContext, WizardState
from recon.workspace import Workspace

API_KEY_PRESENT = bool(os.environ.get("ANTHROPIC_API_KEY"))


requires_api = pytest.mark.skipif(
    not API_KEY_PRESENT,
    reason="ANTHROPIC_API_KEY not set -- skipping real E2E tests",
)


def _build_workspace(root: Path) -> Workspace:
    state = WizardState()
    state.set_identity(
        company_name="E2E Test Co",
        products=["Test Product"],
        domain="developer tools",
        decision_contexts=[DecisionContext.GENERAL],
    )
    state.advance()
    state.advance()
    state.advance()

    schema_dict = state.to_schema_dict()
    root.mkdir(parents=True, exist_ok=True)
    (root / "recon.yaml").write_text(yaml.dump(schema_dict, default_flow_style=False, sort_keys=False))
    return Workspace.init(root=root)


@requires_api
class TestRealLLMClient:
    async def test_basic_llm_call(self) -> None:
        client = create_llm_client(model="claude-haiku-4-5")
        response = await client.complete(
            system_prompt="You are a helpful assistant. Respond in one word.",
            user_prompt="What color is the sky on a sunny day?",
            max_tokens=20,
        )

        assert response.text
        assert response.input_tokens > 0
        assert response.output_tokens > 0
        assert response.model


@requires_api
class TestRealDiscovery:
    async def test_discovery_returns_candidates(self) -> None:
        client = create_llm_client(model="claude-haiku-4-5")
        agent = DiscoveryAgent(
            llm_client=client,
            domain="task management apps for individuals",
            seed_competitors=["Todoist"],
        )
        state = DiscoveryState()
        candidates = await agent.search(state=state)

        assert len(candidates) > 0
        for c in candidates[:3]:
            assert c.name
            assert c.url


@requires_api
class TestRealResearch:
    async def test_research_writes_content_to_profile(self, tmp_path: Path) -> None:
        ws = _build_workspace(tmp_path / "e2e_ws")
        ws.create_profile("GitHub Copilot")

        client = create_llm_client(model="claude-haiku-4-5")
        orchestrator = ResearchOrchestrator(
            workspace=ws,
            llm_client=client,
            max_workers=1,
        )

        results = await orchestrator.research_all()

        assert len(results) > 0

        profile = ws.read_profile("github-copilot")
        assert profile is not None
        content = profile.get("_content", "")
        assert len(content) > 100, f"Research wrote too little content: {content[:200]}"


@requires_api
class TestRealFullLoop:
    async def test_init_add_research_index(self, tmp_path: Path) -> None:
        from recon.incremental import IncrementalIndexer
        from recon.index import IndexManager
        from recon.state import StateStore

        ws = _build_workspace(tmp_path / "full_loop")
        ws.create_profile("Cursor IDE")

        client = create_llm_client(model="claude-haiku-4-5")

        orchestrator = ResearchOrchestrator(
            workspace=ws,
            llm_client=client,
            max_workers=1,
        )
        await orchestrator.research_all()

        manager = IndexManager(persist_dir=str(tmp_path / "vectors"))
        state = StateStore(db_path=ws.root / ".recon" / "state.db")
        await state.initialize()

        indexer = IncrementalIndexer(
            workspace=ws,
            index_manager=manager,
            state_store=state,
        )
        result = await indexer.index()

        assert result.indexed >= 1
        assert result.total_chunks > 0

        query_results = manager.retrieve("features", n_results=3)
        assert len(query_results) > 0
