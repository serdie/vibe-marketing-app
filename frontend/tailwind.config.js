/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      colors: {
        brand: {
          50: '#eef6ff',
          100: '#d9eaff',
          200: '#b6d6ff',
          300: '#85bcff',
          400: '#4f9bff',
          500: '#2a7af6',
          600: '#1a5dd8',
          700: '#1849ad',
          800: '#19408a',
          900: '#19386f',
        },
      },
    },
  },
  plugins: [],
}
