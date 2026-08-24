"""Vaga Rotativa - monitoramento de ocupacao de uma vaga de estacionamento rotativo.

Detecta quando um veiculo entra/sai da vaga usando uma maquina de estados por
presenca/ausencia (vaga_rotativa/zone_state.py::VagaState) - sem tracking por
track_id, ja que so cabe um veiculo por vez na vaga (ao contrario da contagem
de pessoas/veiculos do projeto principal). Grava entrada/saida/duracao na
tabela vaga_eventos do Supabase e tira uma foto local se o veiculo passar do
tempo permitido (LIMITE_MINUTOS_PERMITIDO, padrao 15 min).

Uso:
    python vaga_rotativa/scripts/monitorar_vaga.py
    python vaga_rotativa/scripts/monitorar_vaga.py --debug     # detalhe de cada deteccao/zona por frame
    python vaga_rotativa/scripts/monitorar_vaga.py --headless  # sem janela de video

Se a conexao com o DVR cair, o script fica tentando reconectar a cada 5s (mesmo
comportamento de scripts/03_pipeline.py) em vez de encerrar.

Pressione 'x' na janela para encerrar (ou Ctrl+C no terminal, inclusive --headless).
"""
import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.device_info import print_device_info, should_use_half
from src.fps_meter import FPSMeter
from src.rtsp_client import RTSPClient
from src.zone_counter import point_in_any_polygon
from vaga_rotativa import config
from vaga_rotativa.supabase_client import registrar_entrada, registrar_excesso, registrar_saida
from vaga_rotativa.zone_state import VagaState


def open_capture(retry_wait=5.0):
    while True:
        cap = RTSPClient(config.RTSP_URL)
        if cap.isOpened():
            return cap
        cap.release()
        print(f"Nao foi possivel conectar a {config.RTSP_URL}. Tentando de novo em {retry_wait:.0f}s...")
        time.sleep(retry_wait)


def bbox_bottom_center(xyxy):
    x1, y1, x2, y2 = xyxy
    return ((x1 + x2) / 2, y2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Mostra no console detalhes de cada deteccao/zona por frame")
    parser.add_argument("--headless", action="store_true", help="Nao abrir janela de video")
    args = parser.parse_args()

    if not config.RTSP_URL:
        raise SystemExit(
            "RTSP_URL nao configurada. Copie vaga_rotativa/.env.example para "
            "vaga_rotativa/.env e preencha."
        )

    zona_minima = config.get_zona_minima()
    zona_monitoramento = config.get_zona_monitoramento()
    if zona_minima is None or zona_monitoramento is None:
        raise SystemExit(
            "Zonas nao calibradas. Rode 'python vaga_rotativa/scripts/calibrar_zonas.py --alvo minima' "
            "e '--alvo monitoramento', preenchendo ZONA_MINIMA/ZONA_MONITORAMENTO no vaga_rotativa/.env."
        )
    zona_exclusao = config.get_zona_exclusao()
    if zona_exclusao:
        print(f"{len(zona_exclusao)} area(s) de exclusao carregada(s) de ZONA_EXCLUSAO.")

    config.CAPTURAS_DIR.mkdir(parents=True, exist_ok=True)

    print_device_info(config.DEVICE)
    use_half = config.HALF_PRECISION and should_use_half(config.DEVICE)
    quantize = 16 if use_half else 32
    model = YOLO(config.MODEL_PATH)

    cap = open_capture()
    fps_meter = FPSMeter()
    last_fps_print = 0

    vaga = VagaState(
        tempo_confirmar=config.TEMPO_CONFIRMAR_ESTACIONADO_SEGUNDOS,
        tempo_tolerancia_saida=config.TEMPO_TOLERANCIA_SAIDA_SEGUNDOS,
        limite_minutos=config.LIMITE_MINUTOS_PERMITIDO,
    )
    evento_id_atual = None

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Conexao com o DVR perdida - tentando reconectar...")
                cap.release()
                cap = open_capture()
                print("Reconectado - retomando o monitoramento.")
                continue

            result = model.predict(
                frame,
                classes=list(config.VEHICLE_CLASS_IDS),
                conf=config.CONF_THRESHOLD,
                device=config.DEVICE,
                imgsz=config.IMGSZ,
                quantize=quantize,
                verbose=False,
            )[0]
            fps = fps_meter.tick()

            in_minima = False
            in_monitoramento = False
            boxes = result.boxes
            if boxes is not None:
                for xyxy, conf, cls_id in zip(boxes.xyxy.tolist(), boxes.conf.tolist(), boxes.cls.tolist()):
                    ponto = bbox_bottom_center(xyxy)
                    if zona_exclusao and point_in_any_polygon(zona_exclusao, ponto):
                        if args.debug:
                            print("[debug]   -> ignorado (dentro de ZONA_EXCLUSAO)")
                        continue

                    pertence_minima = point_in_any_polygon([zona_minima], ponto)
                    pertence_monitoramento = pertence_minima or point_in_any_polygon([zona_monitoramento], ponto)
                    in_minima = in_minima or pertence_minima
                    in_monitoramento = in_monitoramento or pertence_monitoramento

                    if args.debug:
                        nome = config.VEHICLE_CLASS_IDS.get(int(cls_id), f"classe_{int(cls_id)}")
                        print(
                            f"[debug] {nome} conf={conf:.2f} minima={pertence_minima} "
                            f"monitoramento={pertence_monitoramento}"
                        )

            evento = vaga.update(in_minima, in_monitoramento)
            if evento is not None:
                if evento["tipo"] == "entrada":
                    evento_id_atual = registrar_entrada(evento["entrada_ts"])
                    print(f"[{config.VAGA_ID}] Veiculo estacionou (evento {evento_id_atual}).")
                elif evento["tipo"] == "saida":
                    if evento_id_atual is not None:
                        registrar_saida(evento_id_atual, evento["saida_ts"], evento["duracao_segundos"])
                        print(
                            f"[{config.VAGA_ID}] Veiculo saiu (evento {evento_id_atual}), "
                            f"ficou {evento['duracao_segundos'] / 60:.1f} min."
                        )
                    evento_id_atual = None
                elif evento["tipo"] == "excesso":
                    nome_arquivo = f"{config.VAGA_ID}_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
                    caminho = config.CAPTURAS_DIR / nome_arquivo
                    cv2.imwrite(str(caminho), frame)
                    if evento_id_atual is not None:
                        registrar_excesso(evento_id_atual, str(caminho))
                    print(
                        f"[{config.VAGA_ID}] Excedeu {config.LIMITE_MINUTOS_PERMITIDO:.0f} min "
                        f"- foto salva em {caminho}"
                    )

            now = time.time()
            if now - last_fps_print >= 5:
                print(f"FPS: {fps:.1f}  estado={vaga.estado}")
                last_fps_print = now

            if not args.headless:
                annotated = result.plot()
                cv2.polylines(
                    annotated, [np.array(zona_monitoramento, dtype=np.int32)], isClosed=True, color=(0, 255, 0), thickness=2
                )
                cv2.polylines(
                    annotated, [np.array(zona_minima, dtype=np.int32)], isClosed=True, color=(255, 0, 0), thickness=2
                )
                for poligono in zona_exclusao:
                    cv2.polylines(
                        annotated, [np.array(poligono, dtype=np.int32)], isClosed=True, color=(0, 0, 255), thickness=2
                    )
                cv2.putText(
                    annotated, f"Estado: {vaga.estado}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2
                )
                cv2.putText(
                    annotated, f"FPS: {fps:.1f}", (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2
                )
                cv2.imshow("Vaga Rotativa", annotated)
                if cv2.waitKey(1) & 0xFF == ord("x"):
                    break
    except KeyboardInterrupt:
        print("\nInterrompido (Ctrl+C).")
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
