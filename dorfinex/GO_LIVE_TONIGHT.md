# Dorfinex Go-Live Checklist

This checklist is optimized for a same-night launch.

## 1) Prepare contact form (required)

The contact form now sends real POST requests.

1. Create a form endpoint (recommended: [Formspree](https://formspree.io/)).
2. Replace `https://formspree.io/f/your-form-id` in:
   - `contact.html`
3. Submit a test message from the live site and confirm you receive it.

## 2) Fast hosting option (recommended): Cloudflare Pages

1. Push this folder to a GitHub repo.
2. In Cloudflare Pages:
   - Create project from GitHub.
   - Build command: none
   - Output directory: `/` (root)
3. Deploy.

## 3) Connect your domain

In Cloudflare DNS (or your registrar DNS):

1. Add `CNAME` record:
   - `www` -> `<your-pages-project>.pages.dev`
2. For apex domain (`yourdomain.com`):
   - Use Cloudflare "Set as apex domain" in Pages (preferred), or
   - Use `A`/`ALIAS` according to your DNS provider's Pages guidance.
3. Enable HTTPS and force redirect:
   - `http://` -> `https://`
   - `yourdomain.com` -> `www.yourdomain.com` (or the reverse, pick one canonical host)

## 4) Final pre-launch QA (10 minutes)

1. Test pages:
   - Home, About, Services, Insights, FAQ, Contact, and 1-2 blog posts
2. Mobile checks:
   - Open/close nav menu
   - Contact form submit
3. Confirm:
   - No broken links
   - Loader disappears normally
   - Contact submission success message appears only after successful send

## 5) Post-launch (same night)

1. Add analytics (GA4 or Plausible).
2. Submit domain in Google Search Console.
3. Add:
   - `sitemap.xml`
   - `robots.txt`

