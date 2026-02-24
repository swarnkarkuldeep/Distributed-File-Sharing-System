# Distributed File Sharing System (Python)

A robust **peer-to-peer file sharing** implementation demonstrating advanced systems concepts with production-ready features.

## 🎯 Core Concepts

- **Networking**: Custom TCP socket protocol with JSON messaging
- **Operating Systems**: Efficient chunked I/O with threaded peer service
- **Security & Integrity**: Dual-layer SHA-256 hash verification (per-chunk and end-to-end)
- **Distributed Architecture**: True peer-to-peer design without central dependencies

## ✨ Key Features

- **🌐 Peer-to-peer architecture**: Each node can serve files directly to other peers
- **📦 Chunk-based transfer**: Large files split into configurable fixed-size chunks (default 256 KiB)
- **🔒 Hash verification**: 
  - Per-chunk SHA-256 validation on every received chunk
  - End-to-end file hash validation after reassembly
- **⚡ Concurrent operations**: Threaded server handling multiple clients simultaneously
- **🛡️ Data integrity**: Automatic corruption detection and prevention
- **📝 Simple CLI**: Intuitive command-line interface for serving, listing, and downloading
- **🔧 Configurable**: Adjustable chunk sizes, ports, and network interfaces

## 🚀 Advantages

### Performance Benefits
- **Parallel downloads**: Chunk-based architecture enables concurrent chunk transfers
- **Memory efficient**: Streams chunks without loading entire files into memory
- **Network optimized**: Configurable chunk size adapts to different network conditions
- **Scalable**: Handles files of any size through chunking

### Reliability & Security
- **Data integrity**: Dual hash verification prevents corrupted downloads
- **Fault tolerance**: Failed chunks can be re-downloaded independently
- **Tamper detection**: Any modification is immediately detected via hash mismatch
- **Secure identification**: Files identified by cryptographic SHA-256 hashes

### Architecture Benefits
- **Decentralized**: No single point of failure
- **Lightweight**: Minimal dependencies, pure Python implementation
- **Cross-platform**: Works on Windows, Linux, and macOS
- **Extensible**: Clean protocol design easy to extend with new features

## 📋 Requirements

- Python 3.10 or higher
- No external dependencies (pure Python standard library)

## 🏃‍♂️ Quick Start

### 1. Setup Directories
```bash
mkdir shared downloads
echo "Hello, distributed world!" > shared/example.txt
```

### 2. Start Server (Terminal 1)
```bash
python -m p2p_share.cli serve ./shared --host 0.0.0.0 --port 9000
```

### 3. Client Operations (Terminal 2)
```bash
# List available files
python -m p2p_share.cli list 127.0.0.1:9000

# Download a file (replace with actual file_id from list command)
python -m p2p_share.cli download 127.0.0.1:9000 ca26fb2c1dad349a506f07d9340556edb6b70f8beeb36dbd11207f810787223c ./downloads/downloaded_file.txt
```

## 🔧 Advanced Usage

### Custom Configuration
```bash
# Custom port and chunk size
python -m p2p_share.cli serve ./shared --host 0.0.0.0 --port 8080 --chunk-size 524288

# Serve from different directory
python -m p2p_share.cli serve /path/to/files --host 192.168.1.100 --port 9000
```

### Multiple Peers
You can run multiple servers on different ports/machines to create a true distributed network:
```bash
# Peer 1
python -m p2p_share.cli serve ./shared1 --port 9000

# Peer 2  
python -m p2p_share.cli serve ./shared2 --port 9001

# Clients can connect to any peer
python -m p2p_share.cli list 192.168.1.100:9000
python -m p2p_share.cli list 192.168.1.101:9001
```

## 📡 Protocol Specification

Messages are JSON-over-TCP (newline-delimited) with the following request/response types:

| Request | Response | Description |
|---------|----------|-------------|
| `GET_CATALOG` | `CATALOG` | Lists all available files with metadata |
| `GET_MANIFEST` | `MANIFEST` | Gets chunk manifest for a specific file |
| `GET_CHUNK` | `CHUNK` | Downloads a specific chunk by index |
| `REFRESH` | `REFRESHED` | Refreshes server's file catalog |

### Message Format
- **Chunks**: Serialized as base64 in JSON for transport simplicity
- **File IDs**: SHA-256 hash of the complete file content
- **Chunk Hashes**: SHA-256 hash of each individual chunk

## 🧪 Testing

Run the test suite to verify functionality:
```bash
python -m pytest tests/ -v
```

## 📊 Performance Characteristics

- **Chunk Size**: 256 KiB default (configurable)
- **Hash Algorithm**: SHA-256 (cryptographically secure)
- **Concurrent Connections**: Limited only by system resources
- **Memory Usage**: O(chunk_size) regardless of file size
- **Network Efficiency**: Minimal overhead with JSON+base64 encoding

## 🔍 Technical Details

### File Identification
Each file is uniquely identified by its SHA-256 hash, ensuring:
- Content-based addressing (same content = same ID)
- Automatic deduplication
- Tamper evidence

### Chunk Verification
Every chunk is verified independently:
- Prevents corruption propagation
- Enables resume/pause functionality
- Supports parallel chunk downloads

### Error Handling
- Connection failures are gracefully handled
- Corrupted chunks are detected and rejected
- Network timeouts prevent hanging operations
