import { useState, useEffect, useCallback, useMemo } from "react";
import { supabase } from "../supabaseClient.js";

function formatDuracao(segundos) {
  const total = Math.max(0, Math.floor(segundos));
  const min = Math.floor(total / 60);
  const seg = total % 60;
  if (min <= 0) return `${seg}s`;
  return `${min}min ${seg}s`;
}

function formatHora(iso) {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function agruparPorDia(eventos) {
  const grupos = new Map();
  for (const e of eventos) {
    const d = new Date(e.entrada);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    if (!grupos.has(key)) grupos.set(key, { key, data: d, eventos: [] });
    grupos.get(key).eventos.push(e);
  }
  return Array.from(grupos.values()).sort((a, b) => b.key.localeCompare(a.key));
}

function formatDiaLabel(data) {
  const hoje = new Date();
  const ontem = new Date(hoje);
  ontem.setDate(hoje.getDate() - 1);
  const mesmoDia = (a, b) => a.toDateString() === b.toDateString();
  if (mesmoDia(data, hoje)) return "Hoje";
  if (mesmoDia(data, ontem)) return "Ontem";
  return data.toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
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
  const porDia = useMemo(() => agruparPorDia(eventos), [eventos]);

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

      <p className="chart-sub" style={{ margin: "0 0 12px" }}>
        Histórico de ocupação, separado por dia (últimos 7 dias)
      </p>

      {porDia.length === 0 ? (
        <div className="glass-card empty-state">Nenhum evento registrado nos últimos 7 dias.</div>
      ) : (
        porDia.map((grupo) => (
          <div className="glass-card table-card" key={grupo.key} style={{ marginBottom: 16 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                marginBottom: 8,
              }}
            >
              <p style={{ margin: 0, fontWeight: 600, color: "var(--text-primary)" }}>
                {formatDiaLabel(grupo.data)}
              </p>
              <p className="chart-sub" style={{ margin: 0 }}>
                {grupo.eventos.length} veículo{grupo.eventos.length !== 1 ? "s" : ""}
              </p>
            </div>
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
                  {grupo.eventos.map((e) => (
                    <tr key={e.id}>
                      <td>{formatHora(e.entrada)}</td>
                      <td>{e.saida ? formatHora(e.saida) : "— (ocupada)"}</td>
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
            </div>
          </div>
        ))
      )}
    </div>
  );
}
