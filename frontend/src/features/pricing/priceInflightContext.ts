import { createContext, useContext } from "react";

export const PriceInflightContext = createContext<ReadonlySet<string>>(new Set());

export function useIsItemPriceInflight(itemId: string | undefined): boolean {
  const inflight = useContext(PriceInflightContext);
  return Boolean(itemId && inflight.has(itemId));
}
