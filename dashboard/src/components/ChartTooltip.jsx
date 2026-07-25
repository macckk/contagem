export default function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <div style={{ fontWeight: 700, marginBottom: 4 }}>{label}</div>
      {payload.map((p) => (
        <div className="tt-row" key={p.dataKey ?? p.name}>
          <span className="stat-dot" style={{ background: p.color ?? p.fill }} />
          {p.name}: {p.value}
        </div>
      ))}
    </div>
  );
}
