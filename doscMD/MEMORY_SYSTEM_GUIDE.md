# 🧠 Long-Term Memory System for FDWA AI Agent

## Overview

Your AI agent now has **persistent long-term memory** powered by LangGraph's memory store. This replaces the simple JSON file with a professional, searchable, and scalable memory system.

## What is Long-Term Memory?

Long-term memory allows your AI agent to:
- **Remember user preferences** (best posting times, successful topics)
- **Learn from performance** (which content got engagement, which products worked)
- **Track patterns** (platform-specific insights, crypto trading patterns)
- **Avoid mistakes** (remember failed attempts)
- **Improve over time** (get smarter with each post)

## Architecture

```
┌─────────────────────────────────────────────────┐
│         AI Agent (LangGraph Workflow)          │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────┐        ┌─────────────┐      │
│  │ Memory Tools │◄──────►│ LangGraph   │      │
│  │ (Read/Write) │        │ Store       │      │
│  └──────────────┘        └─────────────┘      │
│         │                       │              │
│         ▼                       ▼              │
│  ┌──────────────┐        ┌─────────────┐      │
│  │  Decision    │        │  Namespaces │      │
│  │  Engine      │        │  (organized)│      │
│  └──────────────┘        └─────────────┘      │
│                                                 │
└─────────────────────────────────────────────────┘

Memory Namespaces:
  - user/preferences/{user_id}
  - content/performance/{user_id}/{platform}
  - products/mentions/{user_id}
  - crypto/insights/{user_id}/{token}
```

## Key Features

### 1. **Organized Namespaces**
Memory is organized like folders:
- `("user", "preferences", "fdwa_agent")` - User preferences
- `("content", "performance", "fdwa_agent", "twitter")` - Twitter content performance
- `("products", "mentions", "fdwa_agent")` - Product performance tracking
- `("crypto", "insights", "fdwa_agent", "BTC")` - Bitcoin trading insights

### 2. **Semantic Search**
Search memory by meaning, not just exact keywords:
```python
# Find all memories related to "posting times"
results = store.search_memory(query="when is best time to post", limit=5)
```

### 3. **Automatic Learning**
The AI Decision Engine automatically learns:
- Which topics get high engagement
- Which products drive conversions
- Best times to post per platform
- What content to avoid

### 4. **Persistent Across Runs**
Unlike the old JSON file, memory store:
- Survives crashes and restarts
- Scales to millions of entries
- Can use database backends (PostgreSQL, SQLite)
- Supports concurrent access

## Quick Start

### Step 1: Migrate Existing Memory

Run the migration script to move your old `agent_memory.json` data:

```bash
python migrate_memory.py
```

This will:
- ✅ Transfer all successful topics
- ✅ Migrate product mentions
- ✅ Move best posting times
- ✅ Copy high engagement posts
- ✅ Preserve failed attempts
- ✅ Create backup of old JSON file

### Step 2: Memory is Automatically Active

**The AI Decision Engine now uses memory store by default!**

No code changes needed. It will automatically:
- Remember successful topics when generating content
- Track product performance when making product selections
- Learn posting patterns over time

### Step 3: (Optional) Use Memory Tools in Your Workflow

If you want the LLM to directly query memory, add tools to your agent:

```python
from src.agent.memory_tools import ALL_MEMORY_TOOLS
from src.agent.memory_tools import AgentContext

# When creating your agent, add memory tools
tools = ALL_MEMORY_TOOLS + other_tools

# Provide context when running
context = AgentContext(
    user_id="fdwa_agent",
    platform="twitter",
    topic="AI automation"
)
```

## Usage Examples

### Reading Memory (Manual)

```python
from src.agent.memory_store import get_memory_store

store = get_memory_store()

# Get successful topics
topics = store.get_successful_topics(platform="twitter", limit=10)
print(f"Top topics: {topics}")

# Get top products
products = store.get_top_products(limit=5)
for p in products:
    print(f"{p['product_name']}: {p['total_engagement']} engagement")

# Get user preferences
best_time = store.get_user_preference("best_posting_time", default="9:00 AM")
print(f"Best posting time: {best_time}")

# Get crypto insights
btc_insights = store.get_crypto_insights(token_symbol="BTC", limit=5)
print(f"Bitcoin insights: {btc_insights}")
```

### Writing Memory (Manual)

```python
from src.agent.memory_store import get_memory_store

store = get_memory_store()

# Record successful post
store.record_post_performance(
    topic="AI automation",
    platform="twitter",
    engagement=147,  # likes + comments + shares
    success=True,
    metadata={"hashtags": ["#AI", "#automation"]}
)

# Track product mention
store.record_product_mention(
    product_name="AI Business Automation System",
    platform="twitter",
    engagement=89,
    conversion=True  # Did it lead to a sale?
)

# Save preference
store.save_user_preference("best_posting_time", "9:00 AM EST")

# Record crypto insight
store.record_crypto_insight(
    token_symbol="BTC",
    insight_type="high_trade_score",
    data={
        "score": 87,
        "profit_probability": 72,
        "signal": "STRONG_BUY"
    }
)
```

### Automatic Memory (AI Decision Engine)

The AI Decision Engine uses memory automatically:

```python
from src.agent.ai_decision_engine import get_decision_engine

engine = get_decision_engine()

# Get content strategy (consults memory automatically)
strategy = engine.get_content_strategy(trend_data="AI automation trends...")

# Strategy includes:
# - Successful topics from memory
# - Top performing products
# - Platform best practices learned over time

# Record post outcome (saves to memory automatically)
engine.record_post_outcome(
    topic="AI automation",
    products=["AI Business System", "ChatGPT Guide"],
    platform="twitter",
    engagement=150,
    success=True
)
```

## Memory Store vs JSON File

| Feature | Old JSON File | New Memory Store |
|---------|--------------|------------------|
| **Storage** | Single JSON file | Organized namespaces |
| **Search** | Manual parsing | Semantic search |
| **Scalability** | Limited (~10K entries) | Millions of entries |
| **Concurrent Access** | ❌ File locks | ✅ Safe concurrent |
| **Querying** | Load entire file | Query specific data |
| **Relationships** | Manual tracking | Native support |
| **Analytics** | Manual calculation | Built-in aggregation |
| **Backup** | Copy file | Database snapshots |

## Production Deployment

For production, use a database-backed store instead of InMemoryStore:

```python
from langgraph.store.postgres import PostgresStore

# PostgreSQL backend (recommended for production)
store = PostgresStore(
    connection_string="postgresql://user:pass@localhost/agent_memory"
)

# Initialize memory store with database backend
from src.agent.memory_store import initialize_memory_store
memory = initialize_memory_store(store, user_id="fdwa_agent")
```

## API Reference

### AgentMemoryStore

#### User Preferences
- `save_user_preference(key, value)` - Save a preference
- `get_user_preference(key, default)` - Get a preference
- `get_all_user_preferences()` - Get all preferences

#### Content Performance
- `record_post_performance(topic, platform, engagement, success, metadata)` - Record post
- `get_successful_topics(platform, limit)` - Get top topics
- `get_platform_best_practices(platform)` - Get insights for platform

#### Product Tracking
- `record_product_mention(product_name, platform, engagement, conversion)` - Track product
- `get_top_products(limit)` - Get best performing products

#### Crypto Insights
- `record_crypto_insight(token_symbol, insight_type, data)` - Record crypto insight
- `get_crypto_insights(token_symbol, limit)` - Get token insights

#### General Memory
- `save_memory(key, value, namespace)` - Save arbitrary data
- `get_memory(key, namespace, default)` - Get data by key
- `search_memory(query, filter_dict, namespace, limit)` - Semantic search

## Troubleshooting

### Issue: Old JSON file still being used

**Solution:** Make sure `use_memory_store=True` when creating AIDecisionEngine:
```python
engine = AIDecisionEngine(use_memory_store=True)  # Default is True
```

### Issue: Memory not persisting

**Solution:** You're using InMemoryStore (default). For persistent memory, use PostgresStore or SQLite:
```python
from langgraph.store.sqlite import SQLiteStore
store = SQLiteStore(db_path="./agent_memory.db")
```

### Issue: Migration failed

**Solution:** Check that `agent_memory.json` exists and is valid JSON. Run:
```bash
python -c "import json; json.load(open('agent_memory.json'))"
```

## Next Steps

1. ✅ Run migration: `python migrate_memory.py`
2. ✅ Test with existing workflow (memory is automatic)
3. ✅ Monitor memory growth: Check namespaces and data
4. ✅ (Optional) Add memory tools for LLM direct access
5. ✅ (Production) Switch to database-backed store

## Learn More

- **LangGraph Store Docs**: https://langchain-ai.github.io/langgraph/concepts/persistence/
- **Memory Best Practices**: See LangGraph documentation on memory patterns
- **Database Backends**: PostgreSQL, SQLite, or custom implementations

---

**Your AI agent is now smarter and keeps getting better! 🚀**
