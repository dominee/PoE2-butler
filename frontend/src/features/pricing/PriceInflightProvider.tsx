import { useMemo, type ReactNode } from "react";

import { useInflightPriceEstimates } from "@/api/hooks";

import { PriceInflightContext } from "./priceInflightContext";

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
