import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import ChartTooltip from "./ChartTooltip.jsx";

export default function BarChartPorDia({ data }) {
  return (
    <div className="glass-card chart-card">
      <h3>Total por dia</h3>
      <p className="chart-sub">Pessoas vs. veículos, agrupado por dia do mês</p>
      <div className="legend-row">
        <span className="legend-item">
          <span className="stat-dot" style={{ background: "var(--series-pessoas)" }} />
          Pessoas
        </span>
        <span className="legend-item">
          <span className="stat-dot" style={{ background: "var(--series-veiculos)" }} />
          Veículos
        </span>
      </div>
      <div style={{ flex: 1, minHeight: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
            <CartesianGrid stroke="var(--gridline)" vertical={false} />
            <XAxis
              dataKey="label"
              stroke="var(--text-muted)"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: "var(--baseline)" }}
            />
            <YAxis
              stroke="var(--text-muted)"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
            />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(137,135,129,0.08)" }} />
            <Bar dataKey="pessoas" name="Pessoas" fill="var(--series-pessoas)" radius={[3, 3, 0, 0]} maxBarSize={28} />
            <Bar dataKey="veiculos" name="Veículos" fill="var(--series-veiculos)" radius={[3, 3, 0, 0]} maxBarSize={28} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
