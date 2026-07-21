"""Post-install CODE tamper detection.

The package signature is only verified at install time, so the loader re-checks
an install-tree code digest (recorded in plugin state at install) on every load —
a ``.py``/``.pyc`` swapped on disk after install must be refused, not imported
with the install-time trust badge intact. These tests would fail against the
older manifest-only tamper gate, which let any code edit through as long as
``ciaren-plugin.json`` was untouched.
"""

from __future__ import annotations

import importlib.util
import json
import marshal
import struct
import sys
from pathlib import Path

import pytest

from app.plugin_api import ServiceRegistry
from app.plugins import package
from app.plugins.install import install_ciarenplugin, install_directory
from app.plugins.loader import load_plugins
from app.plugins.package import compute_directory_digest
from app.plugins.state import PluginStateStore

PLUGIN_ID = "community.codeguard"
MODULE = "codeguard_plugin"

_MANIFEST = {
    "id": PLUGIN_ID,
    "name": "Code Guard",
    "version": "1.0.0",
    "entrypoint": f"{MODULE}:CodeGuardPlugin",
    "permissions": [],
}

# A real, importable Plugin so the positive tests prove the plugin actually
# loads (not merely "fails with a different error").
_PLUGIN_SOURCE = f'''\
from app.plugin_api import Plugin, PluginMetadata, ServiceRegistry


class CodeGuardPlugin(Plugin):
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(id="{PLUGIN_ID}", name="Code Guard")

    def register(self, registry: ServiceRegistry) -> None:
        pass
'''


@pytest.fixture(autouse=True)
def _module_isolation():
    """Importing the plugin puts its install dir on sys.path and caches the module;
    undo both so every test imports its own tmp copy."""
    before = list(sys.path)
    yield
    sys.path[:] = before
    for name in [n for n in list(sys.modules) if n == MODULE or n.startswith(MODULE + ".")]:
        del sys.modules[name]


@pytest.fixture
def src(tmp_path):
    d = tmp_path / "src"
    d.mkdir()
    (d / "ciaren-plugin.json").write_text(json.dumps(_MANIFEST), encoding="utf-8")
    (d / f"{MODULE}.py").write_text(_PLUGIN_SOURCE, encoding="utf-8")
    return d


def _approve() -> None:
    s = PluginStateStore()
    s.set_enabled(PLUGIN_ID, True)
    s.set_approved(PLUGIN_ID, True)
    s.save()


def _load(install_dir):
    return load_plugins(
        ServiceRegistry(),
        include_entry_points=False,
        plugin_dirs=[install_dir],
        state=PluginStateStore(),
    )


def test_install_pins_code_digest(src, tmp_path):
    """A packaged install records the install-tree code digest, and it reproduces
    exactly on the pristine tree (no false positive on an untouched install)."""
    pkg = package.pack_directory(src, tmp_path / "p.ciarenplugin")
    res = install_ciarenplugin(pkg, install_dir=tmp_path / "i")
    recorded = PluginStateStore().recorded_code_digest(PLUGIN_ID)
    assert recorded
    assert compute_directory_digest(res.location) == recorded


def test_untampered_managed_plugin_loads(src, tmp_path):
    """Positive control: an approved, untouched managed install passes both tamper
    checks and actually loads."""
    pkg = package.pack_directory(src, tmp_path / "p.ciarenplugin")
    install_dir = tmp_path / "i"
    install_ciarenplugin(pkg, install_dir=install_dir)
    _approve()
    result = _load(install_dir)
    assert result.errors == []
    assert result.gated == []
    assert [p.metadata.id for p in result.loaded] == [PLUGIN_ID]


def test_edited_code_file_is_refused_at_load(src, tmp_path):
    """The core finding: editing a .py in the install dir (manifest untouched)
    must be refused at load. Under the old manifest-only digest this plugin would
    have loaded and executed the swapped code."""
    pkg = package.pack_directory(src, tmp_path / "p.ciarenplugin")
    install_dir = tmp_path / "i"
    res = install_ciarenplugin(pkg, install_dir=install_dir)
    _approve()
    (res.location / f"{MODULE}.py").write_text(
        _PLUGIN_SOURCE + "\nEVIL = True  # swapped after install\n", encoding="utf-8"
    )
    result = _load(install_dir)
    assert result.loaded == []
    assert result.gated == []  # refused outright, not merely gated
    assert len(result.errors) == 1
    assert PLUGIN_ID in result.errors[0].error
    assert "code changed on disk" in result.errors[0].error


def test_added_code_file_is_refused_at_load(src, tmp_path):
    """Dropping a NEW code file into the install dir also changes the digest —
    the file set is part of the baseline, not just the bytes of known files."""
    pkg = package.pack_directory(src, tmp_path / "p.ciarenplugin")
    install_dir = tmp_path / "i"
    res = install_ciarenplugin(pkg, install_dir=install_dir)
    _approve()
    (res.location / "extra.py").write_text("EVIL = True\n", encoding="utf-8")
    result = _load(install_dir)
    assert result.loaded == []
    assert len(result.errors) == 1
    assert "code changed on disk" in result.errors[0].error


def test_untampered_bare_pyc_plugin_loads(src, tmp_path):
    """An untampered ``compile_python=True`` install ships its module as a BARE
    ``mod.pyc`` (no ``.py`` source, IP-protection). That bare pyc is the module
    itself and is digest-covered — it is NOT a ``__pycache__`` injection, so the
    survivor scan must not flag it. The plugin must load cleanly through the full
    loader (regression guard: the first fail-closed pass refused every such plugin)."""
    pkg = package.pack_directory(src, tmp_path / "p.ciarenplugin", compile_python=True)
    install_dir = tmp_path / "i"
    res = install_ciarenplugin(pkg, install_dir=install_dir)
    assert (res.location / f"{MODULE}.pyc").is_file()  # bare pyc, the shipped code
    assert not (res.location / f"{MODULE}.py").exists()  # no source
    _approve()
    result = _load(install_dir)
    assert result.errors == []
    assert result.gated == []
    assert [p.metadata.id for p in result.loaded] == [PLUGIN_ID]


def test_tampered_shipped_pyc_is_refused_at_load(src, tmp_path):
    """compile_python packages ship bare .pyc as their code; those are covered by
    the digest too, so swapping the bytecode is refused."""
    pkg = package.pack_directory(src, tmp_path / "p.ciarenplugin", compile_python=True)
    install_dir = tmp_path / "i"
    res = install_ciarenplugin(pkg, install_dir=install_dir)
    _approve()
    pyc = res.location / f"{MODULE}.pyc"
    assert pyc.is_file()  # the shipped code really is a bare .pyc
    pyc.write_bytes(pyc.read_bytes() + b"tampered")
    result = _load(install_dir)
    assert result.loaded == []
    assert len(result.errors) == 1
    assert "code changed on disk" in result.errors[0].error


def test_pycache_and_runtime_data_do_not_trip_tamper(src, tmp_path):
    """Volatile files must not poison the check: Python regenerating __pycache__
    on first import, and a plugin writing data/cache files into its own dir, are
    both excluded from the digest — the plugin keeps loading."""
    pkg = package.pack_directory(src, tmp_path / "p.ciarenplugin")
    install_dir = tmp_path / "i"
    res = install_ciarenplugin(pkg, install_dir=install_dir)
    _approve()
    # First load imports the module (which may itself write __pycache__)...
    assert [p.metadata.id for p in _load(install_dir).loaded] == [PLUGIN_ID]
    # ...and simulate both kinds of volatile writes explicitly.
    cache_dir = res.location / "__pycache__"
    cache_dir.mkdir(exist_ok=True)
    (cache_dir / f"{MODULE}.cpython-312.pyc").write_bytes(b"regenerated bytecode cache")
    (res.location / "runtime_cache.dat").write_bytes(b"downloaded-at-runtime")
    result = _load(install_dir)
    assert result.errors == []
    assert [p.metadata.id for p in result.loaded] == [PLUGIN_ID]


def test_source_dir_install_stays_editable(src, tmp_path):
    """The deliberate dev exemption: a source-directory install pins no code
    digest, so editing its code afterwards is NOT flagged as tampering — the
    plugin still loads."""
    install_dir = tmp_path / "i"
    res = install_directory(src, install_dir=install_dir)
    assert PluginStateStore().recorded_code_digest(PLUGIN_ID) == ""
    _approve()
    (res.location / f"{MODULE}.py").write_text(_PLUGIN_SOURCE + "\nDEV_EDIT = True\n", encoding="utf-8")
    result = _load(install_dir)
    assert result.errors == []
    assert [p.metadata.id for p in result.loaded] == [PLUGIN_ID]


def test_reinstall_from_source_clears_stale_code_pin(src, tmp_path):
    """Packaged install pins a digest; a forced reinstall from a source directory
    (the dev workflow) clears it — otherwise the old pin would falsely flag the
    freshly copied dev tree."""
    pkg = package.pack_directory(src, tmp_path / "p.ciarenplugin")
    install_dir = tmp_path / "i"
    install_ciarenplugin(pkg, install_dir=install_dir)
    assert PluginStateStore().recorded_code_digest(PLUGIN_ID)
    install_directory(src, install_dir=install_dir, force=True)
    assert PluginStateStore().recorded_code_digest(PLUGIN_ID) == ""


# -- __pycache__ bytecode-injection bypass (the verifier's PoC) -----------------

# A module whose *top-level* import runs an observable side effect: it writes a
# marker to $CODEGUARD_SENTINEL. The benign source writes "BENIGN"; the planted
# bytecode writes "EVIL". If the digest gate lets a planted .pyc run in place of
# the digested source, the sentinel reads "EVIL".
_SENTINEL_ENV = "CODEGUARD_SENTINEL"


def _marker_source(marker: str) -> str:
    return (
        "import os\n"
        "from app.plugin_api import Plugin, PluginMetadata, ServiceRegistry\n"
        "\n"
        f"_p = os.environ.get({_SENTINEL_ENV!r})\n"
        "if _p:\n"
        "    with open(_p, 'w', encoding='utf-8') as _fh:\n"
        f"        _fh.write({marker!r})\n"
        "\n"
        "\n"
        "class CodeGuardPlugin(Plugin):\n"
        "    def metadata(self) -> PluginMetadata:\n"
        f"        return PluginMetadata(id={PLUGIN_ID!r}, name='Code Guard')\n"
        "\n"
        "    def register(self, registry: ServiceRegistry) -> None:\n"
        "        pass\n"
    )


def _marker_src_dir(tmp_path):
    d = tmp_path / "src"
    d.mkdir()
    (d / "ciaren-plugin.json").write_text(json.dumps(_MANIFEST), encoding="utf-8")
    (d / f"{MODULE}.py").write_text(_marker_source("BENIGN"), encoding="utf-8")
    return d


def _plant_timestamp_pyc(source_path, evil_code) -> str:
    """Write a VALID timestamp-based .pyc for ``source_path`` into its __pycache__,
    carrying ``evil_code`` — the exact bypass: a header (magic + flags=0 + int
    source mtime + source size) that Python's default invalidation accepts, so it
    runs the planted bytecode without touching (or changing the digest of) the
    unchanged source."""
    import importlib.util
    import marshal
    import os as _os
    import struct

    st = _os.stat(source_path)
    header = (
        importlib.util.MAGIC_NUMBER
        + struct.pack("<I", 0)  # flags=0 → timestamp-based invalidation
        + struct.pack("<I", int(st.st_mtime) & 0xFFFFFFFF)
        + struct.pack("<I", st.st_size & 0xFFFFFFFF)
    )
    cache = importlib.util.cache_from_source(str(source_path))
    _os.makedirs(_os.path.dirname(cache), exist_ok=True)
    with open(cache, "wb") as fh:
        fh.write(header + marshal.dumps(evil_code))
    return cache


def test_planted_valid_pyc_is_neutralized(tmp_path, monkeypatch):
    """The verifier's proven bypass: plant a VALID-header malicious .pyc in
    __pycache__ for an UNCHANGED digested source .py. Prove (a) the plant is real —
    Python's own import executes it — and (b) the loader neutralizes it: it clears
    __pycache__ so import recompiles the digested source and runs the BENIGN code,
    all while the code digest is unchanged (no digested file was touched)."""
    import importlib

    src = _marker_src_dir(tmp_path)
    pkg = package.pack_directory(src, tmp_path / "p.ciarenplugin")
    install_dir = tmp_path / "i"
    res = install_ciarenplugin(pkg, install_dir=install_dir)
    _approve()

    source_path = res.location / f"{MODULE}.py"
    digest_before = compute_directory_digest(res.location)
    evil_code = compile(_marker_source("EVIL"), str(source_path), "exec")

    sentinel = tmp_path / "sentinel.txt"
    monkeypatch.setenv(_SENTINEL_ENV, str(sentinel))

    # (a) Control: with the plant in place, Python's own import machinery accepts
    # the header and executes the planted bytecode — the vector is genuinely live.
    _plant_timestamp_pyc(source_path, evil_code)
    monkeypatch.syspath_prepend(str(res.location))
    try:
        importlib.import_module(MODULE)
    finally:
        sys.modules.pop(MODULE, None)
    assert sentinel.read_text(encoding="utf-8") == "EVIL"

    # The digested source was never touched, so the loader's code digest still
    # matches — the plant is invisible to it.
    assert compute_directory_digest(res.location) == digest_before

    # (b) Re-plant, wipe the marker, and go through the loader. It must clear the
    # bytecode cache, recompile the digested source, and run the BENIGN code.
    _plant_timestamp_pyc(source_path, evil_code)
    sentinel.unlink()
    result = _load(install_dir)
    assert result.errors == []
    assert [p.metadata.id for p in result.loaded] == [PLUGIN_ID]
    assert sentinel.read_text(encoding="utf-8") == "BENIGN"


def test_unreadable_code_fails_closed_for_pinned_install(tmp_path, monkeypatch):
    """A pinned install must fail CLOSED: if the code digest cannot be recomputed
    (an attacker can force an OSError, then swap a digested file behind the skipped
    check), the loader refuses the plugin rather than importing it unverified."""
    src = _marker_src_dir(tmp_path)
    pkg = package.pack_directory(src, tmp_path / "p.ciarenplugin")
    install_dir = tmp_path / "i"
    install_ciarenplugin(pkg, install_dir=install_dir)
    _approve()

    # The loader imports compute_directory_digest from the package module at call
    # time, so patch it there (not on the loader module).
    def _boom(_path):
        raise OSError("simulated unreadable path")

    monkeypatch.setattr(package, "compute_directory_digest", _boom)
    result = _load(install_dir)
    assert result.loaded == []
    assert len(result.errors) == 1
    assert PLUGIN_ID in result.errors[0].error
    assert "could not be verified" in result.errors[0].error


def test_undeletable_pycache_fails_closed_for_pinned_install(tmp_path, monkeypatch):
    """The residual the re-verifier found: an attacker makes the planted cache
    UNDELETABLE (open handle / read-only on Windows — chmod+retry can't beat a
    lock). The clear then fails; a matching-header plant would be trusted and run.
    So the loader must fail CLOSED — re-walk after clearing and refuse the load if
    any bytecode cache survives, never importing the plant."""
    import shutil

    src = _marker_src_dir(tmp_path)
    pkg = package.pack_directory(src, tmp_path / "p.ciarenplugin")
    install_dir = tmp_path / "i"
    res = install_ciarenplugin(pkg, install_dir=install_dir)
    _approve()

    source_path = res.location / f"{MODULE}.py"
    evil_code = compile(_marker_source("EVIL"), str(source_path), "exec")
    sentinel = tmp_path / "sentinel.txt"
    monkeypatch.setenv(_SENTINEL_ENV, str(sentinel))
    cache = Path(_plant_timestamp_pyc(source_path, evil_code))
    assert cache.is_file()  # a valid-header plant is in place

    # Simulate the cache being undeletable: rmtree fails, so _clear_pycache leaves
    # the plant on disk (exactly the open-handle / read-only case).
    def _locked(*_a, **_k):
        raise OSError("cache is locked / read-only")

    monkeypatch.setattr(shutil, "rmtree", _locked)

    result = _load(install_dir)
    assert result.loaded == []
    assert len(result.errors) == 1
    assert PLUGIN_ID in result.errors[0].error
    assert "could not be cleared" in result.errors[0].error
    # The plant survived but was never imported — the malicious code did not run.
    assert cache.is_file()
    assert not sentinel.exists()


def test_symlinked_pycache_fails_closed_for_pinned_install(tmp_path, monkeypatch):
    """The last gap: a SYMLINKED __pycache__ pointing at an attacker-controlled dir
    holding a valid-header malicious .pyc. os.walk(followlinks=False) won't descend
    it and shutil.rmtree refuses a symlink, so a dirpath-based scan would miss it and
    the plant would import. Detection via the parent's dirnames catches the symlink;
    the loader must refuse the load and never run the plant."""
    import os as _os

    src = _marker_src_dir(tmp_path)
    pkg = package.pack_directory(src, tmp_path / "p.ciarenplugin")
    install_dir = tmp_path / "i"
    res = install_ciarenplugin(pkg, install_dir=install_dir)
    _approve()

    source_path = res.location / f"{MODULE}.py"
    evil_code = compile(_marker_source("EVIL"), str(source_path), "exec")
    sentinel = tmp_path / "sentinel.txt"
    monkeypatch.setenv(_SENTINEL_ENV, str(sentinel))

    # Build the attacker dir OUTSIDE the install tree, with a valid-header plant at
    # the exact cache path Python would look for, then point a __pycache__ symlink
    # in the install dir at it.
    attacker = tmp_path / "attacker_cache"
    attacker.mkdir()
    cache_name = Path(importlib.util.cache_from_source(str(source_path))).name
    st = _os.stat(source_path)
    header = (
        importlib.util.MAGIC_NUMBER
        + struct.pack("<I", 0)
        + struct.pack("<I", int(st.st_mtime) & 0xFFFFFFFF)
        + struct.pack("<I", st.st_size & 0xFFFFFFFF)
    )
    (attacker / cache_name).write_bytes(header + marshal.dumps(evil_code))

    link = res.location / "__pycache__"
    try:
        _os.symlink(attacker, link, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"OS cannot create directory symlinks here: {exc}")
    assert link.is_symlink()

    result = _load(install_dir)
    assert result.loaded == []
    assert len(result.errors) == 1
    assert PLUGIN_ID in result.errors[0].error
    assert "could not be cleared" in result.errors[0].error
    # The malicious bytecode was never imported.
    assert not sentinel.exists()
