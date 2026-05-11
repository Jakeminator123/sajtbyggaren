"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

/**
 * Analytics Tracker Component
 *
 * Records page views when the user navigates to different pages.
 * Include this component in your root layout to track all page visits.
 */
export function AnalyticsTracker() {
  const pathname = usePathname();

  useEffect(() => {
    // Don't track admin pages or API routes
    if (pathname.startsWith("/admin") || pathname.startsWith("/api")) {
      return;
    }

    // Record the page view
    const trackPageView = async () => {
      try {
        await fetch("/api/analytics", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            path: pathname,
            referrer: document.referrer || null,
          }),
        });
      } catch {
        // Silently fail - don't interrupt user experience
      }
    };

    trackPageView();
  }, [pathname]);

  // This component doesn't render anything
  return null;
}
