import { create } from "zustand";
import { persist } from "zustand/middleware";

export type AppView = "characters" | "stashes";
export type StashLayout = "grid" | "icons" | "table";

interface UIState {
  selectedLeague: string | null;
  selectedCharacter: string | null;
  view: AppView;
  selectedTab: string | null;
  stashLayout: StashLayout;
  setLeague: (league: string | null) => void;
  setCharacter: (name: string | null) => void;
  setView: (view: AppView) => void;
  setSelectedTab: (tabId: string | null) => void;
  setStashLayout: (layout: StashLayout) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      selectedLeague: null,
      selectedCharacter: null,
      view: "characters",
      selectedTab: null,
      stashLayout: "grid",
      setLeague: (league) =>
        set({ selectedLeague: league, selectedCharacter: null, selectedTab: null }),
      setCharacter: (name) => set({ selectedCharacter: name }),
      setView: (view) => set({ view }),
      setSelectedTab: (tabId) => set({ selectedTab: tabId }),
      setStashLayout: (layout) => set({ stashLayout: layout }),
    }),
    { name: "poe2b-ui" },
  ),
);
