# GOOGLEDOCS Skill

Canonical Composio tools for Google Docs. Call via
`client.tools.execute(SLUG, arguments={...}, user_id=COMPOSIO_ENTITY_ID)`.

## Canonical tools

| Slug | Purpose |
|---|---|
| `GOOGLEDOCS_CREATE_DOCUMENT_MARKDOWN` | Create a new doc from markdown. Args: `title`, `markdown_content`. Returns `documentId`. |
| `GOOGLEDOCS_UPDATE_DOCUMENT_MARKDOWN` | Replace entire doc body with new markdown. Args: `document_id`, `markdown_content`. |
| `GOOGLEDOCS_GET_DOCUMENT_BY_ID` | Read doc metadata + body. Args: `document_id`. |
| `GOOGLEDOCS_INSERT_TEXT_ACTION` | Insert plain text at an index. Args: `document_id`, `text`, `index`. |
| `GOOGLEDOCS_EXPORT_DOCUMENT` | Export doc as PDF / DOCX. Args: `document_id`, `mime_type`. |
| `GOOGLEDOCS_SEARCH_DOCUMENTS` | List recent docs. Args: `query`, `page_size`. |

## Usage pattern

- Weekly report → single doc per week named `FDWA Weekly Report YYYY-WW`.
- Append each run by reading `GET_DOCUMENT_BY_ID`, concatenating, then
  `UPDATE_DOCUMENT_MARKDOWN` (markdown tool rewrites the whole body — safe
  because we control the full string).
- Do not call `INSERT_TEXT_ACTION` for markdown content; it inserts raw text
  and breaks formatting.
