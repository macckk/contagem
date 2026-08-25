"""Ferramenta de calibracao das zonas da Vaga Rotativa.

Captura um frame do DVR, mostra numa janela e permite clicar 4 pontos definindo
um poligono (na ordem, sentido horario ou anti-horario). Ao final, imprime a
variavel para colar no vaga_rotativa/.env.

Uso:
    python vaga_rotativa/scripts/calibrar_zonas.py --alvo exclusao       # vermelho - opcional, pode repetir
    python vaga_rotativa/scripts/calibrar_zonas.py --alvo monitoramento  # verde - area da propria vaga

A zona de monitoramento (verde) deve cobrir a area da vaga em si - e usada
tanto para confirmar que o veiculo estacionou quanto para sustentar a sessao
(tolera pequenas oscilacoes de posicao sem encerrar a toa). A de exclusao
(vermelho) e opcional; pode ter mais de uma - rode de novo e junte os blocos
com ";" no .env.
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.rtsp_client import RTSPClient
from vaga_rotativa import config

points = []


def on_click(event, x, y, flags, userdata):
    if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
        points.append((x, y))
        print(f"Ponto {len(points)}: ({x}, {y})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--alvo",
        choices=["exclusao", "monitoramento"],
        required=True,
        help="Qual zona calibrar (ver docstring do arquivo).",
    )
    args = parser.parse_args()
    env_var = {
        "exclusao": "ZONA_EXCLUSAO",
        "monitoramento": "ZONA_MONITORAMENTO",
    }[args.alvo]

    if not config.RTSP_URL:
        raise SystemExit(
            "RTSP_URL nao configurada. Copie vaga_rotativa/.env.example para "
            "vaga_rotativa/.env e preencha."
        )

    cap = RTSPClient(config.RTSP_URL)
    if not cap.isOpened():
        raise SystemExit(f"Nao foi possivel abrir o stream RTSP: {config.RTSP_URL}")

    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise SystemExit("Nao foi possivel capturar um frame do stream.")

    window = f"Clique 4 pontos para a area de {args.alvo} (q para sair)"
    cv2.namedWindow(window)
    cv2.setMouseCallback(window, on_click)

    while True:
        display = frame.copy()
        for p in points:
            cv2.circle(display, p, 5, (0, 0, 255), -1)
        if len(points) == 4:
            cv2.polylines(display, [np.array(points, dtype=np.int32)], isClosed=True, color=(0, 255, 0), thickness=2)

        cv2.imshow(window, display)
        key = cv2.waitKey(20) & 0xFF
        if key == ord("q") or len(points) == 4:
            cv2.waitKey(1500)
            break

    cv2.destroyAllWindows()

    if len(points) == 4:
        coords = ",".join(f"{x},{y}" for x, y in points)
        if args.alvo == "exclusao":
            print("\nAdicione ao seu vaga_rotativa/.env (junte com ';' se ja tiver outra area):")
        else:
            print("\nAdicione ao seu vaga_rotativa/.env:")
        print(f"{env_var}={coords}")
    else:
        print("Calibracao cancelada (menos de 4 pontos definidos).")


if __name__ == "__main__":
    main()
