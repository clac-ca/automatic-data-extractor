import clsx from "clsx";
import { useMemo, useRef, useState } from "react";

import { Button } from "@ui/Button";

import type { DocumentComment, WorkspacePerson } from "../types";
import { formatRelativeTime } from "../utils";

function renderWithMentions(text: string) {
  const parts: (string | { mention: string })[] = [];
  const re = /@{([^}]+)}/g;
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = re.exec(text))) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    parts.push({ mention: match[1] });
    last = re.lastIndex;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function findMentionQuery(text: string, caret: number) {
  const before = text.slice(0, caret);
  const at = before.lastIndexOf("@");
  if (at < 0) return null;
  const prev = at === 0 ? " " : before[at - 1];
  if (prev !== " " && prev !== "\n" && prev !== "\t") return null;

  const query = before.slice(at + 1);
  if (query.includes("{") || query.includes("}")) return null;
  if (query.length > 40) return null;
  if (query.includes(" ")) return null;

  return { start: at, query };
}

export function CommentsPanel({
  now,
  comments,
  people,
  currentUserKey,
  currentUserLabel,
  onAdd,
  onEdit,
  onDelete,
}: {
  now: number;
  comments: DocumentComment[];
  people: WorkspacePerson[];
  currentUserKey: string;
  currentUserLabel: string;
  onAdd: (body: string, mentions: { key: string; label: string }[]) => void;
  onEdit: (commentId: string, body: string, mentions: { key: string; label: string }[]) => void;
  onDelete: (commentId: string) => void;
}) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [draft, setDraft] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingBody, setEditingBody] = useState("");
  const [query, setQuery] = useState<{ start: number; query: string } | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);

  const mentionCandidates = useMemo(() => {
    const q = query?.query.trim().toLowerCase() ?? "";
    const base = people.filter((p) => p.kind === "user");
    if (!q) return base.slice(0, 10);
    return base.filter((p) => p.label.toLowerCase().includes(q)).slice(0, 10);
  }, [people, query?.query]);

  function extractMentions(body: string) {
    const matches = Array.from(body.matchAll(/@{([^}]+)}/g));
    const labels = matches.map((m) => m[1]).filter(Boolean);
    const map = new Map<string, WorkspacePerson>();
    people.forEach((p) => map.set(p.label, p));
    return labels.map((label) => {
      const person = map.get(label);
      return { key: person?.key ?? `label:${label}`, label };
    });
  }

  function insertMention(label: string) {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const caret = textarea.selectionStart ?? draft.length;
    const q = findMentionQuery(draft, caret);
    if (!q) return;

    const before = draft.slice(0, q.start);
    const after = draft.slice(caret);
    const insert = `@{${label}} `;
    const next = `${before}${insert}${after}`;
    setDraft(next);
    setQuery(null);

    requestAnimationFrame(() => {
      const pos = (before + insert).length;
      textarea.focus();
      textarea.setSelectionRange(pos, pos);
    });
  }

  function onDraftChange(value: string) {
    setDraft(value);
    const textarea = textareaRef.current;
    const caret = textarea?.selectionStart ?? value.length;
    const q = findMentionQuery(value, caret);
    setQuery(q);
    setActiveIndex(0);
  }

  function submit() {
    const body = draft.trim();
    if (!body) return;
    onAdd(body, extractMentions(body));
    setDraft("");
    setQuery(null);
  }

  return (
    <div className="flex min-h-0 flex-col gap-4">
      <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600">
        <p className="font-semibold text-slate-900">Notes and comments</p>
        <p className="mt-1">
          Use <span className="font-semibold">@</span> to mention teammates (e.g. <span className="font-semibold">@{"{Jane Doe}"}</span>).
          Mentions are styled now and can power notifications later.
        </p>
        <p className="mt-1 text-[11px] text-slate-500">
          (For now, notes are stored locally per browser until backend syncing is added.)
        </p>
      </div>

      <div className="flex-1 overflow-auto rounded-2xl border border-slate-200 bg-white">
        {comments.length === 0 ? (
          <div className="px-4 py-6 text-sm text-slate-500">
            No notes yet. Add the first note to capture context for the team.
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {comments
              .slice()
              .sort((a, b) => a.createdAt - b.createdAt)
              .map((c) => {
                const isAuthor = c.authorKey === currentUserKey;
                const isEditing = editingId === c.id;
                return (
                  <div key={c.id} className="px-4 py-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{c.authorLabel}</p>
                        <p className="text-[11px] text-slate-500">
                          {formatRelativeTime(now, c.createdAt)}
                          {c.updatedAt !== c.createdAt ? " - edited" : ""}
                        </p>
                      </div>
                      {isAuthor ? (
                        <div className="flex items-center gap-2">
                          {!isEditing ? (
                            <>
                              <button
                                type="button"
                                onClick={() => {
                                  setEditingId(c.id);
                                  setEditingBody(c.body);
                                }}
                                className="text-xs font-semibold text-slate-500 hover:text-slate-700"
                              >
                                Edit
                              </button>
                              <button
                                type="button"
                                onClick={() => onDelete(c.id)}
                                className="text-xs font-semibold text-rose-600 hover:text-rose-700"
                              >
                                Delete
                              </button>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                    </div>

                    {isEditing ? (
                      <div className="mt-3">
                        <textarea
                          value={editingBody}
                          onChange={(e) => setEditingBody(e.target.value)}
                          className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-brand-300"
                          rows={3}
                        />
                        <div className="mt-2 flex items-center gap-2">
                          <Button
                            type="button"
                            size="sm"
                            onClick={() => {
                              const body = editingBody.trim();
                              if (!body) return;
                              onEdit(c.id, body, extractMentions(body));
                              setEditingId(null);
                              setEditingBody("");
                            }}
                          >
                            Save
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              setEditingId(null);
                              setEditingBody("");
                            }}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="mt-3 whitespace-pre-wrap text-sm text-slate-700">
                        {renderWithMentions(c.body).map((p, idx) =>
                          typeof p === "string" ? (
                            <span key={idx}>{p}</span>
                          ) : (
                            <span
                              key={idx}
                              className="rounded-md bg-brand-50 px-1.5 py-0.5 font-semibold text-brand-700"
                              title="Mention (notifications coming soon)"
                            >
                              @{p.mention}
                            </span>
                          ),
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
          </div>
        )}
      </div>

      <div className="relative rounded-2xl border border-slate-200 bg-white px-4 py-4">
        <p className="text-xs font-semibold text-slate-500">Add a note</p>
        <div className="mt-2">
          <textarea
            ref={textareaRef}
            value={draft}
            onChange={(e) => onDraftChange(e.target.value)}
            onKeyDown={(e) => {
              if (query && mentionCandidates.length > 0) {
                if (e.key === "ArrowDown") {
                  e.preventDefault();
                  setActiveIndex((i) => Math.min(mentionCandidates.length - 1, i + 1));
                }
                if (e.key === "ArrowUp") {
                  e.preventDefault();
                  setActiveIndex((i) => Math.max(0, i - 1));
                }
                if (e.key === "Enter") {
                  if (!e.shiftKey) {
                    e.preventDefault();
                    const chosen = mentionCandidates[activeIndex];
                    if (chosen) insertMention(chosen.label);
                    return;
                  }
                }
                if (e.key === "Escape") {
                  setQuery(null);
                }
              }
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={`Write a note... (author: ${currentUserLabel})`}
            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-brand-300"
            rows={3}
          />

          {query && mentionCandidates.length > 0 ? (
            <div className="absolute bottom-[5.5rem] left-4 right-4 z-20 rounded-2xl border border-slate-200 bg-white shadow-lg">
              <div className="border-b border-slate-100 px-3 py-2 text-[11px] text-slate-500">
                Mention someone (Enter to select, Esc to close)
              </div>
              <div className="max-h-56 overflow-auto p-2">
                {mentionCandidates.map((p, idx) => (
                  <button
                    key={p.key}
                    type="button"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      insertMention(p.label);
                    }}
                    className={clsx(
                      "flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition",
                      idx === activeIndex ? "bg-brand-50" : "hover:bg-slate-50",
                    )}
                  >
                    <span className="font-semibold text-slate-900">{p.label}</span>
                    <span className="text-xs text-slate-400">{p.kind === "user" ? "Member" : ""}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <div className="mt-2 flex items-center justify-between">
            <p className="text-[11px] text-slate-500">Tip: Ctrl/Cmd+Enter to submit</p>
            <Button type="button" size="sm" onClick={submit} disabled={!draft.trim()}>
              Post note
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
