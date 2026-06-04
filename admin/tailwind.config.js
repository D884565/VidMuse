/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#165DFF',
        success: '#00B42A',
        warning: '#FF7D00',
        danger: '#F53F3F',
        gray: {
          50: '#F5F7FA',
          100: '#E5E6EB',
          200: '#C9CDD4',
          300: '#86909C',
          400: '#4E5969',
          500: '#1D2129',
        }
      },
      fontFamily: {
        inter: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
