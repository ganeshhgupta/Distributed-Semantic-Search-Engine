/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: "#6366f1",       // indigo-500
        surface: "#ffffff",       // white
        background: "#f8fafc",    // slate-50
        "text-primary": "#0f172a",  // slate-900
        "text-secondary": "#64748b", // slate-500
        "worker-1": "#3b82f6",    // blue-500
        "worker-2": "#10b981",    // emerald-500
        "worker-3": "#f97316",    // orange-500
        danger: "#ef4444",        // red-500
        warning: "#fbbf24",       // amber-400
        success: "#10b981",       // emerald-500
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        card: "12px",
        pill: "999px",
      },
      keyframes: {
        blob: {
          "0%, 100%": { transform: "translate(0, 0) scale(1)" },
          "33%": { transform: "translate(30px, -20px) scale(1.05)" },
          "66%": { transform: "translate(-20px, 20px) scale(0.97)" },
        },
      },
      animation: {
        blob: "blob 20s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
