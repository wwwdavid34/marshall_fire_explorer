import { create } from "zustand";
import type { ParcelProperties } from "./types";

type RecoveryFilter = "all" | "recovered" | "not-recovered";

interface AppState {
  selectedParcel: ParcelProperties | null;
  setSelectedParcel: (parcel: ParcelProperties | null) => void;
  damageClasses: Set<string>;
  toggleDamageClass: (cls: string) => void;
  recoveryFilter: RecoveryFilter;
  setRecoveryFilter: (filter: RecoveryFilter) => void;
}

export const useStore = create<AppState>((set) => ({
  selectedParcel: null,
  setSelectedParcel: (parcel) => set({ selectedParcel: parcel }),
  damageClasses: new Set(["Destroyed", "Damaged", "Unaffected"]),
  toggleDamageClass: (cls) =>
    set((state) => {
      const next = new Set(state.damageClasses);
      if (next.has(cls)) next.delete(cls);
      else next.add(cls);
      return { damageClasses: next };
    }),
  recoveryFilter: "all",
  setRecoveryFilter: (filter) => set({ recoveryFilter: filter }),
}));
