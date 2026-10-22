import { Link, Route, Routes } from "react-router-dom";
import { Aurora, Glass } from "./components/Glass";
import { Downloader } from "./pages/Downloader";
import { Home } from "./pages/Home";
import { Uploader } from "./pages/Uploader";

function NotFound() {
  return (
    <div className="stage">
      <Aurora />
      <main className="window">
        <Glass>
          <div className="stack">
            <h1 className="glass__title">That page doesn't exist.</h1>
            <Link className="btn" to="/">
              Back to start
            </Link>
          </div>
        </Glass>
      </main>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/uploader" element={<Uploader node="uploader" />} />
      <Route path="/uploader2" element={<Uploader node="uploader2" />} />
      <Route path="/downloader" element={<Downloader />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
