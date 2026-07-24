"""Fase 1 - Protototipo de captura + deteccao.

Conecta no RTSP da camera, roda YOLOv8 (classe "person") frame a frame e
mostra as deteccoes em uma janela. Serve para validar que a camera esta
acessivel e que a deteccao funciona bem no angulo/altura/iluminacao reais.

Uso:
    python scripts/01_captura.py

Pressione 'q' na janela para sair.
"""
import sys
from pathlib import Path

import cv2
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config


def main():
    if not config.RTSP_URL:
        raise SystemExit("RTSP_URL nao configurada. Copie .env.example para .env e preencha.")

    model = YOLO(config.MODEL_PATH)

    cap = cv2.VideoCapture(config.RTSP_URL)
    if not cap.isOpened():
        raise SystemExit(f"Nao foi possivel abrir o stream RTSP: {config.RTSP_URL}")

    frame_idx = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Falha ao ler frame (stream caiu?). Encerrando.")
                break

            frame_idx += 1
            if frame_idx % config.FRAME_SKIP != 0:
                continue

            results = model.predict(
                frame,
                classes=[config.PERSON_CLASS_ID],
                conf=config.CONF_THRESHOLD,
                device=config.DEVICE,
                verbose=False,
            )
            annotated = results[0].plot()

            cv2.imshow("Fase 1 - Deteccao de pessoas", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
