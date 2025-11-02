"""
Seed demo data for AI Agency.

This script creates pre-configured campaigns for demonstration and testing
across different product categories.

Usage:
    python scripts/seed_demo_data.py --campaign=aura  # Default sneaker
    python scripts/seed_demo_data.py --campaign=ember  # Energy drink
    python scripts/seed_demo_data.py --campaign=luxe  # Watch
    python scripts/seed_demo_data.py --campaign=nova  # Smart home
    python scripts/seed_demo_data.py --campaign=all   # All campaigns
"""

import argparse
import asyncio
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.models.assets import CampaignTemplate
from app.models.brief import ProjectBrief, SessionState
from app.services.redis_client import redis_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Demo Campaign Templates

AURA_CAMPAIGN = CampaignTemplate(
    product_name="Aura Smart Sneaker",
    product_category="footwear",
    theme="Tokyo neon",
    key_features=["glowing sole", "smart tracking", "urban design"],
    target_market="Urban runners, tech enthusiasts, night joggers",
    initial_sketch_url="gs://ai-agency-demo/aura_sneaker_sketch.png",
    brand_tone="futuristic",
)

EMBER_CAMPAIGN = CampaignTemplate(
    product_name="Ember Energy Drink",
    product_category="beverage",
    theme="Volcanic energy",
    key_features=["natural caffeine", "zero sugar", "volcanic minerals"],
    target_market="Athletes, gamers, extreme sports enthusiasts",
    initial_sketch_url="gs://ai-agency-demo/ember_drink_sketch.png",
    brand_tone="edgy",
)

LUXE_CAMPAIGN = CampaignTemplate(
    product_name="Luxe Minimalist Watch",
    product_category="fashion",
    theme="Scandinavian minimalism",
    key_features=["automatic movement", "sapphire crystal", "40mm case"],
    target_market="Young professionals, design enthusiasts, minimalists",
    initial_sketch_url="gs://ai-agency-demo/luxe_watch_sketch.png",
    brand_tone="luxury",
)

NOVA_CAMPAIGN = CampaignTemplate(
    product_name="Nova Smart Home Hub",
    product_category="electronics",
    theme="Ambient intelligence",
    key_features=["voice control", "AI learning", "seamless integration"],
    target_market="Tech-savvy homeowners, early adopters, families",
    initial_sketch_url="gs://ai-agency-demo/nova_hub_sketch.png",
    brand_tone="professional",
)

CAMPAIGNS = {
    "aura": AURA_CAMPAIGN,
    "ember": EMBER_CAMPAIGN,
    "luxe": LUXE_CAMPAIGN,
    "nova": NOVA_CAMPAIGN,
}


async def create_demo_campaign(
    campaign_template: CampaignTemplate,
    campaign_key: str,
) -> tuple[str, str]:
    """
    Create a demo campaign with session and project brief.

    Args:
        campaign_template: Campaign configuration
        campaign_key: Campaign key (aura, ember, luxe, nova) for fixed project ID

    Returns:
        Tuple of (session_id, project_id)
    """
    session_id = f"demo_session_{uuid.uuid4().hex[:8]}"
    # Use fixed project ID based on campaign key (e.g., "aura_smart_sneaker")
    project_id = f"{campaign_key}_smart_sneaker" if campaign_key == "aura" else f"{campaign_key}_demo"

    # Create session
    session = SessionState(
        session_id=session_id,
        user_id="demo_user",
        created_at=datetime.utcnow(),
        last_active=datetime.utcnow(),
        status="active",
    )
    await redis_client.create_session(session)
    logger.info(f"Created session: {session_id}")

    # Create project brief
    brief = ProjectBrief(
        project_id=project_id,
        session_id=session_id,
        product_name=campaign_template.product_name,
        product_category=campaign_template.product_category,
        theme=campaign_template.theme,
        key_features=campaign_template.key_features,
        brand_tone=campaign_template.brand_tone,
        target_market=campaign_template.target_market,
        initial_sketch_url=campaign_template.initial_sketch_url,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        status="planning",
    )
    await redis_client.save_project_brief(brief)
    logger.info(f"Created project brief: {project_id}")

    logger.info(f"✓ Demo campaign '{campaign_template.product_name}' created successfully")
    logger.info(f"  Session ID: {session_id}")
    logger.info(f"  Project ID: {project_id}")
    logger.info(f"  Category: {campaign_template.product_category}")
    logger.info(f"  Theme: {campaign_template.theme}")
    logger.info(f"  Brand Tone: {campaign_template.brand_tone}")
    logger.info("")

    return session_id, project_id


async def seed_campaigns(campaign_names: list[str]) -> None:
    """
    Seed one or more demo campaigns.

    Args:
        campaign_names: List of campaign names to seed
    """
    logger.info("=" * 60)
    logger.info("AI Agency - Demo Data Seeder")
    logger.info("=" * 60)
    logger.info("")

    # Connect to Redis
    await redis_client.connect()
    logger.info("Connected to Redis")
    logger.info("")

    # Seed campaigns
    for campaign_name in campaign_names:
        if campaign_name not in CAMPAIGNS:
            logger.error(f"Unknown campaign: {campaign_name}")
            logger.info(f"Available campaigns: {', '.join(CAMPAIGNS.keys())}")
            continue

        campaign = CAMPAIGNS[campaign_name]
        await create_demo_campaign(campaign, campaign_name)

    # Disconnect from Redis
    await redis_client.disconnect()
    logger.info("=" * 60)
    logger.info("Demo data seeding complete!")
    logger.info("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed demo data for AI Agency",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/seed_demo_data.py --campaign=aura
  python scripts/seed_demo_data.py --campaign=ember
  python scripts/seed_demo_data.py --campaign=all
        """,
    )
    parser.add_argument(
        "--campaign",
        type=str,
        default="aura",
        help="Campaign to seed (aura, ember, luxe, nova, all)",
    )

    args = parser.parse_args()

    # Determine which campaigns to seed
    if args.campaign == "all":
        campaign_names = list(CAMPAIGNS.keys())
    else:
        campaign_names = [args.campaign]

    # Run seeding
    asyncio.run(seed_campaigns(campaign_names))


if __name__ == "__main__":
    main()
