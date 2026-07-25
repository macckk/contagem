import { motion } from "framer-motion";
import { useCountUp } from "../lib/useCountUp.js";

export default function StatTile({ label, value, sub, dotColor }) {
  const animated = useCountUp(value ?? 0);
  const display = Math.round(animated).toLocaleString("pt-BR");

  return (
    <motion.div
      className="glass-card stat-tile"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <span className="stat-label">
        {dotColor && <span className="stat-dot" style={{ background: dotColor }} />}
        {label}
      </span>
      <span className="stat-value">{display}</span>
      {sub && <span className="stat-sub">{sub}</span>}
    </motion.div>
  );
}
