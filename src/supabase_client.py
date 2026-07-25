"""Insercao de eventos de contagem no Supabase."""
from supabase import Client, create_client

from src import config

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        if not config.SUPABASE_URL or not config.SUPABASE_KEY:
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_KEY nao configurados no .env"
            )
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    return _client


def insert_event(track_id: int, confianca: float) -> None:
    """Insere um evento de cruzamento na tabela contagem_eventos."""
    get_client().table("contagem_eventos").insert(
        {
            "camera_id": config.CAMERA_ID,
            "track_id": track_id,
            "confianca": confianca,
        }
    ).execute()
