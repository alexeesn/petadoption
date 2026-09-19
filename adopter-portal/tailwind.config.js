/** @type {import('tailwindcss').Config} */

// Pawnscape design tokens (adopter portal)
//  ink  – deep navy used for text, primary actions and the brand mark
//  tag  – collar-tag yellow, reserved for the main call to action and small highlights
//  mist – cool blue-grey neutrals so pet photos (warm) pop against the page
const ink = {
  50: '#EEF3FA',
  100: '#DCE6F4',
  200: '#BCCDE8',
  300: '#93AED6',
  400: '#6588BE',
  500: '#3F65A3',
  600: '#2B4A82',
  700: '#22396A',
  800: '#1B2D54',
  900: '#141F3B',
}

const mist = {
  50: '#F7F9FC',
  100: '#EEF2F7',
  200: '#DFE5ED',
  300: '#C7D0DC',
  400: '#98A4B6',
  500: '#6C788C',
  600: '#515D72',
  700: '#3C465A',
  800: '#2A3348',
  900: '#1C2438',
  950: '#0F1626',
}

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: ink,
        // Pages were written with the `stone` / `slate` neutrals; pointing them at
        // the new tokens restyles every page consistently.
        stone: mist,
        slate: mist,
        accent: {
          50: '#FFF9E5',
          100: '#FFF0BF',
          200: '#FFE38F',
          300: '#FFD666',
          400: '#FFC93C',
          500: '#F2B01E',
          600: '#C98C0E',
          700: '#9A6A0C',
          800: '#6F4C0F',
          900: '#4A3410',
        },
      },
      fontFamily: {
        sans: ['Figtree', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        display: ['"Bricolage Grotesque"', 'Figtree', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        md: '0.625rem',
        lg: '0.875rem',
        xl: '1.25rem',
        '2xl': '1.75rem',
      },
      boxShadow: {
        sm: '0 1px 2px rgba(28, 36, 56, 0.06)',
        DEFAULT: '0 1px 3px rgba(28, 36, 56, 0.08), 0 1px 2px rgba(28, 36, 56, 0.05)',
        md: '0 6px 16px -4px rgba(28, 36, 56, 0.12)',
        lg: '0 16px 32px -8px rgba(28, 36, 56, 0.16)',
      },
    },
  },
  plugins: [],
}
