#!/usr/bin/env python3
"""
Detailed diagnostic test for SERPAPI and Tavily search tools.
Shows actual error messages and response structures.
"""

import os
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from composio import Composio

def print_separator(title: str = ""):
    """Print a visual separator"""
    print("\n" + "="*80)
    if title:
        print(f"  {title}")
        print("="*80)
    print()


def test_serpapi_detailed():
    """Test SERPAPI with full error details"""
    print_separator("🔍 TESTING SERPAPI")
    
    try:
        # Initialize Composio
        composio_client = Composio(
            api_key=os.getenv("COMPOSIO_API_KEY"),
            entity_id=os.getenv("COMPOSIO_ENTITY_ID", "pg-test-e862c589-3f43-4cd7-9023-cc6ec5123c23")
        )
        
        print("✅ Composio client initialized")
        print(f"   API Key: {os.getenv('COMPOSIO_API_KEY')[:15]}...")
        print(f"   Entity ID: {os.getenv('COMPOSIO_ENTITY_ID', 'pg-test-e862c589-3f43-4cd7-9023-cc6ec5123c23')}")
        print(f"   SERPAPI Account ID: {os.getenv('SERPAPI_ACCOUNT_ID')}")
        print()
        
        # Test SERPAPI search
        print("🔎 Executing SERPAPI search...")
        query = "AI automation trends 2026"
        print(f"   Query: {query}")
        
        response = composio_client.tools.execute(
            "SERPAPI_SEARCH",
            {"query": query},
            connected_account_id=os.getenv("SERPAPI_ACCOUNT_ID")
        )
        
        print("\n📦 RAW RESPONSE:")
        print(json.dumps(response, indent=2, default=str)[:1000])
        print()
        
        # Check response structure
        print("📊 RESPONSE STRUCTURE:")
        print(f"   Type: {type(response)}")
        print(f"   Keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
        
        if isinstance(response, dict):
            print(f"   Successful: {response.get('successful', 'N/A')}")
            print(f"   Error: {response.get('error', 'None')}")
            
            data = response.get('data', {})
            print(f"   Data type: {type(data)}")
            print(f"   Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            # Check nested structure
            if isinstance(data, dict):
                if 'results' in data:
                    results = data.get('results', {})
                    print(f"   Results type: {type(results)}")
                    if isinstance(results, dict):
                        print(f"   Results keys: {list(results.keys())[:10]}")
                        if 'organic_results' in results:
                            organic = results['organic_results']
                            print(f"   Organic results count: {len(organic) if isinstance(organic, list) else 'Not a list'}")
                            if isinstance(organic, list) and len(organic) > 0:
                                print(f"   First result keys: {list(organic[0].keys())}")
                elif 'organic_results' in data:
                    organic = data['organic_results']
                    print(f"   Direct organic_results count: {len(organic) if isinstance(organic, list) else 'Not a list'}")
        
        # Test extraction
        print("\n🔧 TESTING EXTRACTION:")
        from src.agent.graph import _extract_search_insights
        try:
            insights = _extract_search_insights(response.get('data', {}))
            print(f"   ✅ Extracted {len(insights)} characters")
            print(f"   Preview: {insights[:200]}...")
            return True
        except Exception as e:
            print(f"   ❌ Extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"\n❌ SERPAPI TEST FAILED:")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tavily_detailed():
    """Test Tavily with full error details"""
    print_separator("🌐 TESTING TAVILY")
    
    try:
        # Initialize Composio
        composio_client = Composio(
            api_key=os.getenv("COMPOSIO_API_KEY"),
            entity_id=os.getenv("COMPOSIO_ENTITY_ID", "pg-test-e862c589-3f43-4cd7-9023-cc6ec5123c23")
        )
        
        print("✅ Composio client initialized")
        print(f"   API Key: {os.getenv('COMPOSIO_API_KEY')[:15]}...")
        print(f"   Entity ID: {os.getenv('COMPOSIO_ENTITY_ID', 'pg-test-e862c589-3f43-4cd7-9023-cc6ec5123c23')}")
        print(f"   Tavily Account ID: {os.getenv('TAVILY_ACCOUNT_ID')}")
        print()
        
        # Test Tavily search
        print("🔎 Executing Tavily search...")
        query = "AI automation trends 2026"
        print(f"   Query: {query}")
        
        response = composio_client.tools.execute(
            "TAVILY_SEARCH",
            {
                "query": query,
                "max_results": 5,
                "search_depth": "advanced",
                "include_answer": True,
                "include_raw_content": True
            },
            connected_account_id=os.getenv("TAVILY_ACCOUNT_ID")
        )
        
        print("\n📦 RAW RESPONSE:")
        print(json.dumps(response, indent=2, default=str)[:1000])
        print()
        
        # Check response structure
        print("📊 RESPONSE STRUCTURE:")
        print(f"   Type: {type(response)}")
        print(f"   Keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
        
        if isinstance(response, dict):
            print(f"   Successful: {response.get('successful', 'N/A')}")
            print(f"   Error: {response.get('error', 'None')}")
            
            data = response.get('data', {})
            print(f"   Data type: {type(data)}")
            print(f"   Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            # Check nested structure
            if isinstance(data, dict):
                if 'response_data' in data:
                    response_data = data.get('response_data', {})
                    print(f"   Response_data type: {type(response_data)}")
                    if isinstance(response_data, dict):
                        print(f"   Response_data keys: {list(response_data.keys())[:10]}")
                        if 'results' in response_data:
                            results = response_data['results']
                            print(f"   Results count: {len(results) if isinstance(results, list) else 'Not a list'}")
                            if isinstance(results, list) and len(results) > 0:
                                print(f"   First result keys: {list(results[0].keys())}")
                elif 'results' in data:
                    results = data['results']
                    print(f"   Direct results count: {len(results) if isinstance(results, list) else 'Not a list'}")
        
        # Test extraction
        print("\n🔧 TESTING EXTRACTION:")
        from src.agent.graph import _extract_search_insights
        try:
            insights = _extract_search_insights(response.get('data', {}))
            print(f"   ✅ Extracted {len(insights)} characters")
            print(f"   Preview: {insights[:200]}...")
            return True
        except Exception as e:
            print(f"   ❌ Extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"\n❌ TAVILY TEST FAILED:")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print_separator("🧪 DETAILED SEARCH TOOLS DIAGNOSTIC")
    
    print("Environment Variables:")
    print(f"  COMPOSIO_API_KEY: {'✅ Set' if os.getenv('COMPOSIO_API_KEY') else '❌ Missing'}")
    print(f"  SERPAPI_ACCOUNT_ID: {'✅ Set' if os.getenv('SERPAPI_ACCOUNT_ID') else '❌ Missing'}")
    print(f"  TAVILY_ACCOUNT_ID: {'✅ Set' if os.getenv('TAVILY_ACCOUNT_ID') else '❌ Missing'}")
    
    # Test both
    serpapi_result = test_serpapi_detailed()
    tavily_result = test_tavily_detailed()
    
    # Summary
    print_separator("📊 SUMMARY")
    print(f"SERPAPI: {'✅ Working' if serpapi_result else '❌ Failed'}")
    print(f"Tavily:  {'✅ Working' if tavily_result else '❌ Failed'}")
    print()
    
    if not serpapi_result or not tavily_result:
        print("⚠️  Issues detected. Check the detailed output above.")
        print("   Common fixes:")
        print("   1. Reconnect accounts at https://app.composio.dev/")
        print("   2. Verify account IDs match connected accounts")
        print("   3. Check API quotas/limits")
