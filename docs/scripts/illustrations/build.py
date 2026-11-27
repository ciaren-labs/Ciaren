"""Build the hand-drawn documentation illustrations.

Figures are Python functions registered in ``figures_*.py``. Each one writes an
SVG with embedded font subsets, so the output needs no external assets.

Usage, from the repository root:

    uv run --no-project --with fonttools==4.63.0 python docs/scripts/illustrations/build.py
    uv run --no-project --with fonttools==4.63.0 python docs/scripts/illustrations/build.py recipes/pivot

Docs figures are written to ``docs/public/illustrations/``. Figures whose name
starts with ``blog/`` belong to the ciaren.com blog; they are built only when
``--website`` names a checkout of that repository, and are written under its
``public/illustrations/``.

A figure with layout problems (overlapping labels or content outside the card)
is reported and not written, and the command exits 1.

The first run downloads the three OFL fonts (Caveat, Inter, JetBrains Mono) into
``docs/scripts/illustrations/.fonts/`` and checks their pinned SHA-256 digests.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Callable
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from sketch import Figure  # noqa: E402

REGISTRY: dict[str, Callable[[], Figure]] = {}


def figure(name: str):
    def register(fn: Callable[[], Figure]) -> Callable[[], Figure]:
        if name in REGISTRY:
            raise ValueError(f"duplicate figure {name}")
        REGISTRY[name] = fn
        return fn

    return register


MODULES = ("figures_recipes", "figures_examples", "figures_blog")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("only", nargs="*", help="figure name prefixes to build (default: all)")
    parser.add_argument("--website", type=Path, help="ciaren.com checkout; required to build blog/ figures")
    args = parser.parse_args()

    sys.modules.setdefault("build", sys.modules[__name__])
    for module in MODULES:
        if (HERE / f"{module}.py").exists():
            importlib.import_module(module)

    docs_out = HERE.parents[1] / "public" / "illustrations"
    built = 0
    failed: list[str] = []
    skipped_blog = 0
    for name, fn in sorted(REGISTRY.items()):
        if args.only and not any(name.startswith(prefix) for prefix in args.only):
            continue
        if name.startswith("blog/"):
            if args.website is None:
                skipped_blog += 1
                continue
            target = args.website / "public" / "illustrations" / f"{name}.svg"
        else:
            target = docs_out / f"{name}.svg"
        fig = fn()
        issues = fig.problems()
        if issues:
            failed.append(name)
            for issue in issues:
                print(f"{name}: {issue}", file=sys.stderr)
            continue
        svg = fig.render()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(svg, encoding="utf-8", newline="\n")
        print(f"{target}  {len(svg) / 1024:.0f} KB")
        built += 1
    if failed:
        print(f"layout problems in {len(failed)} figure(s): {', '.join(failed)}", file=sys.stderr)
        return 1
    if skipped_blog:
        print(f"skipped {skipped_blog} blog/ figure(s): pass --website <ciaren.com checkout>", file=sys.stderr)
    if args.only and not built:
        print("no figure matched", args.only, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
