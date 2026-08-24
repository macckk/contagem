"""Insercao/atualizacao de eventos de ocupacao da vaga no Supabase (tabela vaga_eventos).

Ver vaga_rotativa/sql/schema.sql. Usa o mesmo projeto Supabase do app de contagem de
pessoas/veiculos (credenciais proprias em vaga_rotativa/.env), so numa tabela nova.
"""
from datetime import datetime, timezone

from supabase import Client, create_client

from vaga_rotativa import config

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        if not config.SUPABASE_URL or not config.SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL / SUPABASE_KEY nao configurados no vaga_rotativa/.env")
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    return _client


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def registrar_entrada(entrada_ts: float) -> int:
    """Insere uma sessao de ocupacao (saida ainda nula) e retorna o id gerado."""
    resultado = (
        get_client()
        .table("vaga_eventos")
        .insert({"vaga_id": config.VAGA_ID, "entrada": _iso(entrada_ts)})
        .execute()
    )
    return resultado.data[0]["id"]


def registrar_saida(evento_id: int, saida_ts: float, duracao_segundos: float) -> None:
    get_client().table("vaga_eventos").update(
        {"saida": _iso(saida_ts), "duracao_segundos": int(duracao_segundos)}
    ).eq("id", evento_id).execute()


def registrar_excesso(evento_id: int, imagem_path: str) -> None:
    get_client().table("vaga_eventos").update(
        {"excedeu_limite": True, "imagem_path": imagem_path}
    ).eq("id", evento_id).execute()
