from __future__ import annotations

import argparse
from pathlib import Path

from .client import P2PClient
from .peer import P2PPeerServer
from .gui import launch_gui


def parse_peer(value: str) -> tuple[str, int]:
    host, _, port = value.partition(":")
    if not host or not port:
        raise argparse.ArgumentTypeError("peer must be in host:port format")
    return host, int(port)


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
    client = P2PClient(host, port)
    output = Path(args.output)
    target = client.download(args.file_id, output)
    print(f"Downloaded to {target}")



def cmd_gui(args: argparse.Namespace) -> None:
    launch_gui()

def main() -> None:
    parser = argparse.ArgumentParser(description="Distributed File Sharing System (P2P)")
    sub = parser.add_subparsers(required=True)

    serve = sub.add_parser("serve", help="Serve files from a local directory")
    serve.add_argument("share_dir")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", default=9000, type=int)
    serve.add_argument("--chunk-size", default=256 * 1024, type=int)
    serve.set_defaults(func=cmd_serve)

    listing = sub.add_parser("list", help="List files shared by a peer")
    listing.add_argument("peer", help="host:port")
    listing.set_defaults(func=cmd_list)

    download = sub.add_parser("download", help="Download file from peer by file_id")
    download.add_argument("peer", help="host:port")
    download.add_argument("file_id")
    download.add_argument("output", help="path to save downloaded file")
    download.set_defaults(func=cmd_download)

    gui = sub.add_parser("gui", help="Launch a minimal desktop GUI")
    gui.set_defaults(func=cmd_gui)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
