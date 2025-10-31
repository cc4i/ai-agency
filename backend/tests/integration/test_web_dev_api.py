"""Integration tests for Web Dev Agent with real Gemini Code Assist API.

Tests cover:
- Real code generation with Gemini Code Assist
- Landing page creation for different products
- Category-specific color schemes
- Product-agnostic design

Note: Requires Google Cloud credentials and may incur API costs.
"""

import pytest
import os
from app.agents.web_dev import WebDevAgent


# Skip if credentials not available
pytestmark = pytest.mark.skipif(
    not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
    reason="Google Cloud credentials not configured"
)


@pytest.fixture
def web_dev():
    """Create Web Dev agent instance."""
    return WebDevAgent()


class TestRealCodeGeneration:
    """Test real code generation with Gemini Code Assist."""

    @pytest.mark.asyncio
    async def test_generate_landing_page_footwear(self, web_dev):
        """Test landing page generation for footwear product."""
        code_asset = await web_dev._generate_landing_page(
            image_url="https://example.com/sneaker.jpg",
            slogan="Run Your Future",
            product_name="Aura Smart Sneaker",
            theme="futuristic urban athlete",
            brand_tone="futuristic",
            product_category="footwear",
            key_features=["Smart sensors", "LED lights", "App connectivity"],
        )

        # Verify code was generated
        assert code_asset.asset_id.startswith("landing_")
        assert code_asset.html
        assert code_asset.css
        assert code_asset.javascript

        # Verify product-specific content
        assert "Aura Smart Sneaker" in code_asset.html
        assert "Run Your Future" in code_asset.html

        # Verify HTML structure
        assert "<!DOCTYPE html>" in code_asset.html
        assert "<html" in code_asset.html
        assert "</html>" in code_asset.html

        # Verify CSS exists
        assert len(code_asset.css) > 100

        # Verify JavaScript exists
        assert len(code_asset.javascript) > 50

        print(f"✓ Generated landing page: {code_asset.asset_id}")
        print(f"  HTML: {len(code_asset.html)} chars")
        print(f"  CSS: {len(code_asset.css)} chars")
        print(f"  JS: {len(code_asset.javascript)} chars")

    @pytest.mark.asyncio
    async def test_generate_landing_page_beverage(self, web_dev):
        """Test landing page generation for beverage product."""
        code_asset = await web_dev._generate_landing_page(
            image_url="https://example.com/drink.jpg",
            slogan="Fuel Your Ambition",
            product_name="Pure Energy Drink",
            theme="dynamic energy",
            brand_tone="energetic",
            product_category="beverage",
            key_features=["Natural caffeine", "Zero sugar", "B vitamins"],
        )

        assert code_asset.asset_id.startswith("landing_")
        assert "Pure Energy Drink" in code_asset.html
        assert "Fuel Your Ambition" in code_asset.html

        print(f"✓ Generated beverage landing page: {code_asset.asset_id}")

    @pytest.mark.asyncio
    async def test_generate_landing_page_luxury_product(self, web_dev):
        """Test landing page for luxury product with sophisticated tone."""
        code_asset = await web_dev._generate_landing_page(
            image_url="https://example.com/watch.jpg",
            slogan="Timeless Elegance",
            product_name="Prestige Watch",
            theme="luxury craftsmanship",
            brand_tone="luxury",
            product_category="fashion",
            key_features=["Swiss movement", "Sapphire crystal", "Hand-crafted"],
        )

        assert code_asset.asset_id.startswith("landing_")
        assert "Prestige Watch" in code_asset.html
        assert "Timeless Elegance" in code_asset.html

        print(f"✓ Generated luxury landing page: {code_asset.asset_id}")


class TestFullWebDevExecution:
    """Test complete Web Dev execution with real API."""

    @pytest.mark.asyncio
    async def test_complete_execution_footwear(self, web_dev):
        """Test complete web dev execution for footwear product."""
        task = {
            "product_name": "Aura Smart Sneaker",
            "product_category": "footwear",
            "theme": "futuristic urban athlete",
            "brand_tone": "futuristic",
            "slogan": "Run Your Future",
            "image_url": "https://example.com/sneaker.jpg",
            "key_features": ["Smart sensors", "LED lights", "App connectivity"],
        }
        context = {
            "project_id": "aura_smart_sneaker",
            "session_id": "test_integration",
        }

        # Execute
        result = await web_dev.execute(task, context)

        # Verify all outputs
        assert "code" in result
        assert "framework" in result
        assert "deployment_status" in result

        # Verify code
        code = result["code"]
        assert code["asset_id"].startswith("landing_")
        assert code["html"]
        assert code["css"]
        assert code["javascript"]
        assert "Aura Smart Sneaker" in code["html"]
        assert "Run Your Future" in code["html"]

        # Verify framework and status
        assert result["framework"] == "vanilla"
        assert result["deployment_status"] == "preview"

        print(f"✓ Complete execution: {code['asset_id']}")
        print(f"  Framework: {result['framework']}")
        print(f"  Status: {result['deployment_status']}")

    @pytest.mark.asyncio
    async def test_complete_execution_electronics(self, web_dev):
        """Test complete execution for electronics product."""
        task = {
            "product_name": "Smart Watch Pro",
            "product_category": "electronics",
            "theme": "modern tech",
            "brand_tone": "professional",
            "slogan": "Time Redefined",
            "image_url": "https://example.com/watch.jpg",
            "key_features": ["Heart rate monitor", "GPS tracking", "7-day battery"],
        }
        context = {}

        result = await web_dev.execute(task, context)

        # Verify product-specific content
        assert "Smart Watch Pro" in result["code"]["html"]
        assert "Time Redefined" in result["code"]["html"]

        print(f"✓ Electronics execution complete: {result['code']['asset_id']}")


class TestProductAgnosticDesign:
    """Test product-agnostic design with different categories."""

    @pytest.mark.asyncio
    async def test_automotive_product(self, web_dev):
        """Test with automotive product."""
        task = {
            "product_name": "Electric GT",
            "product_category": "automotive",
            "theme": "speed and power",
            "brand_tone": "edgy",
            "slogan": "Drive Electric",
            "image_url": "https://example.com/car.jpg",
            "key_features": ["0-60 in 3s", "400 mile range", "Autopilot"],
        }

        result = await web_dev.execute(task, {})

        assert "Electric GT" in result["code"]["html"]
        assert "Drive Electric" in result["code"]["html"]
        print(f"✓ Automotive product: {result['code']['asset_id']}")

    @pytest.mark.asyncio
    async def test_beauty_product(self, web_dev):
        """Test with beauty product."""
        task = {
            "product_name": "Radiance Serum",
            "product_category": "beauty",
            "theme": "natural glow",
            "brand_tone": "natural",
            "slogan": "Glow Naturally",
            "image_url": "https://example.com/serum.jpg",
            "key_features": ["Vitamin C", "Hyaluronic acid", "Vegan"],
        }

        result = await web_dev.execute(task, {})

        assert "Radiance Serum" in result["code"]["html"]
        assert "Glow Naturally" in result["code"]["html"]
        print(f"✓ Beauty product: {result['code']['asset_id']}")

    @pytest.mark.asyncio
    async def test_food_product(self, web_dev):
        """Test with food product."""
        task = {
            "product_name": "Artisan Coffee Blend",
            "product_category": "food",
            "theme": "rich aroma",
            "brand_tone": "natural",
            "slogan": "Morning Perfection",
            "image_url": "https://example.com/coffee.jpg",
            "key_features": ["Single origin", "Fair trade", "Dark roast"],
        }

        result = await web_dev.execute(task, {})

        assert "Artisan Coffee Blend" in result["code"]["html"]
        assert "Morning Perfection" in result["code"]["html"]
        print(f"✓ Food product: {result['code']['asset_id']}")
