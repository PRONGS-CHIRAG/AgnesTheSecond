import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/app/**/*.{ts,tsx}", "./src/components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
      colors: {
        bg: {
          DEFAULT: "hsl(222 18% 6%)",
          card: "hsl(222 16% 9%)",
          muted: "hsl(222 15% 13%)",
        },
        border: {
          DEFAULT: "hsl(222 12% 18%)",
        },
        fg: {
          DEFAULT: "hsl(210 20% 96%)",
          muted: "hsl(215 15% 65%)",
          soft: "hsl(215 10% 75%)",
        },
        accent: {
          DEFAULT: "hsl(200 95% 60%)",
          soft: "hsl(200 80% 70%)",
        },
        good: {
          DEFAULT: "hsl(150 65% 50%)",
        },
        warn: {
          DEFAULT: "hsl(40 95% 60%)",
        },
        bad: {
          DEFAULT: "hsl(0 75% 60%)",
        },
      },
      boxShadow: {
        card: "0 1px 0 0 hsl(222 12% 18%), 0 8px 24px -12px hsl(222 40% 2% / 0.6)",
      },
    },
  },
  plugins: [],
};

export default config;
