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
"""

from __future__ import annotations

from typing import Callable, Optional


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
        for s in raw:
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
    :func:`envelope_signatures`)."""
    learning = envelope.get("learning", {})
    n = 0
    for s in envelope_signatures(envelope):
        pk, sig = s["public_key"], s["signature"]
        if not sig:
            continue
        if verify(sign_message(learning, pk), sig, pk):
            n += 1
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


__all__ = ["envelope_signatures", "count_corroboration", "merge_signature"]
