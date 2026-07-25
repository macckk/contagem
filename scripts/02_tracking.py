"""Fase 2 - Tracking + linha de contagem.

Usa model.track() (Ultralytics + ByteTrack) para manter IDs persistentes entre
frames, desenha a linha de contagem calibrada e mostra os contadores de
entrada/saida na tela. Nao grava nada no Supabase (isso e a Fase 3).

Uso:
    python scripts/02_tracking.py
"""
import sys
from pathlib import Path

import cv2
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config
from src.line_crossing import LineCrossingCounter
from src.rtsp_client import RTSPClient


def main():
    if not config.RTSP_URL:
        raise SystemExit("RTSP_URL nao configurada. Copie .env.example para .env e preencha.")

    line = config.get_line_points()
    if line is None:
        raise SystemExit(
            "Linha de contagem nao calibrada. Rode scripts/calibrar_linha.py e "
            "preencha LINE_X1/LINE_Y1/LINE_X2/LINE_Y2 no .env."
        )
    p1, p2 = line
    counter = LineCrossingCounter(p1, p2, entrada_side=config.ENTRADA_SIDE)

    model = YOLO(config.MODEL_PATH)

    cap = RTSPClient(config.RTSP_URL)
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

            result = model.track(
                frame,
                classes=[config.PERSON_CLASS_ID],
                conf=config.CONF_THRESHOLD,
                device=config.DEVICE,
                tracker="bytetrack.yaml",
                persist=True,
                verbose=False,
            )[0]

            annotated = result.plot()
            cv2.line(annotated, p1, p2, (0, 255, 255), 2)

            boxes = result.boxes
            if boxes is not None and boxes.id is not None:
                for xyxy, track_id, conf in zip(
                    boxes.xyxy.tolist(), boxes.id.tolist(), boxes.conf.tolist()
                ):
                    direction = counter.update(int(track_id), xyxy)
                    if direction:
                        print(f"track_id={int(track_id)} conf={conf:.2f} -> {direction}")

            cv2.putText(
                annotated,
                f"Entrada: {counter.total_entrada}  Saida: {counter.total_saida}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )

            cv2.imshow("Fase 2 - Tracking + linha", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print(f"\nTotal final -> Entrada: {counter.total_entrada}  Saida: {counter.total_saida}")


if __name__ == "__main__":
    main()
