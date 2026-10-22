import { createRoot } from "react-dom/client";
import { MustangApp } from "./components/mustang/app";

const root = document.getElementById("root");
if (root) createRoot(root).render(<MustangApp />);
