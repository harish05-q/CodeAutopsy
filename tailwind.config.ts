import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#f4f1e8",
        ink: "#20241f",
        ember: "#e85d3f",
        acid: "#d9ee68",
        mint: "#8bd3bd",
        peach: "#f4b183",
      },
      boxShadow: {
        plate: "0 14px 35px rgba(54, 50, 39, .10)",
      },
    },
  },
  plugins: [],
} satisfies Config;
