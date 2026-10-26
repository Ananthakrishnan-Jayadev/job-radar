import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The build goes straight into the Python package, where `jobradar serve`
// serves it. There is no separate dev server: one terminal, one address.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../jobradar/web/static",
    emptyOutDir: true,
  },
});
