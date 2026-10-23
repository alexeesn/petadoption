/** @type {import('tailwindcss').Config} */
const shades = [50,100,200,300,400,500,600,700,800,900,950]
const scale = name => Object.fromEntries(shades.map(shade => [shade, `rgb(var(--${name}-${shade}) / <alpha-value>)`]))
export default {
  content: { relative: true, files: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'] },
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: { extend: {
    colors: {
      primary: scale('primary'), accent: scale('accent'),
      ...Object.fromEntries(['stone','slate','gray','zinc','neutral'].map(name => [name, scale('neutral')])),
      ...Object.fromEntries(['green','blue','sky','red','amber','purple','orange'].map(name => [name, scale(name)])),
      emerald: scale('green'), teal: scale('primary'), indigo: scale('primary'),
      canvas: 'rgb(var(--canvas) / <alpha-value>)', surface: 'rgb(var(--surface) / <alpha-value>)',
    },
    backgroundColor: {
      white: 'rgb(var(--surface) / <alpha-value>)',
      primary: {600: 'rgb(var(--action-bg) / <alpha-value>)',700: 'rgb(var(--action-bg) / <alpha-value>)',800: 'rgb(var(--action-hover) / <alpha-value>)',900: 'rgb(20 36 44 / <alpha-value>)'},
    },
    fontFamily: { sans: ['Figtree','Segoe UI','ui-sans-serif','system-ui','sans-serif'], display: ['Figtree','Segoe UI','ui-sans-serif','system-ui','sans-serif'] },
    borderRadius: { md: '.625rem', lg: '.875rem', xl: '1rem', '2xl': '1.25rem' },
    boxShadow: { sm: 'var(--canvas-shadow)', md: '0 8px 24px -16px rgb(20 35 50 / .2)', lg: '0 20px 50px -18px rgb(20 35 50 / .25)' },
  } }, plugins: [],
}
