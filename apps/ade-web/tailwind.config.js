/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  // "dark" is a MODE, not a THEME
  darkMode: ["class", '[data-mode="dark"]'],
  theme: {
    extend: {
      colors: {
        // System semantics (what UI should use)
        background: "rgb(var(--sys-color-bg) / <alpha-value>)",
        foreground: "rgb(var(--sys-color-fg) / <alpha-value>)",

        card: "rgb(var(--sys-color-surface) / <alpha-value>)",
        "card-foreground": "rgb(var(--sys-color-fg) / <alpha-value>)",

        popover: "rgb(var(--sys-color-surface-elevated) / <alpha-value>)",
        "popover-foreground": "rgb(var(--sys-color-fg) / <alpha-value>)",

        muted: "rgb(var(--sys-color-surface-muted) / <alpha-value>)",
        "muted-foreground": "rgb(var(--sys-color-fg-muted) / <alpha-value>)",

        border: "rgb(var(--sys-color-border) / <alpha-value>)",
        "border-strong": "rgb(var(--sys-color-border-strong) / <alpha-value>)",

        ring: "rgb(var(--sys-color-ring) / <alpha-value>)",
        overlay: "rgb(var(--sys-color-overlay) / <alpha-value>)",
        shadow: "rgb(var(--sys-color-shadow) / <alpha-value>)",

        // Component surfaces
        terminal: "rgb(var(--comp-terminal-bg) / <alpha-value>)",
        "terminal-foreground": "rgb(var(--comp-terminal-fg) / <alpha-value>)",
        "terminal-muted": "rgb(var(--comp-terminal-muted) / <alpha-value>)",
        "terminal-border": "rgb(var(--comp-terminal-border) / <alpha-value>)",

        // Reference ramps (exposed for charts, data viz, etc)
        brand: {
          50: "rgb(var(--ref-accent-50) / <alpha-value>)",
          100: "rgb(var(--ref-accent-100) / <alpha-value>)",
          200: "rgb(var(--ref-accent-200) / <alpha-value>)",
          300: "rgb(var(--ref-accent-300) / <alpha-value>)",
          400: "rgb(var(--ref-accent-400) / <alpha-value>)",
          500: "rgb(var(--ref-accent-500) / <alpha-value>)",
          600: "rgb(var(--ref-accent-600) / <alpha-value>)",
          700: "rgb(var(--ref-accent-700) / <alpha-value>)",
          800: "rgb(var(--ref-accent-800) / <alpha-value>)",
          900: "rgb(var(--ref-accent-900) / <alpha-value>)",
        },

        success: {
          50: "rgb(var(--ref-success-50) / <alpha-value>)",
          100: "rgb(var(--ref-success-100) / <alpha-value>)",
          200: "rgb(var(--ref-success-200) / <alpha-value>)",
          300: "rgb(var(--ref-success-300) / <alpha-value>)",
          400: "rgb(var(--ref-success-400) / <alpha-value>)",
          500: "rgb(var(--ref-success-500) / <alpha-value>)",
          600: "rgb(var(--ref-success-600) / <alpha-value>)",
          700: "rgb(var(--ref-success-700) / <alpha-value>)",
          800: "rgb(var(--ref-success-800) / <alpha-value>)",
          900: "rgb(var(--ref-success-900) / <alpha-value>)",
        },

        warning: {
          50: "rgb(var(--ref-warning-50) / <alpha-value>)",
          100: "rgb(var(--ref-warning-100) / <alpha-value>)",
          200: "rgb(var(--ref-warning-200) / <alpha-value>)",
          300: "rgb(var(--ref-warning-300) / <alpha-value>)",
          400: "rgb(var(--ref-warning-400) / <alpha-value>)",
          500: "rgb(var(--ref-warning-500) / <alpha-value>)",
          600: "rgb(var(--ref-warning-600) / <alpha-value>)",
          700: "rgb(var(--ref-warning-700) / <alpha-value>)",
          800: "rgb(var(--ref-warning-800) / <alpha-value>)",
          900: "rgb(var(--ref-warning-900) / <alpha-value>)",
        },

        danger: {
          50: "rgb(var(--ref-danger-50) / <alpha-value>)",
          100: "rgb(var(--ref-danger-100) / <alpha-value>)",
          200: "rgb(var(--ref-danger-200) / <alpha-value>)",
          300: "rgb(var(--ref-danger-300) / <alpha-value>)",
          400: "rgb(var(--ref-danger-400) / <alpha-value>)",
          500: "rgb(var(--ref-danger-500) / <alpha-value>)",
          600: "rgb(var(--ref-danger-600) / <alpha-value>)",
          700: "rgb(var(--ref-danger-700) / <alpha-value>)",
          800: "rgb(var(--ref-danger-800) / <alpha-value>)",
          900: "rgb(var(--ref-danger-900) / <alpha-value>)",
        },

        info: {
          50: "rgb(var(--ref-info-50) / <alpha-value>)",
          100: "rgb(var(--ref-info-100) / <alpha-value>)",
          200: "rgb(var(--ref-info-200) / <alpha-value>)",
          300: "rgb(var(--ref-info-300) / <alpha-value>)",
          400: "rgb(var(--ref-info-400) / <alpha-value>)",
          500: "rgb(var(--ref-info-500) / <alpha-value>)",
          600: "rgb(var(--ref-info-600) / <alpha-value>)",
          700: "rgb(var(--ref-info-700) / <alpha-value>)",
          800: "rgb(var(--ref-info-800) / <alpha-value>)",
          900: "rgb(var(--ref-info-900) / <alpha-value>)",
        },

        // Semantic "on-*" tokens (useful for badges/buttons)
        "on-brand": "rgb(var(--sys-color-on-accent) / <alpha-value>)",
        "on-success": "rgb(var(--sys-color-on-success) / <alpha-value>)",
        "on-warning": "rgb(var(--sys-color-on-warning) / <alpha-value>)",
        "on-danger": "rgb(var(--sys-color-on-danger) / <alpha-value>)",
        "on-info": "rgb(var(--sys-color-on-info) / <alpha-value>)",

        filetype: {
          json: "rgb(var(--comp-file-json) / <alpha-value>)",
          py: "rgb(var(--comp-file-py) / <alpha-value>)",
          ts: "rgb(var(--comp-file-ts) / <alpha-value>)",
          tsx: "rgb(var(--comp-file-tsx) / <alpha-value>)",
          js: "rgb(var(--comp-file-js) / <alpha-value>)",
          jsx: "rgb(var(--comp-file-jsx) / <alpha-value>)",
          md: "rgb(var(--comp-file-md) / <alpha-value>)",
          env: "rgb(var(--comp-file-env) / <alpha-value>)",
          txt: "rgb(var(--comp-file-txt) / <alpha-value>)",
          lock: "rgb(var(--comp-file-lock) / <alpha-value>)",
        },
      },
      boxShadow: {
        soft: "0 20px 45px -25px rgb(var(--sys-color-shadow) / 0.45)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
