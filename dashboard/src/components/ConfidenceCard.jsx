import { motion } from "framer-motion";
import { BarChart, Bar, ResponsiveContainer, Cell, Tooltip } from "recharts";
import { useCountUp } from "../lib/useCountUp.js";
import ChartTooltip from "./ChartTooltip.jsx";

export default function ConfidenceCard({ confMedia, histogram }) {
  const animated = useCountUp((confMedia ?? 0) * 100);
  const histogramForTooltip = histogram.map((b) => ({
    ...b,
    name: `Confiança ≥ ${b.label}`,
  }));

  return (
    <motion.div
      className="glass-card stat-tile"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.1 }}
    >
      <span className="stat-label">Confiança média</span>
      <span className="stat-value">{animated.toFixed(0)}%</span>
      <div style={{ height: 44, marginTop: 2 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={histogramForTooltip} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
            <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(137,135,129,0.1)" }} />
            <Bar dataKey="count" radius={[3, 3, 0, 0]} name="Eventos">
              {histogramForTooltip.map((entry, idx) => (
                <Cell key={entry.bin} fill="var(--seq-400)" opacity={0.3 + (idx / 10) * 0.7} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <span className="stat-sub">Distribuição por faixa de confiança</span>
    </motion.div>
  );
}
