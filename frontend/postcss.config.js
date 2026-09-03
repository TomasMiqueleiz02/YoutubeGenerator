// Without this file Vite never runs Tailwind, so every utility class in the
// components silently does nothing and the app renders as unstyled HTML.
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
