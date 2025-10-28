# Product Flexibility - Supporting Any Product Category

## Overview

The AI Agency system is **product-agnostic** and supports ANY product category, not just the default "Aura Smart Sneaker" demo.

## Supported Product Categories

### Out-of-the-Box Categories
1. **Footwear** - Sneakers, boots, athletic shoes, fashion footwear
2. **Beverage** - Energy drinks, soft drinks, alcoholic beverages, coffee, tea
3. **Electronics** - Smart home devices, gadgets, wearables, accessories
4. **Fashion** - Clothing, watches, jewelry, bags, accessories
5. **Beauty** - Skincare, makeup, haircare, fragrances
6. **Food** - Packaged foods, snacks, meal kits, specialty items
7. **Automotive** - Cars, motorcycles, accessories, services
8. **Home Goods** - Furniture, decor, appliances, tools
9. **Toys & Games** - Board games, video games, toys, collectibles
10. **Health & Wellness** - Supplements, fitness equipment, health devices

### Easy to Add
Any product category can be supported by adding category-specific guidelines to the agent prompts.

---

## How Product Flexibility Works

### 1. Campaign Template Schema

```python
class CampaignTemplate(BaseModel):
    product_name: str                    # "Aura Smart Sneaker"
    product_category: str                # "footwear", "beverage", etc.
    theme: str                           # "Tokyo neon", "Volcanic energy"
    key_features: List[str]              # Product-specific features
    target_market: str                   # Category-specific demographics
    initial_sketch_url: str              # Product image
    brand_tone: str                      # "futuristic", "luxury", "edgy"
```

### 2. Agent Adaptations

**Strategy Agent**
- Generates personas specific to product category
- Creates slogans matching brand tone
- Provides category-specific market analysis
- Considers category buying behaviors

**Art Director**
- Applies category-specific visual guidelines:
  - Footwear: Lifestyle context, texture emphasis
  - Beverage: Condensation, pour shots, vibrant colors
  - Electronics: Clean product shots, modern environments
  - Fashion: Model interaction, fabric and fit focus
  - Beauty: Close-ups, elegant presentation
  - Food: Appetizing styling, fresh ingredients
  - Automotive: Dynamic angles, motion blur

**Video Producer**
- Adapts video style to product category
- Highlights category-appropriate features
- Uses category-specific cinematography

**Audio Team**
- Matches jingle style to brand tone:
  - Futuristic → Electronic, synthetic sounds
  - Luxury → Classical, elegant compositions
  - Edgy → Rock, intense beats
  - Playful → Upbeat, fun melodies
  - Professional → Corporate, sophisticated

**Web Dev**
- Adapts color schemes to product theme
- Uses category-appropriate layout styles
- Includes category-specific CTAs

---

## Demo Campaigns

### Campaign 1: Aura Smart Sneaker (Default)
```python
{
    "product_name": "Aura Smart Sneaker",
    "product_category": "footwear",
    "theme": "Tokyo neon",
    "key_features": ["glowing sole", "smart tracking", "urban design"],
    "target_market": "Urban runners, tech enthusiasts, night joggers",
    "brand_tone": "futuristic"
}
```

**Expected Personas:**
- Tech Enthusiast Runner
- Urban Night Jogger
- Fitness Tracker Devotee

**Sample Slogans:**
- "Run on light"
- "Light your steps"
- "Glow forward"

---

### Campaign 2: Ember Energy Drink
```python
{
    "product_name": "Ember Energy Drink",
    "product_category": "beverage",
    "theme": "Volcanic energy",
    "key_features": ["natural caffeine", "zero sugar", "volcanic minerals"],
    "target_market": "Athletes, gamers, extreme sports enthusiasts",
    "brand_tone": "edgy"
}
```

**Expected Personas:**
- Competitive Gamer
- Extreme Athlete
- Night Shift Worker

**Sample Slogans:**
- "Ignite power"
- "Fuel the fire"
- "Volcanic rush"

---

### Campaign 3: Luxe Minimalist Watch
```python
{
    "product_name": "Luxe Minimalist Watch",
    "product_category": "fashion",
    "theme": "Scandinavian minimalism",
    "key_features": ["automatic movement", "sapphire crystal", "40mm case"],
    "target_market": "Young professionals, design enthusiasts, minimalists",
    "brand_tone": "luxury"
}
```

**Expected Personas:**
- Design-Conscious Professional
- Minimalist Enthusiast
- Watch Collector

**Sample Slogans:**
- "Time, refined"
- "Elegance in simplicity"
- "Less is timeless"

---

### Campaign 4: Nova Smart Home Hub
```python
{
    "product_name": "Nova Smart Home Hub",
    "product_category": "electronics",
    "theme": "Ambient intelligence",
    "key_features": ["voice control", "AI learning", "seamless integration"],
    "target_market": "Tech-savvy homeowners, early adopters, families",
    "brand_tone": "professional"
}
```

**Expected Personas:**
- Tech-Savvy Parent
- Smart Home Enthusiast
- Early Adopter Professional

**Sample Slogans:**
- "Intelligence at home"
- "Think ahead"
- "Home, smarter"

---

## Category-Specific Visual Guidelines

### Footwear
- **Composition**: Product in action or lifestyle context
- **Focus**: Texture, materials, design details
- **Setting**: Urban environments, athletic venues, lifestyle scenes
- **Lighting**: Dynamic, emphasizing product features

### Beverage
- **Composition**: Product with condensation, pour shots
- **Focus**: Refreshment appeal, vibrant colors, liquid dynamics
- **Setting**: Active scenes, social settings, outdoor activities
- **Lighting**: Bright, energetic, highlighting freshness

### Electronics
- **Composition**: Clean product shots, minimal backgrounds
- **Focus**: Sleek design, modern aesthetics, tech features
- **Setting**: Modern homes, offices, tech environments
- **Lighting**: Soft, even, emphasizing clean lines

### Fashion
- **Composition**: Lifestyle imagery with models
- **Focus**: Fabric texture, fit, style details
- **Setting**: Urban fashion scenes, elegant environments
- **Lighting**: Professional fashion photography lighting

### Beauty
- **Composition**: Close-up product shots, elegant presentations
- **Focus**: Texture, skin interaction, luxury feel
- **Setting**: Clean, elegant backdrops, lifestyle contexts
- **Lighting**: Soft, flattering, highlighting product quality

### Food
- **Composition**: Appetizing food styling
- **Focus**: Fresh ingredients, delicious appeal
- **Setting**: Kitchen scenes, dining contexts, ingredient displays
- **Lighting**: Warm, inviting, making food look appetizing

### Automotive
- **Composition**: Dynamic angles, motion blur or power shots
- **Focus**: Design lines, performance, innovation
- **Setting**: Roads, landscapes, urban environments
- **Lighting**: Dramatic, emphasizing vehicle design

---

## Adding a New Product Category

### Step 1: Define Visual Guidelines
Add to `CATEGORY_VISUAL_GUIDELINES` in Art Director agent:

```python
CATEGORY_VISUAL_GUIDELINES = {
    # ... existing categories
    "new_category": "Specific composition, focus, setting, and lighting guidelines"
}
```

### Step 2: Create Demo Campaign
Add to `scripts/seed_demo_data.py`:

```python
NEW_CATEGORY_CAMPAIGN = {
    "product_name": "Product Name",
    "product_category": "new_category",
    "theme": "Campaign Theme",
    "key_features": ["feature1", "feature2", "feature3"],
    "target_market": "Target demographic",
    "brand_tone": "tone"
}
```

### Step 3: Test End-to-End
Run the demo campaign through all 5 agents to ensure quality outputs.

---

## Brand Tone Adaptations

### Futuristic
- **Visual**: Neon lights, tech environments, sleek designs
- **Audio**: Electronic, synthetic, innovative sounds
- **Copy**: Forward-looking, tech-focused language
- **Colors**: Electric blues, purples, neons

### Luxury
- **Visual**: Elegant settings, premium materials, sophisticated
- **Audio**: Classical, refined, sophisticated compositions
- **Copy**: Exclusive, premium, refined language
- **Colors**: Gold, black, deep jewel tones

### Edgy
- **Visual**: Bold, high-contrast, dramatic
- **Audio**: Rock, intense beats, aggressive sounds
- **Copy**: Bold, rebellious, daring language
- **Colors**: Red, black, high contrast

### Playful
- **Visual**: Bright, fun, energetic scenes
- **Audio**: Upbeat, fun melodies, bouncy rhythms
- **Copy**: Light, fun, approachable language
- **Colors**: Bright primary colors, pastels

### Professional
- **Visual**: Clean, organized, modern
- **Audio**: Corporate, sophisticated, polished
- **Copy**: Clear, professional, trustworthy language
- **Colors**: Blues, grays, professional palette

---

## User Workflow for Custom Products

### Option 1: Voice Input (Preferred)
User says:
> "Let's create a campaign for my new [PRODUCT CATEGORY] product called [NAME]. It's about [THEME]."

Producer responds:
> "Great! I'll create a campaign for your [CATEGORY] product. Tell me about the key features and target market."

### Option 2: Upload Sketch
User uploads product sketch → System auto-detects category (optional) → User confirms/corrects

### Option 3: Web Form (Initial Setup)
```
Product Name: _______________
Category: [Dropdown]
Theme: _______________
Key Features: _______________
Target Market: _______________
Brand Tone: [Dropdown]
```

---

## Implementation Benefits

### For Users
✅ Works with any product type
✅ No category limitations
✅ Consistent quality across categories
✅ Natural language input

### For Development
✅ Single codebase for all categories
✅ Easy to add new categories
✅ Modular prompt templates
✅ Scalable architecture

### For Agents
✅ Context-aware outputs
✅ Category-specific expertise
✅ Consistent quality metrics
✅ Reusable patterns across categories

---

## Future Enhancements

### Category Auto-Detection
- Use Gemini Vision to detect product category from sketch
- Suggest category based on product name/description
- Learn from user corrections

### Industry-Specific Packs
- Pre-configured campaigns for specific industries
- Industry best practices and benchmarks
- Regulatory compliance considerations (e.g., alcohol, pharma)

### Multi-Product Campaigns
- Support campaigns with multiple related products
- Product bundles and collections
- Cross-selling campaign strategies

### Localization
- Adapt campaigns to regional markets
- Cultural sensitivity in visuals and copy
- Language-specific slogans and messaging
