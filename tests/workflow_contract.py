#!/usr/bin/env python3
"""Keep the deployment system limited to the two approved workflows."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
workflows = ROOT / ".github" / "workflows"
actual = {path.name for path in workflows.glob("*.yml")}
expected = {"deploy-preprod-ovh.yml", "deploy-ovh.yml"}
assert actual == expected, f"Expected only {sorted(expected)}, found {sorted(actual)}"

dependabot = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
assert dependabot.count("target-branch: preprod") == 2, (
    "Dependency updates must be validated in preproduction before main"
)

preprod = (workflows / "deploy-preprod-ovh.yml").read_text(encoding="utf-8")
production = (workflows / "deploy-ovh.yml").read_text(encoding="utf-8")
assert "branches: [preprod]" in preprod
assert 'cron: "*/15 * * * *"' in preprod
assert "pull_request:" in preprod
assert "preprod-change-validation:" in preprod
assert "if: github.event_name != 'pull_request'" in preprod
assert "ridersfanatics-preproduction-pr-{0}" in preprod
assert "github.event.pull_request.number" in preprod
assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in preprod
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

for name, contents in (("preprod", preprod), ("production", production)):
    action_refs = re.findall(r"^\s*uses:\s+([^\s#]+)", contents, flags=re.MULTILINE)
    assert action_refs, f"No external actions found in {name} workflow"
    for reference in action_refs:
        _action, separator, revision = reference.partition("@")
        assert separator and re.fullmatch(r"[0-9a-f]{40}", revision), (
            f"Unpinned action in {name} workflow: {reference}"
        )

assert "tests/deployment_access_contract.py" in preprod
assert "tests/deployment_access_contract.py" in production
assert "--inventory-only" in preprod
assert "drive-source-version.txt" in preprod
assert preprod.index("Inventory Google Drive without downloading images") < preprod.index("Synchronize Google Drive images")
assert "if: steps.change.outputs.changed == 'true'" in preprod
assert "retention-days: 3" in preprod
assert "retention-days: 14" in production
assert "OVH_SFTP_KNOWN_HOSTS" in preprod
assert production.count("OVH_SFTP_KNOWN_HOSTS") >= 2

print("workflow contract: exactly two approved workflows")
