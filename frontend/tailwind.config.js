/** @type {import('tailwindcss').Config} */
// Colors are CSS variables (see src/index.css) so light/dark are each a
// deliberately chosen set rather than an automatic inversion.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["system-ui", "-apple-system", '"Segoe UI"', "Roboto", "sans-serif"] },
      colors: {
        plane: "var(--plane)",
        surface: "var(--surface)",
        raised: "var(--raised)",
        ink: { DEFAULT: "var(--ink)", 2: "var(--ink-2)", 3: "var(--ink-3)" },
        hair: "var(--hair)",
        accent: { DEFAULT: "var(--accent)", ink: "var(--accent-ink)", soft: "var(--accent-soft)" },
        good: { DEFAULT: "var(--good)", soft: "var(--good-soft)" },
        warn: { DEFAULT: "var(--warn)", soft: "var(--warn-soft)" },
        bad: { DEFAULT: "var(--bad)", soft: "var(--bad-soft)" },
      },
      boxShadow: { card: "0 1px 2px rgba(11,11,11,0.04), 0 0 0 1px var(--ring)" },
    },
  },
  plugins: [],
};
