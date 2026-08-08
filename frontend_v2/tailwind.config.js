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
        // PwC consulting palette (replaces V1's prudential red accent)
        pwc: {
          orange: "#D04A02", // primary accent (was red-600)
          orangeDark: "#B23A00", // hover
          tangerine: "#EB8C00", // secondary highlight
          yellow: "#FFB600", // tertiary highlight
          rose: "#E0301E", // alerts / critical
          charcoal: "#2D2D2D", // sidebar background
          charcoalDark: "#1F1F1F" // sidebar deep / borders
        }
      },
      boxShadow: {
        executive: "0 18px 45px rgba(31, 31, 31, 0.10)"
      },
      keyframes: {
        "pulse-dot": {
          "0%, 100%": { opacity: "0.3" },
          "50%": { opacity: "1" }
        }
      },
      animation: {
        "pulse-dot": "pulse-dot 1.2s ease-in-out infinite"
      }
    }
  },
  plugins: []
};
