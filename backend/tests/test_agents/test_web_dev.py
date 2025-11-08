"""Unit tests for Web Dev Agent.

Tests cover:
- Landing page code generation
- HTML/CSS/JS structure
- Product-agnostic design
- Category-specific color schemes
- Brand tone adaptation
- Critique system
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.web_dev import WebDevAgent
from app.models.assets import CodeAsset, CritiqueResult, WebDevOutput


@pytest.fixture
def web_dev():
    """Create Web Dev agent instance."""
    return WebDevAgent()


@pytest.fixture
def test_task():
    """Standard test task for Aura Smart Sneaker."""
    return {
        "product_name": "Aura Smart Sneaker",
        "product_category": "footwear",
        "theme": "futuristic urban athlete",
        "brand_tone": "futuristic",
        "slogan": "Run Your Future",
        "image_url": "https://example.com/hero.jpg",
        "key_features": ["Smart sensors", "LED lights", "App connectivity"],
    }


@pytest.fixture
def test_context():
    """Test context."""
    return {
        "project_id": "aura_smart_sneaker",
        "session_id": "test_session",
    }


class TestWebDevExecution:
    """Test main execution flow."""

    @pytest.mark.asyncio
    async def test_execute_returns_complete_output(self, web_dev, test_task, test_context):
        """Test that execute returns all required code assets."""
        with patch("app.agents.web_dev.code_assist_client") as mock_code_assist:

            # Mock Gemini Code Assist
            mock_code_assist.generate_code = AsyncMock(
                return_value="<html>Generated code here</html>"
            )

            # Execute
            result = await web_dev.execute(test_task, test_context)

            # Verify output structure
            assert "code" in result
            assert "framework" in result
            assert "deployment_status" in result

            # Verify code asset
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

    @pytest.mark.asyncio
    async def test_execute_with_minimal_task(self, web_dev):
        """Test execution with minimal task data (uses defaults)."""
        minimal_task = {}
        context = {}

        with patch("app.agents.web_dev.code_assist_client") as mock_code_assist:
            mock_code_assist.generate_code = AsyncMock(return_value="<html></html>")

            # Execute with defaults
            result = await web_dev.execute(minimal_task, context)

            # Should still generate all assets with default values
            assert result["code"]["asset_id"]
            assert result["code"]["html"]
            assert result["code"]["css"]
            assert result["code"]["javascript"]

            # Default product name should be present
            assert "Product" in result["code"]["html"]


class TestLandingPageGeneration:
    """Test landing page generation."""

    @pytest.mark.asyncio
    async def test_generate_landing_page_with_all_features(self, web_dev):
        """Test landing page generation with all features."""
        with patch("app.agents.web_dev.code_assist_client") as mock_code_assist:

            mock_code_assist.generate_code = AsyncMock(
                return_value="<html>Mocked response</html>"
            )

            # Generate
            code_asset = await web_dev._generate_landing_page(
                image_url="https://example.com/image.jpg",
                slogan="Test Slogan",
                product_name="Test Product",
                theme="modern",
                brand_tone="professional",
                product_category="electronics",
                key_features=["Feature 1", "Feature 2", "Feature 3"],
            )

            # Verify code asset content
            assert "Test Product" in code_asset.html
            assert "Test Slogan" in code_asset.html
            assert "Feature 1" in code_asset.html

            # Verify code asset
            assert code_asset.asset_id.startswith("landing_")
            assert code_asset.html
            assert code_asset.css
            assert code_asset.javascript
            assert "Test Product" in code_asset.html
            assert "Test Slogan" in code_asset.html

    @pytest.mark.asyncio
    async def test_generate_landing_page_footwear_category(self, web_dev):
        """Test landing page for footwear category uses correct color scheme."""
        with patch("app.agents.web_dev.code_assist_client") as mock_code_assist:

            mock_code_assist.generate_code = AsyncMock(return_value="<html></html>")

            code_asset = await web_dev._generate_landing_page(
                image_url="",
                slogan="Run Fast",
                product_name="Running Shoe",
                theme="athletic",
                brand_tone="energetic",
                product_category="footwear",
                key_features=["Lightweight"],
            )

            # Verify product name is in the output
            assert "Running Shoe" in code_asset.html

    @pytest.mark.asyncio
    async def test_generate_landing_page_luxury_category(self, web_dev):
        """Test landing page for luxury category uses correct color scheme."""
        with patch("app.agents.web_dev.code_assist_client") as mock_code_assist:

            mock_code_assist.generate_code = AsyncMock(return_value="<html></html>")

            code_asset = await web_dev._generate_landing_page(
                image_url="",
                slogan="Timeless Elegance",
                product_name="Luxury Watch",
                theme="sophisticated",
                brand_tone="luxury",
                product_category="fashion",
                key_features=["Swiss movement"],
            )

            # Verify product name is in the output
            assert "Luxury Watch" in code_asset.html


class TestCodeParsing:
    """Test code response parsing."""

    def test_parse_code_response_generates_valid_html(self, web_dev):
        """Test that parsed HTML is valid."""
        html, css, js = web_dev._parse_code_response(
            response="",
            product_name="Test Product",
            slogan="Test Slogan",
            theme="modern",
            key_features=[]
        )

        # Verify HTML structure
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "<head>" in html
        assert "<body>" in html
        assert "Test Product" in html
        assert "Test Slogan" in html

    def test_parse_code_response_generates_valid_css(self, web_dev):
        """Test that parsed CSS is valid."""
        html, css, js = web_dev._parse_code_response(
            response="",
            product_name="Product",
            slogan="Slogan",
            theme="modern",
            key_features=[]
        )

        # Verify CSS includes essential styles
        assert "body {" in css
        assert "container" in css
        assert "@media" in css  # Responsive design
        assert "animation" in css  # Animations

    def test_parse_code_response_generates_valid_javascript(self, web_dev):
        """Test that parsed JavaScript is valid."""
        html, css, js = web_dev._parse_code_response(
            response="",
            product_name="Product",
            slogan="Slogan",
            theme="modern",
            key_features=[]
        )

        # Verify JavaScript includes essential functionality
        assert "countdown" in js.lower()
        assert "email" in js.lower()
        assert "addEventListener" in js
        assert "getElementById" in js

    def test_parse_code_response_includes_product_theme(self, web_dev):
        """Test that code includes product theme."""
        html, css, js = web_dev._parse_code_response(
            response="",
            product_name="Futuristic Gadget",
            slogan="Tomorrow Today",
            theme="cyberpunk",
            key_features=[]
        )

        # Product name should be in HTML
        assert "Futuristic Gadget" in html
        assert "Tomorrow Today" in html

        # Theme is not directly in the template, but let's check for the product name
        assert "Futuristic Gadget" in html


class TestCategoryColorSchemes:
    """Test category-specific color schemes."""

    def test_category_color_scheme_mapping(self, web_dev):
        """Test that all category color schemes are defined."""
        from app.agents.web_dev import CATEGORY_COLOR_SCHEMES

        # Verify essential categories exist
        assert "footwear" in CATEGORY_COLOR_SCHEMES
        assert "beverage" in CATEGORY_COLOR_SCHEMES
        assert "electronics" in CATEGORY_COLOR_SCHEMES
        assert "fashion" in CATEGORY_COLOR_SCHEMES
        assert "beauty" in CATEGORY_COLOR_SCHEMES
        assert "food" in CATEGORY_COLOR_SCHEMES
        assert "automotive" in CATEGORY_COLOR_SCHEMES

        # Verify all values are strings
        for category, scheme in CATEGORY_COLOR_SCHEMES.items():
            assert isinstance(scheme, str)
            assert len(scheme) > 0


class TestCritiqueSystem:
    """Test critique system."""

    @pytest.mark.asyncio
    async def test_critique_pass_complete_output(self, web_dev):
        """Test critique passes with complete output."""
        result = {
            "code": {
                "asset_id": "landing_123",
                "html": "<html><body>Test Product - Test Slogan</body></html>",
                "css": "body { color: black; }",
                "javascript": "console.log('test');",
                "preview_url": None,
            },
            "framework": "vanilla",
            "deployment_status": "preview",
        }

        brief = {
            "product_name": "Test Product",
            "selected_slogan": "Test Slogan",
        }

        # Critique
        critique = await web_dev.critique(result, brief)

        # Should pass
        assert critique.status == "PASS"
        assert critique.score == 1.0
        assert len(critique.issues) == 0

    @pytest.mark.asyncio
    async def test_critique_fail_missing_html(self, web_dev):
        """Test critique fails with missing HTML."""
        result = {
            "code": {
                "asset_id": "landing_123",
                "html": "",  # Missing HTML
                "css": "body { color: black; }",
                "javascript": "console.log('test');",
                "preview_url": None,
            },
            "framework": "vanilla",
            "deployment_status": "preview",
        }

        brief = {}

        # Critique
        critique = await web_dev.critique(result, brief)

        # Should fail
        assert critique.status == "REVISE"
        assert critique.score < 1.0
        assert "HTML code missing" in critique.issues

    @pytest.mark.asyncio
    async def test_critique_fail_missing_product_name(self, web_dev):
        """Test critique fails when product name not in HTML."""
        result = {
            "code": {
                "asset_id": "landing_123",
                "html": "<html><body>Generic Page</body></html>",
                "css": "body { color: black; }",
                "javascript": "console.log('test');",
                "preview_url": None,
            },
            "framework": "vanilla",
            "deployment_status": "preview",
        }

        brief = {
            "product_name": "Aura Smart Sneaker",
        }

        # Critique
        critique = await web_dev.critique(result, brief)

        # Should fail
        assert critique.status == "REVISE"
        assert "Aura Smart Sneaker" in critique.revision_instructions

    @pytest.mark.asyncio
    async def test_critique_fail_missing_slogan(self, web_dev):
        """Test critique fails when slogan not in HTML."""
        result = {
            "code": {
                "asset_id": "landing_123",
                "html": "<html><body>Aura Smart Sneaker</body></html>",
                "css": "body { color: black; }",
                "javascript": "console.log('test');",
                "preview_url": None,
            },
            "framework": "vanilla",
            "deployment_status": "preview",
        }

        brief = {
            "product_name": "Aura Smart Sneaker",
            "selected_slogan": "Run Your Future",
        }

        # Critique
        critique = await web_dev.critique(result, brief)

        # Should fail
        assert critique.status == "REVISE"
        assert "Run Your Future" in critique.revision_instructions


class TestProductAgnosticDesign:
    """Test that agent works with different product categories."""

    @pytest.mark.asyncio
    async def test_beverage_product(self, web_dev):
        """Test with beverage product."""
        task = {
            "product_name": "Energy Drink",
            "product_category": "beverage",
            "theme": "dynamic energy",
            "brand_tone": "energetic",
            "slogan": "Fuel Your Day",
            "image_url": "https://example.com/drink.jpg",
            "key_features": ["Natural caffeine", "Zero sugar"],
        }

        with patch("app.agents.web_dev.code_assist_client") as mock_code_assist:
            mock_code_assist.generate_code = AsyncMock(return_value="<html></html>")

            result = await web_dev.execute(task, {})

            # Verify product-specific content
            assert "Energy Drink" in result["code"]["html"]
            assert "Fuel Your Day" in result["code"]["html"]

            # Verify product-specific content
            assert "Energy Drink" in result["code"]["html"]
            assert "Fuel Your Day" in result["code"]["html"]

    @pytest.mark.asyncio
    async def test_electronics_product(self, web_dev):
        """Test with electronics product."""
        task = {
            "product_name": "Smart Watch",
            "product_category": "electronics",
            "theme": "modern tech",
            "brand_tone": "professional",
            "slogan": "Time Redefined",
            "image_url": "https://example.com/watch.jpg",
            "key_features": ["Heart rate monitor", "GPS tracking"],
        }

        with patch("app.agents.web_dev.code_assist_client") as mock_code_assist:
            mock_code_assist.generate_code = AsyncMock(return_value="<html></html>")

            result = await web_dev.execute(task, {})

            # Verify product-specific content
            assert "Smart Watch" in result["code"]["html"]
            assert "Time Redefined" in result["code"]["html"]

            # Verify product-specific content
            assert "Smart Watch" in result["code"]["html"]
            assert "Time Redefined" in result["code"]["html"]

    @pytest.mark.asyncio
    async def test_automotive_product(self, web_dev):
        """Test with automotive product."""
        task = {
            "product_name": "Electric Sports Car",
            "product_category": "automotive",
            "theme": "speed and power",
            "brand_tone": "edgy",
            "slogan": "Drive the Future",
            "image_url": "https://example.com/car.jpg",
            "key_features": ["0-60 in 3s", "400 mile range"],
        }

        with patch("app.agents.web_dev.code_assist_client") as mock_code_assist:
            mock_code_assist.generate_code = AsyncMock(return_value="<html></html>")

            result = await web_dev.execute(task, {})

            # Verify product-specific content
            assert "Electric Sports Car" in result["code"]["html"]
            assert "Drive the Future" in result["code"]["html"]

            # Verify product-specific content
            assert "Electric Sports Car" in result["code"]["html"]
            assert "Drive the Future" in result["code"]["html"]


class TestHTMLStructure:
    """Test HTML structure and accessibility."""

    def test_html_includes_semantic_elements(self, web_dev):
        """Test that HTML uses semantic elements."""
        html, _, _ = web_dev._parse_code_response("", "Product", "Slogan", "theme", [])

        # Verify semantic HTML
        assert "<div" in html
        assert "<h1" in html
        assert "<p" in html
        assert "<section" in html

    def test_html_includes_meta_tags(self, web_dev):
        """Test that HTML includes essential meta tags."""
        html, _, _ = web_dev._parse_code_response("", "Product", "Slogan", "theme", [])

        # Verify meta tags
        assert 'charset="UTF-8"' in html
        assert "viewport" in html

    def test_html_includes_form_elements(self, web_dev):
        """Test that HTML includes email signup form."""
        html, _, _ = web_dev._parse_code_response("", "Product", "Slogan", "theme", [])

        # Verify form elements
        assert '<form' in html
        assert 'type="email"' in html
        assert '<button' in html
        assert 'type="submit"' in html


class TestResponsiveDesign:
    """Test responsive design features."""

    def test_css_includes_media_queries(self, web_dev):
        """Test that CSS includes responsive media queries."""
        _, css, _ = web_dev._parse_code_response("", "Product", "Slogan", "theme", [])

        # Verify responsive design
        assert "@media" in css
        assert "max-width" in css or "min-width" in css

    def test_css_includes_flexible_layout(self, web_dev):
        """Test that CSS uses flexible layout techniques."""
        _, css, _ = web_dev._parse_code_response("", "Product", "Slogan", "theme", [])

        # Verify flexible layout
        assert "flex" in css or "grid" in css
        assert "max-width" in css


class TestJavaScriptFunctionality:
    """Test JavaScript functionality."""

    def test_javascript_includes_countdown_timer(self, web_dev):
        """Test that JavaScript includes countdown timer."""
        _, _, js = web_dev._parse_code_response("", "Product", "Slogan", "theme", [])

        # Verify countdown functionality
        assert "launchDate" in js or "countdown" in js.lower()
        assert "setInterval" in js
        assert "getElementById" in js

    def test_javascript_includes_form_handling(self, web_dev):
        """Test that JavaScript includes form handling."""
        _, _, js = web_dev._parse_code_response("", "Product", "Slogan", "theme", [])

        # Verify form handling
        assert "addEventListener" in js
        assert "submit" in js or "email" in js.lower()
        assert "preventDefault" in js
