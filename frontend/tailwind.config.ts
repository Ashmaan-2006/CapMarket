import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172026",
        paper: "#f7f8f5",
        line: "#d9ded8",
        positive: "#147d64",
        negative: "#b42318",
        accent: "#285c7a"
      }
    }
  },
  plugins: []
};

export default config;

