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
          Classic NLP (VADER lexicon) vs AI transformer (DistilBERT-SST2) — on every comment, side by side
        </p>
      </div>

      {!d || d.compared === 0 ? (
        <Card className="p-10"><EmptyState text="No scored comments to compare yet — start the pipeline." /></Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            <Card hover className="p-5">
              <div className="text-xs font-semibold" style={{ color: "var(--text-soft)" }}>Agreement</div>
              <div className="count-in mt-2 font-mono text-3xl font-extrabold grad-text">{d.agreement_pct}%</div>
              <div className="mt-1 text-[11px]" style={{ color: "var(--text-faint)" }}>{d.agree} of {d.compared} agree</div>
            </Card>
            <Card hover className="p-5">
              <div className="text-xs font-semibold" style={{ color: "var(--text-soft)" }}>Compared</div>
              <div className="count-in mt-2 font-mono text-3xl font-extrabold">{d.compared.toLocaleString()}</div>
              <div className="mt-1 text-[11px]" style={{ color: "var(--text-faint)" }}>recent comments</div>
            </Card>
            <Card hover className="p-5">
              <div className="text-xs font-semibold" style={{ color: "var(--text-soft)" }}>Label accuracy (VADER)</div>
              <div className="count-in mt-2 font-mono text-3xl font-extrabold" style={{ color: "var(--positive)" }}>
                {d.label_accuracy_vader_pct != null ? `${d.label_accuracy_vader_pct}%` : "—"}
              </div>
              <div className="mt-1 text-[11px]" style={{ color: "var(--text-faint)" }}>vs dataset ground truth</div>
            </Card>
            <Card hover className="p-5">
              <div className="text-xs font-semibold" style={{ color: "var(--text-soft)" }}>BERT coverage</div>
              <div className="count-in mt-2 font-mono text-3xl font-extrabold" style={{ color: "var(--cyan)" }}>
                {summary.data ? `${Math.round((summary.data.bert_scored / Math.max(summary.data.total, 1)) * 100)}%` : "—"}
              </div>
              <div className="mt-1 text-[11px]" style={{ color: "var(--text-faint)" }}>{(summary.data?.bert_scored ?? 0).toLocaleString()} scored</div>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card className="p-5">
              <SectionTitle title="How they differ" detail="The two paradigms, explained" />
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
                  <div className="text-sm font-bold" style={{ color: "var(--accent3)" }}>DistilBERT — transformer (AI)</div>
                  <p className="mt-1.5 text-xs leading-relaxed" style={{ color: "var(--text-soft)" }}>
                    A 66M-parameter BERT distilled to 40% smaller / 60% faster, fine-tuned on SST-2.
                    Context-aware — understands "not good" the way a lexicon cannot. Binary
                    (positive/negative, no neutral class — visible in its errors).
                  </p>
                </div>
              </div>
            </Card>

            <Card className="p-5">
              <SectionTitle title="Disagreement examples" detail="Where the two models diverge — the interesting cases" />
              <div className="space-y-2">
                {(d.disagreement_examples ?? []).slice(0, 6).map((ex, i) => (
                  <div key={i} className="rounded-xl border p-3" style={{ borderColor: "var(--border-soft)" }}>
                    <p className="line-clamp-2 text-xs leading-relaxed">"{ex.text}"</p>
                    <div className="mt-2 flex items-center gap-2">
                      <span className="text-[10px]" style={{ color: "var(--text-faint)" }}>vader {ex.vader_score?.toFixed(2)}</span>
                      <SentimentChip label={ex.vader} />
                      <span className="text-[10px]" style={{ color: "var(--text-faint)" }}>vs</span>
                      <SentimentChip label={ex.bert} />
                    </div>
                  </div>
                ))}
                {(d.disagreement_examples ?? []).length === 0 && <EmptyState text="Perfect agreement in the current window." />}
              </div>
            </Card>
          </div>

          <Card className="p-5">
            <SectionTitle title="Why this panel matters" detail="One-liner for your viva" />
            <p className="text-xs leading-relaxed" style={{ color: "var(--text-soft)" }}>
              "We don't just predict sentiment — we <strong style={{ color: "var(--text)" }}>compare two paradigms live</strong>,
              quantify their agreement ({d.agreement_pct}% on {d.compared.toLocaleString()} comments), and
              evaluate both against the dataset's ground-truth labels
              {d.label_accuracy_vader_pct != null ? ` (VADER: ${d.label_accuracy_vader_pct}% accuracy)` : ""}.
              The disagreement examples are surfaced for human inspection — disagreement isn't error, it's signal."
            </p>
          </Card>
        </>
      )}
    </div>
  )
}
