/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        prudential: {
          red: "#d71920",
          dark: "#1f2933"
        }
      },
      boxShadow: {
        executive: "0 18px 45px rgba(15, 23, 42, 0.10)"
      }
    }
  },
  plugins: []
};
