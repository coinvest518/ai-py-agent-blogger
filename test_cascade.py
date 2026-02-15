#!/usr/bin/env python3
"""
Simple test script to verify cascading LLM provider functionality.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agent.llm_provider import get_llm

def test_cascading_llm():
    print("=" * 60)
    print("Testing Cascading LLM Provider")
    print("=" * 60)
    
    try:
        print("\n🔹 Initializing LLM with cascading fallback...")
        llm = get_llm('test-cascading')
        print("✅ LLM initialized successfully!")
        print(f"   Type: {type(llm).__name__}")
        
        print("\n🔹 Invoking LLM with test prompt...")
        print("   Prompt: 'Write a single sentence about AI automation.'")
        print("\n   Note: Watch for provider cascade attempts below:\n")
        
        result = llm.invoke("Write a single sentence about AI automation.")
        
        print("\n✅ LLM invocation successful!")
        if hasattr(result, 'content'):
            print(f"\n📝 Response:\n{result.content}")
        else:
            print(f"\n📝 Response:\n{result}")
            
        print("\n" + "=" * 60)
        print("✅ TEST PASSED - Cascading LLM works!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_cascading_llm()
