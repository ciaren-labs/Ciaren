# SPDX-License-Identifier: AGPL-3.0-only
"""Ciaren plugin tooling command-line entry point.

Exposed as the ``ciaren-plugin`` console script (see ``[project.scripts]``) —
split out from the main ``ciaren`` command so a plain ``pip install ciaren``
followed by ``ciaren serve`` doesn't carry the plugin lifecycle (install,
enable/disable) and authoring surface (signing, packaging, manifest
generation, marketplace indexing, license issuance) in the everyday CLI.
Installed as part of the same ``ciaren`` distribution, just a separate entry
point — nothing extra to install for basic plugin management. Publisher
tooling (`keygen`/`sign`) additionally needs `pip install ciaren[signing]`.

Uses only argparse (stdlib) to keep --help instant; every subcommand lazily
imports its own dependencies.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.cli import _package_version


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ciaren-plugin",
        description="Ciaren plugin tooling — install, inspect, and sign Ciaren plugins.",
    )
    parser.add_argument("--version", action="version", version=f"ciaren-plugin {_package_version()}")

    sub = parser.add_subparsers(dest="command")

    # Shared by read-only commands that can emit machine-readable output.
    output_parent = argparse.ArgumentParser(add_help=False)
    output_parent.add_argument(
        "--output",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table).",
    )

    sub.add_parser("list", help="List discovered plugins and their status.", parents=[output_parent])

    p_install = sub.add_parser("install", help="Install a .ciarenplugin package (or a source dir with --dir).")
    p_install.add_argument("path", help="Path to the .ciarenplugin file (or plugin source directory with --dir).")
    p_install.add_argument("--dir", action="store_true", help="Install from an unpacked source directory.")
    p_install.add_argument("--trusted", action="store_true", help="Refuse unless signed by a trusted key.")
    p_install.add_argument("--force", action="store_true", help="Overwrite an existing install.")

    p_uninstall = sub.add_parser("uninstall", help="Remove an installed plugin by id.")
    p_uninstall.add_argument("plugin_id", help="The plugin id to remove.")

    p_verify = sub.add_parser(
        "verify", help="Verify a .ciarenplugin's signature and integrity.", parents=[output_parent]
    )
    p_verify.add_argument("path", help="Path to the .ciarenplugin file.")

    p_enable = sub.add_parser("enable", help="Enable a plugin.")
    p_enable.add_argument("plugin_id")
    p_disable = sub.add_parser("disable", help="Disable a plugin (its code won't load).")
    p_disable.add_argument("plugin_id")

    sub.add_parser("keygen", help="Generate an Ed25519 signing keypair (for publishers).")

    p_pack = sub.add_parser("pack", help="Package a plugin source directory into an (unsigned) .ciarenplugin.")
    p_pack.add_argument("src_dir", help="Plugin source directory (contains ciaren-plugin.json).")
    p_pack.add_argument("out", help="Output .ciarenplugin path.")
    p_pack.add_argument(
        "--compile",
        action="store_true",
        dest="compile_python",
        help="Ship compiled .pyc bytecode instead of .py source (deters casual "
        "inspection of paid plugins; locks the package to this Python version).",
    )

    p_manifest = sub.add_parser(
        "manifest",
        help="Generate ciaren-plugin.json from a plugin's code (single source of truth).",
    )
    p_manifest.add_argument("src_dir", help="Plugin source directory (contains the plugin package).")
    p_manifest.add_argument(
        "--entrypoint",
        default=None,
        help="module.path:Class of the Plugin. Defaults to the entrypoint in an existing manifest.",
    )
    p_manifest.add_argument(
        "--out",
        default=None,
        help="Where to write the manifest (default: <src_dir>/ciaren-plugin.json). Use '-' for stdout.",
    )
    p_manifest.add_argument("--ciaren", default=">=0.1", help="PEP 440 compatible-Ciaren specifier.")
    p_manifest.add_argument(
        "--api-version",
        dest="api_version",
        default=None,
        help="Plugin-contract version the plugin targets (MAJOR.MINOR). "
        "Defaults to the installed SDK's PLUGIN_API_VERSION. Set a lower minor to "
        "run on more hosts when you only use older-contract features.",
    )
    p_manifest.add_argument("--license", default="community", choices=("community", "commercial"))
    p_manifest.add_argument("--trust", default="community", choices=("trusted", "verified", "community"))

    p_sign = sub.add_parser("sign", help="Sign a .ciarenplugin in place with an Ed25519 private key.")
    p_sign.add_argument("path", help="Path to the .ciarenplugin file.")
    p_sign.add_argument("--key", required=True, help="Hex-encoded Ed25519 private key.")
    p_sign.add_argument(
        "--key-id", required=True, dest="key_id", help="Identifier clients use to look up the public key."
    )
    p_sign.add_argument("--publisher", default="", help="Publisher name to embed in the signature.")

    p_search = sub.add_parser("search", help="Search a local marketplace index.", parents=[output_parent])
    p_search.add_argument("query", nargs="?", default="", help="Search text (empty lists all).")
    p_search.add_argument("--index", required=True, help="Path to a marketplace index JSON file.")

    p_index = sub.add_parser("index", help="Author a local marketplace index (the 'Explore' catalog).")
    index_sub = p_index.add_subparsers(dest="index_command")
    p_index_add = index_sub.add_parser("add", help="Add/replace a plugin entry in a marketplace index.")
    p_index_add.add_argument("package", help="Path to the .ciarenplugin to add.")
    p_index_add.add_argument("--index", required=True, help="Marketplace index JSON file (created if absent).")
    p_index_add.add_argument(
        "--download-url",
        default=None,
        dest="download_url",
        help="Where clients fetch the artifact. Defaults to the package path relative to the index file.",
    )

    p_license = sub.add_parser("license", help="Issue, import, and inspect plugin license tokens.")
    license_sub = p_license.add_subparsers(dest="license_command")
    p_lic_issue = license_sub.add_parser("issue", help="Sign a license token (publisher).")
    p_lic_issue.add_argument("--key", required=True, help="Hex-encoded Ed25519 private key.")
    p_lic_issue.add_argument("--user", required=True, dest="user_id", help="Licensed user id.")
    p_lic_issue.add_argument("--plugin", required=True, dest="plugin_id", help="Plugin id the token grants.")
    p_lic_issue.add_argument("--type", default="pro", dest="license_type", help="License type (default: pro).")
    p_lic_issue.add_argument("--expires", required=True, help="Expiry, ISO-8601 (e.g. 2027-01-01T00:00:00Z).")
    p_lic_issue.add_argument("--grace", required=True, help="Offline grace end, ISO-8601.")
    p_lic_issue.add_argument("--out", default=None, help="Write the token JSON here (default: stdout).")
    p_lic_import = license_sub.add_parser("import", help="Cache a license token locally (user).")
    p_lic_import.add_argument("path", help="Path to the token JSON file.")
    p_lic_status = license_sub.add_parser("status", help="Show a cached license token's status.")
    p_lic_status.add_argument("plugin_id", help="Plugin id to inspect.")
    p_lic_status.add_argument("--key", default=None, help="Issuer public key (hex) to verify the signature.")

    p_lic = sub.add_parser(
        "licenses", help="Scan installed dependency licenses for redistribution review.", parents=[output_parent]
    )
    p_lic.add_argument("--flagged-only", action="store_true", help="Only show packages that need review.")
    p_lic.add_argument("--fail-on-flagged", action="store_true", help="Exit non-zero if any package is flagged.")

    return parser


def _plugin_list(args: argparse.Namespace) -> None:
    from app.plugins import get_load_result, get_plugin_state

    result = get_load_result()
    state = get_plugin_state()
    rows: list[dict[str, Any]] = []
    for p in result.loaded:
        rows.append({"id": p.metadata.id, "name": p.metadata.name, "status": "loaded", "source": p.source})
    for g in result.gated:
        rows.append({"id": g.plugin_id, "name": g.name, "status": g.reason, "source": g.source})
    errors = [{"source": e.source, "error": e.error} for e in result.errors]

    if getattr(args, "output", "table") == "json":
        print(json.dumps({"plugins": rows, "errors": errors}, indent=2))
        return
    if not rows and not errors:
        print("No external plugins discovered.")
        return
    for r in rows:
        print(f"  [{r['status']:<17}] {r['id']:<24} {r['name']}  ({r['source']})")
    for e in errors:
        print(f"  [error            ] {e['source']}: {e['error']}")
    _ = state  # reserved for showing granted permissions in a future column


def _plugin_install(args: argparse.Namespace) -> None:
    from app.plugins.install import InstallError, install_ciarenplugin, install_directory
    from app.plugins.package import PackageError

    try:
        if args.dir:
            res = install_directory(args.path, force=args.force)
        else:
            res = install_ciarenplugin(args.path, require_trusted=args.trusted, force=args.force)
    except (InstallError, PackageError) as exc:
        raise SystemExit(f"install failed: {exc}") from exc
    # install_* already persisted how it verified (trust badge + TOFU signer pin).
    v = res.verification
    print(f"Installed {res.plugin_id} -> {res.location}")
    print(f"  signature: {v.outcome} ({v.reason})")
    print("Run `ciaren serve` (or restart) to load it.")


def _plugin_uninstall(args: argparse.Namespace) -> None:
    from app.plugins.install import uninstall_plugin

    removed = uninstall_plugin(args.plugin_id)
    print(f"Uninstalled {args.plugin_id}." if removed else f"{args.plugin_id} is not installed.")


def _plugin_verify(args: argparse.Namespace) -> None:
    from app.plugins.package import PackageError, read_manifest, verify_package

    try:
        manifest = read_manifest(args.path)
        result = verify_package(args.path)
    except PackageError as exc:
        raise SystemExit(f"verify failed: {exc}") from exc
    if getattr(args, "output", "table") == "json":
        print(
            json.dumps(
                {
                    "id": manifest.id,
                    "outcome": result.outcome,
                    "signed": result.signed,
                    "digest": result.digest,
                    "reason": result.reason,
                    "publisher": result.publisher,
                },
                indent=2,
            )
        )
    else:
        print(f"Plugin:    {manifest.id} ({manifest.name} {manifest.version})")
        print(f"Digest:    {result.digest}")
        print(f"Signature: {result.outcome} — {result.reason}")
    if result.outcome == "invalid":
        raise SystemExit(1)


def _plugin_toggle(args: argparse.Namespace, *, enable: bool) -> None:
    from app.plugins import get_plugin_state

    state = get_plugin_state()
    state.set_enabled(args.plugin_id, enable)
    if enable:
        # Enabling is an explicit opt-in to run the plugin's (unsandboxed) code.
        state.set_approved(args.plugin_id, True)
    state.save()
    print(f"{'Enabled' if enable else 'Disabled'} {args.plugin_id}. Restart `ciaren serve` to apply.")


def _plugin_keygen() -> None:
    from app.plugin_api.signing import SigningUnavailableError, generate_keypair

    try:
        private_hex, public_hex = generate_keypair()
    except SigningUnavailableError as exc:
        raise SystemExit(str(exc)) from exc
    print("Ed25519 keypair generated. Keep the private key secret.\n")
    print(f"  private_key: {private_hex}")
    print(f"  public_key:  {public_hex}")
    print("\nPublish the public key as a trusted key, e.g.:")
    print(f'  CIAREN_TRUSTED_PLUGIN_KEYS=\'{{"your-key-id": "{public_hex}"}}\'')


def _plugin_pack(args: argparse.Namespace) -> None:
    from app.plugins.package import PackageError, pack_directory

    try:
        out = pack_directory(args.src_dir, args.out, compile_python=getattr(args, "compile_python", False))
    except PackageError as exc:
        raise SystemExit(f"pack failed: {exc}") from exc
    note = " (compiled bytecode)" if getattr(args, "compile_python", False) else ""
    print(f"Wrote {out} (unsigned{note}). Sign it with `ciaren-plugin sign`.")
    if getattr(args, "compile_python", False):
        print(f"  Built for Python {sys.version_info.major}.{sys.version_info.minor}; rebuild per Python version.")


def _plugin_manifest(args: argparse.Namespace) -> None:
    from app.plugin_api import PLUGIN_API_VERSION
    from app.plugins.authoring import manifest_json_from_plugin
    from app.plugins.loader import load_entrypoint

    src = Path(args.src_dir).expanduser()
    if not src.is_dir():
        raise SystemExit(f"manifest failed: {src} is not a directory")

    entrypoint = args.entrypoint
    if entrypoint is None:  # fall back to the entrypoint declared in an existing manifest
        manifest_path = src / "ciaren-plugin.json"
        if not manifest_path.is_file():
            raise SystemExit("manifest failed: pass --entrypoint (no existing ciaren-plugin.json to read it from)")
        try:
            entrypoint = json.loads(manifest_path.read_text(encoding="utf-8")).get("entrypoint")
        except (OSError, ValueError) as exc:
            raise SystemExit(f"manifest failed: could not read existing manifest: {exc}") from exc
        if not entrypoint:
            raise SystemExit("manifest failed: existing manifest has no entrypoint; pass --entrypoint")

    if str(src) not in sys.path:  # make the plugin package importable (append: never shadow core)
        sys.path.append(str(src))
    try:
        plugin = load_entrypoint(entrypoint)
        rendered = manifest_json_from_plugin(
            plugin,
            entrypoint=entrypoint,
            ciaren=args.ciaren,
            api_version=args.api_version or PLUGIN_API_VERSION,
            license=args.license,
            trust=args.trust,
        )
    except Exception as exc:  # noqa: BLE001 — surface any import/registration failure to the user
        raise SystemExit(f"manifest failed: {exc}") from exc

    if args.out == "-":
        print(rendered)
        return
    out = Path(args.out).expanduser() if args.out else src / "ciaren-plugin.json"
    out.write_text(rendered + "\n", encoding="utf-8")
    print(f"Wrote {out} (generated from {entrypoint}).")


def _plugin_sign(args: argparse.Namespace) -> None:
    from app.plugin_api.signing import SigningUnavailableError
    from app.plugins.package import PackageError, sign_package

    try:
        sig = sign_package(args.path, args.key, key_id=args.key_id, publisher=args.publisher)
    except SigningUnavailableError as exc:
        raise SystemExit(str(exc)) from exc
    except PackageError as exc:
        raise SystemExit(f"sign failed: {exc}") from exc
    print(f"Signed {args.path}")
    print(f"  key_id: {sig.key_id}")
    print(f"  digest: {sig.digest}")


def _plugin_index(args: argparse.Namespace) -> None:
    if getattr(args, "index_command", None) != "add":
        print("usage: ciaren-plugin index add <package.ciarenplugin> --index <index.json>")
        return
    from app.plugins.marketplace import add_to_index_file
    from app.plugins.package import PackageError

    try:
        entry = add_to_index_file(args.index, args.package, download_url=args.download_url)
    except (OSError, ValueError, PackageError) as exc:
        raise SystemExit(f"index add failed: {exc}") from exc
    print(f"Added {entry.id} {entry.version} to {args.index}")
    print(f"  downloadUrl: {entry.download_url}")
    print(f"  digest:      {entry.digest}")
    if entry.key_id:
        print(f"  keyId:       {entry.key_id}")


def _plugin_search(args: argparse.Namespace) -> None:
    from app.plugins.marketplace import load_index

    try:
        index = load_index(args.index)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"could not read index: {exc}") from exc
    matches = index.search(args.query)
    if getattr(args, "output", "table") == "json":
        print(json.dumps([m.model_dump(by_alias=True) for m in matches], indent=2))
        return
    if not matches:
        print("No matching plugins.")
        return
    for m in matches:
        flag = " [license]" if m.license_required else ""
        print(f"  {m.id:<24} {m.version:<8} {m.name}{flag}")
        if m.description:
            print(f"      {m.description}")


def _plugin_license(args: argparse.Namespace) -> None:
    command = getattr(args, "license_command", None)
    if command == "issue":
        _plugin_license_issue(args)
    elif command == "import":
        _plugin_license_import(args)
    elif command == "status":
        _plugin_license_status(args)
    else:
        print("usage: ciaren-plugin license {issue,import,status}")


def _plugin_license_issue(args: argparse.Namespace) -> None:
    from app.plugin_api.signing import SigningUnavailableError, sign
    from app.plugins.licensing import LicenseToken

    token = LicenseToken(
        user_id=args.user_id,
        plugin_id=args.plugin_id,
        license_type=args.license_type,
        expires_at=args.expires,
        offline_grace_until=args.grace,
    )
    try:
        token.signature = sign(args.key, token.signing_payload())
    except SigningUnavailableError as exc:
        raise SystemExit(str(exc)) from exc
    payload = token.model_dump_json(by_alias=True, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(f"Wrote license token for {token.plugin_id} -> {args.out}")
    else:
        print(payload)


def _plugin_license_import(args: argparse.Namespace) -> None:
    from app.plugins.licensing import LicenseCache, LicenseToken

    try:
        token = LicenseToken.model_validate_json(Path(args.path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"could not read token: {exc}") from exc
    LicenseCache().save(token)
    print(f"Imported license for {token.plugin_id} (user {token.user_id}, expires {token.expires_at}).")


def _plugin_license_status(args: argparse.Namespace) -> None:
    from app.plugins.licensing import LicenseCache, evaluate_token, verify_token

    token = LicenseCache().load(args.plugin_id)
    if token is None:
        print(f"No cached license for {args.plugin_id}.")
        return
    print(f"Plugin:  {token.plugin_id}")
    print(f"User:    {token.user_id}")
    print(f"Type:    {token.license_type}")
    print(f"Expires: {token.expires_at}  (offline grace until {token.offline_grace_until})")
    if args.key:
        status = evaluate_token(token, verified=verify_token(token, args.key))
        print(f"Status:  {'valid' if status.valid else 'invalid'} — {status.reason}")
    else:
        print("Status:  signature not checked (pass --key <issuer public hex> to verify)")


def _plugin_licenses(args: argparse.Namespace) -> None:
    from app.plugins.license_scan import scan_installed

    packages = scan_installed()
    flagged = [p for p in packages if p.flagged]
    shown = flagged if getattr(args, "flagged_only", False) else packages

    if getattr(args, "output", "table") == "json":
        print(
            json.dumps(
                [{"name": p.name, "version": p.version, "license": p.effective, "flagged": p.flagged} for p in shown],
                indent=2,
            )
        )
    else:
        width = max((len(p.name) for p in shown), default=4)
        for p in shown:
            mark = "  REVIEW" if p.flagged else ""
            print(f"  {p.name.ljust(width)}  {p.version:<12} {p.effective or 'UNKNOWN'}{mark}")
        print(f"\n{len(flagged)} of {len(packages)} packages need review.")

    if getattr(args, "fail_on_flagged", False) and flagged:
        raise SystemExit(1)


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command
    if command == "list":
        _plugin_list(args)
    elif command == "install":
        _plugin_install(args)
    elif command == "uninstall":
        _plugin_uninstall(args)
    elif command == "verify":
        _plugin_verify(args)
    elif command in ("enable", "disable"):
        _plugin_toggle(args, enable=command == "enable")
    elif command == "keygen":
        _plugin_keygen()
    elif command == "pack":
        _plugin_pack(args)
    elif command == "manifest":
        _plugin_manifest(args)
    elif command == "sign":
        _plugin_sign(args)
    elif command == "search":
        _plugin_search(args)
    elif command == "index":
        _plugin_index(args)
    elif command == "license":
        _plugin_license(args)
    elif command == "licenses":
        _plugin_licenses(args)
    else:
        parser.print_help()


if __name__ == "__main__":  # pragma: no cover
    main()
