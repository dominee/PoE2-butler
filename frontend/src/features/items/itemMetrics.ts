export function formatChaos(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
  if (value >= 100) return value.toFixed(0);
  if (value >= 10) return value.toFixed(1);
  return value.toFixed(2);
}

/** Mean of mod lines that have a roll percentage (implicit + explicit). */
export function computeItemScore(pcts: (number | null)[]): number | null {
  const valid = pcts.filter((p): p is number => p != null);
  if (valid.length === 0) {
    return null;
  }
  return Math.round(valid.reduce((a, b) => a + b, 0) / valid.length);
}
