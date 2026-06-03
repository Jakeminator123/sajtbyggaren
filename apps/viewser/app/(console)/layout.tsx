import type { Metadata } from "next";

// Operatörskonsolen ska aldrig indexeras publikt — den är localhost-bunden
// och dess API:er 403:ar i produktion. noindex/nofollow här gäller hela
// (console)-route-gruppen (/studio). Ingen marknads-chrome (header/footer/
// cookie-banner) ska wrappa konsolen, så denna layout är medvetet en ren
// pass-through; rot-layouten levererar html/body/Providers.
export const metadata: Metadata = {
  title: "Studio",
  robots: { index: false, follow: false },
};

export default function ConsoleLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return children;
}
