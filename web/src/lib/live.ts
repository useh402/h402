"use client";

import { useEffect, useState } from "react";
import { API_URL } from "./api";

export type Rewards = {
  rewardsPaid: number; rewardsPaidToWorkers: number; rewardsPaidTeamRuns: number; payments: number; peoplePaid: number;
  tasks: { total: number; open: number; completed: number; expired: number };
  openRewards: number; feeBps: number; asset: string;
  recent: { amount: number; taskId: string | null; title: string; wallet: string; team: boolean; at: number; transaction: string | null; explorer: string | null }[];
};

/** The platform's live money figures, refreshed every `seconds`. Keeps the last good answer if a refresh fails. */
export function useRewards(seconds = 20): Rewards | null {
  const [data, setData] = useState<Rewards | null>(null);
  useEffect(() => {
    let live = true;
    const load = () =>
      fetch(`${API_URL}/v1/rewards`)
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .then((d: Rewards) => {
          if (live) setData(d);
        })
        .catch(() => {});
    const first = setTimeout(load, 0);
    const id = setInterval(load, seconds * 1000);
    return () => {
      live = false;
      clearTimeout(first);
      clearInterval(id);
    };
  }, [seconds]);
  return data;
}
