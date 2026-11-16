import type { QueryClient, QueryKey } from "@tanstack/react-query";

type Item = { tags?: string[]; [key: string]: unknown };
type Location = { key: QueryKey; field?: string; identity?: string; id?: string; config?: string; before: string[] | undefined };
type Shape = { prefix: QueryKey; collections?: string[]; collectionKey?: string; identity: string; detail?: QueryKey; config?: boolean };

function update(data: unknown, location: Omit<Location, "key" | "before">, change: (item: Item) => Item): unknown {
  if (!data || typeof data !== "object") return data;
  const obj = data as Item;
  if (location.config) {
    const item = obj[location.config];
    return item && typeof item === "object" ? { ...obj, [location.config]: change(item as Item) } : data;
  }
  if (location.field !== undefined && location.identity !== undefined) {
    const items = obj[location.field];
    if (!Array.isArray(items)) return data;
    return { ...obj, [location.field]: items.map((item) => item && item[location.identity!] === location.id ? change(item as Item) : item) };
  }
  return change(obj);
}

export async function optimisticTags(client: QueryClient, shape: Shape, id: string, tags: string[]) {
  await client.cancelQueries({ queryKey: shape.prefix });
  const locations: Location[] = [];
  for (const [key, data] of client.getQueriesData({ queryKey: shape.prefix })) {
    if (!data || typeof data !== "object") continue;
    const obj = data as Item;
    const targets: Array<Omit<Location, "key" | "before">> = [];
    if (shape.detail && JSON.stringify(key) === JSON.stringify(shape.detail)) targets.push({});
    if (shape.config && (!shape.collectionKey || key[1] === shape.collectionKey) && obj[id] && typeof obj[id] === "object") targets.push({ config: id });
    for (const field of (!shape.collectionKey || key[1] === shape.collectionKey ? shape.collections : []) ?? []) {
      const items = obj[field];
      if (!Array.isArray(items)) continue;
      for (const item of items) {
        if (!item || (item[shape.identity] !== id && !(shape.identity === "name" && item.reviewRef === id))) continue;
        const identity = shape.identity === "name" && typeof item.reviewRef === "string" ? "reviewRef" : shape.identity;
        targets.push({ field, identity, id: item[identity] });
      }
    }
    for (const target of targets) {
      client.setQueryData(key, (current: unknown) => update(current, target, (item) => {
        locations.push({ key, ...target, before: item.tags });
        return { ...item, tags };
      }));
    }
  }
  return () => {
    for (const location of locations) {
      client.setQueryData(location.key, (current: unknown) => update(current, location, (item) => {
        if (item.tags !== tags && JSON.stringify(item.tags) !== JSON.stringify(tags)) return item;
        return { ...item, tags: location.before };
      }));
    }
  };
}
