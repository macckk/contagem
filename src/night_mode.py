"""Deteccao automatica de dia/noite e ajustes para melhorar a deteccao de
veiculos a noite.

A noite, farois acesos estouram o brilho da imagem (pixels saturados em
branco), escondendo a silhueta/carroceria do veiculo e derrubando a
confianca do YOLO - o modelo foi treinado majoritariamente em imagens
diurnas/bem iluminadas. Duas medidas simples ajudam sem precisar re-treinar
o modelo:

1. Detectar "noite" pela saturacao de cor do frame: essa camera (e varias
   outras Yoosee/HiIpCamera) muda pra modo infravermelho preto-e-branco a
   noite, o que deixa o brilho medio ENGANOSAMENTE alto (o IV ilumina a
   cena e reflete no chao molhado) - por isso o brilho sozinho nao serve de
   sinal aqui. Uma imagem monocromatica tem saturacao ~0; isso e o sinal
   confiavel. O brilho baixo fica como sinal secundario, para cameras sem
   modo IR que simplesmente escurecem a imagem colorida.
2. Ja em modo noite: realçar contraste via CLAHE no canal de luminancia
   (LAB), o que melhora a definicao da carroceria nas partes nao totalmente
   estouradas pelo farol, e usar um limiar de confianca mais permissivo,
   ja que mesmo com o realce a confianca tende a ficar mais baixa que de dia.
"""
import cv2
import numpy as np

from src import config


def is_night_frame(frame) -> bool:
    """Retorna True se o frame indica que esta noite (IR P&B ou escuro)."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mean_saturation = float(np.mean(hsv[:, :, 1]))
    if mean_saturation < config.NIGHT_SATURATION_THRESHOLD:
        return True

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray)) < config.NIGHT_LUMINANCE_THRESHOLD


def preprocess_night(frame):
    """Suaviza ruido e realca contraste local via CLAHE no canal L (LAB).

    Imagens em modo IR costumam vir bem granuladas; um leve blur antes do
    CLAHE evita amplificar esse ruido. CLAHE nao recupera detalhe de pixels
    ja 100% saturados pelo farol (nao ha informacao ali para recuperar), mas
    melhora a definicao das bordas do veiculo nas regioes proximas,
    parcialmente iluminadas.
    """
    denoised = cv2.GaussianBlur(frame, (3, 3), 0)
    lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=config.NIGHT_CLAHE_CLIP_LIMIT, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    lab = cv2.merge((l_channel, a_channel, b_channel))
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def prepare_frame_for_detection(frame):
    """Retorna (frame_para_detectar, is_night, conf_threshold_efetivo)."""
    if not config.ENABLE_NIGHT_MODE:
        return frame, False, config.CONF_THRESHOLD

    night = is_night_frame(frame)
    if not night:
        return frame, False, config.CONF_THRESHOLD

    return preprocess_night(frame), True, config.NIGHT_CONF_THRESHOLD
