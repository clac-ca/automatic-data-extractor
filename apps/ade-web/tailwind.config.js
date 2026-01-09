/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      boxShadow: {
        soft: "0 20px 45px -25px rgb(0 0 0 / 0.45)",
      },
    },
  },
  plugins: [],
};
