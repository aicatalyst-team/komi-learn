"""Phase 5 leftover — embedding-based clustering in the curator.

The lexical clustering (shared title-word / tag) misses learnings that overlap in
MEANING but not surface form. With an embedding model, the curator clusters by
cosine similarity instead, catching those — better umbrella detection.

Uses a deterministic MOCK embedder (bag-of-words over a fixed vocab) so the tests
are offline and assert exact clustering behavior. Covers:
  • semantic clustering groups a lexically-distinct but conceptually-related pair
    that lexical clustering would NOT group,
  • the threshold keeps genuinely-unrelated learnings apart,
  • clustering is deterministic (stable across runs / input order),
  • no embedder => lexical fallback is unchanged,
  • a degenerate embedder (empty vectors) falls back to lexical, never crashes,
  • curate() reports which mode it used and consolidates semantic clusters.
"""

import math

import pytest

from komi.engine.store import Store
from komi.engine import embed as embed_mod
from komi.engine.model import Learning, LearningType, Category, Scope
from komi.engine.curator import (
    cluster, curate, _cluster_lexical, DEFAULT_CLUSTER_THRESHOLD, MIN_CLUSTER_SIZE,
)


# ── deterministic mock embedders ─────────────────────────────────────────────

# Vocab chosen so two phrasings of "fast code search" share the CONCEPT words
# (search, fast, code) even though their tool names (ripgrep / silver-searcher)
# differ — exactly the lexically-distinct-but-related case lexical clustering misses.
_VOCAB = ["search", "fast", "code", "ripgrep", "silver", "test", "rerun",
          "failure", "pytest", "traceback", "debug", "python", "css", "layout"]


class MockEmbedder:
    version = "mock/1"
    dim = len(_VOCAB)

    def encode(self, text: str) -> list[float]:
        t = (text or "").lower()
        vec = [float(t.count(w)) for w in _VOCAB]
        n = math.sqrt(sum(x * x for x in vec))
        return [x / n for x in vec] if n else vec


class EmptyEmbedder:
    """Simulates a model that loaded but returns nothing (degenerate) — clustering
    must fall back to lexical, never raise."""
    version = "empty/1"
    dim = 0

    def encode(self, text: str) -> list[float]:
        return []


def P(title, body="", trigger="", tags=None, conf=0.5):
    return Learning(type=LearningType.PROCEDURAL.value, category=Category.TOOLING.value,
                    title=title, body=body or title, trigger=trigger, tags=tags or [],
                    scope=Scope.PERSONAL.value, confidence=conf).finalize()


# the related pair: NO shared significant title word, DIFFERENT tags
RG = P("Prefer ripgrep over grep", "fast code search that respects ignores",
       "search code", ["ripgrep"])
AG = P("Use the silver searcher", "fast code search tool", "search code", ["silver"])
# unrelated
TRACE = P("Read tracebacks", "python traceback debug bottom up", "debug", ["python"])
CSS = P("Use flexbox", "css layout", "layout", ["css"])


# ── semantic clustering catches what lexical misses ──────────────────────────

def test_lexical_misses_the_related_pair():
    # sanity: with no shared title word/tag, lexical clustering does NOT group rg+ag
    assert _cluster_lexical([RG, AG]) == []


def test_semantic_groups_the_related_pair():
    clusters = cluster([RG, AG], embedder=MockEmbedder())
    assert len(clusters) == 1
    ids = {m.id for m in clusters[0].members}
    assert ids == {RG.id, AG.id}


def test_semantic_keeps_unrelated_apart():
    # rg/ag are related to each other; traceback + css are unrelated to everything
    clusters = cluster([RG, AG, TRACE, CSS], embedder=MockEmbedder())
    # exactly one cluster (rg+ag); traceback and css don't reach threshold with anyone
    assert len(clusters) == 1
    assert {m.id for m in clusters[0].members} == {RG.id, AG.id}


def test_semantic_threshold_respected(monkeypatch):
    # raise the threshold above the rg/ag similarity → they no longer cluster
    sim = embed_mod.cosine(MockEmbedder().encode("fast code search ripgrep"),
                           MockEmbedder().encode("fast code search silver"))
    assert 0 < sim < 1
    high = cluster([RG, AG], embedder=MockEmbedder(), threshold=min(0.99, sim + 0.05))
    assert high == []
    low = cluster([RG, AG], embedder=MockEmbedder(), threshold=max(0.0, sim - 0.05))
    assert len(low) == 1


# ── determinism ──────────────────────────────────────────────────────────────

def test_semantic_clustering_is_deterministic():
    a = cluster([RG, AG, TRACE], embedder=MockEmbedder())
    b = cluster([TRACE, AG, RG], embedder=MockEmbedder())   # different input order
    keyset = lambda cs: sorted(tuple(sorted(m.id for m in c.members)) for c in cs)
    assert keyset(a) == keyset(b)


# ── fallbacks ────────────────────────────────────────────────────────────────

def test_no_embedder_uses_lexical():
    # two learnings sharing a tag cluster lexically with NO embedder
    x = P("Alpha trick", tags=["shared"])
    y = P("Beta trick", tags=["shared"])
    clusters = cluster([x, y])                  # embedder defaults to None
    assert len(clusters) == 1
    assert {m.id for m in clusters[0].members} == {x.id, y.id}


def test_empty_embedder_falls_back_to_lexical():
    # degenerate embedder → fall back; the lexically-distinct pair won't group,
    # but a tag-sharing pair still will (proving we used the lexical path)
    x = P("Alpha", tags=["shared"])
    y = P("Beta", tags=["shared"])
    assert cluster([RG, AG], embedder=EmptyEmbedder()) == []      # lexical misses rg/ag
    assert len(cluster([x, y], embedder=EmptyEmbedder())) == 1    # lexical catches tag


# ── end-to-end through curate() ──────────────────────────────────────────────

def _mock_consolidator(members):
    return {"title": "Fast code search (umbrella)",
            "body": "Use a fast, ignore-aware searcher (ripgrep / ag) for code search.",
            "trigger": "searching code", "tags": ["search"], "rationale": "same task"}


def test_curate_semantic_mode_consolidates(tmp_path):
    s = Store(tmp_path)
    s.upsert(RG)
    s.upsert(AG)
    rep = curate(s, consolidator=_mock_consolidator, embedder=MockEmbedder())
    assert rep.cluster_mode == "semantic"
    assert len(rep.consolidated) == 1
    # both originals folded into the umbrella (archived, not deleted)
    states = {l.id: l.lifecycle.state for l in s.all()}
    assert states.get(RG.id) == "archived" and states.get(AG.id) == "archived"
    assert any(l.title.startswith("Fast code search") and l.lifecycle.state == "active"
               for l in s.all())


def test_curate_reports_lexical_mode_without_embedder(tmp_path, monkeypatch):
    # Force "no model installed" so curate()'s auto-resolution yields None and it
    # uses the lexical fallback (on a dev box the real model may be present).
    embed_mod._reset_cache_for_tests()
    monkeypatch.setattr(embed_mod, "get_embedder", lambda: None)
    s = Store(tmp_path)
    s.upsert(P("Alpha", tags=["shared"]))
    s.upsert(P("Beta", tags=["shared"]))
    rep = curate(s, consolidator=None)          # embedder auto-resolves to None
    assert rep.cluster_mode == "lexical"
    assert len(rep.clusters) == 1
    embed_mod._reset_cache_for_tests()


def test_default_threshold_is_sane():
    # guard the calibrated default: between the unrelated ceiling and 1.0
    assert 0.2 < DEFAULT_CLUSTER_THRESHOLD < 0.9


# ── mutual-similarity rule (no star-cluster false positives) ─────────────────

class StarEmbedder:
    """Three items where the SEED is similar to A and to B, but A and B are NOT
    similar to each other. Seed-anchored clustering would wrongly merge all three
    (and archive them); mutual-similarity must refuse to put A and B together."""
    version = "star/1"
    dim = 3
    _V = {  # near-orthogonal A & B; seed sits between them, ~0.7 to each
        "seed": [0.7071, 0.7071, 0.0],
        "a":    [1.0, 0.0, 0.0],
        "b":    [0.0, 1.0, 0.0],
    }

    def encode(self, text):
        t = (text or "").lower()
        for k, v in self._V.items():
            if k in t:
                return list(v)
        return [0.0, 0.0, 1.0]


def test_mutual_similarity_blocks_star_false_positive():
    seed = P("seed item", "seed", "x", [])
    a = P("a item", "a", "x", [])
    b = P("b item", "b", "x", [])
    # seed~a ≈ seed~b ≈ 0.707 (≥ a 0.58 threshold) but a~b = 0 (< threshold)
    clusters = cluster([seed, a, b], embedder=StarEmbedder(), threshold=0.58)
    # mutual-similarity: seed pairs with whichever comes first by id, but a+b can't
    # both join (they're orthogonal). So no cluster contains all three.
    for c in clusters:
        ids = {m.id for m in c.members}
        assert not ({a.id, b.id} <= ids), "star FP: orthogonal a & b merged together"


# ── real-model eval (the regression guard the miscalibration needed) ─────────

@pytest.mark.skipif(not embed_mod.available(),
                    reason="real embedding model not installed (smart extra)")
def test_real_model_threshold_separates_labeled_set():
    """Pins the threshold against the REAL model on a labeled set of procedural
    pairs. This is the test the original 0.45 miscalibration was missing: the mock
    embedder cannot exhibit the real failure (distinct same-domain skills scoring
    high). If the model or the chosen threshold drifts so that a SHOULD-NOT-MERGE
    pair would cluster (or an easy SHOULD-MERGE pair wouldn't), this fails loudly.

    Labeled, with measured cosines (all-MiniLM-L6-v2, curator's _embed_text join):
      SHOULD merge:    two pytest tips 0.76, git rebase rephrased 0.74
      SHOULD NOT merge: pytest -k vs -x 0.55, rg vs git-bisect ~0.33, pytest vs css <0
    The weak "different tool, same task" pairs (rg/ag 0.37, venv/poetry 0.47) are
    intentionally NOT asserted as merges — precision bias accepts missing them.
    """
    from komi.engine import embed
    from komi.engine.curator import _embed_text, DEFAULT_CLUSTER_THRESHOLD
    th = DEFAULT_CLUSTER_THRESHOLD

    def cos(a, b):
        return embed.cosine(embed.get_embedder().encode(_embed_text(a)),
                            embed.get_embedder().encode(_embed_text(b)))

    should_merge = [
        (P("Run only failed tests", "pytest --lf reruns last failures fast.",
           "rerunning tests", ["pytest"]),
         P("Stop at first failure", "pytest -x halts on the first failing test.",
           "debugging a failing suite", ["pytest"])),
        (P("Rebase to keep history linear", "git rebase main avoids merge commits.",
           "integrating a branch", ["git"]),
         P("Prefer rebase over merge", "rebasing keeps a clean linear log.",
           "updating a feature branch", ["git"])),
    ]
    must_not_merge = [
        (P("Filter tests by name", "pytest -k EXPR selects tests matching a substring.",
           "running a subset of tests", ["pytest"]),
         P("Stop at first failure", "pytest -x halts on the first failing test.",
           "debugging a failing suite", ["pytest"])),
        (P("Prefer ripgrep over grep -r", "rg is faster on big trees.",
           "code search", ["ripgrep"]),
         P("Find a regression with git bisect", "git bisect binary-searches commits.",
           "locating a regression", ["git"])),
        (P("Run only failed tests", "pytest --lf reruns failures.",
           "rerunning tests", ["pytest"]),
         P("Use flexbox for layout", "display:flex aligns items easily.",
           "laying out a page", ["css"])),
    ]
    # every clear should-merge pair is at/above threshold
    for a, b in should_merge:
        assert cos(a, b) >= th, f"regression: {a.title!r}~{b.title!r}={cos(a,b):.3f} < {th}"
    # no should-not-merge pair reaches threshold (the costly false positives)
    for a, b in must_not_merge:
        assert cos(a, b) < th, f"FALSE MERGE risk: {a.title!r}~{b.title!r}={cos(a,b):.3f} >= {th}"
