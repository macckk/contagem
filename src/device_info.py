"""Mostra qual dispositivo (CPU/GPU) o PyTorch vai usar para a inferencia."""


def print_device_info(device_setting):
    try:
        import torch
    except ImportError:
        print("PyTorch nao encontrado - nao foi possivel checar GPU.")
        return

    if device_setting == "cpu":
        print("DEVICE=cpu configurado explicitamente - rodando em CPU (GPU ignorada).")
        return

    if not torch.cuda.is_available():
        print("Nenhuma GPU CUDA detectada pelo PyTorch - rodando em CPU.")
        return

    idx = int(device_setting) if device_setting not in (None, "") else 0
    nome = torch.cuda.get_device_name(idx)
    total_mem_gb = torch.cuda.get_device_properties(idx).total_memory / (1024**3)
    print(f"GPU detectada: {nome} (cuda:{idx}, {total_mem_gb:.1f} GB) - device usado na inferencia.")
