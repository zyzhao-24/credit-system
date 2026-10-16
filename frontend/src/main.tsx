import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { Toaster } from "sonner";
import "./index.css";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
        <Toaster richColors position="top-center" />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
