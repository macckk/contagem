"""Medidor de FPS (media movel exponencial) para os loops de captura."""
import time


class FPSMeter:
    def __init__(self, smoothing: float = 0.9):
        self.smoothing = smoothing
        self.fps = 0.0
        self._last = None

    def tick(self) -> float:
        """Chame uma vez por frame processado. Retorna o FPS suavizado atual."""
        now = time.time()
        if self._last is not None:
            elapsed = max(now - self._last, 1e-6)
            instant = 1.0 / elapsed
            self.fps = instant if self.fps == 0 else (
                self.fps * self.smoothing + instant * (1 - self.smoothing)
            )
        self._last = now
        return self.fps
