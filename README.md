# LangSmith AI Agent - FDWA Multi-Platform Social Media Automation

Autonomous AI agent that researches trends, generates content, creates images, and posts to Twitter, Facebook, Instagram, and Telegram with full LangSmith tracing.

## Features

- 🔍 **Research Agent** - Automated trend research using Tavily
- ✍️ **Content Agent** - Template-based social media content generation (no external AI)
- 🎨 **Image Agent** - AI image generation with **Hugging Face Inference API** (100% FREE)
- 📱 **Social Media Agent** - Multi-platform posting (Twitter, Facebook, Instagram, LinkedIn, Telegram)
- 💬 **Telegram Crypto Agent** - DeFi/crypto market updates to Telegram groups
- 📊 **LangSmith Tracing** - Complete observability and monitoring

## Architecture

```
Research → Content Generation → Image Enhancement → Image Generation → Social Media Posting
```

### Agent Flow
1. **Research Agent** - Collects trending topics via Tavily search
2. **Content Agent** - Generates branded social media text (template-based, fast)
3. **Image Prompt Sub-Agent** - Cleans and enhances text into visual prompts
4. **Image Generation** - Creates images via **Hugging Face Stable Diffusion** (FREE)
5. **Social Media Agent** - Posts to Twitter and Facebook with images
6. **Telegram Crypto Agent** - Posts DeFi/crypto updates to Telegram groups
7. **LinkedIn/Instagram Agents** - Format and post to professional networks

## Setup

### Prerequisites
- Python 3.10+
- API Keys:
  - **Hugging Face API Token** (FREE - get at https://huggingface.co/settings/tokens)
  - Composio
  - LangSmith
  - Twitter (via Composio)
  - Facebook (via Composio)
  - Telegram Bot Token (via Composio)

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

# Hugging Face (FREE)
HF_TOKEN=hf_YourTokenHere

# Composio (for social media platforms)
COMPOSIO_API_KEY=your_composio_key

# Social Media Accounts
FACEBOOK_ACCOUNT_ID=your_facebook_account_id
FACEBOOK_PAGE_ID=your_facebook_page_id
INSTAGRAM_ACCOUNT_ID=your_instagram_account_id
INSTAGRAM_USER_ID=your_instagram_user_id
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_GROUP_USERNAME=@your_telegram_group
```

### Hugging Face Setup

See [HUGGINGFACE_SETUP.md](HUGGINGFACE_SETUP.md) for detailed instructions on:
- Getting your FREE Hugging Face API token
- Available models (Stable Diffusion, FLUX, etc.)
- Testing image generation
- Troubleshooting

## Usage

### Run the Agent

```bash
python src/agent/graph.py
```

### Test Hugging Face Image Generation

```bash
python src/agent/hf_image_gen.py
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
- **Google Gemini 2.5 Flash Image Preview** - AI image generation via Composio
- **Composio** - Twitter, Facebook, Tavily search integration
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
Image URL: https://s3.amazonaws.com/... (Gemini generated)
↓
Twitter: Posted ✅
Facebook: Posted ✅ (with image)
```

## License

MIT

## Author

FDWA - Future Digital Wealth Automation
