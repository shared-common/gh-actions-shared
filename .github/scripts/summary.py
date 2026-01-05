from __future__ import annotations

from typing import Any, Dict, List


def format_summary(
    config: Dict[str, str],
    cron_expected: List[str],
    repo_results: List[Dict[str, Any]],
) -> str:
    lines: List[str] = []
    lines.append("# Org fork orchestrator summary")
    lines.append("")
    lines.append("## Config")
    for key, value in sorted(config.items()):
        lines.append(f"- **{key}**: `{value}`")
    lines.append("")
    lines.append("## Schedule")
    for idx, cron in enumerate(cron_expected, start=1):
        lines.append(f"- Workflow cron {idx}: `{cron}`")
    lines.append("")
    lines.append("## Repositories")
    if not repo_results:
        lines.append("- No repositories processed.")
        return "\n".join(lines)
    label_map = [
        ("mirror_sync", "mirror_sync"),
        ("branch_bootstrap", "branch_bootstrap"),
        ("branch_presence", "branch_presence"),
        ("product_merge", "product_merge"),
        ("stage_promo", "staging_promo"),
        ("stage_compare", "staging_compare"),
        ("downstream_target", "downstream_target"),
        ("snap_promo", "snapshot_promo"),
        ("feat_promo", "feature_promo"),
        ("branch_bootstrap_error", "branch_bootstrap_error"),
        ("issue", "issue"),
        ("notes", "notes"),
    ]
    for repo in repo_results:
        name = repo.get("name")
        lines.append(f"### {name}")
        for label, key in label_map:
            if key in repo:
                lines.append(f"- **{label}**: {repo[key]}")
    return "\n".join(lines)
