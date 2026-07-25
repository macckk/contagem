"""Configuracao central, carregada de variaveis de ambiente (.env)."""
import os

from dotenv import load_dotenv

load_dotenv()


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

# IDs de classe no dataset COCO, em que o YOLOv8 padrao foi treinado.
PERSON_CLASS_ID = 0
VEHICLE_CLASS_IDS = {
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
