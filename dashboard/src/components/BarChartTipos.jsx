import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, LabelList } from "recharts";
import ChartTooltip from "./ChartTooltip.jsx";

export default function BarChartTipos({ data }) {
  const dataWithName = data.map((d) => ({ ...d, name: d.label }));

  return (
    <div className="glass-card chart-card">
      <h3>Veículos por tipo</h3>
      <p className="chart-sub">Total de cruzamentos no período filtrado</p>
      <div style={{ flex: 1, minHeight: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={dataWithName} layout="vertical" margin={{ top: 4, right: 28, left: 8, bottom: 0 }}>
            <CartesianGrid stroke="var(--gridline)" horizontal={false} />
            <XAxis
              type="number"
              stroke="var(--text-muted)"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: "var(--baseline)" }}
              allowDecimals={false}
            />
            <YAxis
              type="category"
              dataKey="label"
              stroke="var(--text-secondary)"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              width={82}
            />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(137,135,129,0.08)" }} />
            <Bar dataKey="count" name="Cruzamentos" radius={[0, 4, 4, 0]} maxBarSize={22}>
              {dataWithName.map((entry, idx) => (
                <Cell
                  key={entry.tipo}
                  fill="var(--seq-400)"
                  opacity={0.4 + (0.6 * (dataWithName.length - idx)) / dataWithName.length}
                />
              ))}
              <LabelList
                dataKey="count"
                position="right"
                style={{ fill: "var(--text-secondary)", fontSize: 12, fontWeight: 600 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
