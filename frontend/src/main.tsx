import { createRoot } from "react-dom/client";

import { App } from "./app/App";
import "./styles.css";

// NOTE: React.StrictMode is intentionally omitted. The experimental
// @assistant-ui/react-ag-ui streaming runtime applies run events in effects
// that are not idempotent under StrictMode's double-invoke (dev only), which
// surfaces every assistant reply as a phantom extra branch (e.g. "2/2"). The
// network layer is unaffected (one POST /ag-ui per send); this is purely a
// dev-mode rendering artifact. Production builds never double-invoke.
createRoot(document.getElementById("root")!).render(<App />);
