# Hugging Face Image Generation Setup

This project uses **Hugging Face Inference API** for FREE AI image generation, replacing Google Gemini.

## Why Hugging Face?

- ✅ **100% FREE** - No credit card required
- ✅ **No API costs** - Unlimited free tier for inference
- ✅ **Multiple models** - Stable Diffusion, FLUX, and more
- ✅ **High quality** - Professional AI-generated images
- ✅ **No Google AI dependencies** - Complete independence

## Getting Your Free API Token

### Step 1: Create Hugging Face Account
1. Go to https://huggingface.co/join
2. Sign up with email or GitHub
3. Verify your email address

### Step 2: Generate API Token
1. Go to https://huggingface.co/settings/tokens
2. Click **"New token"**
3. Name it: `ai-agent-image-gen`
4. Type: **Read** (default)
5. Click **"Generate"**
6. Copy your token (starts with `hf_...`)

### Step 3: Add to Environment
Add to your `.env` file:

```env
# Hugging Face API Token (FREE)
HUGGINGFACE_API_TOKEN=hf_YourTokenHere123456789
```

**Important:** Never commit your `.env` file with the token to git!

## Available Models

The agent uses these FREE models from Hugging Face:

| Model | Speed | Quality | Best For |
|-------|-------|---------|----------|
| `stable-diffusion-2` | Medium | High | Default (recommended) |
| `stable-diffusion-xl` | Slow | Very High | Detailed images |
| `stable-diffusion` (v1.5) | Fast | Good | Quick generation |
| `flux-schnell` | Very Fast | High | Rapid turnaround |

Default: **stable-diffusion-2** (best balance of speed and quality)

## How It Works

1. **Tweet Generated** → AI creates social media post
2. **Visual Prompt Created** → Post converted to image description
3. **HF API Called** → Stable Diffusion generates image (512x512)
4. **Image Saved** → Stored in `temp_images/` folder
5. **Posted** → Uploaded to Twitter, Instagram, etc.

## Configuration

Edit `src/agent/hf_image_gen.py` to customize:

```python
generate_image_hf(
    prompt="Your image description",
    model="stable-diffusion-2",  # Change model here
    negative_prompt="blurry, low quality",  # What to avoid
    width=512,  # Image width (512, 768, 1024)
    height=512,  # Image height (512, 768, 1024)
    num_inference_steps=25,  # Higher = better quality (slower)
    guidance_scale=7.5,  # How closely to follow prompt (7-15)
)
```

## Testing Image Generation

Run the test script:

```powershell
python src/agent/hf_image_gen.py
```

This will:
- Test your API token
- Generate a sample image
- Save it to `temp_images/test_hf_gen.png`

## Troubleshooting

### Error: "HUGGINGFACE_API_TOKEN not set"
- Make sure `.env` file exists in project root
- Verify token is set: `HUGGINGFACE_API_TOKEN=hf_...`
- Load environment: `from dotenv import load_dotenv; load_dotenv()`

### Error: "Model loading" (503)
- Model is starting up (cold start)
- Agent automatically waits 20s and retries
- Usually succeeds on second attempt

### Error: "Request timeout"
- Increase timeout: `timeout=120`
- Try faster model: `model="flux-schnell"`

### Error: "Invalid API token"
- Check token on https://huggingface.co/settings/tokens
- Generate new token with **Read** permissions
- Update `.env` file

## Rate Limits

Hugging Face Inference API (FREE tier):
- **No hard rate limit** for most models
- May experience throttling with very high usage
- Cold starts take 10-20 seconds (model loading)
- Subsequent requests are much faster

## Comparison: Gemini vs Hugging Face

| Feature | Google Gemini | Hugging Face |
|---------|---------------|--------------|
| Cost | Paid API | 100% FREE |
| Setup | Google AI API Key | HF Token (1 min) |
| Speed | Fast (2-5s) | Medium (5-25s) |
| Quality | Excellent | Excellent |
| Models | Gemini only | 10+ models |
| Dependencies | langchain_google_genai | requests (built-in) |

## Advanced: Local Generation

For faster generation with GPU:

```python
from diffusers import DiffusionPipeline
import torch

pipe = DiffusionPipeline.from_pretrained(
    "stabilityai/stable-diffusion-2-1",
    torch_dtype=torch.float16
)
pipe.to("cuda")

image = pipe("Your prompt here").images[0]
image.save("output.png")
```

**Requires:**
- NVIDIA GPU with 8GB+ VRAM
- `pip install diffusers transformers accelerate`
- ~5GB disk space for model download

## Support

- Hugging Face Docs: https://huggingface.co/docs/api-inference
- Stable Diffusion Models: https://huggingface.co/stabilityai
- FLUX Models: https://huggingface.co/black-forest-labs

---

**Next Steps:**
1. Get your free token at https://huggingface.co/settings/tokens
2. Add to `.env` file
3. Test with `python src/agent/hf_image_gen.py`
4. Run full agent workflow! 🚀
