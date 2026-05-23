from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .client import P2PClient
from .peer import P2PPeerServer


class P2PGuiApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Distributed File Sharing")
        self.root.geometry("860x520")
        self.root.minsize(760, 460)

        self.server: P2PPeerServer | None = None
        self.server_thread: threading.Thread | None = None

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = ttk.Frame(self.root, padding=(16, 12))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="Distributed File Sharing", font=("TkDefaultFont", 16, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(header, textvariable=self.status_var).grid(row=0, column=1, sticky="e")

        body = ttk.Frame(self.root, padding=(16, 0, 16, 16))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        self._build_server_panel(body)
        self._build_client_panel(body)

    def _build_server_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.LabelFrame(parent, text="Serve Files", padding=12)
        panel.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 8))
        panel.columnconfigure(1, weight=1)

        self.share_dir_var = tk.StringVar(value=str(Path("shared").resolve()))
        self.host_var = tk.StringVar(value="0.0.0.0")
        self.port_var = tk.StringVar(value="9000")
        self.chunk_var = tk.StringVar(value=str(256 * 1024))

        ttk.Label(panel, text="Share Directory").grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(panel, textvariable=self.share_dir_var).grid(row=1, column=0, columnspan=2, sticky="ew")
        ttk.Button(panel, text="Browse", command=self._choose_share_dir).grid(row=1, column=2, padx=(8, 0))

        ttk.Label(panel, text="Host").grid(row=2, column=0, sticky="w", pady=(12, 4))
        ttk.Entry(panel, textvariable=self.host_var, width=16).grid(row=3, column=0, sticky="w")

        ttk.Label(panel, text="Port").grid(row=2, column=1, sticky="w", pady=(12, 4))
        ttk.Entry(panel, textvariable=self.port_var, width=10).grid(row=3, column=1, sticky="w")

        ttk.Label(panel, text="Chunk Size (bytes)").grid(row=4, column=0, sticky="w", pady=(12, 4))
        ttk.Entry(panel, textvariable=self.chunk_var, width=16).grid(row=5, column=0, sticky="w")

        controls = ttk.Frame(panel)
        controls.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(16, 0))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)

        self.start_btn = ttk.Button(controls, text="Start Server", command=self.start_server)
        self.start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.stop_btn = ttk.Button(controls, text="Stop", command=self.stop_server, state="disabled")
        self.stop_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.server_log = tk.Text(panel, height=12, wrap="word", state="disabled")
        self.server_log.grid(row=7, column=0, columnspan=3, sticky="nsew", pady=(12, 0))
        panel.rowconfigure(7, weight=1)

    def _build_client_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.LabelFrame(parent, text="Browse & Download", padding=12)
        panel.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(8, 0))
        panel.columnconfigure(1, weight=1)
        panel.rowconfigure(4, weight=1)

        self.peer_var = tk.StringVar(value="127.0.0.1:9000")
        self.download_path_var = tk.StringVar(value=str(Path("downloads").resolve()))

        ttk.Label(panel, text="Peer (host:port)").grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(panel, textvariable=self.peer_var).grid(row=1, column=0, columnspan=2, sticky="ew")
        ttk.Button(panel, text="Refresh List", command=self.refresh_catalog).grid(row=1, column=2, padx=(8, 0))

        ttk.Label(panel, text="Download Folder").grid(row=2, column=0, sticky="w", pady=(12, 4))
        ttk.Entry(panel, textvariable=self.download_path_var).grid(row=3, column=0, columnspan=2, sticky="ew")
        ttk.Button(panel, text="Browse", command=self._choose_download_dir).grid(row=3, column=2, padx=(8, 0))

        columns = ("file_name", "file_size", "chunk_count", "file_id")
        self.tree = ttk.Treeview(panel, columns=columns, show="headings", height=10)
        self.tree.heading("file_name", text="File")
        self.tree.heading("file_size", text="Size (bytes)")
        self.tree.heading("chunk_count", text="Chunks")
        self.tree.heading("file_id", text="File ID")
        self.tree.column("file_name", width=170)
        self.tree.column("file_size", width=90, anchor="e")
        self.tree.column("chunk_count", width=70, anchor="e")
        self.tree.column("file_id", width=280)
        self.tree.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(12, 0))

        ttk.Button(panel, text="Download Selected", command=self.download_selected).grid(
            row=5, column=0, columnspan=3, sticky="ew", pady=(12, 0)
        )

    def _choose_share_dir(self) -> None:
        picked = filedialog.askdirectory(initialdir=self.share_dir_var.get() or ".")
        if picked:
            self.share_dir_var.set(picked)

    def _choose_download_dir(self) -> None:
        picked = filedialog.askdirectory(initialdir=self.download_path_var.get() or ".")
        if picked:
            self.download_path_var.set(picked)

    def _append_log(self, text: str) -> None:
        self.server_log.configure(state="normal")
        self.server_log.insert("end", f"{text}\n")
        self.server_log.see("end")
        self.server_log.configure(state="disabled")

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def start_server(self) -> None:
        if self.server_thread and self.server_thread.is_alive():
            return

        try:
            port = int(self.port_var.get())
            chunk_size = int(self.chunk_var.get())
            share_dir = Path(self.share_dir_var.get())
            share_dir.mkdir(parents=True, exist_ok=True)
            self.server = P2PPeerServer(share_dir, host=self.host_var.get(), port=port, chunk_size=chunk_size)
        except ValueError:
            messagebox.showerror("Invalid configuration", "Port and chunk size must be integers.")
            return
        except OSError as exc:
            messagebox.showerror("Unable to start server", str(exc))
            return

        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._set_status(f"Serving on {self.host_var.get()}:{self.port_var.get()}")
        self._append_log("Server starting…")

    def _run_server(self) -> None:
        assert self.server is not None
        try:
            self.server.start()
        except OSError as exc:
            self.root.after(0, lambda: self._append_log(f"Server stopped: {exc}"))
            self.root.after(0, lambda: messagebox.showerror("Server error", str(exc)))
        finally:
            self.root.after(0, self._server_stopped_ui)

    def _server_stopped_ui(self) -> None:
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._set_status("Ready")

    def stop_server(self) -> None:
        if self.server:
            self.server.stop()
            self._append_log("Stop signal sent.")
        self._server_stopped_ui()

    def _client(self) -> P2PClient:
        host, sep, port_text = self.peer_var.get().strip().partition(":")
        if not sep:
            raise ValueError("Peer must be in host:port format")
        return P2PClient(host, int(port_text))

    def refresh_catalog(self) -> None:
        try:
            files = self._client().list_files()
        except Exception as exc:
            messagebox.showerror("Unable to fetch catalog", str(exc))
            return

        self.tree.delete(*self.tree.get_children())
        for entry in files:
            self.tree.insert(
                "",
                "end",
                values=(entry["file_name"], entry["file_size"], entry["chunk_count"], entry["file_id"]),
            )
        self._set_status(f"Loaded {len(files)} file(s)")

    def download_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("No file selected", "Select a file from the list first.")
            return

        values = self.tree.item(selected[0], "values")
        file_name, _, _, file_id = values
        destination = Path(self.download_path_var.get()) / file_name

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            self._client().download(file_id, destination)
        except Exception as exc:
            messagebox.showerror("Download failed", str(exc))
            return

        self._set_status(f"Downloaded {file_name}")
        messagebox.showinfo("Download complete", f"Saved to:\n{destination}")

    def _on_close(self) -> None:
        self.stop_server()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def launch_gui() -> None:
    app = P2PGuiApp()
    app.run()
