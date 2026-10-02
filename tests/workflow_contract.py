#!/usr/bin/env python3
"""Keep source refreshes isolated while preserving controlled production promotion."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
workflows = ROOT / ".github" / "workflows"
actual = {path.name for path in workflows.glob("*.yml")}
expected = {
    "deploy-preprod-drive-ovh.yml",
    "deploy-preprod-ovh.yml",
    "deploy-ovh.yml",
}
assert actual == expected, f"Expected only {sorted(expected)}, found {sorted(actual)}"

dependabot = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
assert dependabot.count("target-branch: preprod") == 2, (
    "Dependency updates must be validated in preproduction before main"
)

preprod = (workflows / "deploy-preprod-ovh.yml").read_text(encoding="utf-8")
drive = (workflows / "deploy-preprod-drive-ovh.yml").read_text(encoding="utf-8")
production = (workflows / "deploy-ovh.yml").read_text(encoding="utf-8")
assert "name: Update Notion Preprod" in preprod
assert "branches: [preprod]" in preprod
assert 'cron: "*/15 * * * *"' in preprod
assert "workflow_call:" in preprod
assert "sync_scope:" in preprod
assert "pull_request:" in preprod
assert "preprod-change-validation:" in preprod
assert "if: github.event_name != 'pull_request'" in preprod
assert "ridersfanatics-preproduction-pr-{0}" in preprod
assert "github.event.pull_request.number" in preprod
assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in preprod
assert "name: Update Drive Preprod" in drive
assert 'cron: "7-59/15 * * * *"' in drive
assert "uses: ./.github/workflows/deploy-preprod-ovh.yml" in drive
assert "sync_scope: drive" in drive
assert "secrets: inherit" in drive
assert "pull_request:" not in drive
assert "push:" not in drive
assert "workflow_dispatch:" in production
assert "pull_request:" in production
assert "branches: [main]" in production
assert "production-change-validation:" in production
assert "ridersfanatics-production-pr-{0}" in production
assert "github.event.pull_request.number" in production
assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in production
assert "push:" not in production.split("jobs:", 1)[0]
assert "operation:" in production
assert "rollback_run_id:" in production
assert "confirmation:" in production
assert "inputs.operation == 'promote'" in production
assert "inputs.operation == 'restore'" in production
assert 'test "$RESTORE_CONFIRMATION" = "RESTORE"' in production
assert "scripts/restore_snapshot.py" in production
assert "assets/img/competitions/uci-mtb-world-cup-dh-2026.webp" in production
assert "assets/img/competitions/uci-mtb-world-cup-dh-2026.png" not in production
assert 'select(.event != "pull_request")' in production
assert "actions/runs/$candidate/artifacts?per_page=100" in production
assert 'actions/runs?status=success&per_page=100' in production
assert "No successful preproduction run with a live validated snapshot" in production

for name, contents in (("notion", preprod), ("drive", drive), ("production", production)):
    action_refs = re.findall(r"^\s*uses:\s+([^\s#]+)", contents, flags=re.MULTILINE)
    assert action_refs, f"No external actions found in {name} workflow"
    for reference in action_refs:
        if reference.startswith("./"):
            continue
        _action, separator, revision = reference.partition("@")
        assert separator and re.fullmatch(r"[0-9a-f]{40}", revision), (
            f"Unpinned action in {name} workflow: {reference}"
        )

assert "tests/deployment_access_contract.py" in preprod
assert "tests/deployment_access_contract.py" in production
assert "--inventory-only" in preprod
assert "drive-source-version.txt" in preprod
assert preprod.index("Inventory Google Drive without downloading images") < preprod.index("Synchronize Google Drive images")
assert "if: env.RF_SYNC_SCOPE == 'notion'" in preprod
assert preprod.count("env.RF_SYNC_SCOPE == 'drive'") >= 3
assert "Restore only the unchanged source" in preprod
assert "Validate the combined Notion and Drive snapshot" in preprod
assert 'python3 -m pip install --disable-pip-version-check "Pillow==12.3.0"' in preprod
assert "if: steps.change.outputs.changed == 'true'" in preprod
assert "retention-days: 30" in preprod
assert "retention-days: 14" in production
assert "OVH_SFTP_KNOWN_HOSTS" in preprod
assert production.count("OVH_SFTP_KNOWN_HOSTS") >= 2

print("workflow contract: isolated Notion/Drive refreshes plus controlled production")
