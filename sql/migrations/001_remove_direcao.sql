-- A tabela contagem_eventos ja foi criada com a coluna "direcao" (entrada/saida).
-- Como a contagem passou a ser so "quem cruzou a faixa", sem distinguir direcao,
-- essa coluna deixou de ser necessaria.
alter table contagem_eventos drop column if exists direcao;
