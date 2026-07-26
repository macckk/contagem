"""Configuracao central, carregada de variaveis de ambiente (.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent


def _float_or_none(value):
    return float(value) if value not in (None, "") else None


RTSP_URL = os.getenv("RTSP_URL", "")
CAMERA_ID = os.getenv("CAMERA_ID", "calcada_01")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

MODEL_PATH = os.getenv("MODEL_PATH", "yolov8n.pt")
DEVICE = os.getenv("DEVICE", "") or None

CONF_THRESHOLD = float(os.getenv("CONF_THRESHOLD", "0.4"))
FRAME_SKIP = max(1, int(os.getenv("FRAME_SKIP", "1")))

# Tamanho da imagem usado na inferencia. O YOLO redimensiona o frame para
# este valor antes de detectar; o padrao da Ultralytics (640) pode fundir
# veiculos proximos numa unica caixa (as vezes classificada errado como
# "truck"). Um valor maior preserva mais detalhe, ao custo de mais
# processamento.
IMGSZ = int(os.getenv("IMGSZ", "640"))

# Tracker ByteTrack customizado (mais tolerante a deteccao intermitente,
# comum a noite por ruido do modo IR e desfoque de movimento) - ver
# trackers/bytetrack_tolerante.yaml para os detalhes de cada ajuste.
TRACKER_CONFIG = os.getenv("TRACKER_CONFIG") or str(
    REPO_ROOT / "trackers" / "bytetrack_tolerante.yaml"
)

# Precisao FP16 (half) na inferencia - só tem efeito com GPU CUDA (quase
# 2x mais rapido nela); em CPU e ignorado automaticamente
# (ver src/device_info.should_use_half).
HALF_PRECISION = os.getenv("HALF_PRECISION", "false").strip().lower() in ("1", "true", "yes")

# Test-time augmentation: roda a inferencia em multiplas escalas/espelhamentos
# e combina os resultados. Ajuda a recuperar veiculos com motion blur (carro/
# moto passando rapido) ou parcialmente visiveis, ao custo de ~2-3x mais
# processamento por frame - so vale a pena com GPU sobrando.
AUGMENT_INFERENCE = os.getenv("AUGMENT_INFERENCE", "false").strip().lower() in ("1", "true", "yes")

# Modo noite: a noite, farois acesos estouram o brilho e escondem a
# carroceria do veiculo, derrubando a confianca do YOLO. Essa camera (e
# varias outras Yoosee/HiIpCamera) muda pra modo infravermelho P&B a noite,
# o que deixa o brilho medio do frame ENGANOSAMENTE alto (o IV ilumina a
# cena e reflete no asfalto molhado) - por isso o sinal mais confiavel de
# "noite" e a saturacao de cor quase zero (imagem monocromatica), nao o
# brilho. O brilho baixo fica como sinal secundario, para cameras sem modo
# IR que simplesmente escurecem.
ENABLE_NIGHT_MODE = os.getenv("ENABLE_NIGHT_MODE", "true").strip().lower() in ("1", "true", "yes")
NIGHT_SATURATION_THRESHOLD = float(os.getenv("NIGHT_SATURATION_THRESHOLD", "20"))
NIGHT_LUMINANCE_THRESHOLD = float(os.getenv("NIGHT_LUMINANCE_THRESHOLD", "70"))
NIGHT_CONF_THRESHOLD = float(os.getenv("NIGHT_CONF_THRESHOLD", "0.25"))
NIGHT_CLAHE_CLIP_LIMIT = float(os.getenv("NIGHT_CLAHE_CLIP_LIMIT", "2.5"))

# Contagem de veiculos por ZONA + cooldown (src/zone_counter.py), em vez de
# exigir o cruzamento completo da linha (LineCrossingCounter) - que falha
# sempre que o tracking fragmenta por deteccao intermitente (comum a noite
# por ruido do modo IR, mas tambem de dia quando o veiculo fica
# parcialmente encoberto por outro carro ou sofre motion blur passando
# rapido). So conta deteccoes com confianca suficiente dentro de uma faixa
# ao redor da linha calibrada; deteccoes do mesmo tipo perto (em posicao) e
# logo em seguida (em tempo) sao tratadas como o mesmo veiculo, evitando
# contar 2x quando o track_id muda no meio da passagem.
#
# Parametros separados para dia e noite porque as duas linhas costumam
# ter geometria/exposicao bem diferentes (ver LINE_VEICULOS_NOITE_*).
NIGHT_ZONE_MIN_CONF = float(os.getenv("NIGHT_ZONE_MIN_CONF", "0.55"))
NIGHT_ZONE_WIDTH_PX = float(os.getenv("NIGHT_ZONE_WIDTH_PX", "150"))
NIGHT_ZONE_COOLDOWN_SECONDS = float(os.getenv("NIGHT_ZONE_COOLDOWN_SECONDS", "5.0"))
NIGHT_ZONE_DEDUPE_DISTANCE_PX = float(os.getenv("NIGHT_ZONE_DEDUPE_DISTANCE_PX", "200"))

DAY_ZONE_MIN_CONF = float(os.getenv("DAY_ZONE_MIN_CONF", "0.35"))
DAY_ZONE_WIDTH_PX = float(os.getenv("DAY_ZONE_WIDTH_PX", "150"))
DAY_ZONE_COOLDOWN_SECONDS = float(os.getenv("DAY_ZONE_COOLDOWN_SECONDS", "5.0"))
DAY_ZONE_DEDUPE_DISTANCE_PX = float(os.getenv("DAY_ZONE_DEDUPE_DISTANCE_PX", "200"))

# IDs de classe no dataset COCO, em que o YOLOv8 padrao foi treinado.
PERSON_CLASS_ID = 0
VEHICLE_CLASS_IDS = {
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


def _get_line(prefix):
    coords = tuple(
        _float_or_none(os.getenv(f"{prefix}{suffix}"))
        for suffix in ("X1", "Y1", "X2", "Y2")
    )
    if any(c is None for c in coords):
        return None
    x1, y1, x2, y2 = coords
    return (x1, y1), (x2, y2)


def get_line_pessoas():
    """Retorna ((x1, y1), (x2, y2)) da linha de contagem de pessoas, ou None se nao calibrada."""
    return _get_line("LINE_")


def get_line_veiculos():
    """Retorna ((x1, y1), (x2, y2)) da linha de contagem de veiculos, ou None se nao calibrada."""
    return _get_line("LINE_VEICULOS_")


def get_line_veiculos_noite():
    """Retorna a linha/zona de veiculos usada a noite.

    O veiculo costuma ser detectado com mais confianca assim que entra no
    quadro (antes do farol saturar o resto da cena de perto), entao vale a
    pena calibrar uma linha separada, mais proxima de onde o veiculo
    aparece. Se LINE_VEICULOS_NOITE_* nao estiver calibrada, cai para a
    mesma linha usada de dia (get_line_veiculos()).
    """
    linha_noite = _get_line("LINE_VEICULOS_NOITE_")
    return linha_noite if linha_noite is not None else get_line_veiculos()
