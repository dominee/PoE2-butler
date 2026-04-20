import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type {
  ActivityResponse,
  CharacterDetail,
  CharactersResponse,
  Item,
  LeaguesResponse,
  Me,
  Prefs,
  PricingResponse,
  RefreshResponse,
  StashListResponse,
  StashTab,
  TradeSearchResponse,
} from "./types";

export const queryKeys = {
  activity: (league: string | null) => ["activity", league] as const,
  me: ["me"] as const,
  leagues: ["leagues"] as const,
  characters: (league: string | null) => ["characters", league] as const,
  character: (name: string) => ["character", name] as const,
  stashes: (league: string | null) => ["stashes", league] as const,
  stashTab: (league: string | null, tabId: string | null) =>
    ["stash-tab", league, tabId] as const,
};

export function useMe() {
  return useQuery<Me>({
    queryKey: queryKeys.me,
    queryFn: () => api.get<Me>("/api/me"),
    retry: false,
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
  });
}

export function useRefresh() {
  const qc = useQueryClient();
  return useMutation<RefreshResponse>({
    mutationFn: () => api.post<RefreshResponse>("/api/refresh"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["characters"] });
      qc.invalidateQueries({ queryKey: queryKeys.leagues });
      qc.invalidateQueries({ queryKey: queryKeys.me });
      qc.invalidateQueries({ queryKey: ["activity"] });
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

export function useActivity(league: string | null) {
  const query = league ? `?league=${encodeURIComponent(league)}` : "";
  return useQuery<ActivityResponse>({
    queryKey: queryKeys.activity(league),
    queryFn: () => api.get<ActivityResponse>(`/api/activity${query}`),
    enabled: Boolean(league),
    staleTime: 30_000,
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ status: string }>("/api/auth/logout"),
    onSuccess: () => {
      qc.clear();
      window.location.href = "/";
    },
  });
}
