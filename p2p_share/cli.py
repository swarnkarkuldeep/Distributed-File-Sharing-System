from __future__ import annotations

import argparse
from pathlib import Path

from .client import P2PClient, ProgressEvent
from .peer import P2PPeerServer


def parse_peer(value: str) -> tuple[str, int]:
    host, _, port = value.partition(":")
    if not host or not port:
        raise argparse.ArgumentTypeError("peer must be in host:port format")
    try:
        return host, int(port)
    except ValueError:
        raise argparse.ArgumentTypeError("peer port must be a number") from None


def cmd_serve(args: argparse.Namespace) -> None:
    server = P2PPeerServer(args.share_dir, host=args.host, port=args.port, chunk_size=args.chunk_size)
    server.start()


def cmd_list(args: argparse.Namespace) -> None:
    host, port = parse_peer(args.peer)
    client = P2PClient(host, port)
    files = client.list_files()
    if not files:
        print("No files available")
        return
    for entry in files:
        print(f"{entry['file_id']}\t{entry['file_name']}\t{entry['file_size']} bytes\tchunks={entry['chunk_count']}")


def cmd_download(args: argparse.Namespace) -> None:
    host, port = parse_peer(args.peer)
    client = P2PClient(host, port, connections=args.connections, retries=args.retries)

    def show(event: ProgressEvent) -> None:
        if event.kind in ("chunk_ok", "resumed"):
            percent = 100 * event.bytes_done // event.file_size if event.file_size else 100
            print(f"\r{event.file_name}: {percent}%", end="", flush=True)
        elif event.kind == "chunk_failed":
            print(f"\n{event.message}", flush=True)

    target = client.download(args.file_id, Path(args.output), on_progress=show)
    print(f"\nDownloaded to {target}")


def cmd_refresh(args: argparse.Namespace) -> None:
    host, port = parse_peer(args.peer)
    count = P2PClient(host, port).refresh()
    print(f"Peer now shares {count} files")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Distributed File Sharing System (P2P)")
    sub = parser.add_subparsers(required=True)

    serve = sub.add_parser("serve", help="Serve files from a local directory")
    serve.add_argument("share_dir")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", default=9000, type=int)
    serve.add_argument("--chunk-size", default=None, type=int,
                       help="fixed chunk size in bytes (default: chosen per file from its size)")
    serve.set_defaults(func=cmd_serve)

    listing = sub.add_parser("list", help="List files shared by a peer")
    listing.add_argument("peer", help="host:port")
    listing.set_defaults(func=cmd_list)

    download = sub.add_parser("download", help="Download file from peer by file_id")
    download.add_argument("peer", help="host:port")
    download.add_argument("file_id")
    download.add_argument("output", help="path to save downloaded file")
    download.add_argument("--connections", default=4, type=int, help="parallel connections")
    download.add_argument("--retries", default=3, type=int, help="retries per corrupted chunk")
    download.set_defaults(func=cmd_download)

    refresh = sub.add_parser("refresh", help="Ask a peer to rescan its shared directory")
    refresh.add_argument("peer", help="host:port")
    refresh.set_defaults(func=cmd_refresh)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
