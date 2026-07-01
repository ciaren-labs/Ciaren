"""Guard: the committed example .ciarenplugin stays valid and trusted.

Catches accidental corruption of the artifact or drift between it and the demo
public key documented in the example README.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.plugin_api import signing
from app.plugins.package import read_manifest, read_signature, verify_package

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE = REPO_ROOT / "examples" / "plugins" / "dist" / "community.hello-0.1.0.ciarenplugin"
DEMO_KEY_ID = "ciaren-demo"
DEMO_PUBLIC_KEY = "b827f3795467a701b018a0d57ab5900af43669d3622340905559d86ae2ec4bdd"


def test_example_package_exists_and_has_manifest():
    assert PACKAGE.is_file(), "run examples/plugins/build_hello_ciarenplugin.py"
    assert read_manifest(PACKAGE).id == "community.hello"


def test_example_package_is_signed():
    sig = read_signature(PACKAGE)
    assert sig is not None
    assert sig.key_id == DEMO_KEY_ID


@pytest.mark.skipif(not signing.signing_available(), reason="cryptography not installed")
def test_example_package_verifies_against_demo_key():
    result = verify_package(PACKAGE, trusted_keys={DEMO_KEY_ID: DEMO_PUBLIC_KEY})
    assert result.outcome == "trusted", result.reason


@pytest.mark.skipif(not signing.signing_available(), reason="cryptography not installed")
def test_example_package_untrusted_without_the_key():
    result = verify_package(PACKAGE, trusted_keys={})
    assert result.outcome == "untrusted"
