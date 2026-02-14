#!/usr/bin/env python3
"""
Test SERPAPI and Tavily search tools independently to verify they work.
Also tests the _extract_search_insights function.
"""

import os
import sys
import logging
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from composio import Composio
from dotenv import load_dotenv

# Import the extraction function
from src.agent.graph import _extract_search_insights

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Composio client
composio_client = Composio(
    api_key=os.getenv("COMPOSIO_API_KEY"),
    entity_id=os.getenv("COMPOSIO_ENTITY_ID", "pg-test-e862c589-3f43-4cd7-9023-cc6ec5123c23")
)


def test_serpapi():
    """Test SERPAPI search tool"""
    print("\n" + "="*80)
    print("🔍 Testing SERPAPI Search")
    print("="*80 + "\n")
    
    try:
        query = "AI automation for business"
        logger.info(f"Searching SERPAPI for: {query}")
        
        response = composio_client.tools.execute(
            "SERPAPI_SEARCH",
            {"query": query},
            connected_account_id=os.getenv("SERPAPI_ACCOUNT_ID")
        )
        
        logger.info("✅ SERPAPI response received")
        
        # Check if successful
        if not response.get('successful'):
            print(f"❌ SERPAPI returned unsuccessful: {response.get('error')}")
            return False
        
        # Get data
        data = response.get('data', {})
        
        # Test extraction function
        print("\n🔧 Testing _extract_search_insights()...")
        extracted = _extract_search_insights(data)
        
        print(f"\n📝 Extracted insights ({len(extracted)} chars):")
        print("─" * 80)
        print(extracted[:500])
        if len(extracted) > 500:
            print("...")
        print("─" * 80)
        
        if extracted and extracted != "No results found" and len(extracted) > 50:
            print("\n✅ SERPAPI extraction successful!")
            return True
        else:
            print(f"\n❌ SERPAPI extraction failed - got: {extracted}")
            return False
        
    except Exception as e:
        logger.error(f"❌ SERPAPI failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tavily():
    """Test Tavily search tool"""
    print("\n" + "="*80)
    print("🔍 Testing Tavily Search")
    print("="*80 + "\n")
    
    try:
        query = "AI automation for business"
        logger.info(f"Searching Tavily for: {query}")
        
        response = composio_client.tools.execute(
            "TAVILY_SEARCH",
            {
                "query": query,
                "max_results": 5,
                "search_depth": "advanced",
                "include_answer": True,
                "include_raw_content": False
            },
            connected_account_id=os.getenv("TAVILY_ACCOUNT_ID")
        )
        
        logger.info("✅ Tavily response received")
        
        # Check if successful
        if not response.get('successful'):
            print(f"❌ Tavily returned unsuccessful: {response.get('error')}")
            return False
        
        # Get data
        data = response.get('data', {})
        
        # Test extraction function
        print("\n🔧 Testing _extract_search_insights()...")
        extracted = _extract_search_insights(data)
        
        print(f"\n📝 Extracted insights ({len(extracted)} chars):")
        print("─" * 80)
        print(extracted[:500])
        if len(extracted) > 500:
            print("...")
        print("─" * 80)
        
        if extracted and extracted != "No results found" and len(extracted) > 50:
            print("\n✅ Tavily extraction successful!")
            return True
        else:
            print(f"\n❌ Tavily extraction failed - got: {extracted}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Tavily failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🧪 SEARCH TOOLS TEST")
    print("="*80)
    
    # Test both search tools
    serpapi_works = test_serpapi()
    tavily_works = test_tavily()
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST RESULTS")
    print("="*80)
    print(f"\n  SERPAPI: {'✅ Working' if serpapi_works else '❌ Failed'}")
    print(f"  Tavily:  {'✅ Working' if tavily_works else '❌ Failed'}")
    
    if not serpapi_works and not tavily_works:
        print("\n⚠️  Both search tools failed! Check:")
        print("  1. COMPOSIO_API_KEY is set")
        print("  2. SERPAPI_ACCOUNT_ID is set")
        print("  3. TAVILY_ACCOUNT_ID is set")
        print("  4. Accounts are connected at https://app.composio.dev/")
    elif serpapi_works or tavily_works:
        print("\n✅ At least one search tool is working!")
        print("\n💡 The extraction function now correctly handles:")
        print("  • Nested Composio response structures (data.results.organic_results)")
        print("  • Direct response structures (data.organic_results)")
        print("  • Both SERPAPI and Tavily formats")
    
    print("\n" + "="*80 + "\n")


def test_serpapi():
    """Test SERPAPI search tool"""
    print("\n" + "="*80)
    print("🔍 Testing SERPAPI Search")
    print("="*80 + "\n")
    
    try:
        query = "AI automation for business"
        logger.info(f"Searching SERPAPI for: {query}")
        
        response = composio_client.tools.execute(
            "SERPAPI_SEARCH",
            {"query": query},
            connected_account_id=os.getenv("SERPAPI_ACCOUNT_ID")
        )
        
        logger.info("✅ SERPAPI response received")
        
        # Pretty print the response structure
        print("\n📊 Response Structure:")
        print(f"  Type: {type(response)}")
        print(f"  Keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
        
        if isinstance(response, dict):
            print(f"\n  successful: {response.get('successful')}")
            print(f"  error: {response.get('error')}")
            
            data = response.get('data', {})
            print(f"\n  data type: {type(data)}")
            print(f"  data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            # Check for organic_results
            if isinstance(data, dict):
                organic_results = data.get('organic_results', [])
                print(f"\n  organic_results found: {len(organic_results) if isinstance(organic_results, list) else 'Not a list'}")
                
                if isinstance(organic_results, list) and len(organic_results) > 0:
                    print("\n  First result:")
                    first = organic_results[0]
                    print(f"    title: {first.get('title', 'N/A')}")
                    print(f"    snippet: {first.get('snippet', 'N/A')[:100]}...")
                    return True
                else:
                    print(f"\n  ❌ organic_results is not a list or is empty: {type(organic_results)}")
                    print(f"  Full data: {json.dumps(data, indent=2)[:500]}...")
            else:
                print(f"\n  ❌ data is not a dict: {data}")
        
        return False
        
    except Exception as e:
        logger.error(f"❌ SERPAPI failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tavily():
    """Test Tavily search tool"""
    print("\n" + "="*80)
    print("🔍 Testing Tavily Search")
    print("="*80 + "\n")
    
    try:
        query = "AI automation for business"
        logger.info(f"Searching Tavily for: {query}")
        
        response = composio_client.tools.execute(
            "TAVILY_SEARCH",
            {
                "query": query,
                "max_results": 5,
                "search_depth": "advanced",
                "include_answer": True,
                "include_raw_content": False
            },
            connected_account_id=os.getenv("TAVILY_ACCOUNT_ID")
        )
        
        logger.info("✅ Tavily response received")
        
        # Pretty print the response structure
        print("\n📊 Response Structure:")
        print(f"  Type: {type(response)}")
        print(f"  Keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
        
        if isinstance(response, dict):
            print(f"\n  successful: {response.get('successful')}")
            print(f"  error: {response.get('error')}")
            
            data = response.get('data', {})
            print(f"\n  data type: {type(data)}")
            
            # Handle both dict and object responses
            if hasattr(data, '__dict__'):
                # It's an object, convert to dict
                data_dict = data.__dict__ if hasattr(data, '__dict__') else {}
                print(f"  data is object with attributes: {list(data_dict.keys())}")
                
                # Try to get results
                if hasattr(data, 'results'):
                    results = data.results
                    print(f"\n  results found: {len(results) if isinstance(results, list) else 'Not a list'}")
                    
                    if isinstance(results, list) and len(results) > 0:
                        print("\n  First result:")
                        first = results[0]
                        if hasattr(first, 'title'):
                            print(f"    title: {first.title}")
                        if hasattr(first, 'content'):
                            print(f"    content: {first.content[:100]}...")
                        return True
                elif hasattr(data, 'get'):
                    results = data.get('results', [])
                    print(f"\n  results found (via get): {len(results) if isinstance(results, list) else 'Not a list'}")
                    
                    if isinstance(results, list) and len(results) > 0:
                        print("\n  First result:")
                        first = results[0]
                        print(f"    title: {first.get('title', 'N/A') if isinstance(first, dict) else getattr(first, 'title', 'N/A')}")
                        print(f"    content: {first.get('content', 'N/A')[:100] if isinstance(first, dict) else getattr(first, 'content', 'N/A')[:100]}...")
                        return True
            elif isinstance(data, dict):
                print(f"  data keys: {list(data.keys())}")
                
                results = data.get('results', [])
                print(f"\n  results found: {len(results) if isinstance(results, list) else 'Not a list'}")
                
                if isinstance(results, list) and len(results) > 0:
                    print("\n  First result:")
                    first = results[0]
                    print(f"    title: {first.get('title', 'N/A')}")
                    print(f"    content: {first.get('content', 'N/A')[:100]}...")
                    return True
                else:
                    print(f"\n  ❌ results is not a list or is empty: {type(results)}")
                    print(f"  Full data: {json.dumps(data, indent=2)[:500]}...")
            else:
                print(f"\n  ❌ data is neither dict nor object: {type(data)}")
                print(f"  data value: {str(data)[:500]}...")
        
        return False
        
    except Exception as e:
        logger.error(f"❌ Tavily failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🧪 SEARCH TOOLS TEST")
    print("="*80)
    
    # Test both search tools
    serpapi_works = test_serpapi()
    tavily_works = test_tavily()
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST RESULTS")
    print("="*80)
    print(f"\n  SERPAPI: {'✅ Working' if serpapi_works else '❌ Failed'}")
    print(f"  Tavily:  {'✅ Working' if tavily_works else '❌ Failed'}")
    
    if not serpapi_works and not tavily_works:
        print("\n⚠️  Both search tools failed! Check:")
        print("  1. COMPOSIO_API_KEY is set")
        print("  2. SERPAPI_ACCOUNT_ID is set")
        print("  3. TAVILY_ACCOUNT_ID is set")
        print("  4. Accounts are connected at https://app.composio.dev/")
    elif serpapi_works or tavily_works:
        print("\n✅ At least one search tool is working!")
    
    print("\n" + "="*80 + "\n")
