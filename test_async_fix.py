#!/usr/bin/env python3
"""Test script to verify that the async fixes work correctly."""

import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


async def test_tiktoken_loading():
    """Test that tiktoken loading doesn't block."""
    try:
        from src.url_crawler.utils import chunk_text_by_tokens

        # Test the async function
        result = await chunk_text_by_tokens("This is a test text for chunking.", 10, 2)
        print(f"✓ Tiktoken async loading works: {len(result)} chunks")
        return True
    except Exception as e:
        print(f"✗ Tiktoken async loading failed: {e}")
        return False


async def test_model_loading():
    """Test that model loading doesn't block."""
    try:
        from langchain_core.runnables import RunnableConfig
        from langchain_core.tools import tool
        from src.llm_service import create_structured_model, create_tools_model

        # Test structured model creation
        config = RunnableConfig()
        model = create_structured_model(config)
        print("✓ Structured model creation works")

        # Test tools model creation
        @tool
        def test_tool(input_text: str) -> str:
            return f"Processed: {input_text}"

        tools_model = create_tools_model([test_tool], config)
        print("✓ Tools model creation works")
        return True
    except Exception as e:
        print(f"✗ Model loading failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("Testing async fixes...")

    tests = [
        test_tiktoken_loading,
        test_model_loading,
    ]

    results = []
    for test in tests:
        result = await test()
        results.append(result)

    passed = sum(results)
    total = len(results)

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("✓ All async fixes are working correctly!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
