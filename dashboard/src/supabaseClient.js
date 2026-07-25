import { createClient } from "@supabase/supabase-js";

// Chave "anon public" do Supabase - projetada para ser publica (protegida
// por RLS, ver sql/migrations/004_rls_leitura_publica.sql). Nunca colocar a
// service_role aqui: essa dá acesso total ao banco, ignorando RLS.
const SUPABASE_URL = "https://xaivrjjdjguyrzjcnelx.supabase.co";
const SUPABASE_ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhhaXZyampkamd1eXJ6amNuZWx4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDA0MDg2ODAsImV4cCI6MjA1NTk4NDY4MH0.n55JGUxODTaYs3YlX7JqMpL7mQMnWhEsuog7KzNeJ98";

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
