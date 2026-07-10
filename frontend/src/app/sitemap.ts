import type { MetadataRoute } from "next";
import { publicIndexableRoutes, siteUrl } from "@/lib/seo";

const routePriority: Record<string, number> = {
  "/": 1,
  "/register": 0.9,
  "/subscription": 0.85,
  "/resources": 0.8,
  "/contact": 0.5,
};

const routeChangeFrequency: Record<
  string,
  "always" | "hourly" | "daily" | "weekly" | "monthly" | "yearly" | "never"
> = {
  "/": "weekly",
  "/register": "monthly",
  "/subscription": "weekly",
  "/resources": "weekly",
  "/contact": "monthly",
};

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();

  return publicIndexableRoutes.map((route) => ({
    url: `${siteUrl}${route}`,
    lastModified,
    changeFrequency: routeChangeFrequency[route] || "monthly",
    priority: routePriority[route] || 0.5,
  }));
}
