# Search Console CTR opportunity report

This report identifies pages and queries that already receive impressions but
whose click-through rate is below a conservative target for their average
position. It does not modify page metadata automatically.

## Export from Search Console

1. Open **Performance → Search results** for `ridersfanatics.com`.
2. Select a stable period, preferably the last 28 days.
3. Enable Clicks, Impressions, CTR and Position.
4. Export the **Queries** and **Pages** tables as CSV.
5. Keep the files in `tmp/search-console/` (this directory is ignored by Git).

Then run:

```bash
python3 scripts/search_console_ctr_report.py \
  tmp/search-console/Queries.csv \
  tmp/search-console/Pages.csv
```

The result is written to `tmp/search-console/ctr-opportunities.csv` with:

`Page | Query | Clicks | Impressions | Position | Current CTR | Target CTR | Priority | Opportunity score | Suggested title | Source`

The standard Search Console interface exports Page and Query separately. A
Search Analytics API export containing both columns is also accepted and will
produce combined page-query rows. Raw exports and generated reports must not be
committed because they contain private site telemetry.

Suggested titles are starting points only. Before using one, verify that it
accurately describes the page and does not duplicate another title.
