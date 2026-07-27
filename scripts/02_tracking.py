"""Fase 2 - Tracking + linha de contagem.

Usa model.track() (Ultralytics + ByteTrack) para manter IDs persistentes entre
frames, desenha a(s) linha(s) de contagem calibrada(s) e mostra o total de
pessoas e, se a linha de veiculos estiver calibrada, de cada tipo de veiculo
(carro/moto/onibus/caminhao/bicicleta) que passou - sem distinguir direcao.
Nao grava nada no Supabase (isso e a Fase 3).

Pessoas continuam contadas por cruzamento de linha (LineCrossingCounter).
Veiculos (dia e noite) sao contados por zona + cooldown
(src/zone_counter.py): o tracking fragmenta com frequencia (moto/carro com
motion blur passando rapido, ou parcialmente encobertos por outro veiculo -
mais comum ainda a noite, por ruido do modo IR), entao exigir o cruzamento
completo da linha (LineCrossingCounter) deixa passar muitos veiculos sem
contar. Em vez disso: basta a deteccao aparecer perto da linha com
confianca suficiente, e um cooldown espaco-temporal evita contar o mesmo
veiculo 2x quando o track_id muda no meio da passagem. A faixa da zona
aparece desenhada na tela (translucida) nas duas linhas, dia e noite.

Uso:
    python scripts/02_tracking.py
    python scripts/02_tracking.py --debug  # mostra no console TODAS as deteccoes,
                                            # nao so as que sao contadas

Pressione 'x' na janela para encerrar (ou Ctrl+C no terminal).
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
from src.zone_counter import ZoneCooldownCounter, zone_polygon


def draw_zone(frame, p1, p2, width_px, color):
    """Desenha a faixa (retangulo translucido) usada na contagem de veiculos por zona."""
    poly = np.array(zone_polygon(p1, p2, width_px), dtype=np.int32)
    overlay = frame.copy()
    cv2.fillPoly(overlay, [poly], color)
    cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, frame)
    cv2.polylines(frame, [poly], isClosed=True, color=color, thickness=1)


CLASS_NAMES = {config.PERSON_CLASS_ID: "person", **config.VEHICLE_CLASS_IDS}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Mostra no console todas as deteccoes do frame (classe, confianca, track_id), nao so as que sao contadas",
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
    line_veiculos_noite = None
    counters_veiculos_dia = None
    counters_veiculos_noite = None
    draw_veiculos = None
    draw_veiculos_noite = None
    classes = [config.PERSON_CLASS_ID]
    if line_veiculos is not None:
        line_veiculos_noite = config.get_line_veiculos_noite()
        counters_veiculos_dia = {
            nome: ZoneCooldownCounter(
                *line_veiculos,
                zone_width=config.DAY_ZONE_WIDTH_PX,
                cooldown_seconds=config.DAY_ZONE_COOLDOWN_SECONDS,
                dedupe_distance=config.DAY_ZONE_DEDUPE_DISTANCE_PX,
            )
            for nome in config.VEHICLE_CLASS_IDS.values()
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
    print(f"OpenCL (cv2) disponivel para preprocess noturno: {cv2.ocl.haveOpenCL()}")
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

    # Guarda os track_ids de veiculo ja contados, compartilhado entre os
    # contadores de dia e de noite. Sem isso, um mesmo veiculo fisico pode
    # ser contado 2x se a classificacao dia/noite (is_night) oscilar entre
    # frames perto do limiar (amanhecer/anoitecer, ou saturacao de cor no
    # limite) enquanto o track_id ainda esta ativo - cada contador
    # (ZoneCooldownCounter) so sabe deduplicar dentro de si mesmo.
    veiculo_track_ids_contados = set()

    # Acumuladores de tempo (preprocess de noite vs inferencia) para o print
    # periodico abaixo - ajuda a isolar se uma queda de FPS a noite vem do
    # CLAHE/blur (CPU) ou da propria inferencia do YOLO.
    preprocess_time_total = 0.0
    inference_time_total = 0.0
    timed_frames = 0

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

            t0 = time.time()
            detect_frame, is_night, conf_threshold = prepare_frame_for_detection(frame)
            t1 = time.time()

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
            t2 = time.time()
            preprocess_time_total += t1 - t0
            inference_time_total += t2 - t1
            timed_frames += 1
            fps = fps_meter.tick()

            annotated = result.plot()
            cv2.line(annotated, *draw_pessoas, (0, 255, 255), 2)
            if draw_veiculos:
                cv2.line(annotated, *draw_veiculos, (255, 0, 255), 2)
            if draw_veiculos_noite:
                cv2.line(annotated, *draw_veiculos_noite, (255, 255, 0), 2)
            if counters_veiculos_dia is not None:
                draw_zone(annotated, *line_veiculos, config.DAY_ZONE_WIDTH_PX, (255, 0, 255))
                draw_zone(annotated, *line_veiculos_noite, config.NIGHT_ZONE_WIDTH_PX, (255, 255, 0))

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
                        elif counters_veiculos_dia is not None and cls_id in config.VEHICLE_CLASS_IDS:
                            track_tipo[track_id] = config.VEHICLE_CLASS_IDS[cls_id]
                        else:
                            continue
                    tipo = track_tipo[track_id]

                    if tipo == "pessoa":
                        crossed = counter_pessoas.update(track_id, xyxy)
                        total = counter_pessoas.total
                    elif track_id in veiculo_track_ids_contados:
                        continue
                    elif is_night:
                        if conf < config.NIGHT_ZONE_MIN_CONF:
                            continue
                        crossed = counters_veiculos_noite[tipo].update(track_id, xyxy)
                        total = total_veiculos_tipo(tipo)
                    else:
                        if conf < config.DAY_ZONE_MIN_CONF:
                            continue
                        crossed = counters_veiculos_dia[tipo].update(track_id, xyxy)
                        total = total_veiculos_tipo(tipo)

                    if crossed:
                        if tipo == "pessoa":
                            origem = "linha"
                        else:
                            veiculo_track_ids_contados.add(track_id)
                            origem = "zona-noite" if is_night else "zona-dia"
                        print(f"{tipo} track_id={track_id} conf={conf:.2f} -> contado ({origem}, total {tipo}: {total})")

            texto = f"Pessoas: {counter_pessoas.total}"
            if counters_veiculos_dia is not None:
                total_veiculos = sum(total_veiculos_tipo(n) for n in config.VEHICLE_CLASS_IDS.values())
                texto += f"   Veiculos: {total_veiculos}"
            if is_night:
                texto += "   [modo noite]"
            (texto_w, _), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)
            cv2.putText(
                annotated,
                texto,
                (annotated.shape[1] - texto_w - 10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )
            fps_texto = f"FPS: {fps:.1f}"
            (fps_texto_w, _), _ = cv2.getTextSize(fps_texto, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)
            cv2.putText(
                annotated,
                fps_texto,
                (annotated.shape[1] - fps_texto_w - 10, 65),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )

            now = time.time()
            if now - last_fps_print >= 5:
                if timed_frames > 0:
                    print(
                        f"FPS: {fps:.1f}  "
                        f"(preprocess: {1000 * preprocess_time_total / timed_frames:.0f}ms/frame, "
                        f"inferencia: {1000 * inference_time_total / timed_frames:.0f}ms/frame, "
                        f"{'noite' if is_night else 'dia'})"
                    )
                preprocess_time_total = 0.0
                inference_time_total = 0.0
                timed_frames = 0
                last_fps_print = now

            cv2.imshow("Fase 2 - Tracking + linha", annotated)
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
