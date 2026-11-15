import { useEffect, useMemo, useState } from "react";
import { fetchJson } from "../../api/http";
import type { AssetTagCount } from "./tag-counts";

/** Merge the shared vocabulary with counts from the current asset family. */
export function mergeSharedTagCounts(counts: AssetTagCount[], vocabulary: string[]): AssetTagCount[] {
  const merged = new Map(counts.map((item) => [item.tag.toLowerCase(), item]));
  for (const tag of vocabulary) {
    const key = tag.toLowerCase();
    if (!merged.has(key)) merged.set(key, { tag, count: 0, isStarred: key === "starred" });
  }
  return Array.from(merged.values()).sort((a, b) =>
    Number(b.isStarred) - Number(a.isStarred) || a.tag.localeCompare(b.tag, undefined, { sensitivity: "base" }),
  );
}

export function useSharedTagCounts(counts: AssetTagCount[]): AssetTagCount[] {
  const [vocabulary, setVocabulary] = useState<string[]>([]);
  useEffect(() => {
    let active = true;
    let request = 0;
    const refresh = () => {
      const current = ++request;
      fetchJson<{ tags: string[] }>("/asset-tags/")
        .then((result) => { if (active && current === request) setVocabulary(result.tags); })
        .catch(() => {});
    };
    refresh();
    window.addEventListener("focus", refresh);
    return () => {
      active = false;
      window.removeEventListener("focus", refresh);
    };
  }, [counts]);
  return useMemo(() => mergeSharedTagCounts(counts, vocabulary), [counts, vocabulary]);
}
