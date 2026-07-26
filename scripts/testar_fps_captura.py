"""Mede o FPS puro de captura/decodificacao RTSP, sem YOLO - ajuda a saber
se o teto de FPS observado vem da camera/decode ou da inferencia.

Uso:
    python scripts/testar_fps_captura.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config
from src.rtsp_client import RTSPClient


def main():
    cap = RTSPClient(config.RTSP_URL)
    if not cap.isOpened():
        raise SystemExit(f"Nao foi possivel abrir o stream RTSP: {config.RTSP_URL}")

    n = 100
    print(f"Lendo {n} frames sem processar (so captura + decode)...")
    t0 = time.time()
    lidos = 0
    for _ in range(n):
        ok, _frame = cap.read(timeout=5)
        if ok:
            lidos += 1
    elapsed = time.time() - t0
    cap.release()

    print(f"{lidos} frames em {elapsed:.1f}s -> {lidos / elapsed:.1f} fps de captura pura")


if __name__ == "__main__":
    main()
