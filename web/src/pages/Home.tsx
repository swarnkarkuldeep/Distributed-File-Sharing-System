import { Aurora, Glass } from "../components/Glass";

const POPUP = "popup,width=720,height=900";

function RoleLink({ to, name, label }: { to: string; name: string; label: string }) {
  return (
    <a
      className="btn btn--primary"
      href={to}
      target="_blank"
      rel="noreferrer"
      onClick={(e) => {
        // Open a sized popup so the two windows can sit side by side; fall back to the plain link if blocked.
        if (window.open(to, name, POPUP)) e.preventDefault();
      }}
    >
      {label}
    </a>
  );
}

export function Home() {
  return (
    <div className="stage">
      <Aurora />
      <main className="window">
        <header>
          <h1 className="title">Chunkway</h1>
          <p className="subtitle">Share a file in one window. Watch it arrive, chunk by chunk, in the other.</p>
        </header>

        <div className="launch">
          <Glass className="launch__card" data-tone="uploader">
            <div className="stack">
              <h2 className="glass__title">Uploader</h2>
              <p className="subtitle">Drop files to share them, see who asks for what, and corrupt a chunk on purpose.</p>
            </div>
            <RoleLink to="/uploader" name="p2p-uploader" label="Open the uploader window" />
          </Glass>

          <Glass className="launch__card" data-tone="downloader">
            <div className="stack">
              <h2 className="glass__title">Downloader</h2>
              <p className="subtitle">Connect to a peer, download a file, and watch every chunk get hash-checked.</p>
            </div>
            <RoleLink to="/downloader" name="p2p-downloader" label="Open the downloader window" />
          </Glass>
        </div>

        <p className="label">
          Tip: put the uploader on the left half of your screen and the downloader on the right. Want a second peer?{" "}
          <a href="/uploader2">Open uploader 2</a>.
        </p>
      </main>
    </div>
  );
}
