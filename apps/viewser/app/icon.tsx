import { ImageResponse } from "next/og";

// Genererad favicon (ersätter webbläsarens generiska jordglob i fliken).
// On-brand monogram: off-white "S" på nära-svart kvadrat, samma värden som
// --foreground/--background-tokens (oklch konverterat till hex för Satori).
export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#1a1a1a",
        color: "#f7f6f2",
        fontSize: 22,
        fontWeight: 700,
        borderRadius: 7,
      }}
    >
      S
    </div>,
    { ...size },
  );
}
