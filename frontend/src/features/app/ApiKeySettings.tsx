/**
 * API key management panel — create, copy, and revoke the user's machine API key.
 *
 * The full key is shown **once** after creation and never stored on the server.
 * Used by the Discord bot and other machine integrations.
 */

import { useState } from "react";
import { useApiKey, useCreateApiKey, useRevokeApiKey } from "@/api/hooks";
import type { ApiKeyCreated } from "@/api/types";

interface ApiKeySettingsProps {
  onClose: () => void;
}

export function ApiKeySettings({ onClose }: ApiKeySettingsProps) {
  const keyQ = useApiKey();
  const createMutation = useCreateApiKey();
  const revokeMutation = useRevokeApiKey();

  const [newKey, setNewKey] = useState<ApiKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const [confirmRevoke, setConfirmRevoke] = useState(false);

  const isLoading = keyQ.isLoading;
  const activeKey = keyQ.data;

  async function handleCreate() {
    const result = await createMutation.mutateAsync();
    setNewKey(result);
    setCopied(false);
    setConfirmRevoke(false);
  }

  async function handleRevoke() {
    await revokeMutation.mutateAsync();
    setNewKey(null);
    setConfirmRevoke(false);
  }

  async function handleCopy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      // Clipboard API not available — user must copy manually.
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/80 backdrop-blur-sm">
      <div className="relative w-full max-w-lg rounded-xl border border-ink-700 bg-ink-900 p-6 shadow-2xl">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 text-parchment-300/60 hover:text-parchment-100 transition"
          aria-label="Close"
        >
          ✕
        </button>

        <h2 className="mb-1 font-display text-lg text-ember-400">API Key</h2>
        <p className="mb-5 text-sm text-parchment-300/70">
          Used by the Discord bot and other machine integrations.
          Only one key is active at a time.
        </p>

        {isLoading && <p className="text-ui-muted text-sm">Loading…</p>}

        {/* One-time reveal after creation */}
        {newKey && (
          <div className="mb-4 rounded-lg border border-amber-600/50 bg-amber-950/30 p-4">
            <p className="mb-2 font-semibold text-amber-200 text-sm">
              Key created — copy it now. It will not be shown again.
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 break-all rounded bg-ink-800 px-3 py-2 text-xs text-parchment-100 select-all">
                {newKey.full_key}
              </code>
              <button
                type="button"
                onClick={() => handleCopy(newKey.full_key)}
                className="shrink-0 rounded border border-amber-600/60 px-3 py-2 text-xs text-amber-100 hover:bg-amber-900/30 transition"
              >
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>
            <button
              type="button"
              onClick={() => setNewKey(null)}
              className="mt-3 text-xs text-parchment-300/60 hover:text-parchment-100 underline"
            >
              I've saved it — dismiss
            </button>
          </div>
        )}

        {/* Current key status */}
        {!newKey && (
          <div className="mb-5">
            {activeKey ? (
              <div className="rounded-lg border border-ink-700 bg-ink-800/60 p-4">
                <p className="mb-2 text-sm font-medium text-parchment-100">
                  Active key
                </p>
                <dl className="grid grid-cols-[auto,1fr] gap-x-4 gap-y-1 text-sm">
                  <dt className="text-parchment-300/70">Prefix</dt>
                  <dd>
                    <code className="text-ember-300">hob_{activeKey.prefix}_…</code>
                  </dd>
                  {activeKey.name && (
                    <>
                      <dt className="text-parchment-300/70">Name</dt>
                      <dd className="text-parchment-100">{activeKey.name}</dd>
                    </>
                  )}
                  <dt className="text-parchment-300/70">Created</dt>
                  <dd className="text-parchment-100">
                    {new Date(activeKey.created_at).toLocaleString()}
                  </dd>
                  <dt className="text-parchment-300/70">Last used</dt>
                  <dd className="text-parchment-100">
                    {activeKey.last_used_at
                      ? new Date(activeKey.last_used_at).toLocaleString()
                      : "Never"}
                  </dd>
                </dl>
              </div>
            ) : (
              !isLoading && (
                <p className="text-sm text-parchment-300/60">No active API key.</p>
              )
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-wrap gap-3">
          {!newKey && (
            <button
              type="button"
              className="btn-primary text-sm"
              onClick={handleCreate}
              disabled={createMutation.isPending}
            >
              {createMutation.isPending
                ? "Creating…"
                : activeKey
                  ? "Regenerate key (revokes current)"
                  : "Create API key"}
            </button>
          )}

          {activeKey && !newKey && (
            confirmRevoke ? (
              <div className="flex items-center gap-2">
                <span className="text-sm text-amber-200">Revoke and disable bot access?</span>
                <button
                  type="button"
                  className="rounded border border-red-600/70 px-3 py-1.5 text-sm text-red-300 hover:bg-red-900/30 transition"
                  onClick={handleRevoke}
                  disabled={revokeMutation.isPending}
                >
                  {revokeMutation.isPending ? "Revoking…" : "Yes, revoke"}
                </button>
                <button
                  type="button"
                  className="text-sm text-parchment-300/60 hover:text-parchment-100"
                  onClick={() => setConfirmRevoke(false)}
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="rounded border border-ink-600 px-3 py-1.5 text-sm text-parchment-300 hover:border-red-600/60 hover:text-red-300 transition"
                onClick={() => setConfirmRevoke(true)}
              >
                Revoke key
              </button>
            )
          )}
        </div>

        {(createMutation.error || revokeMutation.error) && (
          <p className="mt-3 text-sm text-red-400" role="alert">
            {String(createMutation.error ?? revokeMutation.error)}
          </p>
        )}
      </div>
    </div>
  );
}
