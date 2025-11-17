import { create } from "zustand";
import type { ObjectId } from "bson";

export interface ObjectSelectionStore {
  selectedIds: Set<string>;
  toggleSelection: (id: ObjectId) => void;
  addToSelection: (id: ObjectId) => void;
  removeFromSelection: (id: ObjectId) => void;
  clearSelection: () => void;
  isSelected: (id: ObjectId) => boolean;
}

export const useObjectSelectionStore = create<ObjectSelectionStore>((set, get) => ({
  selectedIds: new Set<string>(),

  toggleSelection: (id: ObjectId) => {
    const idString = id.toString();
    set((state) => {
      const newSet = new Set(state.selectedIds);
      if (newSet.has(idString)) {
        newSet.delete(idString);
      } else {
        newSet.add(idString);
      }
      return { selectedIds: newSet };
    });
  },

  addToSelection: (id: ObjectId) => {
    const idString = id.toString();
    set((state) => {
      const newSet = new Set(state.selectedIds);
      newSet.add(idString);
      return { selectedIds: newSet };
    });
  },

  removeFromSelection: (id: ObjectId) => {
    const idString = id.toString();
    set((state) => {
      const newSet = new Set(state.selectedIds);
      newSet.delete(idString);
      return { selectedIds: newSet };
    });
  },

  clearSelection: () => {
    set({ selectedIds: new Set<string>() });
  },

  isSelected: (id: ObjectId) => {
    const idString = id.toString();
    return get().selectedIds.has(idString);
  },
}));

