import { useState, useMemo } from "react";
import { tipoLabel } from "../lib/tipos.js";

export default function TableView({ events }) {
  const [open, setOpen] = useState(false);

  const sorted = useMemo(
    () => [...events].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)),
    [events]
  );
  const visible = sorted.slice(0, 50);

  return (
    <div className="glass-card table-card">
      <button className="table-toggle" onClick={() => setOpen((v) => !v)}>
        {open ? "Ocultar tabela de dados ▲" : "Ver tabela de dados ▼"}
      </button>
      {open && (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Quando</th>
                <th>Tipo</th>
                <th>Track ID</th>
                <th>Confiança</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((e) => (
                <tr key={e.id}>
                  <td>{new Date(e.timestamp).toLocaleString("pt-BR")}</td>
                  <td>{tipoLabel(e.tipo)}</td>
                  <td>{e.track_id}</td>
                  <td>{Math.round((e.confianca ?? 0) * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
          {sorted.length > visible.length && (
            <p className="chart-sub" style={{ marginTop: 8 }}>
              Mostrando os {visible.length} mais recentes de {sorted.length} eventos.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
