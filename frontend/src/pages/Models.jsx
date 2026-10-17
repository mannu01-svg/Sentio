import { fetchCompare, fetchSummary } from "../lib/api"
import { usePolling } from "../lib/hooks"
import { Card, SectionTitle, SentimentChip, Skeleton, EmptyState } from "../components/UI"

function ConfusionBar({ matrix, model }) {
  const labels = ["positive", "negative", "neutral"]
  const max = Math.max(...labels.flatMap((t) => labels.map((p) => matrix[t][p])), 1)
  return (
    <div className="space-y-2">
      {labels.map((t) => (
        <div key={t}>
          <div className="mb-1 flex items-center justify-between text-[10px]">
            <span style={{ color: "var(--text-faint)" }}>true: <strong style={{ color: `var(--${t})` }}>{t}</strong></span>
          </div>
          <div className="grid grid-cols-3 gap-1.5">
            {labels.map((p) => (
              <div
                key={p}
                className="rounded-lg px-2 py-2 text-center font-mono text-xs"
                style={{
                  background: `color-mix(in srgb, var(--${p}) ${Math.round((matrix[t][p] / max) * 30)}%, var(--panel-solid))`,
                  border: `1px solid ${t === p ? "var(--positive)" : "var(--border-soft)"}`,
                  opacity: matrix[t][p] / max > 0.02 ? 1 : 0.4,
                }}
                title={`${t} → ${p}: ${matrix[t][p]}`}
              >
                {matrix[t][p]}
                <div className="text-[8px] font-sans opacity-60">pred {p[0].toUpperCase()}</div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function Models() {
  const compare = usePolling(() => fetchCompare(1000), [], 10000)
  const summary = usePolling(fetchSummary, [], 10000)
  const d = compare.data

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-extrabold">Model Comparison</h1>
        <p className="text-xs" style={{ color: "var(--text-soft)" }}>
          Three generations of NLP: VADER lexicon → DistilBERT transformer → tweet-trained LLM — on every comment, side by side
        </p>
      </div>

      {!d || d.compared === 0 ? (
        <Card className="p-10"><EmptyState text="No scored comments to compare yet — start the pipeline." /></Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            <Card hover className="p-5">
              <div className="text-xs font-semibold" style={{ color: "var(--text-soft)" }}>VADER vs LLM agreement</div>
              <div className="count-in mt-2 font-mono text-3xl font-extrabold grad-text">{d.vader_vs_llm_agreement_pct}%</div>
              <div className="mt-1 text-[11px]" style={{ color: "var(--text-faint)" }}>{d.agree_vader_llm} of {d.compared} agree</div>
            </Card>
            <Card hover className="p-5">
              <div className="text-xs font-semibold" style={{ color: "var(--text-soft)" }}>DistilBERT vs LLM agreement</div>
              <div className="count-in mt-2 font-mono text-3xl font-extrabold" style={{ color: "var(--accent3)" }}>
                {d.bert_vs_llm_agreement_pct != null ? `${d.bert_vs_llm_agreement_pct}%` : "—"}
              </div>
              <div className="mt-1 text-[11px]" style={{ color: "var(--text-faint)" }}>
                {d.bert_vs_llm_agreement_pct != null
                  ? `${(summary.data?.bert_scored ?? 0).toLocaleString()} bert-scored comments`
                  : "no DistilBERT rows in the current window"}
              </div>
            </Card>
            <Card hover className="p-5">
              <div className="text-xs font-semibold" style={{ color: "var(--text-soft)" }}>All 3 agree</div>
              <div className="count-in mt-2 font-mono text-3xl font-extrabold" style={{ color: "var(--positive)" }}>
                {d.all_three_agreement_pct}%
              </div>
              <div className="mt-1 text-[11px]" style={{ color: "var(--text-faint)" }}>consensus on recent comments</div>
            </Card>
            <Card hover className="p-5">
              <div className="text-xs font-semibold" style={{ color: "var(--text-soft)" }}>Label accuracy (LLM)</div>
              <div className="count-in mt-2 font-mono text-3xl font-extrabold" style={{ color: "var(--positive)" }}>
                {d.label_accuracy_llm_pct != null ? `${d.label_accuracy_llm_pct}%` : "—"}
              </div>
              <div className="mt-1 text-[11px]" style={{ color: "var(--text-faint)" }}>vs dataset ground truth</div>
            </Card>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <Card hover className="p-4">
              <div className="flex items-center justify-between text-[11px]">
                <span style={{ color: "var(--text-soft)" }}>VADER coverage</span>
                <span className="font-mono font-bold">{summary.data ? `${Math.round(((summary.data.vader_scored ?? 0) / Math.max(summary.data.total, 1)) * 100)}%` : "—"}</span>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full" style={{ background: "var(--border-soft)" }}>
                <div className="h-full rounded-full" style={{ width: summary.data ? `${(summary.data.vader_scored ?? 0) * 100 / Math.max(summary.data.total, 1)}%` : "0%", background: "var(--cyan)" }} />
              </div>
              <div className="mt-1 font-mono text-[10px]" style={{ color: "var(--text-faint)" }}>{(summary.data?.vader_scored ?? 0).toLocaleString()} scored</div>
            </Card>
            <Card hover className="p-4">
              <div className="flex items-center justify-between text-[11px]">
                <span style={{ color: "var(--text-soft)" }}>DistilBERT coverage</span>
                <span className="font-mono font-bold">{summary.data ? `${Math.round(((summary.data.bert_scored ?? 0) / Math.max(summary.data.total, 1)) * 100)}%` : "—"}</span>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full" style={{ background: "var(--border-soft)" }}>
                <div className="h-full rounded-full" style={{ width: summary.data ? `${(summary.data.bert_scored ?? 0) * 100 / Math.max(summary.data.total, 1)}%` : "0%", background: "var(--accent3)" }} />
              </div>
              <div className="mt-1 font-mono text-[10px]" style={{ color: "var(--text-faint)" }}>{(summary.data?.bert_scored ?? 0).toLocaleString()} scored</div>
            </Card>
            <Card hover className="p-4">
              <div className="flex items-center justify-between text-[11px]">
                <span style={{ color: "var(--text-soft)" }}>LLM coverage ★</span>
                <span className="font-mono font-bold" style={{ color: "var(--positive)" }}>{summary.data ? `${Math.round(((summary.data.llm_scored ?? 0) / Math.max(summary.data.total, 1)) * 100)}%` : "—"}</span>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full" style={{ background: "var(--border-soft)" }}>
                <div className="h-full rounded-full" style={{ width: summary.data ? `${(summary.data.llm_scored ?? 0) * 100 / Math.max(summary.data.total, 1)}%` : "0%", background: "var(--positive)" }} />
              </div>
              <div className="mt-1 font-mono text-[10px]" style={{ color: "var(--text-faint)" }}>{(summary.data?.llm_scored ?? 0).toLocaleString()} scored</div>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Card className="p-5">
              <SectionTitle title="How they differ" detail="Three generations of NLP" />
              <div className="space-y-3">
                <div className="rounded-xl border p-4" style={{ borderColor: "var(--border-soft)" }}>
                  <div className="text-sm font-bold" style={{ color: "var(--cyan)" }}>VADER — lexicon & rules</div>
                  <p className="mt-1.5 text-xs leading-relaxed" style={{ color: "var(--text-soft)" }}>
                    A valence dictionary of ~7,500 words tuned for social media, plus rules for
                    punctuation, capitalization, negation and emoji. Transparent: every score is
                    traceable. Outputs a compound score in [-1, 1]; |score| ≤ 0.05 is neutral.
                  </p>
                </div>
                <div className="rounded-xl border p-4" style={{ borderColor: "var(--border-soft)" }}>
                  <div className="text-sm font-bold" style={{ color: "var(--accent3)" }}>DistilBERT — transformer</div>
                  <p className="mt-1.5 text-xs leading-relaxed" style={{ color: "var(--text-soft)" }}>
                    A 66M-parameter BERT distilled to 40% smaller / 60% faster, fine-tuned on SST-2.
                    Context-aware — understands "not good" the way a lexicon cannot. Binary
                    (positive/negative, no neutral class — visible in its errors).
                  </p>
                </div>
                <div className="rounded-xl border p-4" style={{ borderColor: "var(--positive)" }}>
                  <div className="text-sm font-bold" style={{ color: "var(--positive)" }}>RoBERTa LLM — tweet-trained ★</div>
                  <p className="mt-1.5 text-xs leading-relaxed" style={{ color: "var(--text-soft)" }}>
                    cardiffnlp/twitter-roberta-base-sentiment-latest — a 124M-parameter RoBERTa fine-tuned
                    on <strong>124 million real tweets</strong>. Understands slang, emoji semantics and
                    sarcasm patterns natively. 3-class (positive/neutral/negative). The authoritative
                    score for social-media comments.
                  </p>
                </div>
              </div>
            </Card>

            <Card className="p-5">
              <SectionTitle title="Where the LLM corrects VADER" detail="Lexicon fails on sarcasm & slang — the LLM resolves it" />
              <div className="space-y-2">
                {(d.llm_corrections ?? []).slice(0, 7).map((ex, i) => (
                  <div key={i} className="rounded-xl border p-3" style={{ borderColor: "var(--border-soft)" }}>
                    <p className="line-clamp-2 text-xs leading-relaxed">"{ex.text}"</p>
                    <div className="mt-2 flex items-center gap-2">
                      <span className="text-[10px]" style={{ color: "var(--text-faint)" }}>vader {ex.vader_score?.toFixed(2)}</span>
                      <SentimentChip label={ex.vader} />
                      <span className="text-[10px]" style={{ color: "var(--text-faint)" }}>→ LLM</span>
                      <SentimentChip label={ex.llm} />
                    </div>
                  </div>
                ))}
                {(d.llm_corrections ?? []).length === 0 && <EmptyState text="VADER and LLM fully agree in the current window." />}
              </div>
            </Card>

            <Card className="p-5">
              <SectionTitle title="Why this panel matters" detail="One-liner for your viva" />
              <p className="text-xs leading-relaxed" style={{ color: "var(--text-soft)" }}>
                "We run <strong style={{ color: "var(--text)" }}>three generations of NLP live</strong>: a lexicon
                (VADER), a distilled transformer (DistilBERT), and a tweet-trained LLM (RoBERTa). We quantify
                their agreement ({d.vader_vs_llm_agreement_pct}% VADER-vs-LLM on {d.compared.toLocaleString()} comments)
                and evaluate against dataset ground truth
                {d.label_accuracy_llm_pct != null ? ` (LLM: ${d.label_accuracy_llm_pct}% vs VADER: ${d.label_accuracy_vader_pct ?? "—"}%)` : ""}.
                The LLM's corrections of the lexicon — sarcasm, slang, emoji — are surfaced for inspection:
                disagreement isn't error, it's the finding."
              </p>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
