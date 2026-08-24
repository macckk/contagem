create table vaga_eventos (
  id bigserial primary key,
  vaga_id text not null default 'vaga_01',
  entrada timestamptz not null,
  saida timestamptz,
  duracao_segundos integer,
  excedeu_limite boolean not null default false,
  imagem_path text,
  created_at timestamptz not null default now()
);

create index idx_vaga_eventos_vaga_periodo on vaga_eventos (vaga_id, entrada);
