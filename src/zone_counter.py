"""Contagem por zona + cooldown - alternativa ao cruzamento de linha, usada
so a noite para veiculos.

A noite a deteccao fica intermitente (ruido do modo IR + desfoque de
movimento), entao um veiculo pode nunca ser detectado nos dois lados da
linha de contagem - o LineCrossingCounter exige isso e acaba nao contando
nada. Aqui a logica e diferente: em vez de exigir a trajetoria completa,
conta a deteccao assim que ela aparece dentro de uma faixa ao redor da
linha (a "zona"), com confianca suficiente.

O risco disso sozinho seria contar o mesmo veiculo fisico varias vezes,
já que o tracking fragmentado gera track_ids diferentes para o mesmo carro
passando. Por isso tem um cooldown espaco-temporal: se outra deteccao do
mesmo tipo aparecer perto (em posicao) e logo em seguida (em tempo), ela e
tratada como o mesmo veiculo e ignorada, mesmo com track_id diferente.
"""
import math
import time


def _point_segment_distance(p1, p2, point):
    """Distancia do ponto ao segmento de reta p1-p2 (nao a reta infinita)."""
    x1, y1 = p1
    x2, y2 = p2
    px, py = point

    dx, dy = x2 - x1, y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0:
        return math.hypot(px - x1, py - y1)

    t = ((px - x1) * dx + (py - y1) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    proj_x, proj_y = x1 + t * dx, y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


class ZoneCooldownCounter:
    """Conta uma deteccao como "passou" quando cai dentro de uma faixa ao
    redor da linha, deduplicando por proximidade+tempo (nao so por track_id)
    para tolerar tracking fragmentado.
    """

    def __init__(self, p1, p2, zone_width, cooldown_seconds, dedupe_distance):
        self.p1 = p1
        self.p2 = p2
        self.zone_width = zone_width
        self.cooldown_seconds = cooldown_seconds
        self.dedupe_distance = dedupe_distance
        self._counted_track_ids = set()
        self._recent = []  # [(timestamp, x, y), ...] - ja e por-tipo (1 instancia por tipo)
        self.total = 0

    @staticmethod
    def bbox_bottom_center(xyxy):
        x1, y1, x2, y2 = xyxy
        return ((x1 + x2) / 2, y2)

    def _in_zone(self, point):
        return _point_segment_distance(self.p1, self.p2, point) <= self.zone_width

    def _prune_recent(self, now):
        self._recent = [r for r in self._recent if now - r[0] <= self.cooldown_seconds]

    def update(self, track_id: int, xyxy, now: float = None) -> bool:
        """Retorna True se essa deteccao foi contada agora pela primeira vez."""
        if track_id in self._counted_track_ids:
            return False

        point = self.bbox_bottom_center(xyxy)
        if not self._in_zone(point):
            return False

        now = time.time() if now is None else now
        self._prune_recent(now)

        for _, x, y in self._recent:
            if math.hypot(point[0] - x, point[1] - y) <= self.dedupe_distance:
                # Mesmo veiculo fisico (track fragmentado) - nao conta de novo,
                # mas marca esse track_id para nao reavaliar a cada frame.
                self._counted_track_ids.add(track_id)
                return False

        self._counted_track_ids.add(track_id)
        self._recent.append((now, point[0], point[1]))
        self.total += 1
        return True
