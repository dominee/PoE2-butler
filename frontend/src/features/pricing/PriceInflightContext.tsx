import { createContext, useContext, useMemo, type ReactNode } from "react";

import { useInflightPriceEstimates } from "@/api/hooks";

const PriceInflightContext = createContext<ReadonlySet<string>>(new Set());

export function PriceInflightProvider({
  league,
  children,
}: {
  league: string | null;
  children: ReactNode;
}) {
  const q = useInflightPriceEstimates(league);
  const ids = useMemo(
    () => new Set((q.data?.items ?? []).map((row) => row.item_id)),
    [q.data?.items],
  );
  return (
    <PriceInflightContext.Provider value={ids}>{children}</PriceInflightContext.Provider>
  );
}

export function useIsItemPriceInflight(itemId: string | undefined): boolean {
  const inflight = useContext(PriceInflightContext);
  return Boolean(itemId && inflight.has(itemId));
}
