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

# Classe 0 = "person" no COCO, dataset em que o YOLOv8 padrao foi treinado.
PERSON_CLASS_ID = 0

LINE_X1 = _float_or_none(os.getenv("LINE_X1"))
LINE_Y1 = _float_or_none(os.getenv("LINE_Y1"))
LINE_X2 = _float_or_none(os.getenv("LINE_X2"))
LINE_Y2 = _float_or_none(os.getenv("LINE_Y2"))


def get_line_points():
    """Retorna ((x1, y1), (x2, y2)) da linha de contagem, ou None se nao calibrada."""
    coords = (LINE_X1, LINE_Y1, LINE_X2, LINE_Y2)
    if any(c is None for c in coords):
        return None
    return (LINE_X1, LINE_Y1), (LINE_X2, LINE_Y2)
