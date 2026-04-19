import { createRoot } from "react-dom/client";
import App from "./app/App.tsx";
import "./styles/index.css";
import AOS from "aos";
import "aos/dist/aos.css";

AOS.init({
  duration: 600,
  easing: "ease-out-cubic",
  once: true,
  offset: 60,
});

createRoot(document.getElementById("root")!).render(<App />);
