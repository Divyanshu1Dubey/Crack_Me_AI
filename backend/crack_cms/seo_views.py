"""SEO utility views: robots.txt, and future sitemap.xml support."""
from django.http import HttpResponse
from django.conf import settings


def robots_txt(request):
    """Serve robots.txt that:
    - Allows all public pages
    - Blocks /dashboard/, /api/, /admin/
    - Points to the sitemap at /sitemap.xml
    - Explicitly allows major AI crawlers for GEO (ChatGPT, Claude, Perplexity, etc.)
    """
    base = (settings.FRONTEND_URL or 'https://cracklabs.app').rstrip('/')
    sitemap_url = f"{base}/sitemap.xml"

    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /api/",
        "Disallow: /admin/",
        "Disallow: /dashboard/",
        "Disallow: /auth/",
        "Disallow: /reset-password",
        "Disallow: /forgot-password",
        "",
        "# AI crawlers — explicit allow for GEO",
        "User-agent: GPTBot",
        "Allow: /",
        "",
        "User-agent: ChatGPT-User",
        "Allow: /",
        "",
        "User-agent: Claude-Web",
        "Allow: /",
        "",
        "User-agent: ClaudeBot",
        "Allow: /",
        "",
        "User-agent: PerplexityBot",
        "Allow: /",
        "",
        "User-agent: Google-Extended",
        "Allow: /",
        "",
        "User-agent: cohere-ai",
        "Allow: /",
        "",
        "User-agent: ccbot",
        "Allow: /",
        "",
        f"Sitemap: {sitemap_url}",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")
