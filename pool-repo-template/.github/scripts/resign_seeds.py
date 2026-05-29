#!/usr/bin/env python3
"""Re-sign the pool seed learnings under the CURRENT signing scheme.

The seed `.md` files carry a content-addressed id (the BLAKE3 hash of the
content) plus an Ed25519 signature. The id depends only on the *content*, so it
never changes here — but whenever the signing-message scheme changes (e.g. when
we started binding the signer's own public key into the signed root), old
signatures stop verifying and must be regenerated.

This script reads each seed, preserves its content verbatim (so the id and
filename are unchanged), and re-signs it with a freshly generated "komi-pool
seed" contributor key in the multi-signature envelope format. Run it from the
repo root after any signing-scheme change:

    python .github/scripts/resign_seeds.py

It requires the komi-learn package on the path (run it from the code repo, which
vendors the seeds under pool-repo-template/). The generated private key is NOT
written anywhere — only the public key + signature land in the `.md`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# resolve the komi-learn package (this script lives in pool-repo-template/.github/scripts)
_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from komi.engine.model import Learning  # noqa: E402
from komi.pool.identity import Contributor  # noqa: E402
from komi.pool.contribute import prepare_contribution  # noqa: E402
from komi.pool.repo_format import render_md, parse_md, repo_path_for  # noqa: E402


def main() -> int:
    import tempfile

    seeds_root = Path(__file__).resolve().parents[2] / "learnings"
    files = sorted(seeds_root.rglob("*.md"))
    if not files:
        print("no seed files found")
        return 1

    # One stable seed identity for all template seeds (a single "official" endorser).
    with tempfile.TemporaryDirectory() as kd:
        signer = Contributor(Path(kd) / "seed-key")
        if signer.algo != "ed25519":
            print("ERROR: PyNaCl not installed — cannot produce real signatures.")
            return 2

        for f in files:
            env = parse_md(f.read_text(encoding="utf-8"))
            if env is None:
                print(f"skip (unparseable): {f}")
                continue
            rec = env["learning"]
            # rebuild a Learning from the existing content (id recomputed → must match)
            lng = Learning.from_dict(rec)
            lng.provenance.origin = rec.get("provenance", {}).get("origin", "agent:unknown")
            lng.finalize()  # recompute id from content; unchanged for unchanged content
            if lng.id != rec["id"]:
                print(f"ERROR: id changed for {f.name} ({rec['id']} -> {lng.id}); content drift?")
                return 3

            result = prepare_contribution(lng, signer)
            if not result.ok:
                print(f"ERROR: could not sign {f.name}: {result.reason}")
                return 4
            new_md = render_md(result.envelope)
            # path is content-addressed → must equal the existing path
            expected = repo_path_for(result.envelope)
            actual = f.relative_to(seeds_root.parent).as_posix()
            if expected != actual:
                print(f"ERROR: path mismatch for {f.name}: expected {expected}, at {actual}")
                return 5
            f.write_text(new_md, encoding="utf-8")
            print(f"re-signed: {actual}  (signer {signer.public_key[:16]}…)")

    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
