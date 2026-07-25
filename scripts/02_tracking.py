"""Fase 2 - Tracking + linha de contagem.

Usa model.track() (Ultralytics + ByteTrack) para manter IDs persistentes entre
frames, desenha a(s) linha(s) de contagem calibrada(s) e mostra o total de
pessoas e, se a linha de veiculos estiver calibrada, de cada tipo de veiculo
(carro/moto/onibus/caminhao/bicicleta) que cruzou - sem distinguir direcao.
Nao grava nada no Supabase (isso e a Fase 3).

Uso:
    python scripts/02_tracking.py
    python scripts/02_tracking.py --debug  # mostra no console TODAS as deteccoes,
                                            # nao so as que cruzam a linha

Pressione 'x' na janela para encerrar (ou Ctrl+C no terminal).
"""
import argparse
import sys
from pathlib import Path

import cv2
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config
from src.line_crossing import LineCrossingCounter
from src.night_mode import prepare_frame_for_detection
from src.rtsp_client import RTSPClient

CLASS_NAMES = {config.PERSON_CLASS_ID: "person", **config.VEHICLE_CLASS_IDS}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Mostra no console todas as deteccoes do frame (classe, confianca, track_id), nao so as que cruzam a linha",
    )
    args = parser.parse_args()

    if not config.RTSP_URL:
        raise SystemExit("RTSP_URL nao configurada. Copie .env.example para .env e preencha.")

    line_pessoas = config.get_line_pessoas()
    if line_pessoas is None:
        raise SystemExit(
            "Linha de pessoas nao calibrada. Rode scripts/calibrar_linha.py e "
            "preencha LINE_X1/LINE_Y1/LINE_X2/LINE_Y2 no .env."
        )
    counter_pessoas = LineCrossingCounter(*line_pessoas)
    draw_pessoas = tuple((int(p[0]), int(p[1])) for p in line_pessoas)

    line_veiculos = config.get_line_veiculos()
    counters_veiculos = None
    draw_veiculos = None
    classes = [config.PERSON_CLASS_ID]
    if line_veiculos is not None:
        counters_veiculos = {
            nome: LineCrossingCounter(*line_veiculos) for nome in config.VEHICLE_CLASS_IDS.values()
        }
        draw_veiculos = tuple((int(p[0]), int(p[1])) for p in line_veiculos)
        classes += list(config.VEHICLE_CLASS_IDS)
    else:
        print(
            "Linha de veiculos nao calibrada (LINE_VEICULOS_*) - contando so pessoas. "
            "Rode 'python scripts/calibrar_linha.py --alvo veiculos' para habilitar."
        )

    model = YOLO(config.MODEL_PATH)

    cap = RTSPClient(config.RTSP_URL)
    if not cap.isOpened():
        raise SystemExit(f"Nao foi possivel abrir o stream RTSP: {config.RTSP_URL}")

    # O YOLOv8n as vezes reclassifica o mesmo track_id entre frames (ex: uma
    # moto/motociclista pode oscilar entre "motorcycle" e "person"). Se
    # decidissemos o tipo a cada frame, o historico de posicao desse objeto
    # ficaria fragmentado entre os contadores e o cruzamento nunca seria
    # detectado. Por isso o tipo e fixado na primeira vez que o track_id
    # aparece e mantido daí em diante.
    track_tipo = {}

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

            detect_frame, is_night, conf_threshold = prepare_frame_for_detection(frame)

            result = model.track(
                detect_frame,
                classes=classes,
                conf=conf_threshold,
                device=config.DEVICE,
                imgsz=config.IMGSZ,
                tracker="bytetrack.yaml",
                persist=True,
                verbose=False,
            )[0]

            annotated = result.plot()
            cv2.line(annotated, *draw_pessoas, (0, 255, 255), 2)
            if draw_veiculos:
                cv2.line(annotated, *draw_veiculos, (255, 0, 255), 2)

            boxes = result.boxes
            if boxes is not None and boxes.id is not None:
                for xyxy, track_id, conf, cls_id in zip(
                    boxes.xyxy.tolist(), boxes.id.tolist(), boxes.conf.tolist(), boxes.cls.tolist()
                ):
                    track_id = int(track_id)
                    cls_id = int(cls_id)
                    if args.debug:
                        nome = CLASS_NAMES.get(cls_id, f"classe_{cls_id}")
                        print(f"[debug] {nome} track_id={track_id} conf={conf:.2f}")

                    if track_id not in track_tipo:
                        if cls_id == config.PERSON_CLASS_ID:
                            track_tipo[track_id] = "pessoa"
                        elif counters_veiculos is not None and cls_id in config.VEHICLE_CLASS_IDS:
                            track_tipo[track_id] = config.VEHICLE_CLASS_IDS[cls_id]
                        else:
                            continue
                    tipo = track_tipo[track_id]
                    counter = counter_pessoas if tipo == "pessoa" else counters_veiculos[tipo]

                    if counter.update(track_id, xyxy):
                        print(f"{tipo} track_id={track_id} conf={conf:.2f} -> cruzou (total {tipo}: {counter.total})")

            texto = f"Pessoas: {counter_pessoas.total}"
            if counters_veiculos is not None:
                total_veiculos = sum(c.total for c in counters_veiculos.values())
                texto += f"   Veiculos: {total_veiculos}"
            if is_night:
                texto += "   [modo noite]"
            cv2.putText(
                annotated,
                texto,
                (10, annotated.shape[0] - 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )

            cv2.imshow("Fase 2 - Tracking + linha", annotated)
            if cv2.waitKey(1) & 0xFF == ord("x"):
                break
    except KeyboardInterrupt:
        print("\nInterrompido (Ctrl+C).")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print(f"\nTotal final -> Pessoas: {counter_pessoas.total}")
        if counters_veiculos is not None:
            for nome, counter in counters_veiculos.items():
                print(f"  {nome}: {counter.total}")
            print(f"  Total veiculos: {sum(c.total for c in counters_veiculos.values())}")


if __name__ == "__main__":
    main()
