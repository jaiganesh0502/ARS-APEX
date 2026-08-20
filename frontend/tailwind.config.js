/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Deep Charcoal — overrides default slate-900 so text-slate-900
        // matches the "Text" role exactly.
        slate: {
          900: '#172033',
        },
        // Brand palette: Clinical Red family.
        //   50  = Soft Accent (#FDECEC)
        //   500 = Accent / Coral Red (#EF4444)
        //   600 = Primary / Clinical Red (#C62828)
        //   800 = Primary Dark / Deep Red (#8E1B1B)
        primary: {
          50: '#FDECEC',
          100: '#FBD9D9',
          200: '#F7B3B3',
          300: '#F08989',
          400: '#F55F5F',
          500: '#EF4444',
          600: '#C62828',
          700: '#A82424',
          800: '#8E1B1B',
          900: '#6B1414',
          950: '#450D0D',
        },
      },
    },
  },
  plugins: [],
}
