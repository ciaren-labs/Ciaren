"""Bundle plain paragraphs from the versioned guides and immutable GitHub line links."""

import json
import re
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[2]
passages = []
for path in (
    "docs/guide/quick-start.md",
    "docs/guide/engines.md",
    "docs/guide/parameters.md",
    "docs/guide/troubleshooting.md",
    "docs/guide/projects-and-runs.md",
    "docs/guide/scheduling.md",
    "docs/guide/docker.md",
    "docs/guide/connections.md",
    "docs/guide/visualizations.md",
    "docs/guide/interface.md",
    "docs/transformations/join.md",
    "docs/guide/flow-assistant-quick-start.md",
    "docs/guide/flow-assistant.md",
    "docs/guide/external-agent.md",
):
    name = Path(path).stem
    ref = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", path], cwd=root, text=True).strip()
    raw = subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=root).decode()
    title = name
    fence = False
    for match in re.finditer(r"(?:^|\n\n)([^\n]+(?:\n(?!\n)[^\n]+)*)", raw):
        block = match.group(1).strip()
        if "```" in block:
            if block.count("```") % 2:
                fence = not fence
            continue
        if fence:
            continue
        if block.startswith("#"):
            title = block.splitlines()[0].lstrip("# ")
            continue
        if not (40 <= len(block) <= 1000) or not block[0].isalpha() or "<" in block or "](" in block or "|" in block:
            continue
        line = raw.count("\n", 0, match.start(1)) + 1
        passages.append(
            {
                "title": f"{name} · {title}",
                "text": " ".join(block.split()),
                "url": f"https://github.com/ciaren-labs/Ciaren/blob/{ref}/{path}#L{line}",
            }
        )
output = root / "backend/app/services/assistant_passages.json"
output.write_text(json.dumps(passages, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
