import { create } from "zustand";
import type { SSEMessage } from "@/lib/api/types";

interface UploadState {
  receipts: File[];
  cardStatements: File[];
  events: SSEMessage[];
  setReceipts: (files: File[]) => void;
  appendReceipts: (files: File[]) => void;
  setCardStatements: (files: File[]) => void;
  appendCardStatements: (files: File[]) => void;
  removeReceipt: (name: string) => void;
  removeCardStatement: (name: string) => void;
  pushEvent: (e: SSEMessage) => void;
  reset: () => void;
}

export const useUploadStore = create<UploadState>((set) => ({
  receipts: [],
  cardStatements: [],
  events: [],
  setReceipts: (files) => set({ receipts: files }),
  appendReceipts: (files) => set((s) => ({ receipts: [...s.receipts, ...files] })),
  setCardStatements: (files) => set({ cardStatements: files }),
  appendCardStatements: (files) => set((s) => ({ cardStatements: [...s.cardStatements, ...files] })),
  removeReceipt: (name) => set((s) => ({ receipts: s.receipts.filter((f) => f.name !== name) })),
  removeCardStatement: (name) => set((s) => ({ cardStatements: s.cardStatements.filter((f) => f.name !== name) })),
  pushEvent: (e) => set((s) => ({ events: [...s.events, e] })),
  reset: () => set({ receipts: [], cardStatements: [], events: [] }),
}));

const CARD_EXT = /\.(xlsx|csv)$/i;

/** 파일 확장자 기준 receipt vs card_statement 자동 분류. */
export function classifyFiles(files: File[]): { receipts: File[]; cardStatements: File[] } {
  const receipts: File[] = [];
  const cardStatements: File[] = [];
  for (const f of files) {
    if (CARD_EXT.test(f.name)) cardStatements.push(f);
    else receipts.push(f);
  }
  return { receipts, cardStatements };
}
