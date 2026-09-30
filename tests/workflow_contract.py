#!/usr/bin/env python3
"""Keep the deployment system limited to the two approved workflows."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
workflows = ROOT / ".github" / "workflows"
actual = {path.name for path in workflows.glob("*.yml")}
expected = {"deploy-preprod-ovh.yml", "deploy-ovh.yml"}
assert actual == expected, f"Expected only {sorted(expected)}, found {sorted(actual)}"

preprod = (workflows / "deploy-preprod-ovh.yml").read_text(encoding="utf-8")
production = (workflows / "deploy-ovh.yml").read_text(encoding="utf-8")
assert "branches: [preprod]" in preprod
assert 'cron: "*/15 * * * *"' in preprod
assert "workflow_dispatch:" in production
assert "push:" not in production.split("jobs:", 1)[0]

print("workflow contract: exactly two approved workflows")
