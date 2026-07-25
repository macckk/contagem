import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import ChartTooltip from "./ChartTooltip.jsx";

export default function LineChartCrossings({ data }) {
  return (
    <div className="glass-card chart-card">
      <h3>Cruzamentos por hora</h3>
      <p className="chart-sub">Pessoas vs. veículos, agrupado por hora do dia</p>
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
          <LineChart data={data} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
            <CartesianGrid stroke="var(--gridline)" vertical={false} />
            <XAxis
              dataKey="label"
              stroke="var(--text-muted)"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: "var(--baseline)" }}
              interval={2}
            />
            <YAxis
              stroke="var(--text-muted)"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
            />
            <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--baseline)", strokeWidth: 1 }} />
            <Line
              type="monotone"
              dataKey="pessoas"
              name="Pessoas"
              stroke="var(--series-pessoas)"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 5 }}
            />
            <Line
              type="monotone"
              dataKey="veiculos"
              name="Veículos"
              stroke="var(--series-veiculos)"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
