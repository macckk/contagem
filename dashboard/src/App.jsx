import { useState, useEffect, useMemo, useCallback } from "react";
import { supabase } from "./supabaseClient.js";
import FiltersBar from "./components/FiltersBar.jsx";
import StatTile from "./components/StatTile.jsx";
import ConfidenceCard from "./components/ConfidenceCard.jsx";
import LineChartCrossings from "./components/LineChartCrossings.jsx";
import BarChartTipos from "./components/BarChartTipos.jsx";
import BarChartPorDia from "./components/BarChartPorDia.jsx";
import TableView from "./components/TableView.jsx";
import VagaRotativa from "./components/VagaRotativa.jsx";
import {
  rangeStartFor,
  computeStats,
  aggregateByHour,
  aggregateByDay,
  aggregateByTipoVeiculo,
  confidenceHistogram,
} from "./lib/aggregate.js";

function getInitialTheme() {
  const saved = localStorage.getItem("theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

// A API do Supabase (PostgREST) limita cada resposta a "db-max-rows" (1000
// por padrao), mesmo pedindo um .limit() maior - entao paginamos com
// .range() ate a pagina voltar vazia/incompleta, para trazer todos os
// eventos do periodo, nao so os primeiros 1000.
async function fetchEventsSince(since) {
  const pageSize = 1000;
  let all = [];
  let from = 0;
  while (true) {
    let query = supabase
      .from("contagem_eventos")
      .select("id, track_id, tipo, confianca, timestamp")
      .order("timestamp", { ascending: true })
      .range(from, from + pageSize - 1);

    if (since) query = query.gte("timestamp", since.toISOString());

    const { data, error: qError } = await query;
    if (qError) throw qError;

    all = all.concat(data ?? []);
    if (!data || data.length < pageSize) break;
    from += pageSize;
  }
  return all;
}

export default function App() {
  const [view, setView] = useState("contagem");
  const [range, setRange] = useState("hoje");
  const [confMin, setConfMin] = useState(0);
  const [events, setEvents] = useState([]);
  const [events7d, setEvents7d] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // O grafico "Total por dia" sempre mostra os ultimos 7 dias,
      // independente do filtro de periodo escolhido acima (ex: se o
      // usuario esta em "Hoje", ainda queremos comparar com os dias
      // anteriores) - por isso busca numa janela fixa, separada de
      // 'events'.
      const seteDiasAtras = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
      const [principal, ultimos7Dias] = await Promise.all([
        fetchEventsSince(rangeStartFor(range)),
        fetchEventsSince(seteDiasAtras),
      ]);
      setEvents(principal);
      setEvents7d(ultimos7Dias);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err.message ?? "Falha ao carregar dados do Supabase.");
    } finally {
      setLoading(false);
    }
  }, [range]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const filtered = useMemo(
    () => events.filter((e) => (e.confianca ?? 0) >= confMin),
    [events, confMin]
  );
  const filtered7d = useMemo(
    () => events7d.filter((e) => (e.confianca ?? 0) >= confMin),
    [events7d, confMin]
  );

  const stats = useMemo(() => computeStats(filtered), [filtered]);
  const byHour = useMemo(() => aggregateByHour(filtered), [filtered]);
  const byDay = useMemo(() => aggregateByDay(filtered7d).slice(-7), [filtered7d]);
  const byTipo = useMemo(() => aggregateByTipoVeiculo(filtered), [filtered]);
  const histogram = useMemo(() => confidenceHistogram(filtered), [filtered]);

  return (
    <div className="app-shell">
      <div className="bg-blobs" />

      <header className="dash-header">
        <div>
          <h1>{view === "contagem" ? "Contagem de Pessoas e Veículos" : "Vaga Rotativa"}</h1>
          {view === "contagem" && (
            <p>
              {lastUpdated
                ? `Atualizado às ${lastUpdated.toLocaleTimeString("pt-BR")}`
                : "Carregando…"}
            </p>
          )}
        </div>
        <div className="header-actions">
          <div className="pill-group">
            <button
              className={`pill ${view === "contagem" ? "active" : ""}`}
              onClick={() => setView("contagem")}
            >
              Contagem
            </button>
            <button
              className={`pill ${view === "vaga" ? "active" : ""}`}
              onClick={() => setView("vaga")}
            >
              Vaga Rotativa
            </button>
          </div>
          <button
            className="theme-toggle-btn"
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
            title={theme === "dark" ? "Mudar para tema claro" : "Mudar para tema escuro"}
            aria-label="Alternar tema claro/escuro"
          >
            {theme === "dark" ? "☀️" : "🌙"}
          </button>
          {view === "contagem" && (
            <button
              className={`refresh-btn ${loading ? "loading" : ""}`}
              onClick={fetchEvents}
              disabled={loading}
            >
              <span className="refresh-icon">⟳</span>
              {loading ? "Atualizando…" : "Atualizar"}
            </button>
          )}
        </div>
      </header>

      {view === "vaga" ? (
        <VagaRotativa />
      ) : (
        <>
          {error && <div className="error-banner">Erro ao carregar dados: {error}</div>}

          <FiltersBar
            range={range}
            onRangeChange={setRange}
            confMin={confMin}
            onConfChange={setConfMin}
          />

          <div className="kpi-grid">
            <StatTile
              label="Pessoas"
              value={stats.totalPessoas}
              dotColor="var(--series-pessoas)"
              sub="cruzamentos no período"
            />
            <StatTile
              label="Veículos"
              value={stats.totalVeiculos}
              dotColor="var(--series-veiculos)"
              sub="cruzamentos no período"
            />
            <ConfidenceCard confMedia={stats.confMedia} histogram={histogram} />
            <StatTile
              label="Pico de horário"
              value={stats.picoContagem}
              sub={`às ${String(stats.picoHora).padStart(2, "0")}h`}
            />
          </div>

          {!loading && filtered.length === 0 && byDay.length === 0 ? (
            <div className="glass-card empty-state">
              Nenhum evento encontrado para os filtros atuais.
            </div>
          ) : (
            <>
              {filtered.length > 0 && (
                <div className="charts-grid">
                  <LineChartCrossings data={byHour} />
                  <BarChartTipos data={byTipo} />
                </div>
              )}
              {byDay.length > 0 && (
                <div className="charts-grid charts-grid-single">
                  <BarChartPorDia data={byDay} />
                </div>
              )}
              {filtered.length > 0 && <TableView events={filtered} />}
            </>
          )}
        </>
      )}

      <footer className="dash-footer">
        <a href="https://github.com/macckk/contagem" target="_blank" rel="noreferrer">
          github.com/macckk/contagem
        </a>
      </footer>
    </div>
  );
}
