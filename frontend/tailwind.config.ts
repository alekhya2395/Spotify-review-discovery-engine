import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Spotify-inspired palette
        spotify: {
          green: "#1DB954",
          black: "#0a0a0a",
          gray: "#181818",
          panel: "#1f1f1f",
          border: "#2a2a2a",
          text: "#e8e8e8",
          muted: "#8a8a8a",
        },
      },
      fontFamily: {
        sans: ["system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
