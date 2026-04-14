import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#1a1d26",
          raised: "#20232f",
          overlay: "#252836",
        },
        border: {
          DEFAULT: "#2a2d3a",
          strong: "#3a3d4e",
        },
        text: {
          primary: "#e8eaf0",
          secondary: "#8b8fa8",
          muted: "#5a5d72",
        },
        ev: {
          positive: "#22c55e",
          "positive-muted": "#16a34a20",
          neutral: "#eab308",
          negative: "#ef4444",
          "negative-muted": "#dc262620",
        },
        accent: "#3b82f6",
        "accent-muted": "#3b82f620",
        steam: "#f97316",
        elite: "#a855f7",
        high: "#3b82f6",
        standard: "#22c55e",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      fontSize: {
        "2xs": ["0.65rem", { lineHeight: "1rem" }],
      },
    },
  },
  plugins: [],
};

export default config;
