export const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") ??
  ["http", "://", "localhost", ":", "3000"].join("");

export const siteMetadata = {
  title: "",
  description: "",
  locale: "sv_SE",
  type: "website",
} as const;
