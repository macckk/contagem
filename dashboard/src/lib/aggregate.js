import { TIPO_META } from "./tipos.js";

export function rangeStartFor(rangeKey) {
  const now = new Date();
  if (rangeKey === "hoje") {
    const start = new Date(now);
    start.setHours(0, 0, 0, 0);
    return start;
  }
  if (rangeKey === "7dias") {
    return new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  }
  if (rangeKey === "30dias") {
    return new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  }
  return null; // "tudo"
}

export function computeStats(events) {
  const totalPessoas = events.filter((e) => e.tipo === "pessoa").length;
  const totalVeiculos = events.length - totalPessoas;
  const confMedia = events.length
    ? events.reduce((acc, e) => acc + (e.confianca ?? 0), 0) / events.length
    : 0;

  const porHora = new Array(24).fill(0);
  for (const e of events) {
    const h = new Date(e.timestamp).getHours();
    porHora[h] += 1;
  }
  let picoHora = 0;
  for (let h = 1; h < 24; h++) {
    if (porHora[h] > porHora[picoHora]) picoHora = h;
  }

  return {
    totalPessoas,
    totalVeiculos,
    confMedia,
    picoHora,
    picoContagem: porHora[picoHora],
  };
}

export function aggregateByHour(events) {
  const slots = Array.from({ length: 24 }, (_, hour) => ({
    hour,
    label: `${String(hour).padStart(2, "0")}h`,
    pessoas: 0,
    veiculos: 0,
  }));
  for (const e of events) {
    const h = new Date(e.timestamp).getHours();
    if (e.tipo === "pessoa") slots[h].pessoas += 1;
    else slots[h].veiculos += 1;
  }
  return slots;
}

export function aggregateByTipoVeiculo(events) {
  const counts = {};
  for (const e of events) {
    if (e.tipo === "pessoa") continue;
    counts[e.tipo] = (counts[e.tipo] ?? 0) + 1;
  }
  return Object.keys(TIPO_META)
    .filter((tipo) => tipo !== "pessoa")
    .map((tipo) => ({
      tipo,
      label: TIPO_META[tipo].label,
      color: TIPO_META[tipo].color,
      count: counts[tipo] ?? 0,
    }))
    .sort((a, b) => b.count - a.count);
}

export function confidenceHistogram(events) {
  const bins = Array.from({ length: 10 }, (_, i) => ({
    bin: i,
    label: `${(i / 10).toFixed(1)}`,
    count: 0,
  }));
  for (const e of events) {
    const c = Math.max(0, Math.min(0.999, e.confianca ?? 0));
    const idx = Math.floor(c * 10);
    bins[idx].count += 1;
  }
  return bins;
}
