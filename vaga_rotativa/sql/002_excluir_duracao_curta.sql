-- Exclui automaticamente registros de vaga_eventos com duracao_segundos menor
-- que 50s assim que a saida e gravada - normalmente ruido de deteccao (carro
-- passando devagar, moto, pedestre classificado errado) que passou pelo
-- TEMPO_CONFIRMAR_ESTACIONADO_SEGUNDOS por pouco, mas nao representa uma
-- ocupacao real da vaga.
--
-- Ajuste o "50" abaixo se quiser um limiar diferente.
create or replace function vaga_excluir_duracao_curta()
returns trigger as $$
begin
  if new.duracao_segundos is not null and new.duracao_segundos < 50 then
    delete from vaga_eventos where id = new.id;
    return null;
  end if;
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_vaga_excluir_duracao_curta on vaga_eventos;

create trigger trg_vaga_excluir_duracao_curta
after insert or update of duracao_segundos on vaga_eventos
for each row
execute function vaga_excluir_duracao_curta();
