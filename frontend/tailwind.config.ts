import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // PoE2-derived dark palette (inspired, not copied).
        ink: {
          950: "#0b0b0d",
          900: "#121216",
          800: "#1a1a20",
          700: "#23232b",
          600: "#2d2d36",
          500: "#3a3a46",
        },
        parchment: {
          50: "#f4ecd8",
          100: "#e9dcb7",
          200: "#d9c48b",
        },
        ember: {
          400: "#f0b44c",
          500: "#c8a040",
          600: "#9a7a28",
        },
        rarity: {
          normal: "#c8c8c8",
          magic: "#8888ff",
          rare: "#ffff77",
          unique: "#af6025",
          currency: "#aa9e82",
          quest: "#4ae63a",
          gem: "#1ba29b",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["'Cinzel'", "serif"],
      },
      boxShadow: {
        pane: "0 4px 24px rgba(0,0,0,0.5)",
      },
    },
  },
  plugins: [],
} satisfies Config;
