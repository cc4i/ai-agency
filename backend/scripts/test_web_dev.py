"""Test script to verify web_dev agent generates landing pages correctly."""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.web_dev import WebDevAgent


async def test_web_dev_agent():
    """Test the web_dev agent with sample data."""

    print("=" * 80)
    print("🧪 Testing Web Dev Agent")
    print("=" * 80)

    # Initialize agent
    agent = WebDevAgent()
    print("✅ Agent initialized")

    # Test data - Aura Smart Sneaker
    task = {
        "product_name": "Aura Smart Sneaker",
        "slogan": "Step into the Future",
        "theme": "futuristic",
        "brand_tone": "innovative",
        "product_category": "footwear",
        "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=1200&h=800&fit=crop",
        "key_features": [
            "Smart Sensors: Real-time performance tracking",
            "Adaptive Cushioning: AI-powered comfort",
            "Sustainable Materials: Eco-friendly design"
        ]
    }

    context = {
        "project_id": "test_project",
        "session_id": "test_session"
    }

    print("\n📋 Test Data:")
    print(f"  Product: {task['product_name']}")
    print(f"  Slogan: {task['slogan']}")
    print(f"  Category: {task['product_category']}")
    print(f"  Features: {len(task['key_features'])} features")

    # Execute agent
    print("\n⚙️  Executing web_dev agent...")
    result = await agent.execute(task, context)

    # Verify result
    print("\n🔍 Verification:")

    # Check structure
    assert "code" in result, "❌ Missing 'code' in result"
    print("  ✅ Result has 'code' key")

    assert "framework" in result, "❌ Missing 'framework' in result"
    print(f"  ✅ Framework: {result['framework']}")

    code = result["code"]

    # Check HTML
    assert "html" in code, "❌ Missing 'html' in code"
    html = code["html"]
    assert len(html) > 0, "❌ HTML is empty"
    print(f"  ✅ HTML: {len(html):,} characters")

    # Check CSS
    assert "css" in code, "❌ Missing 'css' in code"
    css = code["css"]
    assert len(css) > 0, "❌ CSS is empty"
    print(f"  ✅ CSS: {len(css):,} characters")

    # Check JavaScript
    assert "javascript" in code, "❌ Missing 'javascript' in code"
    js = code["javascript"]
    assert len(js) > 0, "❌ JavaScript is empty"
    print(f"  ✅ JavaScript: {len(js):,} characters")

    # Check content includes product name
    assert task["product_name"] in html, f"❌ HTML doesn't contain product name '{task['product_name']}'"
    print(f"  ✅ HTML contains product name")

    # Check content includes slogan
    assert task["slogan"] in html, f"❌ HTML doesn't contain slogan '{task['slogan']}'"
    print(f"  ✅ HTML contains slogan")

    # Check content includes image URL
    if task["image_url"]:
        assert task["image_url"] in html, f"❌ HTML doesn't contain image URL"
        print(f"  ✅ HTML contains image URL")

    # Save to file for manual inspection
    output_file = Path(__file__).parent.parent / "test_output_landing_page.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n💾 Saved output to: {output_file}")
    print(f"   Open this file in a browser to view the landing page")

    # Test critique
    print("\n🔍 Testing critique...")
    brief = {
        "product_name": task["product_name"],
        "selected_slogan": task["slogan"]
    }

    critique_result = await agent.critique(result, brief)
    print(f"  Status: {critique_result.status}")
    print(f"  Score: {critique_result.score}")

    if critique_result.issues:
        print(f"  Issues: {critique_result.issues}")
    else:
        print(f"  ✅ No issues found")

    print("\n" + "=" * 80)
    print("✅ All tests passed!")
    print("=" * 80)

    return True


async def test_multiple_categories():
    """Test with different product categories."""

    print("\n" + "=" * 80)
    print("🧪 Testing Multiple Product Categories")
    print("=" * 80)

    agent = WebDevAgent()

    test_products = [
        {
            "product_name": "CoolBreeze Energy Drink",
            "slogan": "Unleash Your Energy",
            "product_category": "beverage",
            "theme": "energetic",
            "brand_tone": "bold",
            "key_features": ["Natural Caffeine", "Zero Sugar", "Vitamin Boost"]
        },
        {
            "product_name": "LuxWatch Pro",
            "slogan": "Timeless Elegance",
            "product_category": "electronics",
            "theme": "minimalist",
            "brand_tone": "sophisticated",
            "key_features": ["AMOLED Display", "7-day Battery", "Heart Rate Monitor"]
        },
        {
            "product_name": "Velvet Beauty Cream",
            "slogan": "Natural Radiance",
            "product_category": "beauty",
            "theme": "organic",
            "brand_tone": "gentle",
            "key_features": ["Organic Ingredients", "Anti-Aging Formula", "Dermatologist Tested"]
        }
    ]

    for product in test_products:
        print(f"\n📦 Testing: {product['product_name']} ({product['product_category']})")

        task = {
            **product,
            "image_url": "https://via.placeholder.com/1200x800"
        }

        context = {"project_id": "test", "session_id": "test"}

        result = await agent.execute(task, context)

        # Quick validation
        assert result["code"]["html"], f"❌ Empty HTML for {product['product_name']}"
        assert product["product_name"] in result["code"]["html"], f"❌ Product name not in HTML"

        print(f"  ✅ Generated {len(result['code']['html']):,} chars of HTML")

    print("\n✅ All category tests passed!")


if __name__ == "__main__":
    print("\n🚀 Starting Web Dev Agent Tests\n")

    try:
        # Run basic test
        asyncio.run(test_web_dev_agent())

        # Run category tests
        asyncio.run(test_multiple_categories())

        print("\n🎉 All tests completed successfully!")

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
