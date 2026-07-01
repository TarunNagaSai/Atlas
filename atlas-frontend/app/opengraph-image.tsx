import { ImageResponse } from "next/og";

export const runtime = "nodejs";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OGImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 1200,
          height: 630,
          background: "#0d1117",
          display: "flex",
          flexDirection: "column",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Radial glow top-left */}
        <div
          style={{
            position: "absolute",
            top: -120,
            left: -80,
            width: 600,
            height: 600,
            borderRadius: "50%",
            background:
              "radial-gradient(circle, rgba(4,120,87,0.30) 0%, transparent 70%)",
            display: "flex",
          }}
        />

        {/* Radial glow bottom-right */}
        <div
          style={{
            position: "absolute",
            bottom: -160,
            right: -100,
            width: 520,
            height: 520,
            borderRadius: "50%",
            background:
              "radial-gradient(circle, rgba(4,120,87,0.18) 0%, transparent 70%)",
            display: "flex",
          }}
        />

        {/* Content */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            padding: "56px 64px",
            height: "100%",
            position: "relative",
          }}
        >
          {/* Top: Logo + wordmark */}
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: 12,
                background: "#047857",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <svg
                width={26}
                height={26}
                viewBox="0 0 24 24"
                fill="none"
                stroke="white"
                strokeWidth={2.4}
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
                <polyline points="16 7 22 7 22 13" />
              </svg>
            </div>
            <span
              style={{
                fontSize: 28,
                fontWeight: 700,
                color: "#f0fdf4",
                letterSpacing: "-0.5px",
              }}
            >
              Atlas
            </span>
          </div>

          {/* Center: Main copy */}
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div
                style={{
                  height: 3,
                  width: 40,
                  background: "#10b981",
                  borderRadius: 2,
                  display: "flex",
                }}
              />
              <span
                style={{
                  fontSize: 16,
                  color: "#10b981",
                  fontWeight: 600,
                  letterSpacing: "2px",
                  textTransform: "uppercase",
                }}
              >
                Financial Research Copilot
              </span>
            </div>

            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 4,
              }}
            >
              <span
                style={{
                  fontSize: 72,
                  fontWeight: 800,
                  color: "#f9fafb",
                  letterSpacing: "-3px",
                  lineHeight: 1,
                }}
              >
                Research faster.
              </span>
              <span
                style={{
                  fontSize: 72,
                  fontWeight: 800,
                  color: "#10b981",
                  letterSpacing: "-3px",
                  lineHeight: 1,
                }}
              >
                Think deeper.
              </span>
            </div>

            <span
              style={{
                fontSize: 22,
                color: "#9ca3af",
                lineHeight: 1.5,
                maxWidth: 640,
              }}
            >
              Agentic RAG over filings, contracts, and reports — GraphRAG,
              hybrid search, and grounded citations.
            </span>
          </div>

          {/* Bottom: Feature pills */}
          <div style={{ display: "flex", gap: 12 }}>
            {[
              "Agentic RAG",
              "GraphRAG",
              "Hybrid Search",
              "LLM-as-a-Judge",
              "SSE Streaming",
            ].map((label) => (
              <div
                key={label}
                style={{
                  padding: "8px 18px",
                  borderRadius: 999,
                  border: "1px solid rgba(16,185,129,0.3)",
                  background: "rgba(16,185,129,0.08)",
                  fontSize: 14,
                  color: "#6ee7b7",
                  fontWeight: 600,
                  display: "flex",
                  alignItems: "center",
                }}
              >
                {label}
              </div>
            ))}
          </div>
        </div>
      </div>
    ),
    { ...size }
  );
}
