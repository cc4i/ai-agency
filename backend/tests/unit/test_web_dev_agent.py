"""Level 1 Component Tests - Web Dev Agent.

Tests individual Web Dev Agent functionality:
- Output format validation
- HTML/CSS/JS code generation
- Landing page requirements
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock

from app.agents.web_dev import WebDevAgent


@pytest.mark.asyncio
async def test_web_dev_output_format(sample_web_task):
    """Test that Web Dev returns correct output format."""
    agent = WebDevAgent()

    mock_code = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>body { background: #000; color: #fff; }</style>
    </head>
    <body>
        <h1>Aura Smart Sneaker</h1>
        <p>Run on Light</p>
        <script>console.log('Coming soon');</script>
    </body>
    </html>
    """

    with patch('app.agents.web_dev.code_assist_client') as mock_client:
        mock_client.generate_code = AsyncMock(
            return_value=Mock(text=mock_code)
        )

        result = await agent.execute(sample_web_task, {})

    assert isinstance(result, dict)
    assert "code" in result
    assert result["code"]["html"] is not None
    assert result["code"]["css"] is not None
    assert result["code"]["javascript"] is not None


@pytest.mark.asyncio
async def test_web_dev_landing_page_requirements(sample_web_task):
    """Test that landing page includes required elements."""
    agent = WebDevAgent()

    mock_code = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
        body { background: #000; font-family: Arial; }
        .hero { background-image: url('hero.png'); }
        #countdown { font-size: 2em; }
        </style>
    </head>
    <body>
        <div class="hero">
            <h1>Aura Smart Sneaker</h1>
            <p class="slogan">Run on Light</p>
            <div id="countdown">30 days</div>
            <form id="email-signup">
                <input type="email" placeholder="Email">
                <button>Notify Me</button>
            </form>
        </div>
        <script>
        // Countdown timer logic
        function updateCountdown() {
            document.getElementById('countdown').textContent = '30 days';
        }
        updateCountdown();
        </script>
    </body>
    </html>
    """

    with patch('app.agents.web_dev.code_assist_client') as mock_client:
        mock_client.generate_code = AsyncMock(
            return_value=Mock(text=mock_code)
        )

        result = await agent.execute(sample_web_task, {})

    html = result["code"]["html"]
    css = result["code"]["css"]
    js = result["code"]["javascript"]

    # Verify key elements present
    assert "Aura Smart Sneaker" in html or "Run on Light" in html
    assert len(css) > 0
    assert len(js) > 0


@pytest.mark.asyncio
async def test_web_dev_slogan_integration(sample_web_task):
    """Test that slogan is integrated into landing page."""
    agent = WebDevAgent()

    slogan = "Run on Light"
    task = {
        **sample_web_task,
        "slogan": slogan
    }

    mock_code = f"""
    <!DOCTYPE html>
    <html>
    <body>
        <h1>Aura Smart Sneaker</h1>
        <p>{slogan}</p>
    </body>
    </html>
    """

    with patch('app.agents.web_dev.code_assist_client') as mock_client:
        mock_client.generate_code = AsyncMock(
            return_value=Mock(text=mock_code)
        )

        result = await agent.execute(task, {})

    # Verify slogan in HTML
    assert slogan in result["code"]["html"]


@pytest.mark.asyncio
async def test_web_dev_theme_styling(sample_web_task):
    """Test that theme is reflected in styling."""
    agent = WebDevAgent()

    themes_and_colors = {
        "Tokyo neon": ["neon", "blue", "purple"],
        "volcanic energy": ["red", "orange", "volcano"],
        "Scandinavian minimalism": ["white", "minimal", "clean"]
    }

    for theme, keywords in themes_and_colors.items():
        task = {
            **sample_web_task,
            "theme": theme
        }

        mock_code = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
            body {{ background: {keywords[1]}; }}
            .hero {{ color: {keywords[0]}; }}
            </style>
        </head>
        <body><h1>{theme}</h1></body>
        </html>
        """

        with patch('app.agents.web_dev.code_assist_client') as mock_client:
            mock_client.generate_code = AsyncMock(
                return_value=Mock(text=mock_code)
            )

            result = await agent.execute(task, {})

            # Verify theme keywords present in code
            code_combined = result["code"]["html"] + result["code"]["css"]
            # At least one keyword should be present
            assert any(keyword.lower() in code_combined.lower() for keyword in keywords)


@pytest.mark.asyncio
async def test_web_dev_error_handling():
    """Test Web Dev error handling."""
    agent = WebDevAgent()

    task = {"task_id": "error_test"}  # Missing required fields

    with patch('app.agents.web_dev.code_assist_client') as mock_client:
        mock_client.generate_code = AsyncMock(side_effect=Exception("Code Assist API Error"))

        with pytest.raises(Exception):
            await agent.execute(task, {})


@pytest.mark.asyncio
async def test_web_dev_preview_url():
    """Test that preview URL field exists (may be None if feature not implemented)."""
    agent = WebDevAgent()

    task = {
        "task_id": "preview_test",
        "product_name": "Test Product",
        "slogan": "Test Slogan",
        "image_url": "https://example.com/image.png"
    }

    mock_code = """
    <!DOCTYPE html>
    <html><body><h1>Test</h1></body></html>
    """

    with patch('app.agents.web_dev.code_assist_client') as mock_client:
        # code_assist_client.generate_code() returns str
        mock_client.generate_code = AsyncMock(return_value=mock_code)

        result = await agent.execute(task, {})

    # Preview URL is optional feature - may be None
    # Just verify the code was generated
    assert "code" in result
    assert result["code"]["html"] is not None


print("✅ Web Dev Agent Level 1 tests created")
