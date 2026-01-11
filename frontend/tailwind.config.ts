import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Dark mode color palette
        dark: {
          bg: "#0f0f0f",
          surface: "#1a1a1a",
          border: "#2a2a2a",
          hover: "#333333",
          text: "#e5e5e5",
          muted: "#888888",
        },
        // Article color coding
        article: {
          blue: "#6B7FD7",
          green: "#5BA37C",
          orange: "#D4915D",
          purple: "#9B7FC7",
          red: "#D46A6A",
          gray: "#6B7280",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
