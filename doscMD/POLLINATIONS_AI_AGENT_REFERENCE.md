# Pollinations.ai Image Generation - AI Agent Reference 🎨

## Overview for AI Agents

This document explains how the AI agent can use Pollinations.ai for **any image generation task**. Pollinations is now the PRIMARY image generator (with HuggingFace as automatic fallback).

---

## Quick Start for AI Agents

### When to Use:
- **Social media posts** (Twitter, Instagram, Facebook, LinkedIn) - Generate eye-catching visuals
- **Blog posts** - Create featured images and illustrations
- **Email campaigns** - Add professional graphics
- **Marketing materials** - Generate branded visuals
- **Product mockups** - Visualize concepts
- **Crypto trading posts** - Create chart-style graphics
- **Any visual content need** - Pollinations can generate it!

### Basic Usage:

```python
from src.agent.pollinations_image_gen import generate_image_with_fallback

# Generate image (automatic Pollinations → HF fallback)
result = generate_image_with_fallback(
    prompt="Your detailed prompt here",
    model="flux",  # Fast & free (5000 images per pollen)
    width=1024,
    height=1024,
    timeout=90
)

if result["success"]:
    image_bytes = result["image_bytes"]
    provider = result["provider"]  # "Pollinations.ai" or "HuggingFace (fallback)"
    # Use image_bytes for posting, saving, etc.
```

---

## Available Models 🎨

### FREE Models (1 pollen/day = 5000 images/day)

| Model | Key | Cost | Best For |
|-------|-----|------|----------|
| **FLUX Schnell** | `"flux"` | 0.0002 pollen/img | General use, FAST, high quality (DEFAULT) |
| **Z-Image Turbo** | `"zimage"` | 0.0002 pollen/img | Quick iterations, sketches |

### Premium Models (requires paid pollen)

| Model | Key | Cost | Best For |
|-------|-----|------|----------|
| **FLUX.2 Klein 4B** | `"flux-klein"` | 0.008 pollen/img | Better detail, colors |
| **FLUX.2 Klein 9B** | `"flux-klein-large"` | 0.012 pollen/img | Professional quality |
| **GPT Image 1 Mini** | `"gptimage"` | 0.0125 pollen/img | Photorealistic |
| **Seedream 4.0** | `"seedream"` | 0.03 pollen/img | Creative illustrations |
| **FLUX.1 Kontext** | `"kontext"` | 0.04 pollen/img | Context-aware generation |
| **Seedream 4.5 Pro** | `"seedream-pro"` | 0.04 pollen/img | Best quality |

**Recommendation**: Use `"flux"` (default) for 99% of use cases - it's FREE, fast, and excellent quality.

---

## Use Case Examples 🚀

### 1. Social Media Post Image

```python
from src.agent.pollinations_image_gen import generate_image_with_fallback, save_image_locally

# For Twitter/Instagram post about crypto trading
result = generate_image_with_fallback(
    prompt="Professional crypto trading dashboard showing Bitcoin and Ethereum charts, modern UI, dark theme, vibrant green and red candles, futuristic digital art",
    model="flux",
    width=1024,
    height=1024
)

if result["success"]:
    # Save locally
    filepath = save_image_locally(
        result["image_bytes"],
        provider=result["provider"]
    )
    print(f"✅ Image ready for posting: {filepath}")
```

### 2. Blog Featured Image

```python
# For blog about AI automation
result = generate_image_with_fallback(
    prompt="AI robot working at a computer with holographic screens showing automation workflows, modern office, professional business atmosphere, high detail",
    model="flux",
    width=1280,  # Wider for blog header
    height=720
)

if result["success"]:
    # Upload to public hosting
    from src.agent.pollinations_image_gen import upload_to_imgbb
    
    upload_result = upload_to_imgbb(result["image_bytes"])
    if upload_result["success"]:
        public_url = upload_result["url"]
        print(f"✅ Blog image URL: {public_url}")
```

### 3. Product Visualization

```python
# Generate mockup for FDWA tools
result = generate_image_with_fallback(
    prompt="Modern SaaS dashboard interface for financial automation, clean UI, professional color scheme, credit score charts, document automation features, 3D realistic mockup",
    model="flux-klein",  # Use premium for product mockups
    width=1536,
    height=1024
)
```

### 4. Brand Logo/Icon

```python
# Generate icon for app
result = generate_image_with_fallback(
    prompt="Minimalist logo for 'Yield Bot AI', cryptocurrency theme, modern geometric design, gold and blue colors, professional, transparent background, vector style",
    model="flux",
    width=512,
    height=512
)
```

### 5. Crypto Market Visualization

```python
# For Telegram crypto posts
result = generate_image_with_fallback(
    prompt="Cryptocurrency market data visualization with Bitcoin at $48,234 showing +5.23% gain, modern trading terminal style, dark background, green growth indicators, professional financial chart",
    model="flux",
    width=1024,
    height=1024
)
```

---

## Complete Function Reference 📚

### Main Function: `generate_image_with_fallback()`

**What it does**: Tries Pollinations.ai first (best quality, faster), automatically falls back to HuggingFace if Pollinations fails.

**Parameters**:
- `prompt` (str): Detailed description of image to generate
- `model` (str): Model key (default: `"flux"`)
- `width` (int): Image width - 512, 768, 1024, 1280, 1536, 2048
- `height` (int): Image height - 512, 768, 1024, 1280, 1536, 2048
- `timeout` (int): Request timeout in seconds (default: 90)

**Returns**:
```python
{
    "success": True,
    "image_bytes": b"...",  # Raw PNG data
    "provider": "Pollinations.ai",  # or "HuggingFace (fallback)"
    "model": "flux",
    "seed": 12345,  # Optional: for reproducibility
    "generation_time": 3.2  # seconds
}
```

### Advanced Function: `generate_image_pollinations()`

**What it does**: Direct Pollinations.ai generation (no fallback).

**Additional Parameters**:
- `seed` (int): Random seed for reproducibility (None = random)
- `nologo` (bool): Remove Pollinations watermark (default: True)
- `enhance` (bool): Use prompt enhancement (default: False)

**Use this when**: You specifically want Pollinations and don't want HuggingFace fallback.

### Helper Functions:

**`save_image_locally(image_bytes, filename, provider)`**
- Saves to `temp_images/` directory
- Auto-generates filename if not provided
- Returns absolute file path

**`upload_to_imgbb(image_bytes)`**
- Uploads to ImgBB for public HTTP URL
- Requires `IMGBB_API_KEY` in .env
- Returns dict with `url` and `delete_url`

---

## Prompt Engineering Tips 💡

### Good Prompts (Detailed & Specific):
✅ "Professional crypto trading dashboard showing Bitcoin at $48,234 with +5.23% gain, dark theme, vibrant green candles, modern UI, futuristic digital art, high detail"

✅ "AI robot analyzing financial documents, holographic screens, modern office, professional atmosphere, blue and gold color scheme, photorealistic"

✅ "Minimalist SaaS website hero image, credit score improvement concept, clean modern design, gradient blue background, 3D elements floating"

### Bad Prompts (Vague):
❌ "crypto chart" (too vague)
❌ "make an image about AI" (no details)
❌ "business stuff" (not specific)

### Prompt Structure:
```
[Subject] + [Action/Context] + [Style] + [Color Scheme] + [Quality/Detail]
```

Example:
```
AI robot (subject)
analyzing crypto trading charts (action/context)
digital art style (style)
vibrant neon colors (color scheme)
high detail, professional (quality)
```

---

## Integration with Existing Workflow 🔄

### Current Usage in Agent:
The agent already uses Pollinations in `generate_image_node()` ([graph.py](src/agent/graph.py#L1046)):

```python
from src.agent.pollinations_image_gen import (
    generate_image_with_fallback,
    save_image_locally,
    upload_to_imgbb,
)

result = generate_image_with_fallback(
    prompt=visual_prompt,
    model="flux",
    width=1024,
    height=1024,
    timeout=90
)
```

### How to Use in New Nodes:
Any new workflow node can import and use the same functions:

```python
def my_new_node(state: AgentState) -> dict:
    """Custom node that needs image generation."""
    from src.agent.pollinations_image_gen import generate_image_with_fallback
    
    # Generate image
    result = generate_image_with_fallback(
        prompt="Your custom prompt based on state",
        model="flux"
    )
    
    if result["success"]:
        return {"image_data": result["image_bytes"]}
    else:
        return {"error": result["error"]}
```

---

## Cost Management 💰

### Free Tier (1 pollen/day):
- **5,000 images/day** with FLUX Schnell (default)
- Resets daily at 00:00 UTC
- Unused pollen does NOT carry over
- **Current agent usage**: ~12 images/day (posts every 2 hours)
- **You're using only 0.24% of daily limit** ✅

### Paid Tiers (if you need more):
| Purchase | Pollen | Bonus (beta) | Total Pollen | Images (FLUX) |
|----------|--------|--------------|--------------|---------------|
| $5 | 5 | +5 | 10 | 50,000 images |
| $10 | 10 | +10 | 20 | 100,000 images |
| $20 | 20 | +20 | 40 | 200,000 images |
| $50 | 50 | +50 | 100 | 500,000 images |

**Recommendation**: Free tier is MORE than enough for current usage.

---

## Error Handling 🚨

### Automatic Fallback:
If Pollinations fails for ANY reason, HuggingFace automatically takes over:
- Network issues
- API rate limits
- Insufficient pollen
- Service downtime

### Manual Error Checking:
```python
result = generate_image_with_fallback(prompt="...")

if result["success"]:
    # Handle success
    image = result["image_bytes"]
    provider = result["provider"]
    logger.info(f"Generated with {provider}")
else:
    # Handle failure (should be rare with fallback)
    error = result["error"]
    logger.error(f"Both providers failed: {error}")
```

### Common Errors:

| Error | Cause | Solution |
|-------|-------|----------|
| "Invalid API key" | Wrong key in .env | Check `POLLINATIONS_API_KEY` |
| "Insufficient pollen" | Out of daily/paid pollen | Wait for daily reset or buy more |
| "Rate limit exceeded" | Too many requests | Wait or upgrade tier |
| "Both providers failed" | Both P + HF down | Rare - retry later |

---

## Advanced Features 🔬

### 1. Reproducible Images (Same Seed):
```python
# Generate image with specific seed
result = generate_image_pollinations(
    prompt="Same prompt every time",
    seed=12345,  # Use same seed for identical results
    model="flux"
)

# Save seed for later
if result["success"]:
    seed = result["seed"]
    print(f"Use seed {seed} to regenerate this exact image")
```

### 2. Prompt Enhancement:
```python
# Let Pollinations enhance your prompt
result = generate_image_pollinations(
    prompt="simple crypto chart",  # Vague prompt
    enhance=True,  # AI will improve it
    model="flux"
)
# Pollinations will expand to something like:
# "Professional cryptocurrency trading chart with detailed 
#  candlesticks, modern UI, financial data visualization..."
```

### 3. No Watermark (Premium):
```python
result = generate_image_pollinations(
    prompt="...",
    nologo=True,  # Remove Pollinations logo (default: True)
    model="flux"
)
```

### 4. Custom Dimensions:
Common aspect ratios:
- **Square**: 1024x1024 (Instagram, profile pics)
- **Landscape**: 1280x720, 1536x864 (Twitter, blog headers)
- **Portrait**: 720x1280, 864x1536 (Instagram Stories)
- **Widescreen**: 2048x1024 (banners, covers)

---

## Comparison: Pollinations vs HuggingFace 📊

| Feature | Pollinations.ai | HuggingFace |
|---------|-----------------|-------------|
| **Speed** | 2-5 seconds | 5-15 seconds |
| **Quality** | Excellent | Good |
| **Models** | 15+ models | 6 models |
| **Free Tier** | 5K images/day | Unlimited (rate limited) |
| **Reliability** | 99%+ uptime | 95%+ uptime |
| **Watermark** | Removable | None |
| **API** | REST (simple) | InferenceClient |
| **Cost** | 0.0002 pollen/img | Free |

**Winner**: Pollinations (faster, more models, better quality)  
**Fallback**: HuggingFace (100% free, reliable)

---

## Testing Image Generation 🧪

### Test from Command Line:
```bash
cd ai-agent
python -c "from src.agent.pollinations_image_gen import test_pollinations_image_gen; test_pollinations_image_gen()"
```

**Output**:
```
🧪 Testing Pollinations.ai Image Generation

Prompt: A futuristic AI robot analyzing crypto trading charts...

🌸 Trying Pollinations.ai first...
✅ SUCCESS with Pollinations.ai!
   Provider: Pollinations.ai
   Model: flux
   Size: 1,234,567 bytes
   Seed: 12345
   Saved to: C:\...\temp_images\pollinations_image_20260215_150032.png
   Public URL: https://i.ibb.co/...
```

### Test in Python:
```python
from src.agent.pollinations_image_gen import generate_image_with_fallback

result = generate_image_with_fallback(
    prompt="Test image: futuristic robot",
    model="flux"
)

print(f"Success: {result['success']}")
print(f"Provider: {result.get('provider')}")
print(f"Size: {len(result.get('image_bytes', b'')):,} bytes")
```

---

## Best Practices 🌟

### 1. Use Default Settings:
```python
# This is optimal for 99% of use cases:
result = generate_image_with_fallback(
    prompt=your_detailed_prompt,
    model="flux",  # Fast & free
    width=1024,
    height=1024,
    timeout=90
)
```

### 2. Save API Credits:
- Use FLUX Schnell (`"flux"`) for most images
- Only use premium models for high-value content (product launches, etc.)
- Reuse images when possible (save locally)

### 3. Prompt Quality:
- Be specific and detailed
- Include style, colors, mood
- Test prompts and save good ones
- Use negative prompts when needed (HF only)

### 4. Error Handling:
- Always check `result["success"]`
- Log which provider was used
- Have a placeholder image ready (fallback)

### 5. Performance:
- Cache generated images (don't regenerate same prompt)
- Use appropriate dimensions (don't generate 4K for thumbnails)
- Set reasonable timeouts (90s is good default)

---

## FAQ ❓

**Q: Do I need a Pollinations API key?**  
A: Technically no (free tier works without), but YES for reliability and higher limits. Already added to `.env`!

**Q: What happens if I run out of pollen?**  
A: Agent automatically falls back to HuggingFace (free, unlimited). No failures!

**Q: Which model should I use?**  
A: Use default `"flux"` (FLUX Schnell) - it's fast, free (5K/day), and excellent quality.

**Q: Can I generate videos?**  
A: Not yet - Pollinations has video APIs but not integrated. Could be added later!

**Q: How do I get more pollen?**  
A: Buy at https://pollinations.ai - $5 gets 10 pollen (50K images) with beta bonus.

**Q: Is HuggingFace slower?**  
A: Yes, 2-3x slower than Pollinations, but still good quality as fallback.

**Q: Can I customize the fallback behavior?**  
A: Yes! Edit `generate_image_with_fallback()` in [pollinations_image_gen.py](src/agent/pollinations_image_gen.py#L176)

---

## Reference Links 🔗

- **Pollinations Dashboard**: https://pollinations.ai
- **API Documentation**: https://pollinations.ai/docs
- **Model List**: https://pollinations.ai/models
- **Pricing**: https://pollinations.ai/pricing
- **Discord Support**: https://discord.gg/pollinations
- **GitHub Issues**: https://github.com/pollinations/pollinations/issues

---

## Summary for AI Agents 🤖

**Default Usage** (recommended):
```python
from src.agent.pollinations_image_gen import generate_image_with_fallback

result = generate_image_with_fallback(
    prompt="Detailed prompt about what to generate",
    model="flux"
)

if result["success"]:
    # Use result["image_bytes"] for posting/saving
    # Check result["provider"] to see which service was used
    pass
```

**Key Benefits**:
- ✅ Faster than HuggingFace (2-5 seconds vs 5-15 seconds)
- ✅ Better quality (newer FLUX models)
- ✅ More models available (15+ vs 6)
- ✅ Automatic fallback (never fails)
- ✅ Free tier is generous (5K images/day)
- ✅ Already integrated into workflow

**Cost**: FREE (5000 images/day = far more than needed)  
**Location**: [src/agent/pollinations_image_gen.py](src/agent/pollinations_image_gen.py)  
**Current Usage**: Image generation for all social posts and blogs  
**Future Use Cases**: Product mockups, marketing, visualizations, etc.

---

**Last Updated**: February 15, 2026  
**Version**: v1.0  
**Status**: PRODUCTION READY ✅  
**Primary Generator**: Pollinations.ai ✅  
**Fallback Generator**: HuggingFace ✅
