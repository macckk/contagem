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

    results_stream = model.track(
        source=config.RTSP_URL,
        classes=[config.PERSON_CLASS_ID],
        conf=config.CONF_THRESHOLD,
        device=config.DEVICE,
        tracker="bytetrack.yaml",
        stream=True,
        persist=True,
        verbose=False,
        vid_stride=config.FRAME_SKIP,
    )

    try:
        for result in results_stream:
            frame = result.plot()

            cv2.line(frame, p1, p2, (0, 255, 255), 2)

            boxes = result.boxes
            if boxes is not None and boxes.id is not None:
                for xyxy, track_id, conf in zip(
                    boxes.xyxy.tolist(), boxes.id.tolist(), boxes.conf.tolist()
                ):
                    direction = counter.update(int(track_id), xyxy)
                    if direction:
                        print(f"track_id={int(track_id)} conf={conf:.2f} -> {direction}")

            cv2.putText(
                frame,
                f"Entrada: {counter.total_entrada}  Saida: {counter.total_saida}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )

            cv2.imshow("Fase 2 - Tracking + linha", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cv2.destroyAllWindows()
        print(f"\nTotal final -> Entrada: {counter.total_entrada}  Saida: {counter.total_saida}")


if __name__ == "__main__":
    main()
