"""Deteccao de cruzamento de uma linha virtual por track_id, com dedupe."""


def _side(p1, p2, point):
    """Sinal do produto vetorial (p2 - p1) x (point - p1). Positivo/negativo = lado da linha."""
    (x1, y1), (x2, y2) = p1, p2
    px, py = point
    return (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)


class LineCrossingCounter:
    """Conta cruzamentos de uma linha virtual, uma unica vez por track_id.

    O ponto usado para cada deteccao e o centro inferior da bounding box (posicao
    dos pes), mais estavel que o centroide para pessoas caminhando na calcada.
    """

    def __init__(self, p1, p2):
        self.p1 = p1
        self.p2 = p2
        self._last_side = {}
        self._counted = set()
        self.total = 0

    @staticmethod
    def bbox_bottom_center(xyxy):
        x1, y1, x2, y2 = xyxy
        return ((x1 + x2) / 2, y2)

    def update(self, track_id: int, xyxy) -> bool:
        """Atualiza a posicao do track_id. Retorna True se cruzou agora pela primeira vez."""
        point = self.bbox_bottom_center(xyxy)
        side = _side(self.p1, self.p2, point)
        prev_side = self._last_side.get(track_id)
        self._last_side[track_id] = side

        if prev_side is None or track_id in self._counted:
            return False

        crossed = (prev_side < 0 <= side) or (prev_side >= 0 > side)
        if not crossed:
            return False

        self._counted.add(track_id)
        self.total += 1
        return True
