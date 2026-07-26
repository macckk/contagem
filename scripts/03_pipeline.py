"""Fase 3/4 - Pipeline completo: tracking + linha + insercao no Supabase.

Igual a Fase 2, mas cada evento contado (de pessoa ou, se calibrada, de
veiculo - independente de direcao) vira um insert na tabela
contagem_eventos do Supabase (ver sql/schema.sql), marcado com tipo='pessoa'
ou com o tipo especifico de veiculo ('car', 'motorcycle', 'bus', 'truck',
'bicycle'). Suporta modo headless (sem janela) para deixar rodando durante
o teste de campo (Fase 4).

De dia, veiculos sao contados por cruzamento de linha (LineCrossingCounter).
A noite, a deteccao fica intermitente (ruido do modo IR + desfoque de
movimento) e o tracking raramente sobrevive ao cruzamento completo - por
isso, a noite, veiculos sao contados por zona + cooldown
(src/zone_counter.py): basta a deteccao aparecer perto da linha com
confianca alta (NIGHT_ZONE_MIN_CONF), e um cooldown espaco-temporal evita
contar o mesmo veiculo 2x quando o track_id fragmenta.

Uso:
    python scripts/03_pipeline.py             # com janela
    python scripts/03_pipeline.py --headless  # sem janela, so console

Pressione 'x' na janela para encerrar (ou Ctrl+C no terminal, inclusive no modo --headless).
"""
import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config
from src.device_info import print_device_info, should_use_half
from src.fps_meter import FPSMeter
from src.line_crossing import LineCrossingCounter
from src.night_mode import prepare_frame_for_detection
from src.rtsp_client import RTSPClient
from src.supabase_client import insert_event
from src.zone_counter import ZoneCooldownCounter, zone_polygon


def draw_zone(frame, p1, p2, width_px, color):
    """Desenha a faixa (retangulo translucido) usada na contagem noturna por zona."""
    poly = np.array(zone_polygon(p1, p2, width_px), dtype=np.int32)
    overlay = frame.copy()
    cv2.fillPoly(overlay, [poly], color)
    cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, frame)
    cv2.polylines(frame, [poly], isClosed=True, color=color, thickness=1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true", help="Nao abrir janela de video")
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
    counters_veiculos_dia = None
    counters_veiculos_noite = None
    draw_veiculos = None
    draw_veiculos_noite = None
    classes = [config.PERSON_CLASS_ID]
    if line_veiculos is not None:
        line_veiculos_noite = config.get_line_veiculos_noite()
        counters_veiculos_dia = {
            nome: LineCrossingCounter(*line_veiculos) for nome in config.VEHICLE_CLASS_IDS.values()
        }
        counters_veiculos_noite = {
            nome: ZoneCooldownCounter(
                *line_veiculos_noite,
                zone_width=config.NIGHT_ZONE_WIDTH_PX,
                cooldown_seconds=config.NIGHT_ZONE_COOLDOWN_SECONDS,
                dedupe_distance=config.NIGHT_ZONE_DEDUPE_DISTANCE_PX,
            )
            for nome in config.VEHICLE_CLASS_IDS.values()
        }
        draw_veiculos = tuple((int(p[0]), int(p[1])) for p in line_veiculos)
        if line_veiculos_noite != line_veiculos:
            draw_veiculos_noite = tuple((int(p[0]), int(p[1])) for p in line_veiculos_noite)
        classes += list(config.VEHICLE_CLASS_IDS)
    else:
        print(
            "Linha de veiculos nao calibrada (LINE_VEICULOS_*) - contando so pessoas. "
            "Rode 'python scripts/calibrar_linha.py --alvo veiculos' para habilitar."
        )

    def total_veiculos_tipo(nome):
        dia = counters_veiculos_dia[nome].total
        noite = counters_veiculos_noite[nome].total
        return dia + noite

    print_device_info(config.DEVICE)
    use_half = config.HALF_PRECISION and should_use_half(config.DEVICE)
    quantize = 16 if use_half else 32
    model = YOLO(config.MODEL_PATH)

    cap = RTSPClient(config.RTSP_URL)
    if not cap.isOpened():
        raise SystemExit(f"Nao foi possivel abrir o stream RTSP: {config.RTSP_URL}")

    fps_meter = FPSMeter()
    last_fps_print = 0

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
                quantize=quantize,
                augment=config.AUGMENT_INFERENCE,
                tracker=config.TRACKER_CONFIG,
                persist=True,
                verbose=False,
            )[0]
            fps = fps_meter.tick()

            now = time.time()
            if now - last_fps_print >= 5:
                print(f"FPS: {fps:.1f}")
                last_fps_print = now

            boxes = result.boxes
            if boxes is not None and boxes.id is not None:
                for xyxy, track_id, conf, cls_id in zip(
                    boxes.xyxy.tolist(), boxes.id.tolist(), boxes.conf.tolist(), boxes.cls.tolist()
                ):
                    track_id = int(track_id)
                    cls_id = int(cls_id)

                    if track_id not in track_tipo:
                        if cls_id == config.PERSON_CLASS_ID:
                            track_tipo[track_id] = "pessoa"
                        elif counters_veiculos_dia is not None and cls_id in config.VEHICLE_CLASS_IDS:
                            track_tipo[track_id] = config.VEHICLE_CLASS_IDS[cls_id]
                        else:
                            continue
                    tipo = track_tipo[track_id]

                    if tipo == "pessoa":
                        crossed = counter_pessoas.update(track_id, xyxy)
                        total = counter_pessoas.total
                    elif is_night:
                        if conf < config.NIGHT_ZONE_MIN_CONF:
                            continue
                        crossed = counters_veiculos_noite[tipo].update(track_id, xyxy)
                        total = total_veiculos_tipo(tipo)
                    else:
                        crossed = counters_veiculos_dia[tipo].update(track_id, xyxy)
                        total = total_veiculos_tipo(tipo)

                    if crossed:
                        try:
                            insert_event(track_id, conf, tipo=tipo)
                        except Exception as exc:
                            print(f"Falha ao inserir no Supabase: {exc}")
                        origem = "zona-noite" if (tipo != "pessoa" and is_night) else "linha"
                        print(
                            f"{tipo} track_id={track_id} conf={conf:.2f} -> contado "
                            f"({origem}, total {tipo}: {total})"
                        )

            if not args.headless:
                annotated = result.plot()
                cv2.line(annotated, *draw_pessoas, (0, 255, 255), 2)
                if draw_veiculos:
                    cv2.line(annotated, *draw_veiculos, (255, 0, 255), 2)
                if draw_veiculos_noite:
                    cv2.line(annotated, *draw_veiculos_noite, (255, 255, 0), 2)
                if is_night and counters_veiculos_noite is not None:
                    draw_zone(annotated, *line_veiculos_noite, config.NIGHT_ZONE_WIDTH_PX, (255, 255, 0))
                texto = f"Pessoas: {counter_pessoas.total}"
                if counters_veiculos_dia is not None:
                    total_veiculos = sum(
                        total_veiculos_tipo(n) for n in config.VEHICLE_CLASS_IDS.values()
                    )
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
                cv2.putText(
                    annotated,
                    f"FPS: {fps:.1f}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2,
                )
                cv2.imshow("Fase 3 - Pipeline completo", annotated)
                if cv2.waitKey(1) & 0xFF == ord("x"):
                    break
    except KeyboardInterrupt:
        print("\nInterrompido (Ctrl+C).")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print(f"\nTotal final -> Pessoas: {counter_pessoas.total}")
        if counters_veiculos_dia is not None:
            total_geral = 0
            for nome in config.VEHICLE_CLASS_IDS.values():
                dia = counters_veiculos_dia[nome].total
                noite = counters_veiculos_noite[nome].total
                total_geral += dia + noite
                print(f"  {nome}: {dia + noite} (dia: {dia}, noite: {noite})")
            print(f"  Total veiculos: {total_geral}")


if __name__ == "__main__":
    main()
