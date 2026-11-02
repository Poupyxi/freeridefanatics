#!/usr/bin/env python3
"""Ensure deployment receipts are public without exposing other JSON files."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for relative in (".htaccess", "deploy/preprod.htaccess"):
    contents = (ROOT / relative).read_text(encoding="utf-8")
    allow = "RewriteRule ^deployment-(?:health|manifest)\\.json$ - [L,NC]"
    deny = "RewriteRule \\.json$ - [F,L,NC]"
    assert allow in contents, f"{relative} does not expose deployment receipts"
    assert deny in contents, f"{relative} no longer blocks private JSON files"
    assert contents.index(allow) < contents.index(deny), (
        f"{relative} blocks deployment receipts before the allow rule"
    )

print("deployment access contract: health and manifest allowed, other JSON denied")

# GA4 is loaded dynamically only after explicit consent. Keep its production
# endpoints in the CSP so accepting analytics can actually load and send data.
production_csp = (ROOT / ".htaccess").read_text(encoding="utf-8")
for required_source in (
    "script-src 'self' https://www.googletagmanager.com",
    "img-src 'self' data: https://www.googletagmanager.com https://*.google-analytics.com",
    "connect-src 'self' https://www.googletagmanager.com https://*.google-analytics.com https://*.google.com",
):
    assert required_source in production_csp, (
        f"production CSP no longer permits consented GA4 traffic: {required_source}"
    )

print("deployment access contract: consented GA4 endpoints allowed in production CSP")
