# SPDX-License-Identifier: AGPL-3.0-only
"""Dependency license scanning — surface copyleft/unknown licenses before release.

A lightweight, dependency-free check (stdlib ``importlib.metadata`` only) that
reads each installed distribution's declared license and flags ones that may be
incompatible with redistribution, Ciaren's AGPL-3.0 core, or a commercial plugin
(GPL/AGPL/LGPL family, or undeclared). It is advisory: license metadata is often
imprecise, so treat hits as "review these," not "these are forbidden".

Used by ``ciaren plugin licenses`` and importable for CI.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata

#: License substrings that warrant a manual review before redistribution.
COPYLEFT_MARKERS = ("gpl", "agpl", "lgpl", "mpl", "epl", "cddl", "sspl")
#: Permissive markers we consider clearly safe to ship.
PERMISSIVE_MARKERS = ("mit", "bsd", "apache", "isc", "psf", "python software foundation", "zlib", "unlicense")


@dataclass
class PackageLicense:
    name: str
    version: str
    license: str
    classifier_licenses: list[str]

    @property
    def effective(self) -> str:
        """Best available license text: the classifier if present (more reliable),
        else the free-text ``License`` field."""
        return self.classifier_licenses[0] if self.classifier_licenses else self.license

    @property
    def flagged(self) -> bool:
        """Whether this needs review: copyleft markers, or no license declared."""
        text = self.effective.lower()
        if not text or text in ("unknown", "none"):
            return True
        if any(m in text for m in PERMISSIVE_MARKERS):
            return False
        return any(m in text for m in COPYLEFT_MARKERS) or not _looks_known(text)


def _looks_known(text: str) -> bool:
    return any(m in text for m in (*PERMISSIVE_MARKERS, *COPYLEFT_MARKERS))


def _license_of(dist: metadata.Distribution) -> PackageLicense:
    meta = dist.metadata
    classifiers = [c.split("::", 1)[1].strip() for c in meta.get_all("Classifier", []) if c.startswith("License ::")]
    return PackageLicense(
        name=meta.get("Name", "?") or "?",
        version=meta.get("Version", "?") or "?",
        license=(meta.get("License", "") or "").splitlines()[0][:80] if meta.get("License") else "",
        classifier_licenses=classifiers,
    )


def scan_installed() -> list[PackageLicense]:
    """Every installed distribution's license, sorted by name."""
    seen: dict[str, PackageLicense] = {}
    for dist in metadata.distributions():
        pkg = _license_of(dist)
        seen[pkg.name.lower()] = pkg
    return [seen[k] for k in sorted(seen)]


def flagged_packages() -> list[PackageLicense]:
    """Installed packages whose license needs a manual review before shipping."""
    return [p for p in scan_installed() if p.flagged]
