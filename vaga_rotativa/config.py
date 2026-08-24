"""Configuracao do subprojeto Vaga Rotativa.

Carregada de vaga_rotativa/.env - separado do .env da raiz (que e do projeto de
contagem de pessoas/veiculos) porque as duas fontes de video/credenciais sao
diferentes (outra camera/DVR); usar o mesmo .env colidiria em variaveis como
RTSP_URL e SUPABASE_URL apontando para coisas distintas.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_PATH)

RTSP_URL = os.getenv("RTSP_URL", "")
VAGA_ID = os.getenv("VAGA_ID", "vaga_01")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

MODEL_PATH = os.getenv("MODEL_PATH", "yolov8s.pt")
DEVICE = os.getenv("DEVICE", "") or None
HALF_PRECISION = os.getenv("HALF_PRECISION", "false").strip().lower() in ("1", "true", "yes")
CONF_THRESHOLD = float(os.getenv("CONF_THRESHOLD", "0.35"))
IMGSZ = int(os.getenv("IMGSZ", "1280"))

# Classes COCO monitoradas - "van" nao existe como classe propria do COCO/YOLO,
# cai naturalmente em "car" (mais comum) ou "truck" dependendo do porte.
VEHICLE_CLASS_IDS = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

# Tempo continuo dentro da zona minima (azul) para confirmar que o veiculo
# realmente estacionou (evita contar transito lento/parada de farol).
TEMPO_CONFIRMAR_ESTACIONADO_SEGUNDOS = float(os.getenv("TEMPO_CONFIRMAR_ESTACIONADO_SEGUNDOS", "20"))

# Tempo sem nenhuma deteccao (nem na zona de monitoramento, verde) para
# considerar que o veiculo realmente saiu - tolera oclusao/flicker passageiro.
TEMPO_TOLERANCIA_SAIDA_SEGUNDOS = float(os.getenv("TEMPO_TOLERANCIA_SAIDA_SEGUNDOS", "20"))

# Tempo maximo permitido de permanencia (estacionamento rotativo) antes de
# tirar uma foto e marcar o evento como excedido.
LIMITE_MINUTOS_PERMITIDO = float(os.getenv("LIMITE_MINUTOS_PERMITIDO", "15"))

CAPTURAS_DIR = Path(__file__).resolve().parent / "capturas"


def _parse_polygon(bloco):
    partes = [float(p.strip()) for p in bloco.split(",")]
    if len(partes) < 6 or len(partes) % 2 != 0:
        return None
    return list(zip(partes[0::2], partes[1::2]))


def get_zona_exclusao():
    """Lista de poligonos [[(x,y), ...], ...] a ignorar na deteccao (vermelho).

    Formato no .env: "x1,y1,x2,y2,x3,y3,x4,y4;x1,y1,...", poligonos separados
    por ";" (opcional, pode ter zero ou varios).
    """
    raw = os.getenv("ZONA_EXCLUSAO", "").strip()
    if not raw:
        return []
    zonas = []
    for bloco in raw.split(";"):
        bloco = bloco.strip()
        if not bloco:
            continue
        poligono = _parse_polygon(bloco)
        if poligono:
            zonas.append(poligono)
    return zonas


def get_zona_monitoramento():
    """Poligono unico (verde, inclui a zona minima) - None se nao calibrada."""
    raw = os.getenv("ZONA_MONITORAMENTO", "").strip()
    return _parse_polygon(raw) if raw else None


def get_zona_minima():
    """Poligono unico (azul, nucleo - subconjunto da zona de monitoramento) - None se nao calibrada."""
    raw = os.getenv("ZONA_MINIMA", "").strip()
    return _parse_polygon(raw) if raw else None
