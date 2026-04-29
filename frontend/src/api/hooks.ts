import { useEffect, useRef, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import { useUIStore } from "@/store/uiStore";
import type {
  ActivityResponse,
  AppriseQueued,
  CharacterDetail,
  CharactersResponse,
  CreateShareResponse,
  CurrencyRatesResponse,
  Item,
  LeaguesResponse,
  Me,
  Prefs,
  PriceJobState,
  PricingResponse,
  PublicItemResponse,
  RefreshResponse,
  StashListResponse,
  StashSearchResponse,
  StashTab,
  ItemTextResponse,
  TradeSearchResponse,
} from "./types";

export const shareViewPath = (shareId: string) => `/i/${encodeURIComponent(shareId)}`;

export const queryKeys = {
  activity: (league: string | null) => ["activity", league] as const,
  me: ["me"] as const,
  leagues: ["leagues"] as const,
  characters: (league: string | null) => ["characters", league] as const,
  character: (name: string) => ["character", name] as const,
  stashes: (league: string | null) => ["stashes", league] as const,
  stashTab: (league: string | null, tabId: string | null) =>
    ["stash-tab", league, tabId] as const,
  stashSearch: (league: string | null, q: string) => ["stash-search", league, q] as const,
  publicItem: (shareId: string) => ["public-item", shareId] as const,
};

export function usePublicItem(shareId: string | null | undefined) {
  return useQuery<PublicItemResponse>({
    queryKey: queryKeys.publicItem(shareId ?? ""),
    queryFn: () =>
      api.get<PublicItemResponse>(
        `/api/public/items/${encodeURIComponent(shareId ?? "")}`,
      ),
    enabled: Boolean(shareId),
    retry: false,
  });
}

export function useCreateShare() {
  return useMutation<CreateShareResponse, Error, { league: string; item: Item }>({
    mutationFn: (args) => api.post<CreateShareResponse>("/api/shares", args),
  });
}

export function useRevokeShare() {
  return useMutation<void, Error, { shareId: string }>({
    mutationFn: (args) =>
      api.request<void>(`/api/shares/${encodeURIComponent(args.shareId)}`, {
        method: "DELETE",
      }),
  });
}

export function useMe() {
  return useQuery<Me>({
    queryKey: queryKeys.me,
    queryFn: () => api.get<Me>("/api/me"),
    // OAuth callback -> /app can race with session cookie propagation in CI/proxy
    // setups. A couple of short retries avoids a sticky signed-out UI state.
    retry: 2,
    retryDelay: 1_000,
  });
}

export function useLeagues() {
  return useQuery<LeaguesResponse>({
    queryKey: queryKeys.leagues,
    queryFn: () => api.get<LeaguesResponse>("/api/leagues"),
    staleTime: 5 * 60_000,
  });
}

export function useCharacters(league: string | null) {
  const query = league ? `?league=${encodeURIComponent(league)}` : "";
  return useQuery<CharactersResponse>({
    queryKey: queryKeys.characters(league),
    queryFn: () => api.get<CharactersResponse>(`/api/characters${query}`),
  });
}

export function useCharacter(name: string | null) {
  return useQuery<CharacterDetail>({
    queryKey: queryKeys.character(name ?? ""),
    queryFn: () => api.get<CharacterDetail>(`/api/characters/${encodeURIComponent(name ?? "")}`),
    enabled: Boolean(name),
    // Detail can take minutes against the Poe.ninja mock; retries multiply painful waits.
    retry: false,
  });
}

export function useRefresh() {
  const qc = useQueryClient();
  return useMutation<RefreshResponse, Error, { league?: string | null } | void>({
    mutationFn: (vars) => {
      const raw = vars && typeof vars === "object" ? vars.league : undefined;
      const l = typeof raw === "string" && raw.trim() ? raw.trim() : "";
      const suffix = l ? `?league=${encodeURIComponent(l)}` : "";
      return api.post<RefreshResponse>(`/api/refresh${suffix}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["characters"] });
      qc.invalidateQueries({ queryKey: ["character"] });
      qc.invalidateQueries({ queryKey: queryKeys.leagues });
      qc.invalidateQueries({ queryKey: queryKeys.me });
      qc.invalidateQueries({ queryKey: ["activity"] });
      qc.invalidateQueries({ queryKey: ["currency-rates"] });
      qc.invalidateQueries({ queryKey: ["stashes"] });
      qc.invalidateQueries({ queryKey: ["stash-tab"] });
      qc.invalidateQueries({ queryKey: ["stash-search"] });
    },
  });
}

export function useApprise() {
  const qc = useQueryClient();
  return useMutation<AppriseQueued, Error, { league: string | null }>({
    mutationFn: ({ league }) => {
      const q = league ? `?league=${encodeURIComponent(league)}` : "";
      return api.post<AppriseQueued>(`/api/pricing/apprise${q}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["persisted-price-estimate"] });
      qc.invalidateQueries({ queryKey: ["prices"] });
    },
  });
}

export function usePrefs() {
  return useQuery<Prefs>({
    queryKey: ["prefs"],
    queryFn: () => api.get<Prefs>("/api/prefs"),
  });
}

export function useUpdatePrefs() {
  const qc = useQueryClient();
  return useMutation<Prefs, Error, Partial<Prefs>>({
    mutationFn: (patch) =>
      api.request<Prefs>("/api/prefs", { method: "PATCH", json: patch }),
    onSuccess: (data) => {
      qc.setQueryData(["prefs"], data);
      qc.invalidateQueries({ queryKey: queryKeys.me });
    },
  });
}

export interface TradeSearchArgs {
  mode: "exact" | "upgrade";
  item: Item;
  league: string | null;
  tolerance_pct?: number;
}

export function useTradeSearch() {
  return useMutation<TradeSearchResponse, Error, TradeSearchArgs>({
    mutationFn: (args) => api.post<TradeSearchResponse>("/api/trade/search", args),
  });
}

export function useItemText() {
  return useMutation<ItemTextResponse, Error, { item: Item }>({
    mutationFn: (args) => api.post<ItemTextResponse>("/api/items/item-text", args),
  });
}

export function useStashList(league: string | null) {
  return useQuery<StashListResponse>({
    queryKey: queryKeys.stashes(league),
    queryFn: () =>
      api.get<StashListResponse>(
        `/api/stashes?league=${encodeURIComponent(league ?? "")}`,
      ),
    enabled: Boolean(league),
  });
}

export function useStashTab(league: string | null, tabId: string | null) {
  return useQuery<StashTab>({
    queryKey: queryKeys.stashTab(league, tabId),
    queryFn: () =>
      api.get<StashTab>(
        `/api/stashes/${encodeURIComponent(tabId ?? "")}?league=${encodeURIComponent(league ?? "")}`,
      ),
    enabled: Boolean(league && tabId),
  });
}

export function useRefreshStashes() {
  const qc = useQueryClient();
  return useMutation<{ status: string }, Error, { league: string }>({
    mutationFn: (args) =>
      api.request<{ status: string }>("/api/stashes/refresh", {
        method: "POST",
        json: args,
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: queryKeys.stashes(vars.league) });
      qc.invalidateQueries({ queryKey: ["stash-tab", vars.league] });
      qc.invalidateQueries({ queryKey: queryKeys.activity(vars.league) });
    },
  });
}

export function usePriceLookup(league: string | null, items: Item[]) {
  const ids = items.map((i) => i.id).join(",");
  return useQuery<PricingResponse>({
    queryKey: ["prices", league, ids],
    queryFn: () =>
      api.post<PricingResponse>("/api/pricing/lookup", { league, items }),
    enabled: Boolean(league) && items.length > 0,
    staleTime: 60_000,
  });
}

/** Divine/Exalted chaos rates and ex-per-div (poe.ninja or server fallbacks). */
export function useCurrencyRates(league: string | null) {
  return useQuery<CurrencyRatesResponse>({
    queryKey: ["currency-rates", league],
    queryFn: () =>
      api.get<CurrencyRatesResponse>(
        `/api/pricing/currency-rates?league=${encodeURIComponent(league ?? "")}`,
      ),
    enabled: Boolean(league),
    staleTime: 120_000,
  });
}

export function useStashSearch(league: string | null, q: string) {
  return useQuery<StashSearchResponse>({
    queryKey: queryKeys.stashSearch(league, q),
    queryFn: () =>
      api.get<StashSearchResponse>(
        `/api/stashes/search?league=${encodeURIComponent(league ?? "")}&q=${encodeURIComponent(q)}`,
      ),
    enabled: Boolean(league) && q.trim().length >= 2,
    staleTime: 30_000,
  });
}

export function useActivity(league: string | null) {
  const query = league ? `?league=${encodeURIComponent(league)}` : "";
  return useQuery<ActivityResponse>({
    queryKey: queryKeys.activity(league),
    queryFn: () => api.get<ActivityResponse>(`/api/activity${query}`),
    enabled: Boolean(league),
    staleTime: 30_000,
  });
}

/**
 * Loads the last persisted hybrid estimate (Postgres); 204 when none / tolerance mismatch.
 */
export function usePersistedPriceEstimate(
  league: string | null,
  item: Item | null,
  tolerancePct: number,
  enabled: boolean,
) {
  return useQuery<PriceJobState | null>({
    queryKey: ["persisted-price-estimate", league, item?.id, tolerancePct] as const,
    queryFn: async () => {
      const q = new URLSearchParams({
        league: league!,
        item_id: item!.id,
        tolerance_pct: String(tolerancePct),
      });
      const d = await api.get<PriceJobState | undefined>(`/api/pricing/estimate/item?${q.toString()}`);
      return d ?? null;
    },
    enabled: Boolean(enabled && league && item),
    staleTime: 5 * 60_000,
  });
}

/**
 * Hybrid (aggregator + trade median) job: loads persisted result first, then POST+poll on refresh.
 * See ``docs/pricing_estimates.md``.
 * @param rerunKey - Increment to enqueue a new estimate (e.g. user clicks refresh) for the same item.
 * @param autoStart - Unused; kept for API compatibility.
 */
export function useRefinedPriceEstimate(
  league: string | null,
  item: Item | null,
  tolerancePct: number,
  enabled: boolean,
  rerunKey: number = 0,
  autoStart: boolean = false,
) {
  void autoStart;
  const qc = useQueryClient();
  const persistedQ = usePersistedPriceEstimate(league, item, tolerancePct, enabled && rerunKey < 1);
  const sessionKey = league && item ? `${league}::${item.id}` : "";
  const runKey = `${sessionKey}::${rerunKey}`;
  const [jobId, setJobId] = useState<string | null>(null);
  const prevRunKey = useRef<string>("");
  const started = useRef(false);

  useEffect(() => {
    if (runKey === prevRunKey.current) return;
    prevRunKey.current = runKey;
    setJobId(null);
    started.current = false;
  }, [runKey]);

  useEffect(() => {
    if (!sessionKey || !enabled || !item) return;
    if (rerunKey < 1) return;
    if (started.current) return;
    started.current = true;
    (async () => {
      try {
        const r = await api.post<{ job_id: string; deduped: boolean }>("/api/pricing/estimate", {
          league,
          item,
          tolerance_pct: tolerancePct,
        });
        setJobId(r.job_id);
      } catch {
        started.current = false;
      }
    })();
  }, [sessionKey, runKey, enabled, item, league, tolerancePct, rerunKey]);

  const jobQ = useQuery<PriceJobState>({
    queryKey: ["price-estimate", jobId],
    queryFn: () =>
      api.get<PriceJobState>(`/api/pricing/estimate/${encodeURIComponent(jobId ?? "")}`),
    enabled: Boolean(jobId),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      if (s === "completed" || s === "failed") return false;
      return 1000;
    },
  });

  useEffect(() => {
    const s = jobQ.data?.status;
    if (s === "completed" || s === "failed") {
      void qc.invalidateQueries({
        queryKey: ["persisted-price-estimate", league, item?.id, tolerancePct],
      });
    }
  }, [jobQ.data?.status, qc, league, item?.id, tolerancePct]);

  const mergedJob: PriceJobState | null =
    rerunKey >= 1 ? (jobQ.data ?? null) : (persistedQ.data ?? null);

  const waitingLiveJob =
    rerunKey >= 1 &&
    (!jobId ||
      !jobQ.data ||
      (jobQ.data.status !== "completed" && jobQ.data.status !== "failed"));
  const waitingPersisted = rerunKey < 1 && enabled && persistedQ.isLoading;
  const isLoading = Boolean(waitingLiveJob || waitingPersisted);

  return {
    jobId,
    job: mergedJob ?? null,
    isLoading,
    error: jobQ.error ?? persistedQ.error,
  };
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ status: string }>("/api/auth/logout"),
    onSuccess: () => {
      qc.clear();
      // Avoid carrying a persisted character across sessions (detail keys / roster can drift).
      useUIStore.setState({ selectedCharacter: null, selectedTab: null });
      window.location.href = "/";
    },
  });
}
