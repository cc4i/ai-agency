# AI Agency - UI Mockups & Design Specifications

## Important: Product-Agnostic Design

**This UI is designed to support ANY product category**, not just sneakers:
- Footwear (Aura Smart Sneaker - default demo)
- Beverage (Ember Energy Drink)
- Electronics (Nova Smart Home Hub)
- Fashion (Luxe Minimalist Watch)
- Beauty, Food, Automotive, etc.

The UI adapts to:
- Product category-specific terminology
- Brand tone (futuristic, luxury, edgy, playful, professional)
- Theme-appropriate color schemes
- Category-specific visual guidelines

## Screen 1: Welcome/Handoff Screen

### ASCII Wireframe
```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│                                                             │
│                                                             │
│              Welcome, Creative Director.                    │
│                                                             │
│                                                             │
│                         ╔═══╗                               │
│                         ║   ║                               │
│                         ║ 🎤 ║  ← Glowing microphone        │
│                         ║   ║     (pulsing animation)       │
│                         ╚═══╝                               │
│                                                             │
│                  (Animated glow rings)                      │
│                                                             │
│           Click the mic and say "Let's get started"         │
│                                                             │
│                                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Image Generation Prompt
```
A modern, minimalist web application welcome screen with a dark gradient background
(deep navy to black). Large, elegant typography displaying "Welcome, Creative Director."
in a clean sans-serif font (similar to Inter or SF Pro). Center of screen features
a large, glowing microphone icon with concentric pulsing rings of blue light
(#3b82f6). The microphone should have a subtle 3D effect with soft shadows.
Below the microphone, smaller text reads "Click the mic and say 'Let's get started'".
Overall aesthetic: sleek, professional, futuristic, with Tokyo neon-inspired accent
colors (electric blue, purple). UI should feel premium and AI-focused.
```

### Design Specifications
- **Background**: Linear gradient from `#0f172a` (top) to `#020617` (bottom)
- **Headline**: 48px, font-weight 700, color `#f8fafc`, letter-spacing -0.02em
- **Microphone Icon**: 120px diameter, `#3b82f6` fill, drop-shadow: 0 0 40px rgba(59, 130, 246, 0.6)
- **Glow Rings**: 3 concentric circles, animated expanding fade-out, 2s loop
- **CTA Text**: 16px, font-weight 400, color `#cbd5e1`
- **Spacing**: Vertical center alignment with 80px gaps

---

## Screen 2: Main Workspace Layout

### ASCII Wireframe
**Example 1: Footwear Product (Aura Smart Sneaker)**
```
┌────────────────────────────────────────────────────────────────────────┐
│  Welcome, Creative Director                              [Show API]    │
├──────────────────┬─────────────────────────────────────────────────────┤
│                  │                                                     │
│ PROJECT BRIEF    │              WORKSPACE                              │
│ ───────────────  │                                                     │
│                  │  ┌─────────────────────────────────────────┐       │
│ Aura Smart       │  │                                         │       │
│ Sneaker          │  │        [Asset Display Area]             │       │
│ [Footwear]       │  │                                         │       │
│ Tokyo Neon       │  │   - Strategy outputs                    │       │
│ Futuristic       │  │   - Image gallery (4-up)                │       │
│                  │  │   - Video player                        │       │
│ CAMPAIGN PLAN    │  │   - Audio players                       │       │
│ ✓ Strategy       │  │   - Code + Preview                      │       │
│ ⟳ Art Director   │  │                                         │       │
│ ○ Video          │  └─────────────────────────────────────────┘       │
│ ○ Audio          │                                                     │
│ ○ Web Dev        │                                                     │
│                  │          [Thinking Animation]                       │
│ PERSONAS (3)     │              • • •                                  │
│ • Tech Runner    │                                                     │
│ • Night Jogger   │                                                     │
│ • Tracker User   │                                                     │
│                  │                                                     │
│ SLOGANS (5)      │                                                     │
│ 1. Run Free      │                                                     │
│ 2. Light Steps   │                                                     │
│ ✓ 3. Run on light│                                                     │
│ 4. Night Runner  │                                                     │
│ 5. Glow Forward  │                                                     │
├──────────────────┴─────────────────────────────────────────────────────┤
│                          ╔═══════════╗                                 │
│                          ║    🎤     ║  ← Persistent Microphone        │
│                          ╚═══════════╝                                 │
│                         "Listening..."                                 │
└────────────────────────────────────────────────────────────────────────┘
```

**Example 2: Beverage Product (Ember Energy Drink)**
```
┌────────────────────────────────────────────────────────────────────────┐
│  Welcome, Creative Director                              [Show API]    │
├──────────────────┬─────────────────────────────────────────────────────┤
│                  │                                                     │
│ PROJECT BRIEF    │              WORKSPACE                              │
│ ───────────────  │                                                     │
│                  │  ┌─────────────────────────────────────────┐       │
│ Ember Energy     │  │                                         │       │
│ Drink            │  │        [Asset Display Area]             │       │
│ [Beverage]       │  │                                         │       │
│ Volcanic Energy  │  │   - Strategy outputs                    │       │
│ Edgy             │  │   - Image gallery (4-up)                │       │
│                  │  │   - Video player                        │       │
│ CAMPAIGN PLAN    │  │   - Audio players                       │       │
│ ✓ Strategy       │  │   - Code + Preview                      │       │
│ ⟳ Art Director   │  │                                         │       │
│ ○ Video          │  └─────────────────────────────────────────┘       │
│ ○ Audio          │                                                     │
│ ○ Web Dev        │                                                     │
│                  │          [Thinking Animation]                       │
│ PERSONAS (3)     │              • • •                                  │
│ • Gamer Pro      │                                                     │
│ • Athlete        │                                                     │
│ • Night Shifter  │                                                     │
│                  │                                                     │
│ SLOGANS (5)      │                                                     │
│ 1. Fuel the Fire │                                                     │
│ ✓ 2. Ignite Power│                                                     │
│ 3. Volcanic Rush │                                                     │
│ 4. Pure Energy   │                                                     │
│ 5. Ember Within  │                                                     │
├──────────────────┴─────────────────────────────────────────────────────┤
│                          ╔═══════════╗                                 │
│                          ║    🎤     ║  ← Persistent Microphone        │
│                          ╚═══════════╝                                 │
│                         "Listening..."                                 │
└────────────────────────────────────────────────────────────────────────┘
```

**Example 3: Electronics Product (Nova Smart Home Hub)**
```
┌────────────────────────────────────────────────────────────────────────┐
│  Welcome, Creative Director                              [Show API]    │
├──────────────────┬─────────────────────────────────────────────────────┤
│                  │                                                     │
│ PROJECT BRIEF    │              WORKSPACE                              │
│ ───────────────  │                                                     │
│                  │  ┌─────────────────────────────────────────┐       │
│ Nova Smart       │  │                                         │       │
│ Home Hub         │  │        [Asset Display Area]             │       │
│ [Electronics]    │  │                                         │       │
│ Ambient Intel    │  │   - Strategy outputs                    │       │
│ Professional     │  │   - Image gallery (4-up)                │       │
│                  │  │   - Video player                        │       │
│ CAMPAIGN PLAN    │  │   - Audio players                       │       │
│ ✓ Strategy       │  │   - Code + Preview                      │       │
│ ⟳ Art Director   │  │                                         │       │
│ ○ Video          │  └─────────────────────────────────────────┘       │
│ ○ Audio          │                                                     │
│ ○ Web Dev        │                                                     │
│                  │          [Thinking Animation]                       │
│ PERSONAS (3)     │              • • •                                  │
│ • Tech Parent    │                                                     │
│ • Smart Homeowner│                                                     │
│ • Early Adopter  │                                                     │
│                  │                                                     │
│ SLOGANS (5)      │                                                     │
│ 1. Home, Smarter │                                                     │
│ 2. Think Ahead   │                                                     │
│ ✓ 3. Intelligence│                                                     │
│    at Home       │                                                     │
│ 4. Nova Light    │                                                     │
│ 5. Future Living │                                                     │
├──────────────────┴─────────────────────────────────────────────────────┤
│                          ╔═══════════╗                                 │
│                          ║    🎤     ║  ← Persistent Microphone        │
│                          ╚═══════════╝                                 │
│                         "Listening..."                                 │
└────────────────────────────────────────────────────────────────────────┘
```

### Image Generation Prompt
```
A professional web application interface showing a creative AI workspace.
Left sidebar (25% width) contains a "Project Brief" panel with dark background
(#1e293b), showing hierarchical information: product name "Aura Smart Sneaker",
theme badge "Tokyo Neon", campaign plan with checkmarks and loading indicators,
3 customer personas, 5 slogans (one highlighted with checkmark), and asset tracker.
Main workspace area (75% width) shows a large content display area with dark
card background. Bottom footer contains a large, glowing microphone icon
centered with "Listening..." text below. Color scheme: dark navy background,
electric blue accents (#3b82f6), purple highlights, white text. Modern,
clean UI with cards, subtle shadows, and smooth gradients. Status indicators
use colors: completed (green), in-progress (blue rotating), pending (gray).
```

### Design Specifications

**Left Sidebar (Project Brief Panel)**
- Width: 320px (fixed)
- Background: `#1e293b`
- Padding: 24px
- Border-right: 1px solid `#334155`

**Product Header**
- Product name: 24px, font-weight 700, color `#f8fafc`
- Theme badge: 12px, padding 4px 12px, background `#3b82f6`, border-radius 12px

**Campaign Plan**
- Section title: 14px, font-weight 600, color `#94a3b8`, uppercase
- Phase items: 14px, font-weight 400, color `#cbd5e1`
- Icons: ✓ (green), ⟳ (blue, rotating), ○ (gray)

**Main Workspace**
- Background: `#0f172a`
- Content cards: background `#1e293b`, border-radius 12px, padding 32px

**Persistent Microphone**
- Container: 160px width, centered
- Icon: 80px diameter, glowing effect
- States: idle (pulsing glow), listening (active pulse), thinking (dots animation)

---

## Screen 3: Image Gallery (4-up Grid)

### ASCII Wireframe
```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Art Director - Hero Images                                 │
│  ───────────────────────────────────────────────────────    │
│                                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │                     │  │                     │          │
│  │                     │  │    ✓ SELECTED       │          │
│  │    Image 1          │  │    Image 2          │          │
│  │                     │  │                     │          │
│  │                     │  │  (Glowing border)   │          │
│  └─────────────────────┘  └─────────────────────┘          │
│                                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │                     │  │                     │          │
│  │                     │  │                     │          │
│  │    Image 3          │  │    Image 4          │          │
│  │                     │  │                     │          │
│  │                     │  │                     │          │
│  └─────────────────────┘  └─────────────────────┘          │
│                                                             │
│  Select your preferred hero image                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Image Generation Prompt
```
A 2x2 grid gallery interface showing 4 AI-generated images of futuristic smart
sneakers with glowing soles in Tokyo neon night settings. Each image in a card
with subtle border and rounded corners. Top-right image has a bright blue
glowing border (#3b82f6) and a checkmark badge, indicating selection. Each card
shows "Image 1", "Image 2", etc. labels. Dark background (#0f172a), cards have
dark navy background (#1e293b). Below grid: "Select your preferred hero image"
in light gray text. Professional, modern UI design with hover effects implied.
```

### Design Specifications
- **Grid**: 2x2, gap 24px
- **Card**: background `#1e293b`, border-radius 12px, border 2px solid `#334155`
- **Selected Card**: border color `#3b82f6`, box-shadow: 0 0 24px rgba(59, 130, 246, 0.4)
- **Checkmark Badge**: Absolute position top-right, 32px circle, background `#3b82f6`
- **Image**: object-fit cover, aspect-ratio 16/9
- **Label**: 14px, font-weight 500, color `#94a3b8`, position bottom-left overlay

---

## Screen 4: Split-Screen Code Preview

### ASCII Wireframe
```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  Web Dev Agent - Landing Page                                       │
│  ─────────────────────────────────────────────────────────────      │
│                                                                     │
│  ┌──────────────────────────┬──────────────────────────┐           │
│  │  CODE                    │  LIVE PREVIEW            │           │
│  │  ────                    │  ────────────            │           │
│  │                          │                          │           │
│  │  [HTML] [CSS] [JS]       │  ┌──────────────────┐   │           │
│  │                          │  │                  │   │           │
│  │  <!DOCTYPE html>         │  │  AURA SNEAKER    │   │           │
│  │  <html>                  │  │                  │   │           │
│  │    <head>                │  │  Run on light    │   │           │
│  │      <style>             │  │                  │   │           │
│  │        body {            │  │  [Hero Image]    │   │           │
│  │          background:     │  │                  │   │           │
│  │            linear-...    │  │  Coming Soon     │   │           │
│  │        }                 │  │                  │   │           │
│  │      </style>            │  │  [Email Signup]  │   │           │
│  │    </head>               │  │                  │   │           │
│  │    <body>                │  └──────────────────┘   │           │
│  │      <h1>Aura</h1>       │                          │           │
│  │      ...                 │                          │           │
│  │                          │                          │           │
│  │                          │                          │           │
│  │                          │                          │           │
│  └──────────────────────────┴──────────────────────────┘           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Image Generation Prompt
```
A split-screen interface showing code editor on the left and live preview on the
right. Left side: dark code editor (VSCode-style) with HTML code visible, syntax
highlighting (keywords in blue, tags in purple, strings in green), line numbers,
tab navigation showing "HTML", "CSS", "JS" tabs. Right side: live rendered webpage
preview showing a modern landing page with "AURA SNEAKER" title, "Run on light"
slogan, hero image of glowing sneaker, "Coming Soon" text, and email signup form.
Preview has neon blue and purple color scheme. Dark theme throughout (#0f172a
background), professional code editor aesthetic, clear 50/50 split.
```

### Design Specifications

**Split Container**
- Display: grid, grid-template-columns: 1fr 1fr
- Gap: 2px (divider line)

**Code Panel**
- Background: `#1e1e1e` (darker for contrast)
- Font: 'Fira Code' or 'JetBrains Mono', 14px
- Line height: 1.6
- Syntax highlighting: VSCode Dark+ theme colors

**Preview Panel**
- Background: `#0f172a`
- iframe: width 100%, height 100%, border none
- Scale: 1.0 (actual size) or 0.8 (fit to view)

**Tab Navigation**
- Height: 40px, background `#252526`
- Active tab: `#1e1e1e`, border-bottom 2px solid `#3b82f6`
- Inactive tab: `#2d2d2d`, color `#858585`

---

## Screen 5: Thinking Animation States

### ASCII Wireframe
```
State 1: Idle (Glowing)
    ╔═══╗
    ║   ║
    ║ 🎤 ║  ← Slow pulsing glow
    ║   ║     (2s cycle)
    ╚═══╝
  "Click to speak"


State 2: Listening (Active Pulse)
    ╔═══╗
    ║   ║
    ║ 🎤 ║  ← Fast pulsing
    ║   ║     Audio waveform
    ╚═══╝
   "Listening..."


State 3: Thinking (Bouncing Dots)
    ╔═══╗
    ║   ║
    ║ 🎤 ║
    ║   ║
    ╚═══╝

    • • •  ← Bouncing animation
              (staggered delay)
   "Thinking..."


State 4: Speaking (Waveform)
    ╔═══╗
    ║   ║
    ║ 🎤 ║
    ║   ║
    ╚═══╝

   ▁▃▅▇▅▃▁  ← Audio waveform
              (animated)
   "Speaking..."
```

### Image Generation Prompts

**State 1 - Idle:**
```
A minimalist microphone icon with a gentle glowing effect. Center-aligned circular
microphone (80px) in electric blue (#3b82f6) against dark background (#0f172a).
Soft concentric glow rings emanating outward, semi-transparent. Below the icon,
light gray text "Click to speak". Peaceful, inviting aesthetic.
```

**State 2 - Listening:**
```
Same microphone icon but with active pulsing animation suggested by stronger glow.
Small animated waveform bars beneath the icon showing audio input levels. Text below
reads "Listening..." in electric blue. More energetic feel than idle state.
```

**State 3 - Thinking:**
```
Microphone icon with three dots beneath it in a row (• • •), suggesting loading/
thinking. Middle dot slightly elevated to show bounce animation state. Text below
reads "Thinking..." in light gray. Professional waiting state indicator.
```

**State 4 - Speaking:**
```
Microphone icon with animated audio waveform visualization beneath it, showing
varying heights of bars representing voice output. Text below reads "Speaking..."
in electric blue. Dynamic, active state visualization.
```

---

## Component Library Specifications

### Colors (Tailwind CSS)
```css
--background-dark: #020617      /* slate-950 */
--background-navy: #0f172a      /* slate-900 */
--surface: #1e293b              /* slate-800 */
--surface-hover: #334155        /* slate-700 */
--border: #475569               /* slate-600 */
--text-primary: #f8fafc         /* slate-50 */
--text-secondary: #cbd5e1       /* slate-300 */
--text-muted: #94a3b8           /* slate-400 */
--accent-blue: #3b82f6          /* blue-500 */
--accent-purple: #a855f7        /* purple-500 */
--accent-green: #10b981         /* emerald-500 */
--accent-orange: #f97316        /* orange-500 */
```

### Typography
```css
--font-display: 'Inter', -apple-system, sans-serif
--font-code: 'Fira Code', 'JetBrains Mono', monospace

/* Scale */
--text-xs: 12px
--text-sm: 14px
--text-base: 16px
--text-lg: 18px
--text-xl: 20px
--text-2xl: 24px
--text-3xl: 30px
--text-4xl: 36px
--text-5xl: 48px
```

### Spacing
```css
--space-xs: 4px
--space-sm: 8px
--space-md: 16px
--space-lg: 24px
--space-xl: 32px
--space-2xl: 48px
--space-3xl: 64px
```

### Animation Durations
```css
--duration-fast: 150ms
--duration-normal: 300ms
--duration-slow: 500ms
--duration-pulse: 2000ms
```

### Shadows
```css
--shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05)
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1)
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1)
--shadow-glow-blue: 0 0 24px rgba(59, 130, 246, 0.4)
--shadow-glow-purple: 0 0 24px rgba(168, 85, 247, 0.4)
```

---

## Key Interactions

### Microphone Interaction States
1. **Idle → Click** → Listening
2. **Listening → Voice detected** → Thinking
3. **Thinking → Response ready** → Speaking
4. **Speaking → Complete** → Idle

### Project Brief Updates
- **New item added**: Slide-in from left with fade
- **Item updated**: Pulse blue glow for 1s
- **Item completed**: Checkmark appears with bounce animation
- **Item in-progress**: Rotating spinner icon

### Asset Display
- **Asset loading**: Skeleton loader with shimmer effect
- **Asset ready**: Fade-in with scale up (0.95 → 1.0)
- **Asset selected**: Border glow + checkmark badge
- **Asset hover**: Slight scale up (1.0 → 1.02) + increased shadow

---

## Accessibility Considerations

- **Keyboard Navigation**: All interactive elements must be keyboard accessible
- **Screen Readers**: Proper ARIA labels for all components
- **Focus Indicators**: Visible focus rings (blue, 2px solid)
- **Color Contrast**: All text meets WCAG AA standards (4.5:1 minimum)
- **Motion Reduction**: Respect `prefers-reduced-motion` for animations
- **Audio Indicators**: Visual alternatives for all audio cues

---

## Responsive Breakpoints

```css
/* Mobile First */
--breakpoint-sm: 640px   /* Small devices */
--breakpoint-md: 768px   /* Tablets */
--breakpoint-lg: 1024px  /* Laptops */
--breakpoint-xl: 1280px  /* Desktops */
--breakpoint-2xl: 1536px /* Large screens */
```

**Mobile Adaptations:**
- Project Brief Panel: Collapsible drawer at bottom
- Workspace: Full width with stacked content
- Image Gallery: 1 column on mobile, 2 columns on tablet
- Code Preview: Tabbed view instead of split screen
