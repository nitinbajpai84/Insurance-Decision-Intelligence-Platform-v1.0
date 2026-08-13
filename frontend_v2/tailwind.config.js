/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./services/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        // Signature palette: deep indigo + gold, tuned for an executive
        // decision-intelligence product rather than a consulting deck.
        brand: {
          orange: "#3454D1", // primary accent
          orangeDark: "#25399A", // hover
          tangerine: "#D97706", // secondary highlight (warm gold)
          yellow: "#F5A623", // tertiary highlight (light gold)
          rose: "#DC2626", // alerts / critical
          charcoal: "#0F172A", // sidebar background (deep navy)
          charcoalDark: "#0A0F1E" // sidebar deep / borders
        }
      },
      backgroundImage: {
        "brand-radial": "radial-gradient(circle at top left, rgba(52,84,209,0.16), transparent 55%)",
        "brand-hero": "linear-gradient(135deg, #0F172A 0%, #16213E 55%, #1B2A5C 100%)",
        "brand-sidebar": "linear-gradient(180deg, #0F172A 0%, #0B1330 100%)"
      },
      boxShadow: {
        executive: "0 18px 45px rgba(15, 23, 42, 0.10)",
        glow: "0 8px 30px rgba(52, 84, 209, 0.25)",
        card: "0 1px 2px rgba(15,23,42,0.04), 0 8px 24px rgba(15,23,42,0.06)"
      },
      keyframes: {
        "pulse-dot": {
          "0%, 100%": { opacity: "0.3" },
          "50%": { opacity: "1" }
        },
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" }
        }
      },
      animation: {
        "pulse-dot": "pulse-dot 1.2s ease-in-out infinite",
        "fade-in-up": "fade-in-up 0.35s ease-out"
      }
    }
  },
  plugins: []
};
