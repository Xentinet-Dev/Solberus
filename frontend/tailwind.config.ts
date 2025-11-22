import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: "#0a0a0f",
          secondary: "#12121a",
          tertiary: "#1a1a24",
          hover: "#1f1f2e",
        },
        accent: {
          primary: "#00d4ff",
          secondary: "#7b2cbf",
          success: "#00ff88",
          warning: "#ffb800",
          danger: "#ff3366",
        },
        text: {
          primary: "#ffffff",
          secondary: "#b0b0b0",
          muted: "#6b6b7a",
        },
        border: "#2a2a3a",
      },
      fontFamily: {
        sans: ["'Segoe UI'", "system-ui", "sans-serif"],
        mono: ["Consolas", "Monaco", "monospace"],
      },
      fontSize: {
        xs: ["12px", { lineHeight: "16px", letterSpacing: "0.05em" }],
        sm: ["14px", { lineHeight: "20px" }],
        base: ["16px", { lineHeight: "24px" }],
        lg: ["18px", { lineHeight: "28px" }],
        xl: ["20px", { lineHeight: "28px" }],
        "2xl": ["24px", { lineHeight: "32px" }],
        "3xl": ["30px", { lineHeight: "36px" }],
      },
      backdropBlur: {
        md: "10px",
      },
      boxShadow: {
        neon: "0 0 12px rgba(0,212,255,0.4)",
        danger: "0 0 12px rgba(255,51,102,0.5)",
        success: "0 0 12px rgba(0,255,136,0.5)",
      },
      transitionTimingFunction: {
        smooth: "cubic-bezier(0.4, 0.0, 0.2, 1)",
      },
      animation: {
        "fade-in": "fadeIn 0.3s ease-in-out",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(-10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      // Tailwind CSS v3.4+ animate-in utilities
      // These are provided by tailwindcss-animate plugin or custom CSS
    },
  },
  plugins: [],
};

export default config;

