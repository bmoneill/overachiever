"""
Standalone image compression service.

Listens on a local TCP port and accepts newline-delimited file paths.
Each received path is queued for compression. A bounded thread pool
processes the queue, ensuring no more than MAX_WORKERS images are
compressed concurrently.

Usage:
    python -m scripts.image_compressor          # uses defaults
    COMPRESSOR_PORT=9801 COMPRESSOR_WORKERS=2 python -m scripts.image_compressor

The companion helper (src/helpers/image_cache.py) can send paths to this
service instead of spawning ad-hoc threads.

Protocol (TCP, plain text):
    • Client connects and sends one or more file paths, each terminated
      by a newline (``\\n``).
    • The server responds with ``QUEUED <path>\\n`` for every path that
      was successfully enqueued, or ``ERROR <message>\\n`` if the path
      was rejected (e.g. file does not exist).
    • The client may close the connection at any time; the already-queued
      items will still be processed.
"""

import logging
import os
import queue
import selectors
import signal
import socket
import threading
from types import FrameType

from PIL import Image

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PORT: int = int(os.environ.get("COMPRESSOR_PORT", "9800"))
HOST: str = os.environ.get("COMPRESSOR_HOST", "127.0.0.1")

# Maximum number of images that can be compressed at the same time.
MAX_WORKERS: int = int(os.environ.get("COMPRESSOR_WORKERS", "4"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("image_compressor")

# ---------------------------------------------------------------------------
# Compression logic
# ---------------------------------------------------------------------------


def compress_image(image_path: str, quality: int = 70) -> None:
    """Resize and compress *image_path* in place."""
    with Image.open(image_path) as img:
        rgb_img = img.convert("RGB")
        ratio = img.width / img.height
        resized_img = rgb_img.resize((int(128 * ratio), 128))
        resized_img.save(image_path, "JPEG", optimize=True, quality=quality)


# ---------------------------------------------------------------------------
# Worker pool
# ---------------------------------------------------------------------------

# Unbounded queue – we never want the TCP handler to block on put().
work_queue: queue.Queue[str | None] = queue.Queue()


def _worker(worker_id: int) -> None:
    """Loop forever, pulling paths from *work_queue* and compressing them.

    A ``None`` sentinel causes the worker to exit cleanly.
    """
    log.info("Worker %d started.", worker_id)
    while True:
        path = work_queue.get()
        if path is None:
            log.info("Worker %d shutting down.", worker_id)
            work_queue.task_done()
            break
        try:
            log.info("Worker %d compressing: %s", worker_id, path)
            compress_image(path)
            log.info("Worker %d finished: %s", worker_id, path)
        except Exception:
            log.exception("Worker %d failed to compress: %s", worker_id, path)
        finally:
            work_queue.task_done()


# ---------------------------------------------------------------------------
# TCP server (non-blocking via selectors so we can shut down cleanly)
# ---------------------------------------------------------------------------

_selector = selectors.DefaultSelector()
_running = True


def _accept(server_sock: socket.socket) -> None:
    """Accept a new client connection and register it for reading."""
    conn, addr = server_sock.accept()
    conn.setblocking(False)
    log.info("Connection from %s", addr)
    # Attach a bytearray buffer to accumulate partial reads.
    _selector.register(conn, selectors.EVENT_READ, data=bytearray())


def _read(conn: socket.socket, buf: bytearray) -> None:
    """Read available data from *conn*, enqueue complete lines."""
    try:
        data = conn.recv(4096)
    except ConnectionResetError:
        data = b""

    if not data:
        _selector.unregister(conn)
        conn.close()
        return

    buf.extend(data)

    # Process every complete newline-delimited message.
    while b"\n" in buf:
        line, _, remaining = buf.partition(b"\n")
        buf.clear()
        buf.extend(remaining)

        path = line.decode("utf-8", errors="replace").strip()
        if not path:
            continue

        if not os.path.isfile(path):
            _safe_send(conn, f"ERROR File not found: {path}\n")
            log.warning("Rejected (not found): %s", path)
            continue

        work_queue.put(path)
        _safe_send(conn, f"QUEUED {path}\n")
        log.info("Queued: %s (backlog ~%d)", path, work_queue.qsize())


def _safe_send(conn: socket.socket, message: str) -> None:
    """Best-effort send; swallow errors if the client already disconnected."""
    try:
        conn.sendall(message.encode("utf-8"))
    except OSError:
        pass


def _shutdown(_signum: int = 0, _frame: FrameType | None = None) -> None:
    """Signal handler: ask the event loop and workers to stop."""
    global _running
    if not _running:
        return
    _running = False
    log.info("Shutdown requested.")


def serve() -> None:
    """Start the TCP server and worker threads, then loop until shutdown."""
    global _running

    # -- Start worker threads ------------------------------------------------
    workers: list[threading.Thread] = []
    for i in range(MAX_WORKERS):
        t = threading.Thread(target=_worker, args=(i,), daemon=True)
        t.start()
        workers.append(t)

    # -- Create and register the listening socket ----------------------------
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen()
    server_sock.setblocking(False)
    _selector.register(server_sock, selectors.EVENT_READ, data=None)

    log.info(
        "Image compressor listening on %s:%d with %d workers.",
        HOST,
        PORT,
        MAX_WORKERS,
    )

    # -- Event loop ----------------------------------------------------------
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while _running:
            events = _selector.select(timeout=0.5)
            for key, _ in events:
                if key.data is None:
                    # This is the server socket – accept a new connection.
                    _accept(key.fileobj)
                else:
                    # This is a client socket – read data.
                    _read(key.fileobj, key.data)
    finally:
        log.info("Closing server socket.")
        _selector.unregister(server_sock)
        server_sock.close()

        # Close any lingering client connections.
        for key in list(_selector.get_map().values()):
            _selector.unregister(key.fileobj)
            key.fileobj.close()
        _selector.close()

        # Send poison pills so workers exit, then wait for them.
        for _ in workers:
            work_queue.put(None)
        for t in workers:
            t.join()

        log.info("All workers stopped. Goodbye.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    serve()
