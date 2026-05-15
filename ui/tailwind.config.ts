import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "var(--brand)",
          2: "var(--brand-2)",
          soft: "var(--brand-soft)",
          border: "var(--brand-border)",
        },
        bg: "var(--bg)",
        surface: {
          DEFAULT: "var(--surface)",
          2: "var(--surface-2)",
        },
        border: {
          DEFAULT: "var(--border)",
          strong: "var(--border-strong)",
        },
        text: {
          DEFAULT: "var(--text)",
          2: "var(--text-2)",
          3: "var(--text-3)",
          4: "var(--text-4)",
        },
        success: {
          DEFAULT: "var(--success)",
          soft: "var(--success-soft)",
        },
        conf: {
          high: "var(--conf-high)",
          medium: "var(--conf-medium)",
          low: "var(--conf-low)",
          none: "var(--conf-none)",
        },
      },
      fontFamily: {
        sans: ["Inter", "Pretendard Variable", "Pretendard", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Menlo", "monospace"],
      },
      boxShadow: {
        sm: "0 1px 2px rgb(0 0 0 / 0.04)",
        md: "0 4px 12px rgb(0 0 0 / 0.06)",
        lg: "0 12px 32px rgb(0 0 0 / 0.12)",
      },
      borderRadius: {
        xl: "0.875rem",
      },
    },
  },
  plugins: [],
};

export default config;
