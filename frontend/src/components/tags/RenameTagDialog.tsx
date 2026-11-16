import * as Dialog from "@radix-ui/react-dialog";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { errorMessage, fetchJson, postJson } from "../../api/http";
import { useToast } from "../Toast";
import { tagIdentity } from "./tag-identity";

export function renamedTagParams(params: URLSearchParams, source: string, target: string): URLSearchParams {
  const updated = new URLSearchParams(params);
  const original = params.getAll("tag");
  const hasSource = original.some((tag) => tagIdentity(tag) === tagIdentity(source));
  const tags = original.map((tag) => hasSource &&
    (tagIdentity(tag) === tagIdentity(source) || tagIdentity(tag) === tagIdentity(target)) ? target : tag);
  updated.delete("tag");
  const seen = new Set<string>();
  for (const tag of tags) {
    if (!seen.has(tagIdentity(tag))) updated.append("tag", tag);
    seen.add(tagIdentity(tag));
  }
  return updated;
}

export function RenameTagDialog({ source, onClose }: { source: string; onClose: () => void }) {
  const [target, setTarget] = useState(source);
  const [vocabulary, setVocabulary] = useState<string[] | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [params, setParams] = useSearchParams();
  const client = useQueryClient();
  const { toast } = useToast();
  useEffect(() => {
    let active = true;
    fetchJson<{ tags: string[] }>("/asset-tags/").then((result) => {
      if (active) setVocabulary(result.tags);
    }).catch(() => { if (active) setError("Could not load tags. Try again."); });
    return () => { active = false; };
  }, []);
  const trimmed = target.trim();
  const merge = tagIdentity(trimmed) !== tagIdentity(source) &&
    (vocabulary ?? []).some((tag) => tagIdentity(tag) === tagIdentity(trimmed));
  async function submit() {
    setPending(true);
    setError("");
    try {
      const result = await postJson<{ assets_changed: number }>("/asset-tags/rename", { from: source, to: trimmed });
      setParams(renamedTagParams(params, source, trimmed), { replace: true });
      window.dispatchEvent(new Event("asset-tags-changed"));
      void client.invalidateQueries();
      toast(`Renamed tag on ${result.assets_changed} ${result.assets_changed === 1 ? "asset" : "assets"}.`);
      onClose();
    } catch (e) {
      setError(errorMessage(e, "Could not rename tag."));
    } finally { setPending(false); }
  }
  return (
    <Dialog.Root open onOpenChange={(open) => { if (!open && !pending) onClose(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className="dialog-content" onInteractOutside={(e) => { if (pending) e.preventDefault(); }}>
          <Dialog.Title className="dialog-title">Rename tag</Dialog.Title>
          <Dialog.Description className="dialog-description">Rename {source} across all assets.</Dialog.Description>
          <form onSubmit={(e) => { e.preventDefault(); void submit(); }}>
            <label className="form-field" htmlFor="rename-tag-input">
              <span className="form-field__label">New name</span>
              <input id="rename-tag-input" className="form-field__input" value={target} onChange={(e) => setTarget(e.target.value)} autoFocus />
            </label>
            {merge ? <p className="dialog-description">A tag with this name already exists. The two tags will be merged.</p> : null}
            {error ? <p className="dialog-error" role="alert">{error}</p> : null}
            <div className="dialog-actions">
              <button type="button" className="btn" disabled={pending} onClick={onClose}>Cancel</button>
              <button type="submit" className="btn" disabled={pending || vocabulary === null || !trimmed || Array.from(trimmed).length > 64 || tagIdentity(trimmed) === "starred"}>Rename</button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
