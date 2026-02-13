import os
import json
from src.agent.blog_email_agent import generate_blog_content

# Force LLM-only (no template fallback)
os.environ["BLOG_REQUIRE_LLM"] = "true"
# For this test force use of Hugging Face by clearing Mistral key in-process
os.environ.pop("MISTRAL_API_KEY", None)
# Optional: prefer Mistral first (already default). Set a small test trend.
trend_data = (
    "AI automation for SMB marketing shows strong ROI: automated funnels can increase conversions by 20-40% (estimate)."
)

print('BLOG_REQUIRE_LLM =', os.environ.get('BLOG_REQUIRE_LLM'))

try:
    result = generate_blog_content(trend_data)
    print('\n=== LLM generation result ===')
    print(json.dumps(result, indent=2, ensure_ascii=False))
except Exception as e:
    print('\nLLM generation raised an exception:')
    import traceback
    traceback.print_exc()
