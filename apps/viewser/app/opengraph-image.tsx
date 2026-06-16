import { ImageResponse } from "next/og";

// Genererad delningsbild (Open Graph / Twitter) för länkförhandsvisningar.
// Tidigare saknades helt → länkar delades utan bild. On-brand: varm off-white
// bakgrund, nära-svart ordmärke och tagline, hårfin ram likt marknadssajten.
export const alt = "Sajtbyggaren — din hemsida, byggd med AI";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        background: "#f7f6f2",
        color: "#1a1a1a",
        padding: "96px",
      }}
    >
      <div
        style={{
          fontSize: 26,
          letterSpacing: 2,
          textTransform: "uppercase",
          color: "#8a8a8a",
          fontWeight: 600,
        }}
      >
        Sajtbyggaren
      </div>
      <div
        style={{
          display: "flex",
          marginTop: 28,
          fontSize: 84,
          fontWeight: 700,
          lineHeight: 1.05,
          letterSpacing: -2,
          maxWidth: 900,
        }}
      >
        Din hemsida, byggd med AI.
      </div>
      <div
        style={{
          display: "flex",
          marginTop: 28,
          fontSize: 34,
          color: "#52525b",
          maxWidth: 820,
          lineHeight: 1.3,
        }}
      >
        Beskriv din verksamhet — vi bygger en färdig företagshemsida åt dig.
      </div>
    </div>,
    { ...size },
  );
}
