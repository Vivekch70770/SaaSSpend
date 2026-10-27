import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import { LoaderCircle, Send, Sparkles } from "lucide-react";
import { requestApi } from "../lib/api";
import { formatDate, inr } from "../lib/format";
import { Card, Page } from "../ui";

type AssistantItem = Record<string, string | number | boolean | null>;
type ChatResponse = { intent: string; answer: string; items: AssistantItem[] };
type Message = { role: "user" | "assistant"; text: string; items?: AssistantItem[] };

const starters = [
  "Which applications cost us the most?",
  "Which subscriptions have the most unused licenses?",
  "What renewals are coming up?",
  "How much potential savings do we have?",
];

function displayKey(key: string) {
  return key.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function displayValue(key: string, value: string | number | boolean | null) {
  if (value === null) return "Unavailable";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number" && /(cost|savings|annual)/i.test(key)) return inr(value);
  if (typeof value === "number" && /utilization/i.test(key)) return `${value}%`;
  if (typeof value === "number" && /days_remaining/i.test(key)) return `${value} days`;
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) return formatDate(value);
  return String(value);
}

export default function Assistant() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const sendingRef = useRef(false);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  async function sendMessage(text = draft) {
    const message = text.trim();
    if (!message || sendingRef.current) return;

    sendingRef.current = true;
    setSending(true);
    setError("");
    setDraft("");
    setMessages((current) => [...current, { role: "user", text: message }]);
    try {
      const response = await requestApi<ChatResponse>("/assistant/chat", {
        method: "POST",
        body: JSON.stringify({ message }),
      });
      setMessages((current) => [
        ...current,
        { role: "assistant", text: response.answer, items: response.items },
      ]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The assistant could not answer. Please try again.");
    } finally {
      sendingRef.current = false;
      setSending(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  }

  return (
    <Page
      title="Assistant"
      sub="Ask about your saved application, license, renewal, and savings data."
    >
      <div className="mx-auto flex min-h-[68vh] w-full max-w-4xl flex-col">
        <Card className="flex min-h-[440px] flex-1 flex-col overflow-hidden p-0">
          <div className="flex items-center gap-3 border-b border-stone-200 px-5 py-4 dark:border-white/[.06]">
            <span className="grid size-9 place-items-center rounded-xl bg-[#c6f36a]/10 text-[#c6f36a]">
              <Sparkles size={17} />
            </span>
            <div>
              <p className="text-sm font-medium">SaaSSpend Assistant</p>
              <p className="text-xs text-stone-500">Data-grounded · Read-only</p>
            </div>
          </div>

          <div aria-live="polite" className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-6">
            {!messages.length && (
              <div className="mx-auto max-w-xl py-8 text-center">
                <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-[#c6f36a]/10 text-[#c6f36a]">
                  <Sparkles size={21} />
                </span>
                <h2 className="mt-4 text-lg font-semibold">What would you like to understand?</h2>
                <p className="mt-2 text-sm text-stone-500">
                  I answer from the current SaaSSpend records. I don’t use an external AI model or change data.
                </p>
                <div className="mt-6 grid gap-2 sm:grid-cols-2">
                  {starters.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      disabled={sending}
                      onClick={() => void sendMessage(prompt)}
                      className="rounded-xl border border-stone-200 px-3 py-3 text-left text-xs text-stone-600 transition hover:border-[#c6f36a]/40 hover:text-stone-900 disabled:opacity-50 dark:border-white/[.08] dark:text-stone-300 dark:hover:text-white"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((message, index) => (
              <div key={`${message.role}-${index}`} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[92%] rounded-2xl px-4 py-3 sm:max-w-[82%] ${message.role === "user" ? "bg-[#c6f36a] text-[#171a12]" : "border border-stone-200 bg-stone-50 text-stone-800 dark:border-white/[.07] dark:bg-[#171914] dark:text-stone-100"}`}>
                  <p className="whitespace-pre-wrap text-sm leading-6">{message.text}</p>
                  {!!message.items?.length && (
                    <div className="mt-3 space-y-2">
                      {message.items.map((item, itemIndex) => (
                        <div key={itemIndex} className="rounded-xl border border-stone-200/70 bg-white/70 p-3 text-xs dark:border-white/[.06] dark:bg-black/15">
                          {Object.entries(item).map(([key, value]) => (
                            <div key={key} className="flex flex-wrap justify-between gap-x-4 gap-y-1 py-0.5">
                              <span className="text-stone-500">{displayKey(key)}</span>
                              <span className="text-right font-medium">{displayValue(key, value)}</span>
                            </div>
                          ))}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {sending && (
              <div role="status" className="flex items-center gap-2 px-2 text-xs text-stone-500">
                <LoaderCircle size={14} className="animate-spin text-[#c6f36a]" />
                Checking SaaSSpend data…
              </div>
            )}
            <div ref={endRef} />
          </div>

          <div className="border-t border-stone-200 p-3 sm:p-4 dark:border-white/[.06]">
            {error && (
              <div role="alert" className="mb-3 flex items-center justify-between gap-3 rounded-lg border border-rose-400/20 bg-rose-400/[.05] px-3 py-2 text-xs text-rose-200">
                <span>{error}</span>
                <button type="button" onClick={() => setError("")} className="shrink-0 underline underline-offset-2">Dismiss</button>
              </div>
            )}
            <form onSubmit={submit} className="flex items-end gap-2">
              <label className="sr-only" htmlFor="assistant-message">Message the SaaSSpend Assistant</label>
              <textarea
                id="assistant-message"
                value={draft}
                maxLength={1000}
                rows={2}
                disabled={sending}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about spend, licenses, renewals, or savings…"
                className="max-h-36 min-h-12 flex-1 resize-y rounded-xl border border-stone-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-[#a6d84d] disabled:opacity-60 dark:border-white/[.08] dark:bg-[#0e0f0c]"
              />
              <button
                type="submit"
                disabled={sending || !draft.trim()}
                className="grid size-11 shrink-0 place-items-center rounded-xl bg-[#c6f36a] text-[#171a12] transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="Send message"
              >
                {sending ? <LoaderCircle size={17} className="animate-spin" /> : <Send size={17} />}
              </button>
            </form>
            <p className="mt-2 text-right text-[10px] text-stone-500">Enter to send · Shift+Enter for a new line · 1000 characters max</p>
          </div>
        </Card>
      </div>
    </Page>
  );
}
