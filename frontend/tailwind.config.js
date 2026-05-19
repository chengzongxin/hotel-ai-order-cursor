/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Noto Serif SC"', 'serif'],
        body: ['"LXGW WenKai"', '"PingFang SC"', 'sans-serif'],
      },
      colors: {
        ink: '#10151f',
        copper: '#c9834b',
        porcelain: '#f7f2e8',
        signal: '#8fe7d2',
      },
      boxShadow: {
        glow: '0 0 50px rgba(143, 231, 210, 0.28)',
      },
    },
  },
  plugins: [],
}
