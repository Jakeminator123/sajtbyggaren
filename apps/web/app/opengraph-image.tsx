import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Sajtbyggaren – AI-driven webbplatsgenerering";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #0a0a0a 0%, #111827 50%, #0a0a0a 100%)",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div
          style={{
            position: "absolute",
            display: "flex",
            top: 0,
            left: 0,
            right: 0,
            height: 4,
            background: "linear-gradient(90deg, #14b8a6, #3b82f6, #f59e0b, #14b8a6)",
          }}
        />

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 20,
            marginBottom: 40,
          }}
        >
          <svg
            width="56"
            height="56"
            viewBox="0 0 40 40"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <circle cx="20" cy="20" r="18" stroke="#3b82f6" strokeWidth="2" fill="none" />
            <g transform="translate(20 21) rotate(-25)">
              <path
                d="M0 -10 C3 -7 5 -3 5 2 C5 9 2 13 0 15 C-2 13 -5 9 -5 2 C-5 -3 -3 -7 0 -10 Z"
                stroke="#3b82f6"
                strokeWidth="2"
                fill="none"
              />
              <circle cx="0" cy="2" r="2" stroke="#f43f5e" strokeWidth="1.5" fill="none" />
              <path
                d="M-5 6 L-9 9 L-5 11"
                stroke="#3b82f6"
                strokeWidth="2"
                fill="none"
              />
              <path
                d="M5 6 L9 9 L5 11"
                stroke="#3b82f6"
                strokeWidth="2"
                fill="none"
              />
            </g>
          </svg>
          <span
            style={{
              fontSize: 48,
              fontWeight: 700,
              color: "#ffffff",
              letterSpacing: "-0.03em",
            }}
          >
            Sajtbyggaren
          </span>
        </div>

        <div
          style={{
            fontSize: 28,
            color: "rgba(255,255,255,0.7)",
            textAlign: "center",
            maxWidth: 700,
            lineHeight: 1.4,
          }}
        >
          AI-driven webbplatsgenerering.
          <br />
          Skapa professionella webbplatser på minuter.
        </div>

        <div
          style={{
            display: "flex",
            gap: 32,
            marginTop: 48,
          }}
        >
          {["Analyserad", "Kategori", "Audit", "Fritext"].map((label) => (
            <div
              key={label}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "10px 24px",
                borderRadius: 12,
                border: "1px solid rgba(255,255,255,0.12)",
                background: "rgba(255,255,255,0.04)",
                color: "rgba(255,255,255,0.6)",
                fontSize: 16,
                fontWeight: 500,
              }}
            >
              {label}
            </div>
          ))}
        </div>

        <div
          style={{
            position: "absolute",
            bottom: 32,
            display: "flex",
            alignItems: "center",
            gap: 8,
            color: "rgba(255,255,255,0.35)",
            fontSize: 14,
          }}
        >
          En tjänst från Pretty Good AB
        </div>
      </div>
    ),
    { ...size },
  );
}
