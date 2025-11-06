"""End-to-end test for web_dev agent through WebSocket."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.web_dev import WebDevAgent


async def test_e2e_web_dev():
    """Test web_dev agent end-to-end to verify frontend integration."""

    print("=" * 80)
    print("🧪 End-to-End Web Dev Test (Backend → Frontend Flow)")
    print("=" * 80)

    # Initialize agent
    agent = WebDevAgent()
    print("✅ Agent initialized")

    # Test data - Aura Smart Sneaker (matching demo flow)
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
        "project_id": "aura_smart_sneaker",
        "session_id": "test_session"
    }

    print(f"\n📋 Test Product: {task['product_name']}")

    # Execute agent
    print("\n⚙️  Executing web_dev agent...")
    result = await agent.execute(task, context)

    # Simulate WebSocket message format
    print("\n📡 Simulating WebSocket broadcast...")

    # This is how the backend sends it
    websocket_message = {
        "type": "asset_added",
        "data": {
            "agent_id": "web_dev",
            "asset_type": "landing_page",
            "asset_data": result  # Full web_dev output
        }
    }

    print(f"   Message type: {websocket_message['type']}")
    print(f"   Agent ID: {websocket_message['data']['agent_id']}")
    print(f"   Asset type: {websocket_message['data']['asset_type']}")

    # Verify frontend can parse it
    print("\n🔍 Verifying frontend compatibility...")

    asset_data = websocket_message['data']['asset_data']

    # Frontend expects: assetData.code.html/css/javascript
    assert 'code' in asset_data, "❌ Missing 'code' key (frontend expects assetData.code)"
    print("   ✅ Has 'code' key")

    code = asset_data['code']
    assert 'html' in code, "❌ Missing 'html' in code"
    assert 'css' in code, "❌ Missing 'css' in code"
    assert 'javascript' in code, "❌ Missing 'javascript' in code"
    print("   ✅ Has html, css, javascript keys")

    html = code['html']
    css = code['css']
    js = code['javascript']

    assert len(html) > 0, "❌ HTML is empty"
    assert len(css) > 0, "❌ CSS is empty"
    assert len(js) > 0, "❌ JavaScript is empty"
    print(f"   ✅ HTML: {len(html):,} chars")
    print(f"   ✅ CSS: {len(css):,} chars")
    print(f"   ✅ JS: {len(js):,} chars")

    # Verify HTML structure (frontend checks for <!DOCTYPE to decide how to render)
    assert html.startswith('<!DOCTYPE'), "❌ HTML should start with <!DOCTYPE"
    print("   ✅ HTML is a complete document (starts with <!DOCTYPE)")

    # Verify product name and slogan are in HTML
    assert task['product_name'] in html, f"❌ Product name '{task['product_name']}' not in HTML"
    print(f"   ✅ Product name in HTML")

    assert task['slogan'] in html, f"❌ Slogan '{task['slogan']}' not in HTML"
    print(f"   ✅ Slogan in HTML")

    # Verify image URL is in HTML
    if task['image_url']:
        assert task['image_url'] in html, f"❌ Image URL not in HTML"
        print(f"   ✅ Image URL in HTML")

    # Simulate frontend rendering logic (from AssetDisplay.tsx)
    print("\n🎨 Simulating frontend rendering...")

    # Frontend code:
    # const fullHTML = html.includes('<!DOCTYPE') ? html : `...template...`
    if '<!DOCTYPE' in html:
        full_html_for_iframe = html
        print("   ✅ Using complete HTML (as expected)")
    else:
        print("   ⚠️  Would use template wrapper (not expected)")

    # Frontend creates a Blob and iframe URL
    print(f"   ✅ Would create blob URL with {len(full_html_for_iframe):,} chars")
    print(f"   ✅ Would render in iframe with sandbox='allow-scripts'")

    # Save message for inspection
    output_file = Path(__file__).parent.parent / "test_websocket_message.json"
    with open(output_file, 'w') as f:
        json.dump(websocket_message, f, indent=2)

    print(f"\n💾 Saved WebSocket message to: {output_file}")
    print("   You can inspect this to verify the exact data structure")

    print("\n" + "=" * 80)
    print("✅ End-to-End Test PASSED!")
    print("=" * 80)
    print("\n📌 Summary:")
    print("   - Backend web_dev agent generates complete HTML/CSS/JS ✅")
    print("   - WebSocket message format is correct ✅")
    print("   - Frontend can parse and render the data ✅")
    print("\n💡 If the frontend still shows empty landing page:")
    print("   1. Check browser console for errors")
    print("   2. Verify WebSocket connection is established")
    print("   3. Check if assets.web_dev exists in store")
    print("   4. Inspect iframe sandbox permissions")


if __name__ == "__main__":
    try:
        asyncio.run(test_e2e_web_dev())
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
