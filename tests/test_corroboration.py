"""Phase 5b — corroboration-based trust.

Corroboration = how many DISTINCT contributors independently signed the SAME
content-addressed learning. These tests cover the whole path:

  • counting distinct VALID signers (and rejecting bogus/duplicate ones)
  • appending a second signer to an existing file (merge_signature)
  • the min_corroboration gate in pull (stubbed + GitHub-backed local)
  • the .md render/parse round-trip carrying a signatures array
  • recall ranking: a well-corroborated pool item beats an equally-relevant
    single-signer one, but corroboration never overrides relevance
  • parity: the vendored CI verifier counts corroboration like the engine

Runs fully offline. Signature tests are skipped automatically if PyNaCl is
absent (unsigned mode) — there's nothing to verify there.
"""

import copy
import importlib.util
import tempfile
from pathlib import Path

import pytest

from komi.engine.model import Learning, LearningType, Category, Scope
from komi.engine.store import Store
from komi.engine.recall import _rank_score
from komi.pool.identity import Contributor
from komi.pool import contribute as C
from komi.pool import corroboration as corro
from komi.pool.repo_format import render_md, parse_md
from komi.pool.github_backend import GitHubPool, PoolConfig


def _detect_nacl() -> bool:
    with tempfile.TemporaryDirectory() as d:
        return Contributor(Path(d) / "probe").algo == "ed25519"


HAVE_NACL = _detect_nacl()
needs_nacl = pytest.mark.skipif(not HAVE_NACL, reason="PyNaCl not installed (unsigned mode)")


def _learning(**kw) -> Learning:
    base = dict(type=LearningType.PROCEDURAL.value, category=Category.TOOLING.value,
                title="Prefer rg over grep -r", body="ripgrep is faster and respects .gitignore.",
                trigger="code search", tags=["ripgrep"], scope=Scope.GLOBAL.value)
    base.update(kw)
    return Learning(**base).finalize()


def _envelope(c: Contributor, lng: Learning) -> dict:
    """A signed envelope from one contributor (signatures array, length 1)."""
    return C.prepare_contribution(lng, c).envelope


def _co_sign(envelope: dict, c2: Contributor) -> dict:
    """Produce the signature a SECOND contributor would make over the same learning
    and merge it in — exactly what publish() does on an already-present file."""
    pub = envelope["learning"]
    msg = C._signing_message(pub, signer_public_key=c2.public_key)
    sig = c2.sign(msg)
    new_sig = {"algo": c2.algo, "public_key": c2.public_key, "signature": sig}
    return corro.merge_signature(envelope, new_sig)


# ── distinct-signer counting ─────────────────────────────────────────────────

@needs_nacl
def test_single_signer_corroboration_is_one(tmp_path):
    c = Contributor(tmp_path / "k")
    rep = C.ingest_verify(_envelope(c, _learning()), require_signature=True)
    assert rep.accepted and rep.corroboration == 1


@needs_nacl
def test_two_distinct_signers_corroboration_is_two(tmp_path):
    c1, c2 = Contributor(tmp_path / "k1"), Contributor(tmp_path / "k2")
    env = _co_sign(_envelope(c1, _learning()), c2)
    rep = C.ingest_verify(env, require_signature=True)
    assert rep.accepted and rep.corroboration == 2
    # both legacy mirror + array agree on the primary signer
    assert env["signer"]["public_key"] == c1.public_key
    assert {s["public_key"] for s in env["signatures"]} == {c1.public_key, c2.public_key}


@needs_nacl
def test_same_signer_twice_does_not_inflate(tmp_path):
    c1 = Contributor(tmp_path / "k1")
    env = _envelope(c1, _learning())
    # a second endorsement by the SAME signer is a no-op (merge returns None)
    assert _co_sign(env, c1) is None
    # and even a hand-crafted duplicate entry is de-duped to corroboration 1
    env2 = copy.deepcopy(env)
    env2["signatures"] = env2["signatures"] + env2["signatures"]
    assert C.ingest_verify(env2, require_signature=True).corroboration == 1


@needs_nacl
def test_bogus_signature_does_not_count(tmp_path):
    c1, c2 = Contributor(tmp_path / "k1"), Contributor(tmp_path / "k2")
    env = _co_sign(_envelope(c1, _learning()), c2)
    # corrupt the second signer's signature → only the first counts
    env["signatures"][1]["signature"] = "AAAA" + env["signatures"][1]["signature"][4:]
    rep = C.ingest_verify(env, require_signature=True)
    assert rep.corroboration == 1


# ── min_corroboration gate ───────────────────────────────────────────────────

@needs_nacl
def test_pull_gate_filters_below_threshold(tmp_path):
    c1, c2 = Contributor(tmp_path / "k1"), Contributor(tmp_path / "k2")
    outbox = tmp_path / "outbox"
    # one single-signer learning, one two-signer learning
    single = _envelope(c1, _learning(title="single", body="a lone tip about tmux splits"))
    pair = _co_sign(_envelope(c1, _learning(title="pair", body="a corroborated tip about vim")), c2)
    C.publish(single, outbox)
    C.publish(pair, outbox)

    all_pulled = C.pull(outbox, require_signature=True, min_corroboration=1)
    assert {l.title for l in all_pulled} == {"single", "pair"}
    assert {l.title: l.corroboration for l in all_pulled} == {"single": 1, "pair": 2}

    only_corroborated = C.pull(outbox, require_signature=True, min_corroboration=2)
    assert [l.title for l in only_corroborated] == ["pair"]


@needs_nacl
def test_github_pull_attaches_corroboration_and_gates(tmp_path):
    """End-to-end on the real GitHubPool (local mode): a second contributor's
    publish() APPENDS a signature to the same file, raising its corroboration."""
    cache = tmp_path / "repo"
    pool = GitHubPool(PoolConfig(cache_dir=str(cache), mode="local", branch="main",
                                 require_signature=True, min_corroboration=1))
    c1, c2 = Contributor(tmp_path / "k1"), Contributor(tmp_path / "k2")
    lng = _learning()

    r1 = pool.publish(_envelope(c1, lng))
    assert r1.ok and r1.extra.get("action") == "learn"
    # second contributor independently distills + signs the same lesson
    r2 = pool.publish(_envelope(c2, lng))
    assert r2.ok and r2.extra.get("action") == "corroborate"
    # a third publish by c1 again is a true no-op
    r3 = pool.publish(_envelope(c1, lng))
    assert r3.ok and r3.extra.get("noop") is True

    pulled = pool.pull()
    assert len(pulled) == 1 and pulled[0].corroboration == 2

    # raising the gate to 3 now filters it out
    pool.cfg.min_corroboration = 3
    assert pool.pull() == []


# ── .md round-trip with a signatures array ───────────────────────────────────

@needs_nacl
def test_render_parse_roundtrip_preserves_signatures(tmp_path):
    c1, c2 = Contributor(tmp_path / "k1"), Contributor(tmp_path / "k2")
    env = _co_sign(_envelope(c1, _learning()), c2)
    md = render_md(env)
    assert "corroborated" in md.lower()                 # human header shows it
    parsed = parse_md(md)
    assert C.ingest_verify(parsed, require_signature=True).corroboration == 2


# ── recall ranking bonus ─────────────────────────────────────────────────────

def test_rank_corroboration_breaks_ties_for_community():
    """Equal relevance/recency/confidence: the more-corroborated pool item ranks
    higher. A personal item (corroboration 1) gets no bonus."""
    base = dict(reused=0, confidence=0.5, updated_at="", scope="global")
    low = {**base, "corroboration": 1}
    high = {**base, "corroboration": 5}
    assert _rank_score(high, 0.5) > _rank_score(low, 0.5)


def test_rank_corroboration_never_overrides_relevance():
    """A highly-corroborated but IRRELEVANT item must not outrank a highly-relevant
    one. The bonus is a tie-breaker, capped well below the relevance weight."""
    relevant = {"reused": 0, "confidence": 0.5, "updated_at": "", "scope": "global",
                "corroboration": 1}
    corroborated_irrelevant = {"reused": 0, "confidence": 0.5, "updated_at": "",
                               "scope": "global", "corroboration": 50}
    assert _rank_score(relevant, 0.95) > _rank_score(corroborated_irrelevant, 0.10)


def test_store_carries_corroboration_into_index(tmp_path):
    """mirror_external must persist the corroboration count so recall can read it."""
    s = Store(tmp_path)
    g = _learning()
    g.corroboration = 4
    s.mirror_external([g], source="pool")
    row = next(r for r in s.rows() if r["id"] == g.id)
    assert row["corroboration"] == 4


# ── CI parity: vendored verifier counts corroboration like the engine ─────────

def _load_vendored_verify():
    p = (Path(__file__).resolve().parents[1]
         / "pool-repo-template" / ".github" / "scripts" / "verify.py")
    spec = importlib.util.spec_from_file_location("vendored_verify_corro", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@needs_nacl
def test_template_seed_files_still_verify():
    """Guard against seed-signature rot: every seed `.md` shipped in the pool
    template must validate under the current scheme. This is exactly what a fresh
    pool's CI runs on its first commit — if it's red here, new pools ship broken.
    (Signing-scheme changes require re-running .github/scripts/resign_seeds.py.)"""
    seeds = (Path(__file__).resolve().parents[1] / "pool-repo-template" / "learnings")
    files = sorted(seeds.rglob("*.md"))
    assert files, "no template seed files found"
    for f in files:
        env = parse_md(f.read_text(encoding="utf-8"))
        assert env is not None, f"unparseable seed: {f.name}"
        rep = C.ingest_verify(env, require_signature=True)
        assert rep.accepted, f"seed {f.name} fails verification: {rep.reasons}"
        assert rep.corroboration >= 1


@needs_nacl
def test_vendored_corroboration_matches_engine(tmp_path):
    v = _load_vendored_verify()
    c1, c2 = Contributor(tmp_path / "k1"), Contributor(tmp_path / "k2")
    env = _co_sign(_envelope(c1, _learning()), c2)

    # same distinct-signer normalization
    assert v.envelope_signatures(env) == corro.envelope_signatures(env)
    # same valid-signer count, via the vendored crypto
    valid, problems = v.signature_problems(env)
    assert valid == 2 and not problems
    # a bogus signature is a hard failure in CI (must never carry an invalid sig)
    env["signatures"][1]["signature"] = "AAAA" + env["signatures"][1]["signature"][4:]
    valid2, problems2 = v.signature_problems(env)
    assert valid2 == 1 and problems2     # one still valid, but the bad one is reported
