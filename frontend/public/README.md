# Public Assets Directory

This directory contains static assets that are served directly by Next.js.

## Usage

Place static files here that should be accessible at the root URL path:

- `public/favicon.ico` → `/favicon.ico`
- `public/logo.png` → `/logo.png`
- `public/robots.txt` → `/robots.txt`

## Common Files

Typical files you might add:

- `favicon.ico` - Browser favicon
- `robots.txt` - Search engine instructions
- `sitemap.xml` - Site structure for SEO
- `manifest.json` - PWA manifest
- Images, fonts, and other static assets

## Important Notes

- Files in this directory are served at the root path
- Do not use the `/public` prefix when referencing these files in code
- This directory is required for Next.js Docker builds
- Keep this directory even if empty (use `.gitkeep`)

## Example

```jsx
// Correct way to reference public assets
<Image src="/logo.png" alt="Logo" />

// Wrong - don't include /public
<Image src="/public/logo.png" alt="Logo" />
```
