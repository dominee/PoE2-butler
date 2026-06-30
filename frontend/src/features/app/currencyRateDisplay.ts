/** Format ex↔chaos for header copy when 1 ex may be worth less than 1 chaos. */
export function formatExChaosRate(chaosPerExalted: number): {
  leftAmount: string;
  leftUnit: "ex" | "chaos";
  rightAmount: string;
  rightUnit: "ex" | "chaos";
} {
  if (chaosPerExalted >= 1) {
    return {
      leftAmount: "1",
      leftUnit: "ex",
      rightAmount: String(Math.ceil(chaosPerExalted)),
      rightUnit: "chaos",
    };
  }
  const exPerChaos = 1 / chaosPerExalted;
  return {
    leftAmount: String(Math.ceil(exPerChaos)),
    leftUnit: "ex",
    rightAmount: "1",
    rightUnit: "chaos",
  };
}
