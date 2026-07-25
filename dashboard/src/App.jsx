import { useState, useEffect, useMemo, useCallback } from "react";
import { supabase } from "./supabaseClient.js";
import FiltersBar from "./components/FiltersBar.jsx";
import StatTile from "./components/StatTile.jsx";
import ConfidenceCard from "./components/ConfidenceCard.jsx";
import LineChartCrossings from "./components/LineChartCrossings.jsx";
import BarChartTipos from "./components/BarChartTipos.jsx";
import TableView from "./components/TableView.jsx";
import {
  rangeStartFor,
  computeStats,
  aggregateByHour,
  aggregateByTipoVeiculo,
  confidenceHistogram,
} from "./lib/aggregate.js";

export default function App() {
  const [range, setRange] = useState("hoje");
  const [confMin, setConfMin] = useState(0);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let query = supabase
        .from("contagem_eventos")
        .select("id, track_id, tipo, confianca, timestamp")
        .order("timestamp", { ascending: true })
        .limit(20000);

      const since = rangeStartFor(range);
      if (since) query = query.gte("timestamp", since.toISOString());

      const { data, error: qError } = await query;
      if (qError) throw qError;
      setEvents(data ?? []);
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

  const stats = useMemo(() => computeStats(filtered), [filtered]);
  const byHour = useMemo(() => aggregateByHour(filtered), [filtered]);
  const byTipo = useMemo(() => aggregateByTipoVeiculo(filtered), [filtered]);
  const histogram = useMemo(() => confidenceHistogram(filtered), [filtered]);

  return (
    <div className="app-shell">
      <div className="bg-blobs" />

      <header className="dash-header">
        <div>
          <h1>Contagem de Pessoas e Veículos</h1>
          <p>
            {lastUpdated
              ? `Atualizado às ${lastUpdated.toLocaleTimeString("pt-BR")}`
              : "Carregando…"}
          </p>
        </div>
        <button
          className={`refresh-btn ${loading ? "loading" : ""}`}
          onClick={fetchEvents}
          disabled={loading}
        >
          <span className="refresh-icon">⟳</span>
          {loading ? "Atualizando…" : "Atualizar"}
        </button>
      </header>

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

      {!loading && filtered.length === 0 ? (
        <div className="glass-card empty-state">
          Nenhum evento encontrado para os filtros atuais.
        </div>
      ) : (
        <>
          <div className="charts-grid">
            <LineChartCrossings data={byHour} />
            <BarChartTipos data={byTipo} />
          </div>
          <TableView events={filtered} />
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
