-- A coluna "tipo" gravava so 'pessoa' ou o generico 'veiculo'. Para saber
-- quantos carros/motos/onibus/caminhoes/bicicletas passaram (nao so o total
-- agregado de veiculos), o tipo especifico passa a ser gravado.
alter table contagem_eventos drop constraint if exists contagem_eventos_tipo_check;

alter table contagem_eventos
  add constraint contagem_eventos_tipo_check
  check (tipo in ('pessoa', 'car', 'motorcycle', 'bus', 'truck', 'bicycle'));
