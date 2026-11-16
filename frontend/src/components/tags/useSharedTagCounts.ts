import { useEffect, useMemo } from "react";
import { useAssetTagVocabulary } from "./asset-tag-vocabulary";
import type { AssetTagCount } from "./tag-counts";
import { tagIdentity } from "./tag-identity";

/** Merge the shared vocabulary with counts from the current asset family. */
export function mergeSharedTagCounts(counts: AssetTagCount[], vocabulary: string[]): AssetTagCount[] {
  const merged = new Map(counts.map((item) => [tagIdentity(item.tag), item]));
  for (const tag of vocabulary) {
    const key = tagIdentity(tag);
    if (!merged.has(key)) merged.set(key, { tag, count: 0, isStarred: key === "starred" });
  }
  return Array.from(merged.values()).sort((a, b) =>
    Number(b.isStarred) - Number(a.isStarred) || a.tag.localeCompare(b.tag, undefined, { sensitivity: "base" }),
  );
}

export function useSharedTagCounts(counts: AssetTagCount[]): AssetTagCount[] {
  const { vocabulary, refresh } = useAssetTagVocabulary();
  useEffect(() => {
    window.addEventListener("focus", refresh);
    window.addEventListener("asset-tags-changed", refresh);
    return () => {
      window.removeEventListener("focus", refresh);
      window.removeEventListener("asset-tags-changed", refresh);
    };
  }, [refresh]);
  return useMemo(() => mergeSharedTagCounts(counts, vocabulary), [counts, vocabulary]);
}
