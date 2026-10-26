import { createRoot } from "react-dom/client";
import { AutoTech } from "./components/auto/auto-tech";

const root = document.getElementById("root");
if (root) createRoot(root).render(<AutoTech />);
