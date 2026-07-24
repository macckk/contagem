"""Deteccao de cruzamento de uma linha virtual por track_id, com direcao e dedupe."""


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

    def __init__(self, p1, p2, entrada_side: str = "neg_to_pos"):
        self.p1 = p1
        self.p2 = p2
        if entrada_side not in ("neg_to_pos", "pos_to_neg"):
            raise ValueError("entrada_side deve ser 'neg_to_pos' ou 'pos_to_neg'")
        self.entrada_side = entrada_side
        self._last_side = {}
        self._counted = set()
        self.total_entrada = 0
        self.total_saida = 0

    @staticmethod
    def bbox_bottom_center(xyxy):
        x1, y1, x2, y2 = xyxy
        return ((x1 + x2) / 2, y2)

    def update(self, track_id: int, xyxy):
        """Atualiza a posicao do track_id. Retorna 'entrada'/'saida' se cruzou agora, senao None."""
        point = self.bbox_bottom_center(xyxy)
        side = _side(self.p1, self.p2, point)
        prev_side = self._last_side.get(track_id)
        self._last_side[track_id] = side

        if prev_side is None or track_id in self._counted:
            return None

        crossed = (prev_side < 0 <= side) or (prev_side >= 0 > side)
        if not crossed:
            return None

        went_neg_to_pos = prev_side < 0 <= side
        direction = (
            "entrada"
            if (went_neg_to_pos and self.entrada_side == "neg_to_pos")
            or (not went_neg_to_pos and self.entrada_side == "pos_to_neg")
            else "saida"
        )

        self._counted.add(track_id)
        if direction == "entrada":
            self.total_entrada += 1
        else:
            self.total_saida += 1
        return direction
