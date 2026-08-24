-- Mesmo padrao de sql/migrations/004_rls_leitura_publica.sql do projeto de
-- contagem: o dashboard le vaga_eventos direto do navegador com a chave
-- "anon public" - RLS + policy de SELECT garante que essa chave so consegue
-- ler, nunca escrever (quem grava e o script Python, com a service_role).
alter table vaga_eventos enable row level security;

drop policy if exists "Leitura publica para o dashboard" on vaga_eventos;

create policy "Leitura publica para o dashboard"
  on vaga_eventos
  for select
  to anon
  using (true);
