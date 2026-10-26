import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";

try { document.documentElement.dataset.theme = localStorage.getItem("theme") ?? "dark"; } catch { /* standart: dark */ }

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
