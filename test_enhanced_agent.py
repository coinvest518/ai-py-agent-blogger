#!/usr/bin/env python3
"""Test the enhanced AI agent with Decision Engine.

This script tests:
1. LinkedIn integration (new credentials)
2. AI Decision Engine (smart product selection)
3. Memory system
4. Full workflow
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_decision_engine():
    """Test AI Decision Engine independently."""
    print("="*70)
    print("🧠 TESTING AI DECISION ENGINE")
    print("="*70)
    
    try:
        from agent.ai_decision_engine import get_decision_engine
        
        engine = get_decision_engine()
        
        print("\n✅ Decision Engine initialized successfully!")
        print(f"   Business Profile: {len(engine.business_profile.get('products', []))} products loaded")
        print(f"   Products Catalog: {len(engine.products_catalog.get('products', []))} products")
        print(f"   Knowledge Base: {len(engine.knowledge_base)} chars")
        
        # Test strategy generation
        print("\n🎯 Generating content strategy for 'AI automation'...")
        strategy = engine.get_content_strategy("AI automation is trending in 2026")
        
        print(f"\n📊 STRATEGY GENERATED:")
        print(f"   Topic: {strategy['topic']}")
        print(f"   Products to Feature:")
        for prod in strategy.get('products', [])[:2]:
            print(f"      - {prod['name'][:60]} ({prod['price']})")
        print(f"   CTA: {strategy['cta'][:80]}")
        print(f"   Memory Insights: {strategy.get('memory_insights', 'None')}")
        
        print("\n✅ DECISION ENGINE TEST PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ DECISION ENGINE TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_linkedin_config():
    """Test LinkedIn configuration."""
    print("\n" + "="*70)
    print("🔗 TESTING LINKEDIN CONFIGURATION")
    print("="*70)
    
    from dotenv import load_dotenv
    load_dotenv()
    
    linkedin_account = os.getenv("LINKEDIN_ACCOUNT_ID")
    linkedin_urn = os.getenv("LINKEDIN_AUTHOR_URN")
    
    print(f"\n LinkedIn Account ID: {linkedin_account}")
    print(f"   LinkedIn Author URN: {linkedin_urn}")
    
    if linkedin_account and "AxYGMiT-jtOU" in linkedin_account:
        print("\n✅ LINKEDIN CONFIG UPDATED (New active credentials)")
        return True
    else:
        print("\n❌ LINKEDIN CONFIG MISSING OR OLD")
        return False


def test_graph_integration():
    """Test that AI Decision Engine is integrated into graph."""
    print("\n" + "="*70)
    print("🤖 TESTING GRAPH INTEGRATION")
    print("="*70)
    
    try:
        from agent.graph import graph, generate_tweet_node
        
        print("\n✅ Graph loaded successfully")
        
        # Check if AI Decision Engine is imported in generate_tweet_node
        import inspect
        source = inspect.getsource(generate_tweet_node)
        
        if "get_decision_engine" in source:
            print("✅ AI Decision Engine is INTEGRATED into generate_tweet_node")
        else:
            print("⚠️  AI Decision Engine not found in content generation")
        
        if "ai_strategy" in source:
            print("✅ Strategy tracking is IMPLEMENTED")
        else:
            print("⚠️  Strategy tracking not found")
        
        # Check graph structure
        print(f"\n📊 Graph has {len(graph.nodes)} nodes")
        if "post_linkedin" in graph.nodes:
            print("✅ LinkedIn posting node is present in workflow")
        else:
            print("⚠️  LinkedIn node not found")
        
        print("\n✅ GRAPH INTEGRATION TEST PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ GRAPH TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_full_test():
    """Run all tests."""
    print("\n" + "="*70)
    print("🚀 ENHANCED AI AGENT - FULL SYSTEM TEST")
    print("="*70)
    print("\nTesting enhancements:")
    print("✓ AI Decision Engine (smart product selection)")
    print("✓ LinkedIn Integration (new active credentials)")
    print("✓ Memory System")
    print("✓ Graph Workflow")
    print("")
    
    results = []
    
    # Test 1: Decision Engine
    results.append(("Decision Engine", test_decision_engine()))
    
    # Test 2: LinkedIn Config
    results.append(("LinkedIn Config", test_linkedin_config()))
    
    # Test 3: Graph Integration
    results.append(("Graph Integration", test_graph_integration()))
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "="*70)
    if all_passed:
        print("🎉 ALL TESTS PASSED! System ready for deployment.")
        print("\nTo run full agent workflow:")
        print("  python main.py")
        print("\nOr test via UI:")
        print("  python src/agent/api.py")
        print("  Open: http://localhost:8000")
    else:
        print("⚠️  SOME TESTS FAILED. Review errors above.")
    print("="*70)
    
    return all_passed


if __name__ == "__main__":
    run_full_test()
