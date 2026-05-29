"""komi-learn pool — corroboration: counting distinct, independent endorsements.

A signed learning is *verified* (its signature is valid and its content matches
its content-addressed id), but verification alone says nothing about whether the
lesson is any *good*. Corroboration is the trust signal that does: how many
**distinct contributors** independently arrived at — and signed — the *same*
content.

Why this is mechanically sound. The id is the BLAKE3 hash of the content, so two
people who independently distill the same lesson produce the *same file*. Each
contributor signs a message that binds the content id **and their own public
key** (see :func:`..contribute._signing_message`), so a signature can't be
replayed under another identity. Therefore "N distinct public keys each produced
a valid signature over this content + their own identity" genuinely means N
independent parties vouched for it — not one party replaying one signature.

The corroboration count is a *transient* property computed at pull time. It is
deliberately NOT part of the content view (and so not part of the id): the same
lesson must hash identically no matter how many people have signed it, or
corroboration would fork the very files it's meant to merge.

This module is the single source of truth for "extract the distinct valid
signers from an envelope". The vendored CI verifier mirrors this logic; a parity
test guards the two against drift.

⚠️ Trust limitation (read before relying on the count). A contributor key is an
Ed25519 keypair generated locally for free — it is NOT bound to any real-world or
GitHub identity. So "N distinct public keys" is a proxy for "N independent people"
that a single attacker can defeat by minting N keys and signing the same content
under each (a Sybil attack). Until signer↔account binding exists (planned: enforce
it at the pool's CI boundary, Phase 7), corroboration is treated as a *soft,
advisory* signal, NOT a hard trust gate:
  • the counted value is CLAMPED to ``MAX_COUNTED_SIGNERS`` so a flood of fake keys
    cannot manufacture a runaway "×50 experts agree" cue, and
  • recall only ever *down-weights/filters* on corroboration, never *admits*
    untrusted content it would otherwise exclude.
See docs/05-adr-log.md ADR-9.
"""

from __future__ import annotations

from typing import Callable, Optional

# Hard upper bound on signature-array entries we will even look at. A real learning
# accrues a handful of independent endorsers; thousands is either abuse or a DoS
# (each entry forces an Ed25519 verify). Bounding here protects every consumer AND
# the CI verifier (mirrored in verify.py). Generous for legitimate use, lethal to a flood.
MAX_SIGNATURES = 64

# Cap on the corroboration level we will COUNT/report. Because keys are free to mint
# (see the trust-limitation note above), more signatures past a small number is not
# more evidence of independence — so we refuse to count it as such. 3 distinct valid
# signers is plenty to mark a lesson "independently corroborated"; beyond that adds no
# trust until real identity binding lands. Mirrored in verify.py.
MAX_COUNTED_SIGNERS = 3


def envelope_signatures(envelope: dict) -> list[dict]:
    """Normalize an envelope's signatures into a list of ``{algo, public_key,
    signature}`` dicts, regardless of format version.

    Accepts both shapes, so old files and the live pool need no migration:

      • new: a top-level ``signatures: [{algo, public_key, signature}, ...]``
      • legacy: a single ``signer: {algo, public_key}`` +
        ``learning.provenance.signature``  → treated as signatures[0]

    If both are present we trust ``signatures`` (it is the superset; by
    construction its first entry mirrors the legacy fields). De-dupes by public
    key, keeping first occurrence, so a malformed file that lists the same key
    twice can't inflate its own corroboration.
    """
    out: list[dict] = []
    seen: set[str] = set()

    raw = envelope.get("signatures")
    if isinstance(raw, list) and raw:
        # Bound the work: only inspect the first MAX_SIGNATURES entries so a padded
        # array can't turn signature verification into a CPU-DoS (anti-flood).
        for s in raw[:MAX_SIGNATURES]:
            if not isinstance(s, dict):
                continue
            pk = s.get("public_key") or ""
            if not pk or pk in seen:
                continue
            seen.add(pk)
            out.append({
                "algo": s.get("algo", "unsigned"),
                "public_key": pk,
                "signature": s.get("signature") or "",
            })
        return out

    # legacy single-signer shape
    signer = envelope.get("signer", {}) or {}
    pk = signer.get("public_key") or ""
    sig = (envelope.get("learning", {}).get("provenance", {}) or {}).get("signature") or ""
    if pk:
        out.append({"algo": signer.get("algo", "unsigned"),
                    "public_key": pk, "signature": sig})
    return out


def count_corroboration(
    envelope: dict,
    *,
    sign_message: Callable[[dict, str], bytes],
    verify: Callable[[bytes, str, str], bool],
) -> int:
    """Number of DISTINCT contributors with a VALID signature over this learning.

    ``sign_message(learning, public_key)`` rebuilds the exact bytes that signer
    would have signed (content id + parents + origin + that signer's own key).
    ``verify(message, signature_b64, public_key_b64)`` checks one Ed25519
    signature. Both are injected so this module stays free of crypto/engine
    imports and the CI verifier can pass its own equivalents.

    A signature that doesn't verify (wrong key, tampered content, unsigned)
    simply doesn't count — it can't drag the level down, but it can't pad it up
    either. Distinctness is by public key (already de-duped by
    :func:`envelope_signatures`).

    The result is CLAMPED to :data:`MAX_COUNTED_SIGNERS`: because keys are free to
    mint, counting past a small number would let a Sybil flood fabricate trust (see
    the module docstring). We stop verifying once the clamp is reached — also a
    short-circuit that bounds work."""
    learning = envelope.get("learning", {})
    n = 0
    for s in envelope_signatures(envelope):
        pk, sig = s["public_key"], s["signature"]
        if not sig:
            continue
        if verify(sign_message(learning, pk), sig, pk):
            n += 1
            if n >= MAX_COUNTED_SIGNERS:
                break
    return n


def merge_signature(envelope: dict, new_sig: dict) -> Optional[dict]:
    """Return a copy of ``envelope`` with ``new_sig`` appended to its signatures,
    or ``None`` if that signer already endorses it (a true no-op).

    ``new_sig`` is ``{algo, public_key, signature}``. The result always carries an
    explicit ``signatures`` array (upgrading a legacy file in place) and keeps the
    legacy ``signer`` / ``provenance.signature`` fields pointed at signatures[0]
    for human-readable diffs and old readers."""
    existing = envelope_signatures(envelope)
    pk = new_sig.get("public_key") or ""
    if not pk:
        return None
    if any(s["public_key"] == pk for s in existing):
        return None  # already corroborated by this signer

    merged = dict(envelope)
    sigs = existing + [{
        "algo": new_sig.get("algo", "unsigned"),
        "public_key": pk,
        "signature": new_sig.get("signature") or "",
    }]
    merged["signatures"] = sigs
    # keep legacy mirror fields aligned to the primary signer (signatures[0])
    primary = sigs[0]
    merged["signer"] = {"algo": primary["algo"], "public_key": primary["public_key"]}
    learning = dict(merged.get("learning", {}))
    prov = dict(learning.get("provenance", {}) or {})
    prov["signature"] = primary["signature"] or None
    learning["provenance"] = prov
    merged["learning"] = learning
    return merged


__all__ = ["envelope_signatures", "count_corroboration", "merge_signature",
           "MAX_SIGNATURES", "MAX_COUNTED_SIGNERS"]
