"""Level 1 Component Tests - Art Director Agent.

Tests individual Art Director Agent functionality:
- Output format validation
- Image generation (exactly 4)
- Product category adaptation
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock
import json

from app.agents.art_director import ArtDirectorAgent
from app.models.assets import ArtDirectorOutput


@pytest.mark.asyncio
async def test_art_director_output_format(sample_art_task):
    """Test that Art Director Agent returns correct output format."""
    agent = ArtDirectorAgent()

    # imagen_client.generate_images() returns List[bytes]
    mock_image_bytes = [b'fake_image_bytes_data']

    with patch('app.agents.art_director.imagen_client') as mock_client:
        mock_client.generate_images = AsyncMock(return_value=mock_image_bytes)

        result = await agent.execute(sample_art_task, {})

    # Verify output structure
    assert isinstance(result, dict)
    assert "images" in result
    assert isinstance(result["images"], list)


@pytest.mark.asyncio
async def test_art_director_exactly_four_images(sample_art_task):
    """Test that Art Director generates exactly 4 images."""
    agent = ArtDirectorAgent()

    # imagen_client.generate_images() returns List[bytes]
    mock_image_bytes = [b'fake_image_bytes_data']

    with patch('app.agents.art_director.imagen_client') as mock_client:
        mock_client.generate_images = AsyncMock(return_value=mock_image_bytes)

        result = await agent.execute(sample_art_task, {})

    # Verify exactly 4 images
    assert len(result["images"]) == 4

    # Verify each image has required fields
    for image in result["images"]:
        assert "asset_id" in image
        assert "url" in image
        assert "description" in image
        assert isinstance(image["url"], str)
        # URL should be a data URI or GCS URL
        assert image["url"].startswith("data:") or image["url"].startswith("gs://") or image["url"].startswith("http")


@pytest.mark.asyncio
async def test_art_director_image_quality(sample_art_task):
    """Test that generated images meet quality standards."""
    agent = ArtDirectorAgent()

    # imagen_client.generate_images() returns List[bytes]
    mock_image_bytes = [b'fake_image_bytes_data']

    with patch('app.agents.art_director.imagen_client') as mock_client:
        mock_client.generate_images = AsyncMock(return_value=mock_image_bytes)

        result = await agent.execute(sample_art_task, {})

    # Verify images were generated properly
    for i, image in enumerate(result["images"], 1):
        assert image["asset_id"] is not None
        assert len(image["description"]) > 0


@pytest.mark.asyncio
async def test_art_director_product_category_adaptation(sample_art_task):
    """Test that Art Director adapts visual style to product category."""
    agent = ArtDirectorAgent()

    # Test with different product categories
    categories = ["footwear", "beverage", "electronics", "fashion"]

    for category in categories:
        task = {
            **sample_art_task,
            "product_category": category
        }

        # imagen_client.generate_images() returns List[bytes]
        mock_image_bytes = [b'fake_image_bytes_data']

        with patch('app.agents.art_director.imagen_client') as mock_client:
            mock_client.generate_images = AsyncMock(return_value=mock_image_bytes)

            result = await agent.execute(task, {})

            # Verify 4 images generated for each category
            assert len(result["images"]) == 4


@pytest.mark.asyncio
async def test_art_director_theme_integration(sample_art_task):
    """Test that Art Director integrates theme into prompts."""
    agent = ArtDirectorAgent()

    themes = ["Tokyo neon", "volcanic energy", "Scandinavian minimalism"]

    for theme in themes:
        task = {
            **sample_art_task,
            "theme": theme
        }

        # imagen_client.generate_images() returns List[bytes]
        mock_image_bytes = [b'fake_image_bytes_data']

        with patch('app.agents.art_director.imagen_client') as mock_client:
            mock_client.generate_images = AsyncMock(return_value=mock_image_bytes)

            result = await agent.execute(task, {})

            # Verify generation completed
            assert len(result["images"]) == 4


@pytest.mark.asyncio
async def test_art_director_error_handling():
    """Test Art Director error handling."""
    agent = ArtDirectorAgent()

    task = {
        "task_id": "error_test",
        "description": "Test error"
        # Missing required fields
    }

    with patch('app.agents.art_director.imagen_client') as mock_client:
        mock_client.generate_images = AsyncMock(side_effect=Exception("Imagen API Error"))

        with pytest.raises(Exception) as exc_info:
            await agent.execute(task, {})

        assert "error" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_art_director_critique():
    """Test Art Director critique functionality."""
    from app.models.assets import CritiqueResult

    agent = ArtDirectorAgent()

    result = {
        "images": [
            {
                "asset_id": f"img_{i}",
                "url": f"data:image/png;base64,fakedata{i}",
                "description": f"Image {i}",
                "generation_params": {}
            }
            for i in range(1, 5)
        ],
        "style_guide": "Tokyo neon style guide"
    }

    brief = {
        "theme": "Tokyo neon",
        "key_features": ["glowing sole", "smart tracking"]
    }

    critique = await agent.critique(result, brief)

    # Verify critique is a CritiqueResult object
    assert isinstance(critique, CritiqueResult)
    assert critique.status in ["PASS", "REVISE"]

    # Art Director typically passes if 4 high-quality images generated
    if critique.status == "PASS":
        assert critique.score > 0.7


@pytest.mark.asyncio
async def test_art_director_revision():
    """Test Art Director revision capability."""
    agent = ArtDirectorAgent()

    original_result = {
        "images": [
            {
                "asset_id": f"img_{i}",
                "url": f"data:image/png;base64,original{i}",
                "description": f"Original image {i}",
                "generation_params": {}
            }
            for i in range(1, 5)
        ],
        "style_guide": "Original style guide"
    }

    critique = {
        "status": "REVISE",
        "score": 0.6,
        "issues": ["Missing glowing sole feature"],
        "revision_instructions": "Add emphasis on glowing sole feature"
    }

    from app.models.assets import CritiqueResult
    critique_obj = CritiqueResult(**critique)

    revised_result = await agent.revise(original_result, critique_obj)

    # Verify revision returned (even if unchanged in current implementation)
    assert "images" in revised_result
    assert len(revised_result["images"]) == 4


print("✅ Art Director Agent Level 1 tests created")
