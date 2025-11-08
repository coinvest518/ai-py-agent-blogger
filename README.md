# LangSmith AI Agent - FDWA Multi-Platform Social Media Automation

Autonomous AI agent that researches trends, generates content, creates images, and posts to Twitter and Facebook with full LangSmith tracing.

## Features

- 🔍 **Research Agent** - Automated trend research using SERP API
- ✍️ **Content Agent** - AI-powered social media content generation
- 🎨 **Image Agent** - AI image generation with Pollinations API
- 📱 **Social Media Agent** - Multi-platform posting (Twitter + Facebook)
- 📊 **LangSmith Tracing** - Complete observability and monitoring

## Architecture

```
Research → Content Generation → Image Enhancement → Image Generation → Social Media Posting
```

### Agent Flow
1. **Research Agent** - Collects trending topics via SERP API
2. **Content Agent** - Generates branded social media text using Google Gemini
3. **Image Prompt Sub-Agent** - Cleans and enhances text into visual prompts
4. **Image Generation** - Creates images via Pollinations API
5. **Social Media Agent** - Posts to Twitter and Facebook with images

## Setup

### Prerequisites
- Python 3.10+
- API Keys:
  - Google AI (Gemini)
  - Composio
  - LangSmith
  - Twitter (via Composio)
  - Facebook (via Composio)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/coinvest518/Lnagsmith-ai-agent.git
cd Lnagsmith-ai-agent
```

2. Install dependencies:
```bash
pip install -e .
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys
```

### Environment Variables

```env
# LangSmith Tracing
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT=fdwa-multi-agent
LANGSMITH_WORKSPACE_ID=your_workspace_id

# AI Models
GOOGLE_AI_API_KEY=your_google_ai_key

# Composio (for Twitter, Facebook, SERP)
COMPOSIO_API_KEY=your_composio_key

# Social Media Accounts
FACEBOOK_ACCOUNT_ID=your_facebook_account_id
FACEBOOK_PAGE_ID=your_facebook_page_id
```

## Usage

### Run the Agent

```bash
python src/agent/graph.py
```

### LangGraph Studio

```bash
langgraph dev
```

Then open: http://localhost:8123

## Project Structure

```
ai-agent/
├── src/
│   └── agent/
│       ├── graph.py              # Main agent graph
│       ├── image_prompt_agent.py # Image prompt enhancement
│       └── api.py                # FastAPI endpoints
├── langgraph.json                # LangGraph configuration
├── .env                          # Environment variables (not in git)
├── .env.example                  # Environment template
└── pyproject.toml                # Python dependencies
```

## API Integrations

- **Google Gemini 2.5 Flash Lite** - Content generation
- **Pollinations AI** - Image generation (Flux model)
- **Composio** - Twitter, Facebook, SERP API integration
- **LangSmith** - Tracing and observability

## LangSmith Tracing

All agent executions are traced in LangSmith:
- Individual agent steps
- Tool executions
- Error tracking
- Performance metrics

View traces at: https://smith.langchain.com

## Output Example

```
Research: "AI automation business trends"
↓
Content: "Digital wealth isn't just about managing money; it's about the systems..."
↓
Image Prompt: "A modern, professional image depicting business automation..."
↓
Image URL: https://image.pollinations.ai/prompt/...
↓
Twitter: Posted ✅
Facebook: Posted ✅ (with image)
```

## License

MIT

## Author

FDWA - Future Digital Wealth Automation
