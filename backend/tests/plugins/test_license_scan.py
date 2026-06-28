"""Dependency license scanning."""

from __future__ import annotations

from app.plugins.license_scan import PackageLicense, flagged_packages, scan_installed


def _pkg(license_="", classifiers=None):
    return PackageLicense(name="x", version="1.0", license=license_, classifier_licenses=classifiers or [])


def test_permissive_not_flagged():
    assert _pkg("MIT License").flagged is False
    assert _pkg("Apache Software License").flagged is False
    assert _pkg("BSD-3-Clause").flagged is False


def test_copyleft_flagged():
    assert _pkg("GNU General Public License v3 (GPLv3)").flagged is True
    assert _pkg("GNU Affero General Public License v3").flagged is True


def test_unknown_or_missing_flagged():
    assert _pkg("").flagged is True
    assert _pkg("UNKNOWN").flagged is True
    assert _pkg("Some Bespoke Proprietary Terms").flagged is True


def test_classifier_takes_precedence_over_free_text():
    pkg = _pkg(license_="GPL", classifiers=["OSI Approved :: MIT License"])
    assert pkg.effective == "OSI Approved :: MIT License"
    assert pkg.flagged is False


def test_scan_installed_includes_known_permissive_deps():
    packages = {p.name.lower() for p in scan_installed()}
    # FlowFrame depends on these; they are installed in the test environment.
    assert "fastapi" in packages
    assert "pydantic" in packages


def test_flagged_packages_subset_of_scan():
    flagged = flagged_packages()
    all_names = {p.name for p in scan_installed()}
    assert all(p.name in all_names for p in flagged)
    assert all(p.flagged for p in flagged)
