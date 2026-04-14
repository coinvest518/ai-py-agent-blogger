# GOOGLE_ANALYTICS Skill

Canonical Composio tools for Google Analytics 4 Data API.
Requires `GA_PROPERTY_ID` env var (format: `properties/123456789`).

## Canonical tools

| Slug | Purpose |
|---|---|
| `GOOGLE_ANALYTICS_LIST_ACCOUNT_SUMMARIES` | List GA accounts + properties visible to the authed user. No args. |
| `GOOGLE_ANALYTICS_GET_PROPERTY` | Fetch property metadata. Args: `name` (e.g. `properties/123`). |
| `GOOGLE_ANALYTICS_RUN_REPORT` | Run a report query. Args: `property`, `dateRanges`, `dimensions`, `metrics`. |
| `GOOGLE_ANALYTICS_CHECK_COMPATIBILITY` | Validate dim/metric combos before RUN_REPORT. Args: `property`, `dimensions`, `metrics`. |
| `GOOGLE_ANALYTICS_GET_METADATA` | List available dimensions + metrics for a property. Args: `name`. |

## Canonical report shapes

**Daily traffic (last 24h):**
```json
{
  "property": "properties/XXXXXXXX",
  "dateRanges": [{"startDate": "yesterday", "endDate": "today"}],
  "dimensions": [{"name": "pagePath"}, {"name": "sessionSource"}],
  "metrics": [{"name": "activeUsers"}, {"name": "sessions"}, {"name": "screenPageViews"}]
}
```

**Top pages (7-day):**
```json
{
  "property": "properties/XXXXXXXX",
  "dateRanges": [{"startDate": "7daysAgo", "endDate": "today"}],
  "dimensions": [{"name": "pagePath"}],
  "metrics": [{"name": "screenPageViews"}, {"name": "engagementRate"}],
  "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": true}],
  "limit": 10
}
```

## Usage pattern

- `research_agent` calls `RUN_REPORT` (7-day top pages) to see which content is driving traffic.
- `final_report_agent` calls `RUN_REPORT` (24h) + top referrers and bakes it into the briefing.
- If `GA_PROPERTY_ID` is unset, callers return `{"skipped": True}` rather than error.
