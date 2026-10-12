"use client";

import { useEffect, useState } from "react";
import { api, getToken, SESSION_EVENT, type Worker } from "./api";

/**
 * Wallets that see the operator controls on the site. The controls themselves
 * still need the operator key; this only decides who is shown them.
 */
export const ADMIN_WALLETS = ["0x243E224d65D2EeEa6EE08A1f8DfC94Bdeae9F3Ba"];

export const isAdminWallet = (wallet?: string | null) => !!wallet && ADMIN_WALLETS.some((a) => a.toLowerCase() === wallet.toLowerCase());

/**
 * The worker signed in on this browser, or null. Re-checked whenever the
 * session token changes (sign in, sign out, another tab) and when the tab
 * comes back into focus.
 */
export function useMe(): Worker | null {
  const [me, setMe] = useState<Worker | null>(null);
  useEffect(() => {
    let live = true;
    const check = () => {
      if (!getToken()) {
        setMe(null);
        return;
      }
      api<Worker>("/v1/workers/me")
        .then((w) => live && setMe(w))
        .catch(() => live && setMe(null));
    };
    const t = setTimeout(check, 0);
    window.addEventListener(SESSION_EVENT, check);
    window.addEventListener("storage", check);
    window.addEventListener("focus", check);
    return () => {
      live = false;
      clearTimeout(t);
      window.removeEventListener(SESSION_EVENT, check);
      window.removeEventListener("storage", check);
      window.removeEventListener("focus", check);
    };
  }, []);
  return me;
}

/** True only while the admin wallet is signed in. */
export function useIsAdmin(): boolean {
  return isAdminWallet(useMe()?.wallet);
}
