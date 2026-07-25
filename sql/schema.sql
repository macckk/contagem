create table contagem_eventos (
  id bigserial primary key,
  camera_id text not null,
  track_id integer not null,
  confianca numeric,
  timestamp timestamptz not null default now()
);

create index idx_contagem_eventos_camera_timestamp
  on contagem_eventos (camera_id, timestamp);
