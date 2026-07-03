#!/usr/bin/env python3
"""Build and sign the MLP Classifier plugin into a distributable ``.ciarenplugin``.

Run from anywhere (needs Ciaren installed):

    python examples/plugins/build_mlp_classifier_ciarenplugin.py

It regenerates the plugin's ``ciaren-plugin.json`` from the code (single source of
truth), packs ``mlp-classifier-plugin/`` into
``dist/community.mlp-classifier-<version>.ciarenplugin``, signs it with the **demo**
key below, and copies it into the bundled Explore catalog so a fresh install lists it
next to the Hello plugin, ready to install.

The key here is the same throwaway DEMO key the Hello plugin uses — committed on
purpose so anyone can reproduce the signed artifact. A real publisher keeps their
private key secret (``ciaren-plugin keygen``) and never commits it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from app.plugins.marketplace import add_to_index_file
from app.plugins.package import pack_directory, read_manifest, sign_package, verify_package

# DEMO ONLY — do not use this key for real plugins. Same key as the Hello example.
DEMO_PRIVATE_KEY = "71e08038bfe55013640eb49a0f7faeaf5fd99bae76654217a67987e71cc4fb5b"
DEMO_PUBLIC_KEY = "b827f3795467a701b018a0d57ab5900af43669d3622340905559d86ae2ec4bdd"
DEMO_KEY_ID = "ciaren-demo"

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SRC = HERE / "mlp-classifier-plugin"
DIST = HERE / "dist"
BUNDLED = ROOT / "backend" / "app" / "bundled_plugins"
ENTRYPOINT = "ciaren_mlp.plugin:MlpClassifierPlugin"


def main() -> None:
    # Regenerate the manifest from the plugin code so it can never drift.
    subprocess.run(
        [sys.executable, "-m", "app.cli", "plugin", "manifest", str(SRC), "--entrypoint", ENTRYPOINT],
        check=True,
    )

    manifest = read_manifest_from_dir(SRC)
    out = DIST / f"{manifest.id}-{manifest.version}.ciarenplugin"
    DIST.mkdir(parents=True, exist_ok=True)

    pack_directory(SRC, out)
    sig = sign_package(out, DEMO_PRIVATE_KEY, key_id=DEMO_KEY_ID, publisher="community")

    result = verify_package(out, trusted_keys={DEMO_KEY_ID: DEMO_PUBLIC_KEY})
    BUNDLED.mkdir(parents=True, exist_ok=True)
    bundled_out = BUNDLED / out.name
    shutil.copy2(out, bundled_out)
    add_to_index_file(BUNDLED / "marketplace.json", bundled_out)

    # Sanity: the bundled package still reads its manifest and verifies as trusted.
    assert read_manifest(bundled_out).id == manifest.id
    print(f"Built  {out.relative_to(ROOT)}")
    print(f"Bundled {bundled_out.relative_to(ROOT)}")
    print(f"Digest {sig.digest}")
    print(f"Verify {result.outcome} ({result.reason})")
    print("\nTrust this demo key to verify/install it:")
    print(f"  CIAREN_TRUSTED_PLUGIN_KEYS='{json.dumps({DEMO_KEY_ID: DEMO_PUBLIC_KEY})}'")


def read_manifest_from_dir(src: Path):  # noqa: ANN201
    from app.plugin_api import validate_manifest

    return validate_manifest(json.loads((src / "ciaren-plugin.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
