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
    python vaga_rotativa/scripts/monitorar_vaga.py --gravar    # grava um video por sessao de ocupacao

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


def draw_zona_preenchida(frame, poligono, color, alpha=0.25):
    """Desenha um poligono preenchido com transparencia (mesmo padrao de
    draw_zone em scripts/02_tracking.py e 03_pipeline.py) - mais legivel na
    tela que so o contorno."""
    pts = np.array(poligono, dtype=np.int32)
    overlay = frame.copy()
    cv2.fillPoly(overlay, [pts], color)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=1)


def bbox_ponto_referencia(xyxy):
    """Ponto de contato usado para testar as zonas: base da caixa, deslocado
    25% da largura para a esquerda do centro (ajustado empiricamente - o
    centro exato as vezes caia fora da vaga dependendo do angulo da camera)."""
    x1, y1, x2, y2 = xyxy
    largura = x2 - x1
    return (x1 + 0.25 * largura, y2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Mostra no console detalhes de cada deteccao/zona por frame")
    parser.add_argument("--headless", action="store_true", help="Nao abrir janela de video")
    parser.add_argument(
        "--gravar",
        action="store_true",
        help="Grava um video por sessao de ocupacao (da entrada na zona de monitoramento ate "
        "a saida) em vaga_rotativa/gravacoes/*.mp4 - util para exemplos na documentacao.",
    )
    parser.add_argument(
        "--fps-gravacao",
        type=float,
        default=12.0,
        help="FPS do arquivo gravado (opcional, so com --gravar). Padrao: 12.0 - ajuste para "
        "perto do FPS real exibido no console, senao o video grava rapido/lento demais.",
    )
    args = parser.parse_args()

    if not config.RTSP_URL:
        raise SystemExit(
            "RTSP_URL nao configurada. Copie vaga_rotativa/.env.example para "
            "vaga_rotativa/.env e preencha."
        )

    zona_monitoramento = config.get_zona_monitoramento()
    if zona_monitoramento is None:
        raise SystemExit(
            "Zona de monitoramento nao calibrada. Rode "
            "'python vaga_rotativa/scripts/calibrar_zonas.py --alvo monitoramento', "
            "preenchendo ZONA_MONITORAMENTO no vaga_rotativa/.env."
        )
    zona_exclusao = config.get_zona_exclusao()
    if zona_exclusao:
        print(f"{len(zona_exclusao)} area(s) de exclusao carregada(s) de ZONA_EXCLUSAO.")

    config.CAPTURAS_DIR.mkdir(parents=True, exist_ok=True)
    gravacoes_dir = Path(__file__).resolve().parent.parent / "gravacoes"
    if args.gravar:
        gravacoes_dir.mkdir(parents=True, exist_ok=True)

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
    video_writer = None
    video_path = None

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

            in_monitoramento = False
            boxes = result.boxes
            if boxes is not None:
                for xyxy, conf, cls_id in zip(boxes.xyxy.tolist(), boxes.conf.tolist(), boxes.cls.tolist()):
                    ponto = bbox_ponto_referencia(xyxy)
                    if zona_exclusao and point_in_any_polygon(zona_exclusao, ponto):
                        if args.debug:
                            print("[debug]   -> ignorado (dentro de ZONA_EXCLUSAO)")
                        continue

                    pertence_monitoramento = point_in_any_polygon([zona_monitoramento], ponto)
                    in_monitoramento = in_monitoramento or pertence_monitoramento

                    if args.debug:
                        nome = config.VEHICLE_CLASS_IDS.get(int(cls_id), f"classe_{int(cls_id)}")
                        print(f"[debug] {nome} conf={conf:.2f} monitoramento={pertence_monitoramento}")

            estado_antes = vaga.estado
            evento = vaga.update(in_monitoramento)
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

            if not args.headless or args.gravar:
                annotated = result.plot()
                draw_zona_preenchida(annotated, zona_monitoramento, (0, 255, 0))
                for poligono in zona_exclusao:
                    draw_zona_preenchida(annotated, poligono, (0, 0, 255))
                texto_estado = f"Estado: {vaga.estado}"
                (texto_w, _), _ = cv2.getTextSize(texto_estado, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)
                cv2.putText(
                    annotated,
                    texto_estado,
                    (annotated.shape[1] - texto_w - 10, annotated.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (255, 255, 255),
                    2,
                )

                if args.gravar:
                    if estado_antes == VagaState.LIVRE and vaga.estado == VagaState.PENDENTE:
                        nome_arquivo = f"vaga_{config.VAGA_ID}_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
                        video_path = gravacoes_dir / nome_arquivo
                        altura, largura = annotated.shape[:2]
                        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                        video_writer = cv2.VideoWriter(str(video_path), fourcc, args.fps_gravacao, (largura, altura))
                        print(f"[{config.VAGA_ID}] Gravando sessao em: {video_path}")

                    if video_writer is not None:
                        video_writer.write(annotated)

                    if estado_antes in (VagaState.PENDENTE, VagaState.OCUPADA) and vaga.estado == VagaState.LIVRE:
                        if video_writer is not None:
                            video_writer.release()
                            print(f"[{config.VAGA_ID}] Video da sessao salvo em: {video_path}")
                            video_writer = None

                if not args.headless:
                    cv2.imshow("Vaga Rotativa", annotated)
                    if cv2.waitKey(1) & 0xFF == ord("x"):
                        break
    except KeyboardInterrupt:
        print("\nInterrompido (Ctrl+C).")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if video_writer is not None:
            video_writer.release()
            print(f"[{config.VAGA_ID}] Video da sessao (interrompida) salvo em: {video_path}")


if __name__ == "__main__":
    main()
