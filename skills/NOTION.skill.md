# NOTION Skill

Canonical Composio tools for the Notion toolkit. Import via `skills_loader.load_skill("NOTION")`
and inject this text into the LLM prompt instead of dumping the full 50+ tool catalogue.

Call via `composio_client.tools.execute(TOOL_SLUG, arguments={...}, user_id=COMPOSIO_ENTITY_ID)`.

## Canonical tools

| Slug | Purpose |
|---|---|
| `NOTION_CREATE_NOTION_PAGE` | Create a new page under a parent page or database. Args: `parent_id`, `title`, `cover`, `icon`. |
| `NOTION_APPEND_BLOCK_CHILDREN` | Append blocks (paragraph/heading/todo) to an existing page. Args: `block_id`, `children` (list of Notion block objects). |
| `NOTION_FETCH_PAGE_MARKDOWN` | Read a page as markdown. Args: `page_id`. |
| `NOTION_UPDATE_PAGE_PROPERTIES` | Patch page properties (title, tags, status). Args: `page_id`, `properties`. |
| `NOTION_QUERY_DATABASE` | Query a Notion database with filters/sorts. Args: `database_id`, `filter`, `sorts`. |
| `NOTION_SEARCH` | Full-text search across workspace. Args: `query`, `filter`. |

## Block object shortcuts (for APPEND_BLOCK_CHILDREN)

```json
{ "object": "block", "type": "heading_2",
  "heading_2": { "rich_text": [{"type":"text","text":{"content":"Section"}}] } }

{ "object": "block", "type": "paragraph",
  "paragraph": { "rich_text": [{"type":"text","text":{"content":"Body text"}}] } }

{ "object": "block", "type": "to_do",
  "to_do": { "rich_text": [{"type":"text","text":{"content":"Task"}}],
             "checked": false } }
```

## Usage pattern (agent prompt hint)

- One briefing per run → `CREATE_NOTION_PAGE` under `NOTION_RUNS_PAGE_ID`.
- Append summary + next-actions via `APPEND_BLOCK_CHILDREN`.
- Read last 7 runs via `QUERY_DATABASE` when building self-review context.
