export interface AssetTagCount {
  tag: string;
  count: number;
  isStarred: boolean;
}

export function extractAssetTagCounts(
  items: Array<{ tags?: string[] } | null | undefined> | null | undefined,
): AssetTagCount[] {
  if (!items) return [{ tag: "starred", count: 0, isStarred: true }];
  const countsMap = new Map<string, { display: string; count: number }>();
  let starredCount = 0;

  for (const item of items) {
    if (!item || !item.tags) continue;
    const seenInItem = new Set<string>();
    for (const tag of item.tags) {
      const lower = tag.toLowerCase();
      if (seenInItem.has(lower)) continue;
      seenInItem.add(lower);

      if (lower === "starred") {
        starredCount += 1;
      } else {
        const existing = countsMap.get(lower);
        if (existing) {
          existing.count += 1;
        } else {
          countsMap.set(lower, { display: tag, count: 1 });
        }
      }
    }
  }

  const regularTags = Array.from(countsMap.values())
    .sort((a, b) => a.display.localeCompare(b.display, undefined, { sensitivity: "base" }))
    .map(({ display, count }) => ({ tag: display, count, isStarred: false }));

  return [
    { tag: "starred", count: starredCount, isStarred: true },
    ...regularTags,
  ];
}

export function matchesAssetTags(
  item: { tags?: string[] } | null | undefined,
  tags: string[] | null | undefined,
): boolean {
  if (!tags || tags.length === 0) return true;
  if (!item || !item.tags || item.tags.length === 0) return false;
  const itemTags = item.tags.map((t) => t.toLowerCase());
  return tags.some((tag) => itemTags.includes(tag.toLowerCase()));
}
