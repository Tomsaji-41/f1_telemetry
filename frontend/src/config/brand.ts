/**
 * brand.ts — Single source of truth for the app brand.
 *
 * All components import from here. The logo path can be swapped
 * before any public launch. The assistant keeps its own name.
 */

import en from "@/content/en.json";

export const brand = {
  /** Display name of the application */
  appName: process.env.NEXT_PUBLIC_APP_NAME || "Telemetra",

  /** The AI assistant keeps a separate name */
  assistantName: process.env.NEXT_PUBLIC_ASSISTANT_NAME || "Pit Boss",

  /** Logo path (public directory, transparent PNG) */
  logo: "/brand/logo.png",

  /** Logo intrinsic dimensions (for next/image sizing) */
  logoWidth: 364,
  logoHeight: 111,
  logoRatio: 3.28,

  /** Favicon paths */
  favicon: "/brand/favicon.ico",

  /** Legal disclaimer (shown in footer on every page) */
  disclaimer:
    en?.footer?.disclaimer ||
    "Independent student project. Not affiliated with or endorsed by Formula 1 or any team. Formula 1 and the F1 logo are trademarks of their owners.",
} as const;

export type Brand = typeof brand;
