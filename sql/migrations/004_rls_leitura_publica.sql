-- O dashboard e uma pagina estatica publica (GitHub Pages) que le a tabela
-- direto do navegador usando a chave "anon public" do Supabase - nunca a
-- service_role. RLS habilitado + uma policy de SELECT restringe o que essa
-- chave anon pode fazer a "so ler", sem permissao de escrita.
alter table contagem_eventos enable row level security;

drop policy if exists "Leitura publica para o dashboard" on contagem_eventos;

create policy "Leitura publica para o dashboard"
  on contagem_eventos
  for select
  to anon
  using (true);
