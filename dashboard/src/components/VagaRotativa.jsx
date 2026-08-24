import { useState, useEffect, useCallback, useMemo } from "react";
import { supabase } from "../supabaseClient.js";

function formatDuracao(segundos) {
  const total = Math.max(0, Math.floor(segundos));
  const min = Math.floor(total / 60);
  const seg = total % 60;
  if (min <= 0) return `${seg}s`;
  return `${min}min ${seg}s`;
}

export default function VagaRotativa() {
  const [eventos, setEventos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [agora, setAgora] = useState(Date.now());

  const fetchEventos = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const desde = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
      const { data, error: qError } = await supabase
        .from("vaga_eventos")
        .select("id, vaga_id, entrada, saida, duracao_segundos, excedeu_limite")
        .gte("entrada", desde.toISOString())
        .order("entrada", { ascending: false })
        .limit(300);
      if (qError) throw qError;
      setEventos(data ?? []);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err.message ?? "Falha ao carregar dados da vaga.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEventos();
  }, [fetchEventos]);

  // Contador do tempo ao vivo enquanto a vaga estiver ocupada.
  useEffect(() => {
    const id = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const atual = useMemo(() => eventos.find((e) => !e.saida) ?? null, [eventos]);
  const ultimas24h = useMemo(() => {
    const desde = Date.now() - 24 * 60 * 60 * 1000;
    return eventos.filter((e) => new Date(e.entrada).getTime() >= desde);
  }, [eventos]);
  const concluidas = useMemo(() => eventos.filter((e) => e.saida), [eventos]);
  const duracaoMediaMin = useMemo(() => {
    if (!concluidas.length) return 0;
    const mediaSegundos = concluidas.reduce((acc, e) => acc + (e.duracao_segundos ?? 0), 0) / concluidas.length;
    return mediaSegundos / 60;
  }, [concluidas]);

  return (
    <div>
      <div className="dash-header" style={{ marginBottom: 24 }}>
        <div>
          <h1>Vaga Rotativa</h1>
          <p>
            {lastUpdated
              ? `Atualizado às ${lastUpdated.toLocaleTimeString("pt-BR")}`
              : "Carregando…"}
          </p>
        </div>
        <button
          className={`refresh-btn ${loading ? "loading" : ""}`}
          onClick={fetchEventos}
          disabled={loading}
        >
          <span className="refresh-icon">⟳</span>
          {loading ? "Atualizando…" : "Atualizar"}
        </button>
      </div>

      {error && <div className="error-banner">Erro ao carregar dados: {error}</div>}

      <div className="kpi-grid">
        <div className="glass-card stat-tile">
          <span className="stat-label">
            <span
              className="stat-dot"
              style={{ background: atual ? "var(--series-veiculos)" : "var(--success)" }}
            />
            Status da vaga
          </span>
          <span className="stat-value" style={{ fontSize: 26 }}>
            {atual ? "Ocupada" : "Livre"}
          </span>
          <span className="stat-sub">
            {atual
              ? `há ${formatDuracao((agora - new Date(atual.entrada).getTime()) / 1000)}`
              : "nenhum veículo no momento"}
          </span>
        </div>
        <div className="glass-card stat-tile">
          <span className="stat-label">Veículos (24h)</span>
          <span className="stat-value">{ultimas24h.length}</span>
          <span className="stat-sub">sessões iniciadas</span>
        </div>
        <div className="glass-card stat-tile">
          <span className="stat-label">Tempo médio</span>
          <span className="stat-value">{duracaoMediaMin.toFixed(1)} min</span>
          <span className="stat-sub">sessões concluídas, últimos 7 dias</span>
        </div>
      </div>

      <div className="glass-card table-card">
        <p className="chart-sub" style={{ margin: "0 0 8px" }}>
          Histórico de ocupação (últimos 7 dias)
        </p>
        {eventos.length === 0 ? (
          <div className="empty-state">Nenhum evento registrado nos últimos 7 dias.</div>
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Entrada</th>
                  <th>Saída</th>
                  <th>Duração</th>
                  <th>Excedeu 15min?</th>
                </tr>
              </thead>
              <tbody>
                {eventos.slice(0, 50).map((e) => (
                  <tr key={e.id}>
                    <td>{new Date(e.entrada).toLocaleString("pt-BR")}</td>
                    <td>{e.saida ? new Date(e.saida).toLocaleString("pt-BR") : "— (ocupada)"}</td>
                    <td>
                      {e.duracao_segundos != null
                        ? formatDuracao(e.duracao_segundos)
                        : formatDuracao((agora - new Date(e.entrada).getTime()) / 1000)}
                    </td>
                    <td>{e.excedeu_limite ? "Sim" : "Não"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {eventos.length > 50 && (
              <p className="chart-sub" style={{ marginTop: 8 }}>
                Mostrando os 50 mais recentes de {eventos.length} eventos.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
