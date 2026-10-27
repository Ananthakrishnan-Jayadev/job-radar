import "@fontsource-variable/instrument-sans";
import { MotionConfig } from "motion/react";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AppProvider } from "./state";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* "user": animations follow the system's reduced-motion setting. */}
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <AppProvider>
          <App />
        </AppProvider>
      </BrowserRouter>
    </MotionConfig>
  </StrictMode>,
);
