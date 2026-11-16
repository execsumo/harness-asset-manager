import { useEffect, useMemo, useState } from "react";
import { fetchJson } from "../../api/http";
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

/** Accept only a list of tag strings; anything else is treated as an empty vocabulary. */
function vocabularyFrom(result: { tags?: unknown } | null | undefined): string[] {
  const tags = result?.tags;
  return Array.isArray(tags) ? tags.filter((tag): tag is string => typeof tag === "string") : [];
}

export function useSharedTagCounts(counts: AssetTagCount[]): AssetTagCount[] {
  const [vocabulary, setVocabulary] = useState<string[]>([]);
  useEffect(() => {
    let active = true;
    let request = 0;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const refresh = () => {
      clearTimeout(retry);
      const current = ++request;
      fetchJson<{ tags?: unknown }>("/asset-tags/")
        .then((result) => { if (active && current === request) setVocabulary(vocabularyFrom(result)); })
        .catch(() => {
          if (active && current === request) retry = setTimeout(refresh, 5000);
        });
    };
    refresh();
    window.addEventListener("focus", refresh);
    window.addEventListener("asset-tags-changed", refresh);
    return () => {
      active = false;
      clearTimeout(retry);
      window.removeEventListener("focus", refresh);
      window.removeEventListener("asset-tags-changed", refresh);
    };
  }, [counts]);
  return useMemo(() => mergeSharedTagCounts(counts, vocabulary), [counts, vocabulary]);
}
