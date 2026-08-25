"""Maquina de estados de ocupacao de uma vaga: livre -> pendente -> ocupada -> livre.

Ao contrario da contagem de veiculos por cruzamento (src/zone_counter.py), que precisa
lidar com varios veiculos simultaneos e tracking fragmentado por track_id, aqui so cabe
um veiculo por vez na vaga - entao presenca/ausencia ao longo do tempo, sem depender de
track_id do ByteTrack, e mais simples e imune a troca de identidade do tracker.
"""
import time


class VagaState:
    LIVRE = "livre"
    PENDENTE = "pendente"
    OCUPADA = "ocupada"

    def __init__(self, tempo_confirmar: float, tempo_tolerancia_saida: float, limite_minutos: float):
        self.tempo_confirmar = tempo_confirmar
        self.tempo_tolerancia_saida = tempo_tolerancia_saida
        self.limite_segundos = limite_minutos * 60

        self.estado = self.LIVRE
        self.pendente_desde = None
        self.ultimo_visto = None
        self.entrada_ts = None
        self.excedeu_limite_registrado = False

    def update(self, in_zona: bool, now: float = None):
        """Processa um frame (ja resolvido se algum veiculo detectado cai na
        zona de monitoramento). Retorna um dict de evento ou None:

        {"tipo": "entrada", "entrada_ts": float}
        {"tipo": "saida", "entrada_ts": float, "saida_ts": float, "duracao_segundos": float}
        {"tipo": "excesso", "entrada_ts": float}
        """
        now = time.time() if now is None else now

        if in_zona:
            self.ultimo_visto = now

        if self.estado == self.LIVRE:
            if in_zona:
                self.estado = self.PENDENTE
                self.pendente_desde = now
            return None

        if self.estado == self.PENDENTE:
            if in_zona:
                if now - self.pendente_desde >= self.tempo_confirmar:
                    self.estado = self.OCUPADA
                    self.entrada_ts = self.pendente_desde
                    self.excedeu_limite_registrado = False
                    return {"tipo": "entrada", "entrada_ts": self.entrada_ts}
            else:
                # Nao esta na zona neste frame - tolera flicker curto antes
                # de desistir (o carro pode nao ter realmente parado).
                if self.ultimo_visto is None or now - self.ultimo_visto > self.tempo_tolerancia_saida:
                    self.estado = self.LIVRE
                    self.pendente_desde = None
            return None

        if self.estado == self.OCUPADA:
            if now - self.ultimo_visto > self.tempo_tolerancia_saida:
                saida_ts = self.ultimo_visto
                entrada_ts = self.entrada_ts
                self.estado = self.LIVRE
                self.entrada_ts = None
                self.pendente_desde = None
                return {
                    "tipo": "saida",
                    "entrada_ts": entrada_ts,
                    "saida_ts": saida_ts,
                    "duracao_segundos": saida_ts - entrada_ts,
                }
            if not self.excedeu_limite_registrado and (now - self.entrada_ts) >= self.limite_segundos:
                self.excedeu_limite_registrado = True
                return {"tipo": "excesso", "entrada_ts": self.entrada_ts}
            return None

        return None
