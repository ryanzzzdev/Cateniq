import { useEffect, useState } from "react";
import { fetchHealth } from "./api";

export function App() {
  const [health, setHealth] = useState<string>("checking");

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then((h) => setHealth(h.status))
      .catch(() => setHealth("unavailable"));
    return () => controller.abort();
  }, []);

  return (
    <main className="shell">
      <h1>Cateniq</h1>
      <p>Spatial QA workbench — development shell.</p>
      <p>
        api: <output data-testid="api-status">{health}</output>
      </p>
    </main>
  );
}
