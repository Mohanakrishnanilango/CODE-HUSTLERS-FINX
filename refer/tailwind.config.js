/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        marine: {
          950: '#060B14',
          900: '#0B132B',
          850: '#0F1A3A',
          800: '#1C2541',
          700: '#2A3B66',
          600: '#3A506B',
          500: '#5B7898',
          400: '#7F9CB8',
          300: '#A4BFD8',
          200: '#CCE0F0',
          100: '#E5F1FC',
        },
        sonar: {
          cyan: '#00F0FF',
          green: '#00FF66',
          amber: '#FFB800',
          red: '#FF3366',
          purple: '#B026FF',
          blue: '#00A3FF'
        }
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Courier New', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'sonar-cyan': '0 0 15px rgba(0, 240, 255, 0.25)',
        'sonar-green': '0 0 15px rgba(0, 255, 102, 0.25)',
        'sonar-amber': '0 0 15px rgba(255, 184, 0, 0.25)',
      }
    },
  },
  plugins: [],
}
