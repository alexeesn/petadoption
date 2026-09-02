/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#fef7ee',
          100: '#fdedd3',
          200: '#fad6a5',
          300: '#f6b86d',
          400: '#f19033',
          500: '#ee7712',
          600: '#df5d08',
          700: '#b94509',
          800: '#93370e',
          900: '#772f0f',
        },
        warm: {
          50: '#fdf8f0',
          100: '#faeedd',
          200: '#f4d9b8',
          300: '#ecbe89',
          400: '#e29b58',
          500: '#db8237',
          600: '#cd6b2c',
          700: '#aa5325',
          800: '#884324',
          900: '#6f3820',
        },
      },
    },
  },
  plugins: [],
}
