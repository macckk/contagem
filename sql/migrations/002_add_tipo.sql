-- Adiciona a distincao entre eventos de pessoa e de veiculo, agora que a
-- camera tambem pode contar veiculos passando na via (alem de pessoas na
-- calcada). Eventos existentes (todos de pessoas) recebem o default 'pessoa'.
alter table contagem_eventos
  add column if not exists tipo text not null default 'pessoa'
  check (tipo in ('pessoa', 'veiculo'));
