const RANGE_OPTIONS = [
  { key: "hoje", label: "Hoje" },
  { key: "7dias", label: "7 dias" },
  { key: "30dias", label: "30 dias" },
  { key: "tudo", label: "Tudo" },
];

export default function FiltersBar({ range, onRangeChange, confMin, onConfChange }) {
  const pct = Math.round(confMin * 100);
  const fillPct = (confMin / 0.95) * 100;

  return (
    <div className="glass-card filters-bar">
      <div className="filter-group">
        <span className="filter-label">Período</span>
        <div className="pill-group">
          {RANGE_OPTIONS.map((o) => (
            <button
              key={o.key}
              className={`pill ${range === o.key ? "active" : ""}`}
              onClick={() => onRangeChange(o.key)}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>

      <div className="conf-slider-wrap">
        <span className="filter-label">Confiança mín.</span>
        <input
          type="range"
          min="0"
          max="0.95"
          step="0.05"
          value={confMin}
          onChange={(e) => onConfChange(parseFloat(e.target.value))}
          className="conf-slider"
          style={{ "--fill-pct": `${fillPct}%` }}
          aria-label="Confiança mínima"
        />
        <span className="conf-value">{pct}%</span>
      </div>
    </div>
  );
}
