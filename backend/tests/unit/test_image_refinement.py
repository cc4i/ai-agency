"""Unit Tests - Image Refinement Workflow.

Tests the interactive image refinement functionality:
- Feedback analysis with Gemini vision
- Single image refinement workflow
- Batch parallel refinement
- Version rollback and mixing
- Max iteration limits
- Critique validation with user feedback
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock
import json
import base64

from app.workflows.art_director_workflow import ArtDirectorWorkflow
from app.workflows.art_director_agents import critique_image_tool
from app.models.assets import ImageAsset


@pytest.fixture
def sample_original_image():
    """Sample original ImageAsset for refinement testing."""
    return {
        "asset_id": "img_original_123",
        "url": "data:image/png;base64,ZmFrZV9vcmlnaW5hbF9pbWFnZQ==",  # "fake_original_image"
        "description": "Aura Smart Sneaker - Hero shot - Variation 1",
        "generation_params": {
            "model": "gemini-2.5-flash-image",
            "variation": 1,
            "theme": "futuristic",
            "approved": True,
            "score": 0.85,
            "prompt": "Futuristic smart sneaker with glowing sole, dramatic lighting, 16:9",
        },
        "parent_asset_id": None,
        "refinement_iteration": 0,
        "user_feedback_applied": None,
        # Generation tracking (NEW - production level)
        "generation_number": 1,
        "variation_number": 1,
    }


@pytest.fixture
def sample_product_context():
    """Sample product context for refinement."""
    return {
        "product_name": "Aura Smart Sneaker",
        "product_category": "footwear",
        "theme": "futuristic",
        "brand_tone": "innovative",
        "key_features": ["glowing sole", "smart tracking"],
    }


@pytest.fixture
def mock_feedback_analysis():
    """Mock feedback analysis response."""
    return {
        "keep_aspects": [
            "Dramatic lighting",
            "Product centered in frame",
            "16:9 composition",
            "Futuristic aesthetic"
        ],
        "change_aspects": [
            "Add modern UI elements",
            "Include holographic overlays",
            "Tech graphics around product"
        ],
        "refinement_strategy": "Maintain hero shot composition and lighting, overlay modern tech UI elements"
    }


@pytest.fixture
def mock_generated_image():
    """Mock generated refined image."""
    return {
        "success": True,
        "image_b64": "ZmFrZV9yZWZpbmVkX2ltYWdl",  # "fake_refined_image"
        "size_bytes": 1024,
        "variation": 1,
    }


@pytest.fixture
def mock_critique_approved():
    """Mock critique result - approved."""
    return {
        "approved": True,
        "score": 0.9,
        "issues": [],
        "strengths": [
            "Modern UI elements successfully added",
            "Maintained original composition",
            "User feedback fully addressed"
        ],
        "recommendation": "APPROVE",
        "feedback_addressed": True,
    }


@pytest.fixture
def mock_critique_needs_work():
    """Mock critique result - needs revision."""
    return {
        "approved": False,
        "score": 0.6,
        "issues": [
            "Modern elements too subtle",
            "Feedback only partially addressed"
        ],
        "strengths": [
            "Maintained composition well"
        ],
        "recommendation": "REVISE",
        "feedback_addressed": False,
    }


# ============================================================================
# FEEDBACK ANALYSIS TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_analyze_user_feedback_extracts_keep_change(
    sample_original_image,
    mock_feedback_analysis
):
    """Test that feedback analysis correctly extracts keep/change aspects."""
    workflow = ArtDirectorWorkflow()

    # Mock Gemini API response
    mock_response = Mock()
    mock_response.text = json.dumps(mock_feedback_analysis)

    with patch('app.workflows.art_director_workflow.genai_client') as mock_genai:
        mock_genai.aio.models.generate_content = AsyncMock(return_value=mock_response)

        result = await workflow._analyze_user_feedback(
            original_prompt="Futuristic smart sneaker with glowing sole",
            user_feedback="add modern UI elements",
            image_b64="ZmFrZV9vcmlnaW5hbF9pbWFnZQ=="
        )

    # Verify structure
    assert "keep_aspects" in result
    assert "change_aspects" in result
    assert "refinement_strategy" in result

    # Verify content
    assert isinstance(result["keep_aspects"], list)
    assert isinstance(result["change_aspects"], list)
    assert len(result["keep_aspects"]) > 0
    assert len(result["change_aspects"]) > 0
    assert "modern" in result["refinement_strategy"].lower() or "ui" in result["refinement_strategy"].lower()


@pytest.mark.asyncio
async def test_analyze_user_feedback_handles_malformed_json():
    """Test feedback analysis fallback on malformed JSON."""
    workflow = ArtDirectorWorkflow()

    # Mock Gemini API returning invalid JSON
    mock_response = Mock()
    mock_response.text = "This is not valid JSON"

    with patch('app.workflows.art_director_workflow.genai_client') as mock_genai:
        mock_genai.aio.models.generate_content = AsyncMock(return_value=mock_response)

        result = await workflow._analyze_user_feedback(
            original_prompt="Product shot",
            user_feedback="make it brighter",
            image_b64="ZmFrZQ=="
        )

    # Should return fallback
    assert "keep_aspects" in result
    assert "change_aspects" in result
    assert "make it brighter" in result["change_aspects"]


# ============================================================================
# REFINEMENT PROMPT GENERATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_generate_refinement_prompt_includes_keep_change(
    sample_product_context
):
    """Test refinement prompt includes keep/change aspects."""
    workflow = ArtDirectorWorkflow()

    keep_aspects = ["Dramatic lighting", "Product centered"]
    change_aspects = ["Add modern UI elements", "Include holograms"]

    prompt = await workflow._generate_refinement_prompt(
        original_prompt="Original prompt here",
        keep_aspects=keep_aspects,
        change_aspects=change_aspects,
        refinement_strategy="Maintain composition, add tech elements",
        product_context=sample_product_context
    )

    # Verify prompt structure
    assert isinstance(prompt, str)
    assert len(prompt) > 100

    # Verify keeps are mentioned
    assert "Dramatic lighting" in prompt
    assert "Product centered" in prompt

    # Verify changes are mentioned
    assert "modern UI" in prompt
    assert "holograms" in prompt.lower()

    # Verify product context included
    assert "Aura Smart Sneaker" in prompt
    assert "futuristic" in prompt


# ============================================================================
# SINGLE IMAGE REFINEMENT TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_refine_image_creates_new_version(
    sample_original_image,
    sample_product_context,
    mock_feedback_analysis,
    mock_generated_image,
    mock_critique_approved
):
    """Test that refine_image creates a new version with correct metadata."""
    workflow = ArtDirectorWorkflow()

    # Mock all the workflow steps
    with patch.object(workflow, '_analyze_user_feedback', AsyncMock(return_value=mock_feedback_analysis)), \
         patch.object(workflow, '_generate_refinement_prompt', AsyncMock(return_value="Refined prompt")), \
         patch('app.workflows.art_director_workflow.generate_image_tool', AsyncMock(return_value=mock_generated_image)), \
         patch('app.workflows.art_director_workflow.critique_image_tool', AsyncMock(return_value=mock_critique_approved)):

        result = await workflow.refine_image(
            original_image=sample_original_image,
            user_feedback="add modern UI elements",
            product_context=sample_product_context
        )

    # Verify new version created
    assert result["asset_id"] != sample_original_image["asset_id"]
    assert result["refinement_iteration"] == 1
    assert result["parent_asset_id"] == sample_original_image["asset_id"]
    assert result["user_feedback_applied"] == "add modern UI elements"

    # Verify generation params
    assert result["generation_params"]["variation"] == 1
    assert result["generation_params"]["approved"] == True
    assert result["generation_params"]["score"] == 0.9
    assert result["generation_params"]["feedback_addressed"] == True

    # Verify generation tracking metadata is preserved (NEW - production level)
    assert result["generation_number"] == 1  # Should stay same generation
    assert result["variation_number"] == 1  # Should stay same variation


@pytest.mark.asyncio
async def test_refine_image_retries_on_low_score(
    sample_original_image,
    sample_product_context,
    mock_feedback_analysis,
    mock_generated_image,
    mock_critique_needs_work,
    mock_critique_approved
):
    """Test refinement retries when critique score < 0.7."""
    workflow = ArtDirectorWorkflow()

    # First critique fails, second passes
    critique_results = [mock_critique_needs_work, mock_critique_approved]

    with patch.object(workflow, '_analyze_user_feedback', AsyncMock(return_value=mock_feedback_analysis)), \
         patch.object(workflow, '_generate_refinement_prompt', AsyncMock(return_value="Refined prompt")), \
         patch('app.workflows.art_director_workflow.generate_image_tool', AsyncMock(return_value=mock_generated_image)), \
         patch('app.workflows.art_director_workflow.critique_image_tool', AsyncMock(side_effect=critique_results)):

        result = await workflow.refine_image(
            original_image=sample_original_image,
            user_feedback="add modern UI elements",
            product_context=sample_product_context,
            max_iterations=2
        )

    # Verify retry happened and succeeded
    assert result["generation_params"]["score"] == 0.9
    assert result["generation_params"]["approved"] == True


@pytest.mark.asyncio
async def test_refine_image_max_iterations_enforced(
    sample_original_image,
    sample_product_context
):
    """Test that MAX_REFINEMENT_ITERATIONS = 5 is enforced."""
    workflow = ArtDirectorWorkflow()

    # Set original image to iteration 5 (max reached)
    original_at_max = {
        **sample_original_image,
        "refinement_iteration": 5
    }

    with pytest.raises(ValueError) as exc_info:
        await workflow.refine_image(
            original_image=original_at_max,
            user_feedback="add more elements",
            product_context=sample_product_context
        )

    assert "Maximum refinement iterations" in str(exc_info.value)
    assert "5" in str(exc_info.value)


@pytest.mark.asyncio
async def test_refine_image_uses_original_as_reference(
    sample_original_image,
    sample_product_context,
    mock_feedback_analysis,
    mock_generated_image,
    mock_critique_approved
):
    """Test that refinement passes original image as reference."""
    workflow = ArtDirectorWorkflow()

    with patch.object(workflow, '_analyze_user_feedback', AsyncMock(return_value=mock_feedback_analysis)), \
         patch.object(workflow, '_generate_refinement_prompt', AsyncMock(return_value="Refined prompt")), \
         patch('app.workflows.art_director_workflow.generate_image_tool', AsyncMock(return_value=mock_generated_image)) as mock_gen, \
         patch('app.workflows.art_director_workflow.critique_image_tool', AsyncMock(return_value=mock_critique_approved)):

        await workflow.refine_image(
            original_image=sample_original_image,
            user_feedback="add modern UI elements",
            product_context=sample_product_context
        )

        # Verify generate_image_tool was called with original as reference
        call_args = mock_gen.call_args
        assert call_args is not None
        assert "reference_images_b64" in call_args.kwargs

        # Original image base64 should be in references
        original_b64 = sample_original_image["url"].split(",")[1]
        assert original_b64 in call_args.kwargs["reference_images_b64"]


# ============================================================================
# BATCH REFINEMENT TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_refine_all_images_processes_in_parallel(
    sample_original_image,
    sample_product_context,
    mock_feedback_analysis,
    mock_generated_image,
    mock_critique_approved
):
    """Test batch refinement processes all images in parallel."""
    workflow = ArtDirectorWorkflow()

    # Create 4 original images
    all_images = [
        {**sample_original_image, "asset_id": f"img_{i}", "generation_params": {**sample_original_image["generation_params"], "variation": i}}
        for i in range(1, 5)
    ]

    with patch.object(workflow, 'refine_image', AsyncMock(return_value={"asset_id": "refined", "refinement_iteration": 1})) as mock_refine:
        results = await workflow.refine_all_images(
            all_images=all_images,
            global_feedback="increase brightness",
            product_context=sample_product_context
        )

    # Verify all images processed
    assert len(results) == 4

    # Verify refine_image called 4 times with same feedback
    assert mock_refine.call_count == 4

    for call in mock_refine.call_args_list:
        assert call.kwargs["user_feedback"] == "increase brightness"


@pytest.mark.asyncio
async def test_refine_all_images_handles_partial_failures(
    sample_original_image,
    sample_product_context
):
    """Test batch refinement handles partial failures gracefully."""
    workflow = ArtDirectorWorkflow()

    all_images = [
        {**sample_original_image, "asset_id": f"img_{i}"}
        for i in range(1, 5)
    ]

    # Mock: first 2 succeed, 3rd fails, 4th succeeds
    async def mock_refine(original_image, user_feedback, product_context):
        if original_image["asset_id"] == "img_3":
            raise Exception("Image generation failed")
        return {"asset_id": f"refined_{original_image['asset_id']}", "refinement_iteration": 1}

    with patch.object(workflow, 'refine_image', side_effect=mock_refine):
        results = await workflow.refine_all_images(
            all_images=all_images,
            global_feedback="increase brightness",
            product_context=sample_product_context
        )

    # Should have 4 results (3 refined + 1 original fallback)
    assert len(results) == 4

    # The failed one should be the original
    assert any(r["asset_id"] == "img_3" for r in results)


# ============================================================================
# VERSION ROLLBACK TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_rollback_to_version_restores_without_regeneration(
    sample_original_image
):
    """Test rollback restores version without regenerating."""
    workflow = ArtDirectorWorkflow()

    v2_image = {
        **sample_original_image,
        "asset_id": "img_v2",
        "refinement_iteration": 2,
        "parent_asset_id": sample_original_image["asset_id"]
    }

    result = await workflow.rollback_to_version(target_version=v2_image)

    # Should return exact same version without changes
    assert result == v2_image
    assert result["refinement_iteration"] == 2


# ============================================================================
# VERSION MIXING TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_refine_version_with_attributes_combines_versions(
    sample_original_image,
    sample_product_context,
    mock_feedback_analysis,
    mock_generated_image,
    mock_critique_approved
):
    """Test version mixing combines attributes from different versions."""
    workflow = ArtDirectorWorkflow()

    v2 = {**sample_original_image, "asset_id": "img_v2", "refinement_iteration": 2}
    v4 = {**sample_original_image, "asset_id": "img_v4", "refinement_iteration": 4}

    attribute_sources = {
        "brightness": v4,
        "saturation": v2
    }

    with patch.object(workflow, 'refine_image', AsyncMock(return_value={"asset_id": "img_mixed", "refinement_iteration": 3})) as mock_refine:
        result = await workflow.refine_version_with_attributes(
            base_version=v2,
            attribute_sources=attribute_sources,
            product_context=sample_product_context
        )

    # Verify refine_image called with synthetic feedback
    assert mock_refine.called
    call_args = mock_refine.call_args

    # Feedback should mention version 4 and version 2
    feedback = call_args.kwargs["user_feedback"]
    assert "version 4" in feedback.lower() or "version 2" in feedback.lower()


# ============================================================================
# CRITIQUE VALIDATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_critique_validates_feedback_addressed():
    """Test enhanced critique validates user feedback was addressed."""

    # Mock Gemini API response for refinement critique
    mock_critique_response = {
        "approved": True,
        "score": 0.9,
        "issues": [],
        "strengths": ["Modern elements successfully added", "Feedback fully addressed"],
        "recommendation": "APPROVE",
        "feedback_addressed": True
    }

    mock_response = Mock()
    mock_response.text = json.dumps(mock_critique_response)

    with patch('app.services.google_ai_client.genai_client') as mock_genai:
        mock_genai.aio.models.generate_content = AsyncMock(return_value=mock_response)

        result = await critique_image_tool(
            image_b64="ZmFrZV9pbWFnZQ==",
            variation=1,
            theme="futuristic",
            brand_tone="innovative",
            product_category="footwear",
            user_feedback="add modern UI elements"  # Refinement mode
        )

    # Verify feedback validation
    assert "feedback_addressed" in result
    assert result["feedback_addressed"] == True
    assert result["score"] >= 0.7


@pytest.mark.asyncio
async def test_critique_without_feedback_uses_standard_mode():
    """Test critique uses standard validation when no feedback provided."""

    mock_critique_response = {
        "approved": True,
        "score": 0.85,
        "issues": [],
        "strengths": ["High technical quality", "Brand aligned"],
        "recommendation": "APPROVE"
    }

    mock_response = Mock()
    mock_response.text = json.dumps(mock_critique_response)

    with patch('app.services.google_ai_client.genai_client') as mock_genai:
        mock_genai.aio.models.generate_content = AsyncMock(return_value=mock_response)

        result = await critique_image_tool(
            image_b64="ZmFrZV9pbWFnZQ==",
            variation=1,
            theme="futuristic",
            brand_tone="innovative",
            product_category="footwear",
            user_feedback=None  # Original mode
        )

    # Should NOT have feedback_addressed field in original mode
    assert "feedback_addressed" not in result or result.get("feedback_addressed") is None


@pytest.mark.asyncio
async def test_critique_enforces_score_threshold():
    """Test critique enforces approved=True only if score >= 0.7."""

    # Mock response with score < 0.7 but approved=True (should be overridden)
    mock_critique_response = {
        "approved": True,  # Invalid - score too low
        "score": 0.6,
        "issues": ["Needs improvement"],
        "strengths": [],
        "recommendation": "REVISE"
    }

    mock_response = Mock()
    mock_response.text = json.dumps(mock_critique_response)

    with patch('app.services.google_ai_client.genai_client') as mock_genai:
        mock_genai.aio.models.generate_content = AsyncMock(return_value=mock_response)

        result = await critique_image_tool(
            image_b64="ZmFrZV9pbWFnZQ==",
            variation=1,
            theme="futuristic",
            brand_tone="innovative",
            product_category="footwear"
        )

    # Should override approved to False
    assert result["approved"] == False
    assert result["score"] == 0.6


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_refine_image_handles_invalid_data_uri():
    """Test refinement handles invalid image data URI."""
    workflow = ArtDirectorWorkflow()

    invalid_image = {
        "asset_id": "img_invalid",
        "url": "http://example.com/image.png",  # Not a data URI
        "description": "Invalid",
        "generation_params": {},
        "refinement_iteration": 0
    }

    with pytest.raises(ValueError) as exc_info:
        await workflow.refine_image(
            original_image=invalid_image,
            user_feedback="add elements",
            product_context={"product_name": "Test"}
        )

    assert "data URI" in str(exc_info.value)


@pytest.mark.asyncio
async def test_refine_image_handles_generation_failure(
    sample_original_image,
    sample_product_context,
    mock_feedback_analysis
):
    """Test refinement handles image generation failure."""
    workflow = ArtDirectorWorkflow()

    # Mock generation failure
    failed_generation = {
        "success": False,
        "error": "Imagen API error"
    }

    with patch.object(workflow, '_analyze_user_feedback', AsyncMock(return_value=mock_feedback_analysis)), \
         patch.object(workflow, '_generate_refinement_prompt', AsyncMock(return_value="Refined prompt")), \
         patch('app.workflows.art_director_agents.generate_image_tool', AsyncMock(return_value=failed_generation)):

        with pytest.raises(RuntimeError) as exc_info:
            await workflow.refine_image(
                original_image=sample_original_image,
                user_feedback="add elements",
                product_context=sample_product_context,
                max_iterations=1
            )

        assert "Failed to generate" in str(exc_info.value)


print("✅ Image Refinement unit tests created")
