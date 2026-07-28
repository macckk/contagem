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


def zone_polygon(p1, p2, width):
    """4 pontos (em ordem) do retangulo formado ao redor do segmento p1-p2,
    com margem perpendicular de 'width' pixels para cada lado - usado so
    para desenhar a zona na tela; a checagem real usa distancia ao
    segmento (_point_segment_distance), nao esse poligono.
    """
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length * width, dx / length * width
    return [
        (x1 + nx, y1 + ny),
        (x2 + nx, y2 + ny),
        (x2 - nx, y2 - ny),
        (x1 - nx, y1 - ny),
    ]


def point_in_any_rect(rects, point):
    """True se 'point' cai dentro de algum retangulo (x1, y1, x2, y2) da
    lista - usado para excluir uma area do quadro (EXCLUDE_ZONES) que gera
    falsos positivos, antes mesmo de entrar no tracking/contagem.
    """
    px, py = point
    for x1, y1, x2, y2 in rects:
        if min(x1, x2) <= px <= max(x1, x2) and min(y1, y2) <= py <= max(y1, y2):
            return True
    return False


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

    O dedupe (track_ids ja contados + posicoes recentes) pode ser
    compartilhado entre varias instancias via 'shared_state' - usado para as
    zonas de dia e de noite do mesmo tipo de veiculo nao contarem o mesmo
    veiculo fisico 2x quando o tracking fragmenta (gera um track_id novo)
    bem no momento em que a classificacao dia/noite muda: sem
    compartilhar, cada instancia so ve seu proprio historico e nao sabe que
    o outro fragmento ja foi contado na outra zona. 'total' continua
    proprio de cada instancia, para manter a quebra dia/noite no relatorio
    final.
    """

    def __init__(self, p1, p2, zone_width, cooldown_seconds, dedupe_distance, shared_state=None):
        self.p1 = p1
        self.p2 = p2
        self.zone_width = zone_width
        self.cooldown_seconds = cooldown_seconds
        self.dedupe_distance = dedupe_distance
        self._shared = shared_state if shared_state is not None else {"counted_track_ids": set(), "recent": []}
        self.total = 0

    @staticmethod
    def bbox_bottom_center(xyxy):
        x1, y1, x2, y2 = xyxy
        return ((x1 + x2) / 2, y2)

    def _in_zone(self, point):
        return _point_segment_distance(self.p1, self.p2, point) <= self.zone_width

    def update(self, track_id: int, xyxy, now: float = None) -> bool:
        """Retorna True se essa deteccao foi contada agora pela primeira vez."""
        counted_track_ids = self._shared["counted_track_ids"]
        if track_id in counted_track_ids:
            return False

        point = self.bbox_bottom_center(xyxy)
        if not self._in_zone(point):
            return False

        now = time.time() if now is None else now
        recent = self._shared["recent"]
        recent[:] = [r for r in recent if now - r[0] <= self.cooldown_seconds]

        for _, x, y in recent:
            if math.hypot(point[0] - x, point[1] - y) <= self.dedupe_distance:
                # Mesmo veiculo fisico (track fragmentado, possivelmente na
                # outra zona dia/noite) - nao conta de novo, mas marca esse
                # track_id para nao reavaliar a cada frame.
                counted_track_ids.add(track_id)
                return False

        counted_track_ids.add(track_id)
        recent.append((now, point[0], point[1]))
        self.total += 1
        return True
