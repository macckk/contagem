"""Ferramenta de calibracao da linha de contagem.

Captura um unico frame do RTSP, mostra em uma janela e permite clicar 2
pontos com o mouse (clique esquerdo) para definir a linha virtual. Ao final,
imprime as coordenadas para colar no .env.

Uso:
    python scripts/calibrar_linha.py                          # linha de pessoas (calcada)
    python scripts/calibrar_linha.py --alvo veiculos           # linha de veiculos (via), de dia
    python scripts/calibrar_linha.py --alvo veiculos-noite     # linha de veiculos a noite (rode isso de noite!)
    python scripts/calibrar_linha.py --alvo exclusao           # retangulo de area a ignorar na deteccao

A linha de veiculos-noite e opcional: se nao for calibrada, a contagem
noturna usa a mesma linha/zona de veiculos do dia. Vale calibrar separado
porque a noite o veiculo costuma ser detectado com mais confianca assim
que entra no quadro (antes do farol saturar a cena de perto) - um lugar
diferente do ponto ideal para a linha de dia.

O modo "exclusao" e diferente dos outros: em vez de uma linha, clique 4
pontos definindo um poligono (na ordem, sentido horario ou anti-horario)
- a area a ignorar na deteccao (EXCLUDE_ZONES no .env), util quando a
regiao real nao e um retangulo perfeito (ex: um muro em diagonal). Qualquer
deteccao com o ponto de contato (base da caixa) dentro do poligono e
ignorada, antes mesmo do tracking/contagem. Pode ter mais de uma area:
rode de novo e junte os blocos com ";" no .env
(formato "x1,y1,x2,y2,x3,y3,x4,y4;x1,y1,x2,y2,x3,y3,x4,y4").
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config
from src.rtsp_client import RTSPClient

points = []
num_pontos = 2


def on_click(event, x, y, flags, userdata):
    if event == cv2.EVENT_LBUTTONDOWN and len(points) < num_pontos:
        points.append((x, y))
        print(f"Ponto {len(points)}: ({x}, {y})")


def main():
    global num_pontos

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--alvo",
        choices=["pessoas", "veiculos", "veiculos-noite", "exclusao"],
        default="pessoas",
        help="Qual calibrar: pessoas (calcada), veiculos (via, de dia), veiculos-noite ou "
        "exclusao (poligono de 4 pontos, area a ignorar na deteccao). Padrao: pessoas.",
    )
    args = parser.parse_args()
    is_exclusao = args.alvo == "exclusao"
    num_pontos = 4 if is_exclusao else 2
    env_prefix = {
        "pessoas": "LINE_",
        "veiculos": "LINE_VEICULOS_",
        "veiculos-noite": "LINE_VEICULOS_NOITE_",
    }.get(args.alvo)

    if not config.RTSP_URL:
        raise SystemExit("RTSP_URL nao configurada. Copie .env.example para .env e preencha.")

    cap = RTSPClient(config.RTSP_URL)
    if not cap.isOpened():
        raise SystemExit(f"Nao foi possivel abrir o stream RTSP: {config.RTSP_URL}")

    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise SystemExit("Nao foi possivel capturar um frame do stream.")

    window = f"Clique {num_pontos} pontos para {args.alvo} (q para sair)"
    cv2.namedWindow(window)
    cv2.setMouseCallback(window, on_click)

    while True:
        display = frame.copy()
        for p in points:
            cv2.circle(display, p, 5, (0, 0, 255), -1)
        if len(points) == num_pontos:
            if is_exclusao:
                cv2.polylines(display, [np.array(points, dtype=np.int32)], isClosed=True, color=(0, 0, 255), thickness=2)
            else:
                cv2.line(display, points[0], points[1], (0, 255, 0), 2)

        cv2.imshow(window, display)
        key = cv2.waitKey(20) & 0xFF
        if key == ord("q") or len(points) == num_pontos:
            cv2.waitKey(1500)
            break

    cv2.destroyAllWindows()

    if len(points) == num_pontos:
        if is_exclusao:
            coords = ",".join(f"{x},{y}" for x, y in points)
            print("\nAdicione ao seu .env (junte com ';' se ja tiver outra area):")
            print(f"EXCLUDE_ZONES={coords}")
        else:
            (x1, y1), (x2, y2) = points
            print("\nAdicione ao seu .env:")
            print(f"{env_prefix}X1={x1}")
            print(f"{env_prefix}Y1={y1}")
            print(f"{env_prefix}X2={x2}")
            print(f"{env_prefix}Y2={y2}")
    else:
        print(f"Calibracao cancelada (menos de {num_pontos} pontos definidos).")


if __name__ == "__main__":
    main()
