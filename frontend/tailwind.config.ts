import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        app: {
          bg: "#000000",
          panel: "#121212",
          border: "#282828",
          text: "#FFFFFF",
          muted: "#A7A7A7",
          green: "#1ED760",
        },
        sentiment: {
          positive: "#1ED760",
          negative: "#E91429",
          neutral: "#71717A",
          mixed: "#FACC15",
        },
        spotify: {
          green: "#1ED760",
          black: "#000000",
          gray: "#121212",
          panel: "#121212",
          border: "#282828",
          text: "#FFFFFF",
          muted: "#A7A7A7",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        display: ["Plus Jakarta Sans", "Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
