export const TIPO_META = {
  pessoa: { label: "Pessoas", color: "var(--series-pessoas)" },
  car: { label: "Carros", color: "var(--series-car)" },
  motorcycle: { label: "Motos", color: "var(--series-motorcycle)" },
  bus: { label: "Ônibus", color: "var(--series-bus)" },
  truck: { label: "Caminhões", color: "var(--series-truck)" },
  bicycle: { label: "Bicicletas", color: "var(--series-bicycle)" },
};

export function tipoLabel(tipo) {
  return TIPO_META[tipo]?.label ?? tipo;
}

export function tipoColor(tipo) {
  return TIPO_META[tipo]?.color ?? "var(--text-muted)";
}
