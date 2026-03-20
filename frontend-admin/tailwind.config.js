export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: { 500: '#6366f1', 600: '#4f46e5' },
        dark: { 700: '#334155', 800: '#1e293b', 900: '#0f111a' }
      }
    }
  },
  plugins: []
}
