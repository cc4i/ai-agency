"""Web Dev Agent - Landing page code generation.

Uses Gemini Code Assist to generate HTML/CSS/JavaScript for landing pages.
Adapts styling to match product category and brand tone.
"""

import logging
import re
import uuid
from typing import Any, Dict

from app.agents.base import AgentBase
from app.models.assets import CodeAsset, CritiqueResult, WebDevOutput
from app.services.google_ai_client import code_assist_client

logger = logging.getLogger(__name__)


# Category-specific color schemes
CATEGORY_COLOR_SCHEMES = {
    "footwear": "Athletic blues and energetic oranges, sporty gradients",
    "beverage": "Vibrant reds and refreshing blues, bold contrasts",
    "electronics": "Sleek grays and tech blues, minimalist palette",
    "fashion": "Sophisticated blacks and elegant golds, refined tones",
    "beauty": "Soft pinks and natural earth tones, gentle palette",
    "food": "Warm oranges and appetite-inducing reds, inviting colors",
    "automotive": "Powerful blacks and racing reds, dynamic scheme",
}


class WebDevAgent(AgentBase):
    """
    Web Dev Agent generates landing page code.

    Outputs:
    - Complete HTML structure
    - Responsive CSS styling
    - Interactive JavaScript
    - Live preview-ready code
    """

    def __init__(self):
        """Initialize Web Dev Agent."""
        super().__init__(agent_id="web_dev")

    async def execute(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute landing page code generation.

        Args:
            task: Contains image_url, slogan, product info, theme, brand_tone
            context: Shared project context

        Returns:
            WebDevOutput with HTML/CSS/JS code
        """
        logger.info(f"Web Dev Agent executing for: {task.get('product_name')}")

        image_url = task.get("image_url", "")
        slogan = task.get("slogan", "Coming Soon")
        product_name = task.get("product_name", "Product")
        theme = task.get("theme", "modern")
        brand_tone = task.get("brand_tone", "professional")
        product_category = task.get("product_category", "product")
        key_features = task.get("key_features", [])

        # Generate landing page code
        code = await self._generate_landing_page(
            image_url=image_url,
            slogan=slogan,
            product_name=product_name,
            theme=theme,
            brand_tone=brand_tone,
            product_category=product_category,
            key_features=key_features,
        )

        output = WebDevOutput(
            code=code, framework="vanilla", deployment_status="preview"
        )

        logger.info(f"[WEB_DEV] Web Dev completed: {code.asset_id}")
        logger.info(f"[WEB_DEV] Output has code: {output.code is not None}")
        logger.info(f"[WEB_DEV] Code HTML length: {len(output.code.html) if output.code else 0}")

        result = output.model_dump()
        logger.info(f"[WEB_DEV] Returning result with keys: {list(result.keys())}")

        return result

    async def _generate_landing_page(
        self,
        image_url: str,
        slogan: str,
        product_name: str,
        theme: str,
        brand_tone: str,
        product_category: str,
        key_features: list,
    ) -> CodeAsset:
        """
        Generate complete landing page code.

        Args:
            image_url: Hero image URL
            slogan: Campaign slogan
            product_name: Product name
            theme: Visual theme
            brand_tone: Brand tone
            product_category: Product category
            key_features: Product features

        Returns:
            CodeAsset with HTML, CSS, and JavaScript
        """
        # Get category-specific color scheme
        color_scheme = CATEGORY_COLOR_SCHEMES.get(
            product_category, "Modern blues and grays"
        )

        # Check if image_url is a data URI (base64) to avoid token overflow
        # Data URIs can be 100k+ characters and blow up the token count
        if image_url.startswith("data:"):
            image_placeholder = "{{HERO_IMAGE_URL}}"  # Placeholder to be replaced
            logger.info(f"Using placeholder for data URI image (length: {len(image_url)})")
        else:
            image_placeholder = image_url

        prompt = f"""
        Generate a beautiful "Coming Soon" landing page.

        PRODUCT: {product_name}
        SLOGAN: "{slogan}"
        THEME: {theme}
        BRAND TONE: {brand_tone}
        CATEGORY: {product_category}
        COLOR SCHEME: {color_scheme}

        PAGE REQUIREMENTS:
        1. Hero section with image placeholder: {image_placeholder}
           (Use this as the src attribute for the hero image)
        2. Prominent slogan display
        3. Countdown timer to launch date (30 days from now)
        4. Email signup form
        5. Feature highlights: {', '.join(key_features[:3])}
        6. Social media links (placeholder)

        DESIGN SPECIFICATIONS:
        - Color scheme: {color_scheme}
        - Typography: {brand_tone} fonts (sans-serif for modern/futuristic, serif for luxury)
        - Layout: Responsive, mobile-first
        - Style: {theme} aesthetic with {brand_tone} feel
        - Animation: Subtle, professional transitions
        - Accessibility: Semantic HTML, ARIA labels

        TECHNICAL REQUIREMENTS:
        - Pure HTML5, CSS3, vanilla JavaScript
        - No external dependencies
        - Responsive grid layout
        - Form validation
        - Countdown timer with JavaScript
        - Smooth scroll animations
        - Cross-browser compatible

        OUTPUT FORMAT:
        Provide complete, production-ready code split into:
        1. HTML (full document structure)
        2. CSS (complete styling)
        3. JavaScript (countdown timer, form handling, animations)

        Make it visually stunning and {brand_tone}!
        """

        # SKIP Gemini Code Assist - Always use modern template for better quality
        # (Gemini's generated landing pages are too simple)
        logger.info(f"[WEB_DEV] Using modern template instead of Gemini generation")

        # Load and populate the modern template directly with image URL
        html, css, js = self._load_modern_template(product_name, slogan, key_features, image_url)

        logger.info(f"[WEB_DEV] After template loading - HTML: {len(html)} chars, CSS: {len(css)} chars, JS: {len(js)} chars")

        asset_id = f"landing_{uuid.uuid4().hex[:12]}"

        logger.info(f"[WEB_DEV] Creating CodeAsset: {asset_id}")

        # Combine into full HTML for upload
        full_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>{css}</style>
</head>
<body>
  {html}
  <script>{js}</script>
</body>
</html>"""

        # Upload to GCS and get public URL
        from app.services.storage_client import storage_client
        try:
            _, preview_url = await storage_client.upload_html(full_html, asset_id)
            logger.info(f"[WEB_DEV] Uploaded landing page to: {preview_url}")
        except Exception as e:
            logger.error(f"[WEB_DEV] Failed to upload landing page: {e}")
            preview_url = None

        code_asset = CodeAsset(
            asset_id=asset_id,
            html=html,
            css=css,
            javascript=js,
            preview_url=preview_url,
        )

        logger.debug(f"Generated landing page: {asset_id}")

        return code_asset

    def _load_modern_template(
        self,
        product_name: str,
        slogan: str,
        key_features: list,
        image_url: str = ""
    ) -> tuple[str, str, str]:
        """
        Load the modern landing page template and extract HTML, CSS, JS.

        Args:
            product_name: Product name
            slogan: Campaign slogan
            key_features: Product features list
            image_url: Hero image URL

        Returns:
            Tuple of (html, css, javascript)
        """
        import os
        import re

        template_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "templates",
            "modern_landing_page.html"
        )

        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()

            # Apply template variables
            html = self._apply_template_variables(
                template_content, product_name, slogan, key_features, image_url
            )

            logger.info(f"[WEB_DEV] ✓ Loaded modern template ({len(html)} chars)")

            # Extract CSS from <style> tags
            css_match = re.search(r'<style>(.*?)</style>', html, re.DOTALL)
            css = css_match.group(1).strip() if css_match else ""
            logger.info(f"[WEB_DEV] ✓ Extracted CSS from template ({len(css)} chars)")

            # Extract JS from <script> tags
            js_match = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
            js = js_match.group(1).strip() if js_match else ""
            logger.info(f"[WEB_DEV] ✓ Extracted JS from template ({len(js)} chars)")

            return html, css, js

        except FileNotFoundError:
            logger.error(f"[WEB_DEV] ✗ Modern template not found at {template_path}")
            # Return empty strings to trigger fallback
            return "", "", ""

    def _apply_template_variables(
        self,
        template: str,
        product_name: str,
        slogan: str,
        key_features: list,
        image_url: str = ""
    ) -> str:
        """
        Apply variable replacements to landing page template.

        Args:
            template: HTML template with placeholders
            product_name: Product name
            slogan: Campaign slogan
            key_features: List of product features
            image_url: Hero image URL

        Returns:
            Template with variables replaced
        """
        # Extract up to 3 features
        features = []
        default_features = [
            {"title": "Innovation", "description": "Experience cutting-edge features"},
            {"title": "Quality", "description": "Premium craftsmanship and materials"},
            {"title": "Design", "description": "Beautiful aesthetics meets functionality"}
        ]

        for i in range(3):
            if i < len(key_features):
                # If key_features contains strings, use them
                if isinstance(key_features[i], str):
                    features.append({
                        "title": key_features[i].split(':')[0].strip() if ':' in key_features[i] else key_features[i],
                        "description": key_features[i].split(':')[1].strip() if ':' in key_features[i] else f"Experience {key_features[i].lower()}"
                    })
                # If key_features contains dicts
                elif isinstance(key_features[i], dict):
                    features.append(key_features[i])
            else:
                features.append(default_features[i])

        # Use placeholder image if no URL provided
        if not image_url:
            image_url = "https://images.unsplash.com/photo-1556906781-9cba4c2bc7ec?w=1200&h=800&fit=crop"

        # Apply replacements
        result = template
        result = result.replace("{{PRODUCT_NAME}}", product_name)
        result = result.replace("{{SLOGAN}}", slogan)
        result = result.replace("{{HERO_IMAGE_URL}}", image_url)
        result = result.replace("{{FEATURE_1_TITLE}}", features[0]["title"])
        result = result.replace("{{FEATURE_1_DESC}}", features[0]["description"])
        result = result.replace("{{FEATURE_2_TITLE}}", features[1]["title"])
        result = result.replace("{{FEATURE_2_DESC}}", features[1]["description"])
        result = result.replace("{{FEATURE_3_TITLE}}", features[2]["title"])
        result = result.replace("{{FEATURE_3_DESC}}", features[2]["description"])

        logger.info(f"[WEB_DEV] Applied template variables for {product_name}")
        return result

    def _parse_code_response(
        self,
        response: str,
        product_name: str,
        slogan: str,
        theme: str,
        key_features: list
    ) -> tuple[str, str, str]:
        """
        Parse code response into HTML, CSS, and JavaScript.

        Args:
            response: Raw code response from Gemini Code Assist
            product_name: Product name
            slogan: Slogan
            theme: Theme
            key_features: Product features list

        Returns:
            Tuple of (html, css, javascript)
        """
        import re

        logger.info(f"[WEB_DEV] Parsing code response ({len(response)} chars)")
        logger.info(f"[WEB_DEV] Response starts with: {response[:100]}")

        # Try to extract code blocks from markdown-style response
        # Look for ```html, ```css, ```javascript code blocks

        html = ""
        css = ""
        js = ""

        # Extract HTML
        html_match = re.search(r'```html\n(.*?)```', response, re.DOTALL | re.IGNORECASE)
        if html_match:
            html = html_match.group(1).strip()
            logger.info(f"[WEB_DEV] ✓ Extracted HTML: {len(html)} chars")
        else:
            logger.warning(f"[WEB_DEV] ✗ No HTML code block found")

        # Extract CSS
        css_match = re.search(r'```css\n(.*?)```', response, re.DOTALL | re.IGNORECASE)
        if css_match:
            css = css_match.group(1).strip()
            logger.info(f"[WEB_DEV] ✓ Extracted CSS: {len(css)} chars")
        else:
            logger.warning(f"[WEB_DEV] ✗ No CSS code block found")

        # Extract JavaScript
        js_match = re.search(r'```(?:javascript|js)\n(.*?)```', response, re.DOTALL | re.IGNORECASE)
        if js_match:
            js = js_match.group(1).strip()
            logger.info(f"[WEB_DEV] ✓ Extracted JS: {len(js)} chars")
        else:
            logger.warning(f"[WEB_DEV] ✗ No JS code block found")

        # If extraction failed, try to use the whole response as HTML
        if not html and not css and not js:
            logger.warning("No code blocks found, using response as HTML")
            # Remove any code fences
            cleaned = re.sub(r'```[\w]*\n?', '', response).strip()
            html = cleaned if cleaned else response

        # Fallback template if nothing was extracted
        if not html or not css or not js:
            logger.warning(f"Falling back to modern template (html={bool(html)}, css={bool(css)}, js={bool(js)})")

            # ALWAYS load modern template as fallback (don't use partial/broken code from Gemini)
            # Load modern landing page template
            import os
            template_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "templates",
                "modern_landing_page.html"
            )

            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    template_content = f.read()

                # Apply template variables
                html = self._apply_template_variables(
                    template_content, product_name, slogan, key_features
                )

                logger.info(f"[WEB_DEV] ✓ Loaded modern template ({len(html)} chars)")

                # Extract CSS and JS from the template
                # CSS is between <style> tags
                css_match = re.search(r'<style>(.*?)</style>', html, re.DOTALL)
                if css_match:
                    css = css_match.group(1).strip()
                    logger.info(f"[WEB_DEV] ✓ Extracted CSS from template ({len(css)} chars)")

                # JS is between <script> tags
                js_match = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
                if js_match:
                    js = js_match.group(1).strip()
                    logger.info(f"[WEB_DEV] ✓ Extracted JS from template ({len(js)} chars)")

            except FileNotFoundError:
                logger.error(f"[WEB_DEV] ✗ Modern template not found at {template_path}")
                # Fallback to basic template
                html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{product_name} - Coming Soon</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <main class="container">
        <header>
            <h1 class="product-name">{product_name}</h1>
        </header>

        <section class="hero">
            <div class="hero-image">
                <!-- Hero image placeholder -->
                <div class="image-placeholder"></div>
            </div>
            <h2 class="slogan">{slogan}</h2>
        </section>

        <section class="countdown">
            <h3>Launching In</h3>
            <div class="timer">
                <div class="time-unit">
                    <span id="days">00</span>
                    <span class="label">Days</span>
                </div>
                <div class="time-unit">
                    <span id="hours">00</span>
                    <span class="label">Hours</span>
                </div>
                <div class="time-unit">
                    <span id="minutes">00</span>
                    <span class="label">Minutes</span>
                </div>
                <div class="time-unit">
                    <span id="seconds">00</span>
                    <span class="label">Seconds</span>
                </div>
            </div>
        </section>

        <section class="signup">
            <h3>Be the First to Know</h3>
            <form id="email-form">
                <input type="email" id="email" placeholder="Enter your email" required>
                <button type="submit">Notify Me</button>
            </form>
            <p id="form-message"></p>
        </section>

        <footer>
            <p>&copy; 2024 {product_name}. All rights reserved.</p>
        </footer>
    </main>

    <script src="script.js"></script>
</body>
</html>"""

            if not css:
                css = f"""/* {product_name} Landing Page - {theme} Theme */

* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
    color: #ffffff;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
}}

.container {{
    max-width: 1200px;
    padding: 2rem;
    text-align: center;
}}

header {{
    margin-bottom: 3rem;
}}

.product-name {{
    font-size: 3rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    animation: fadeIn 1s ease-in;
}}

.hero {{
    margin-bottom: 4rem;
}}

.image-placeholder {{
    width: 100%;
    max-width: 800px;
    height: 400px;
    margin: 0 auto 2rem;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 1rem;
    backdrop-filter: blur(10px);
}}

.slogan {{
    font-size: 2.5rem;
    font-weight: 300;
    font-style: italic;
    animation: fadeIn 1.5s ease-in;
}}

.countdown {{
    margin-bottom: 4rem;
}}

.countdown h3 {{
    font-size: 1.5rem;
    margin-bottom: 2rem;
    opacity: 0.9;
}}

.timer {{
    display: flex;
    justify-content: center;
    gap: 2rem;
    flex-wrap: wrap;
}}

.time-unit {{
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 100px;
}}

.time-unit span:first-child {{
    font-size: 4rem;
    font-weight: 700;
    line-height: 1;
}}

.label {{
    font-size: 0.875rem;
    opacity: 0.7;
    margin-top: 0.5rem;
}}

.signup {{
    margin-bottom: 4rem;
}}

.signup h3 {{
    font-size: 1.5rem;
    margin-bottom: 1.5rem;
}}

#email-form {{
    display: flex;
    gap: 1rem;
    max-width: 500px;
    margin: 0 auto 1rem;
    flex-wrap: wrap;
    justify-content: center;
}}

#email {{
    flex: 1;
    min-width: 250px;
    padding: 1rem;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-radius: 0.5rem;
    background: rgba(255, 255, 255, 0.1);
    color: #ffffff;
    font-size: 1rem;
}}

#email::placeholder {{
    color: rgba(255, 255, 255, 0.6);
}}

button {{
    padding: 1rem 2rem;
    background: #ffffff;
    color: #1e3a8a;
    border: none;
    border-radius: 0.5rem;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.2s;
}}

button:hover {{
    transform: scale(1.05);
}}

#form-message {{
    color: #86efac;
    font-size: 0.875rem;
}}

footer {{
    opacity: 0.7;
    font-size: 0.875rem;
}}

@keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(20px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}

@media (max-width: 768px) {{
    .product-name {{
        font-size: 2rem;
    }}
    .slogan {{
        font-size: 1.5rem;
    }}
    .time-unit span:first-child {{
        font-size: 2.5rem;
    }}
}}"""

            if not js:
                javascript = """// Countdown Timer
const launchDate = new Date();
launchDate.setDate(launchDate.getDate() + 30); // 30 days from now

function updateCountdown() {
    const now = new Date().getTime();
    const distance = launchDate - now;

    const days = Math.floor(distance / (1000 * 60 * 60 * 24));
    const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((distance % (1000 * 60)) / 1000);

    document.getElementById('days').textContent = String(days).padStart(2, '0');
    document.getElementById('hours').textContent = String(hours).padStart(2, '0');
    document.getElementById('minutes').textContent = String(minutes).padStart(2, '0');
    document.getElementById('seconds').textContent = String(seconds).padStart(2, '0');

    if (distance < 0) {
        clearInterval(countdownInterval);
        document.querySelector('.countdown').innerHTML = '<h3>We are Live!</h3>';
    }
}

const countdownInterval = setInterval(updateCountdown, 1000);
updateCountdown();

// Email Form Handling
document.getElementById('email-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const message = document.getElementById('form-message');

    // Simple validation
    if (email && email.includes('@')) {
        message.textContent = 'Thank you! We will notify you at launch.';
        message.style.color = '#86efac';
        document.getElementById('email').value = '';

        // In production: send to backend
        console.log('Email submitted:', email);
    } else {
        message.textContent = 'Please enter a valid email address.';
        message.style.color = '#fca5a5';
    }
});"""
            else:
                # Use the extracted JavaScript
                javascript = js

        return html, css, javascript

    async def critique(
        self, result: Dict[str, Any], brief: Dict[str, Any]
    ) -> CritiqueResult:
        """
        Evaluate code output against brief.

        Args:
            result: Web Dev output
            brief: Project brief

        Returns:
            Critique result
        """
        output = WebDevOutput(**result)
        code = output.code

        issues = []

        # Check all code sections exist
        if not code.html:
            issues.append("HTML code missing")
        if not code.css:
            issues.append("CSS code missing")
        if not code.javascript:
            issues.append("JavaScript code missing")

        # Check product name in HTML
        product_name = brief.get("product_name", "")
        if product_name and product_name not in code.html:
            issues.append(f"HTML should include product name '{product_name}'")

        # Check slogan in HTML
        slogan = brief.get("selected_slogan", "")
        if slogan and slogan not in code.html:
            issues.append(f"HTML should display slogan '{slogan}'")

        if issues:
            return CritiqueResult(
                status="REVISE",
                score=0.5,
                issues=issues,
                revision_instructions=f"Fix: {'; '.join(issues)}",
            )

        return CritiqueResult(status="PASS", score=1.0, issues=[])

    async def revise(
        self, result: Dict[str, Any], critique: CritiqueResult
    ) -> Dict[str, Any]:
        """
        Revise code based on critique.

        Args:
            result: Original output
            critique: Critique feedback

        Returns:
            Revised output
        """
        logger.info(f"Web Dev revising: {critique.revision_instructions}")

        # In production, regenerate with critique feedback
        return result
