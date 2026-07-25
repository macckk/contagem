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
