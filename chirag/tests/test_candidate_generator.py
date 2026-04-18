"""End-to-end tests for Phase 4 candidate generator (no network)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from agnes.config.settings import Settings
from agnes.graph.queries import MaterialGraphIndex
from agnes.models.canonical import (
    CanonicalMaterial,
    CanonicalRegistry,
    RegistryCoverage,
)
from agnes.models.graph import KGEdge, KGNode, node_id
from agnes.substitutes.candidate_generator import (
    classify_substitution_type,
    generate_candidates,
)
from agnes.models.substitutes import CandidateFeatures
from agnes.substitutes.embeddings import EmbeddingBackend, EmbeddingClient


class _StubBackend:
    """Deterministic, content-derived embedding backend for tests."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_batch(self, texts: list[str], model: str) -> list[list[float]]:
        self.calls.append(list(texts))
        out: list[list[float]] = []
        for t in texts:
            toks = sorted({c for c in t.lower() if c.isalpha()})
            vec = [1.0 if chr(ord("a") + i) in toks else 0.0 for i in range(26)]
            out.append(vec)
        return out


def _fixture_registry() -> CanonicalRegistry:
    mats = [
        CanonicalMaterial(
            raw_product_id=10,
            sku="RM-C1-calcium-citrate-x1",
            company_id=1,
            normalized_name="calcium citrate",
            canonical_key="calcium-citrate",
            ingredient_family="vitamin_mineral",
            functional_role="active_ingredient",
            confidence=0.9,
            missing_info=[],
            parse_ok=True,
            taxonomy_version="v1",
        ),
        CanonicalMaterial(
            raw_product_id=20,
            sku="RM-C2-calcium-lactate-x2",
            company_id=2,
            normalized_name="calcium lactate",
            canonical_key="calcium-lactate",
            ingredient_family="vitamin_mineral",
            functional_role="active_ingredient",
            confidence=0.9,
            missing_info=[],
            parse_ok=True,
            taxonomy_version="v1",
        ),
        CanonicalMaterial(
            raw_product_id=30,
            sku="RM-C1-magnesium-oxide-x3",
            company_id=1,
            normalized_name="magnesium oxide",
            canonical_key="magnesium-oxide",
            ingredient_family="vitamin_mineral",
            functional_role="active_ingredient",
            confidence=0.8,
            missing_info=[],
            parse_ok=True,
            taxonomy_version="v1",
        ),
        CanonicalMaterial(
            raw_product_id=40,
            sku="RM-C1-sodium-citrate-x4",
            company_id=1,
            normalized_name="sodium citrate",
            canonical_key="sodium-citrate",
            ingredient_family="acidulant",
            functional_role="ph_buffering",
            confidence=0.8,
            missing_info=[],
            parse_ok=True,
            taxonomy_version="v1",
        ),
    ]
    return CanonicalRegistry(
        taxonomy_version="v1",
        generated_at=datetime.now(UTC),
        unique_canonical_keys=len({m.canonical_key for m in mats}),
        coverage=RegistryCoverage(assigned=len(mats), unassigned=0, parse_failed=0),
        materials=mats,
    )


def _fixture_index(reg: CanonicalRegistry) -> MaterialGraphIndex:
    supplier_map = {
        "calcium-citrate": [1, 2],
        "calcium-lactate": [1, 3],
        "magnesium-oxide": [4],
        "sodium-citrate": [2],
    }
    nodes: list[KGNode] = []
    edges: list[KGEdge] = []
    for fam in {"vitamin_mineral", "acidulant"}:
        nodes.append(KGNode(id=node_id("IngredientFamily", fam), kind="IngredientFamily"))
    for role in {"active_ingredient", "ph_buffering"}:
        nodes.append(KGNode(id=node_id("FunctionalRole", role), kind="FunctionalRole"))
    for sid in {s for ss in supplier_map.values() for s in ss}:
        nodes.append(KGNode(id=node_id("Supplier", sid), kind="Supplier"))

    for m in reg.materials:
        cm = node_id("CanonicalMaterial", m.canonical_key)
        rp = node_id("RawProduct", m.raw_product_id)
        co = node_id("Company", m.company_id)
        fam = node_id("IngredientFamily", m.ingredient_family)
        role = node_id("FunctionalRole", m.functional_role)
        nodes.append(KGNode(id=cm, kind="CanonicalMaterial"))
        nodes.append(KGNode(id=rp, kind="RawProduct"))
        nodes.append(KGNode(id=co, kind="Company"))
        edges.append(KGEdge(source=rp, target=cm, kind="INSTANCE_OF"))
        edges.append(KGEdge(source=co, target=rp, kind="OWNS"))
        edges.append(KGEdge(source=cm, target=fam, kind="BELONGS_TO_FAMILY"))
        edges.append(KGEdge(source=cm, target=role, kind="HAS_ROLE"))
        for sid in supplier_map[m.canonical_key]:
            sp = node_id("Supplier", sid)
            edges.append(KGEdge(source=sp, target=rp, kind="OFFERS"))

    nodes_unique = list({n.id: n for n in nodes}.values())
    return MaterialGraphIndex.from_payload(nodes_unique, edges)


def _client(tmp_path: Path, backend: EmbeddingBackend) -> EmbeddingClient:
    return EmbeddingClient(
        Settings(openai_api_key="test-key"),
        model="stub-embed",
        cache_path=tmp_path / "phase4_embeddings.json",
        backend=backend,
    )


def test_embedding_cache_roundtrip(tmp_path: Path) -> None:
    backend = _StubBackend()
    client = _client(tmp_path, backend)
    v1 = client.get("calcium-citrate", "calcium citrate")
    v2 = client.get("calcium-citrate", "calcium citrate")
    assert v1 == v2
    assert len(backend.calls) == 1  # second call served from cache
    client.save()
    assert (tmp_path / "phase4_embeddings.json").is_file()


def test_in_family_candidates_ranked_by_score(tmp_path: Path) -> None:
    reg = _fixture_registry()
    idx = _fixture_index(reg)
    client = _client(tmp_path, _StubBackend())

    cands, diag = generate_candidates(
        target_key="calcium-citrate",
        registry=reg,
        graph_index=idx,
        embeddings=client,
        top_k=5,
        min_score=0.0,
        cross_family=False,
    )
    keys = [c.candidate_key for c in cands]
    assert keys == ["calcium-lactate", "magnesium-oxide"]
    assert diag.n_pool == 2
    assert diag.best_score == cands[0].score
    assert cands[0].score >= cands[1].score


def test_cross_family_allows_acidulant_candidate(tmp_path: Path) -> None:
    reg = _fixture_registry()
    idx = _fixture_index(reg)
    client = _client(tmp_path, _StubBackend())

    cands, _ = generate_candidates(
        target_key="calcium-citrate",
        registry=reg,
        graph_index=idx,
        embeddings=client,
        top_k=5,
        min_score=0.0,
        cross_family=True,
    )
    assert "sodium-citrate" in [c.candidate_key for c in cands]


def test_missing_family_reports_empty_reason(tmp_path: Path) -> None:
    reg = _fixture_registry()
    idx = _fixture_index(reg)
    client = _client(tmp_path, _StubBackend())

    cands, diag = generate_candidates(
        target_key="does-not-exist",
        registry=reg,
        graph_index=idx,
        embeddings=client,
        top_k=5,
        min_score=0.0,
        cross_family=False,
    )
    assert cands == []
    assert diag.reason == "no_family"


def test_deterministic_across_runs(tmp_path: Path) -> None:
    reg = _fixture_registry()
    idx = _fixture_index(reg)
    client_a = _client(tmp_path / "a", _StubBackend())
    client_b = _client(tmp_path / "b", _StubBackend())

    cands_a, _ = generate_candidates(
        target_key="calcium-citrate",
        registry=reg,
        graph_index=idx,
        embeddings=client_a,
        top_k=5,
        min_score=0.0,
        cross_family=False,
    )
    cands_b, _ = generate_candidates(
        target_key="calcium-citrate",
        registry=reg,
        graph_index=idx,
        embeddings=client_b,
        top_k=5,
        min_score=0.0,
        cross_family=False,
    )
    assert [c.model_dump() for c in cands_a] == [c.model_dump() for c in cands_b]


def _feats(*, family: bool, lex: float) -> CandidateFeatures:
    return CandidateFeatures(
        family_match=family,
        role_match=True,
        lexical_sim=lex,
        embed_sim=None,
        supplier_overlap=0.0,
        co_company_overlap=0.0,
        missing_signals=[],
    )


def test_substitution_type_direct() -> None:
    t, c = classify_substitution_type("a", "a", _feats(family=True, lex=0.9))
    assert (t, c) == ("direct", 1.0)


def test_substitution_type_variant_when_family_match_and_high_lex() -> None:
    t, c = classify_substitution_type("a-b", "a-c", _feats(family=True, lex=0.5))
    assert t == "variant"
    assert c == 0.75


def test_substitution_type_functional_when_family_match_but_low_lex() -> None:
    t, c = classify_substitution_type("a", "b", _feats(family=True, lex=0.1))
    assert (t, c) == ("functional", 0.5)


def test_substitution_type_low_confidence_cross_family() -> None:
    t, c = classify_substitution_type("a", "b", _feats(family=False, lex=0.1))
    assert (t, c) == ("functional", 0.25)


def test_generate_candidates_attaches_substitution_type(tmp_path: Path) -> None:
    reg = _fixture_registry()
    idx = _fixture_index(reg)
    client = _client(tmp_path, _StubBackend())

    cands, _ = generate_candidates(
        target_key="calcium-citrate",
        registry=reg,
        graph_index=idx,
        embeddings=client,
        top_k=5,
        min_score=0.0,
        cross_family=True,
    )
    assert cands
    for cand in cands:
        assert cand.substitution_type in {"direct", "variant", "functional"}
        assert 0.0 <= cand.type_confidence <= 1.0


@pytest.mark.parametrize("embeddings_enabled", [True, False])
def test_candidate_generator_without_embeddings(tmp_path: Path, embeddings_enabled: bool) -> None:
    reg = _fixture_registry()
    idx = _fixture_index(reg)
    client = _client(tmp_path, _StubBackend()) if embeddings_enabled else None

    cands, _ = generate_candidates(
        target_key="calcium-citrate",
        registry=reg,
        graph_index=idx,
        embeddings=client,
        top_k=5,
        min_score=0.0,
        cross_family=False,
    )
    assert cands, "pool should not be empty"
    for c in cands:
        if embeddings_enabled:
            assert c.features.embed_sim is not None
            assert c.embedding_model == "stub-embed"
        else:
            assert c.features.embed_sim is None
            assert "embed" in c.features.missing_signals
