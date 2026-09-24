import { fetchPipeline, fetchSummary } from "../lib/api"
import { usePolling } from "../lib/hooks"
import { Card, SectionTitle, Skeleton } from "../components/UI"

const FLOW = [
  { key: "raw", name: "Producer", detail: "CSV replay + link fetches → JSON events", color: "var(--accent)" },
  { key: "kafka_raw", name: "Kafka · comments-raw", detail: "ingestion topic (3 partitions)", color: "var(--accent2)" },
  { key: "spark", name: "Spark Streaming", detail: "clean → VADER + DistilBERT → 1-min windows", color: "var(--accent3)" },
  { key: "kafka_scored", name: "Kafka · comments-scored", detail: "scored feed (powers the live feed)", color: "var(--cyan)" },
  { key: "pg", name: "PostgreSQL", detail: "scored rows + window stats (powers every chart)", color: "var(--positive)" },
]

export default function Pipeline() {
  const pipeline = usePolling(fetchPipeline, [], 5000)
  const summary = usePolling(fetchSummary, [], 6000)
  const stages = pipeline.data?.stages ?? []

  const valueFor = (idx) => {
    const st = stages[idx]
    return st?.value != null ? st.value.toLocaleString() : "—"
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-extrabold">Pipeline</h1>
        <p className="text-xs" style={{ color: "var(--text-soft)" }}>
          What's streaming right now — real counters from Kafka, Spark and PostgreSQL
        </p>
      </div>

      {/* live flow */}
      <div className="grid gap-3 xl:grid-cols-5">
        {FLOW.map((f, i) => (
          <div key={f.key} className="relative">
            <Card hover className="h-full p-4">
              <div className="flex items-center justify-between">
                <span className="flex size-8 items-center justify-center rounded-lg font-mono text-[10px] font-bold text-white" style={{ background: f.color }}>
                  {i + 1}
                </span>
                <span className="live-dot" />
              </div>
              <div className="mt-3 text-[13px] font-bold">{f.name}</div>
              <div className="mt-0.5 text-[10px] leading-relaxed" style={{ color: "var(--text-faint)" }}>{f.detail}</div>
              <div className="mt-3 border-t pt-2" style={{ borderColor: "var(--border-soft)" }}>
                <div className="font-mono text-xl font-extrabold" style={{ color: f.color }}>
                  {i === 2 ? `${pipeline.data?.flow_per_min ?? 0}` : valueFor(i === 0 ? 0 : i - 1)}
                </div>
                <div className="text-[9px]" style={{ color: "var(--text-faint)" }}>
                  {i === 2 ? "comments/min" : i === 0 ? "ingested (approx)" : stages[i - 1]?.unit ?? ""}
                </div>
              </div>
            </Card>
            {i < FLOW.length - 1 && (
              <span className="absolute -right-3 top-1/2 z-10 hidden -translate-y-1/2 text-lg xl:block" style={{ color: "var(--text-faint)" }}>→</span>
            )}
          </div>
        ))}
      </div>

      {/* stage details */}
      <div className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
        <Card className="p-5">
          <SectionTitle title="Stage counters" detail="Refreshed every 5 seconds — these are the numbers behind the charts" />
          {pipeline.data ? (
            <div className="space-y-2">
              {stages.map((st) => (
                <div key={st.name} className="flex items-center justify-between rounded-xl border px-4 py-3" style={{ borderColor: "var(--border-soft)" }}>
                  <div>
                    <div className="text-xs font-bold">{st.name}</div>
                    <div className="text-[10px]" style={{ color: "var(--text-faint)" }}>{st.detail}</div>
                  </div>
                  <div className="font-mono text-lg font-extrabold" style={{ color: "var(--accent)" }}>
                    {st.value != null ? st.value.toLocaleString() : "—"}
                    <span className="ml-1 text-[9px] font-normal" style={{ color: "var(--text-faint)" }}>{st.unit}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : <div className="space-y-2"><Skeleton h={48} /><Skeleton h={48} /><Skeleton h={48} /></div>}
        </Card>

        <Card className="p-5">
          <SectionTitle title="How the graphs are fed" detail="The data path, end to end" />
          <ol className="space-y-3 text-xs leading-relaxed" style={{ color: "var(--text-soft)" }}>
            <li className="flex gap-3">
              <span className="font-mono font-bold" style={{ color: "var(--accent)" }}>1.</span>
              <span><strong style={{ color: "var(--text)" }}>Producer</strong> replays Kaggle datasets & fetched post comments into Kafka at ~15 msg/s (each: id, source, text, timestamp).</span>
            </li>
            <li className="flex gap-3">
              <span className="font-mono font-bold" style={{ color: "var(--accent)" }}>2.</span>
              <span><strong style={{ color: "var(--text)" }}>Spark</strong> consumes micro-batches, cleans text, scores VADER + DistilBERT, and aggregates 1-minute windows with a 2-minute watermark.</span>
            </li>
            <li className="flex gap-3">
              <span className="font-mono font-bold" style={{ color: "var(--accent)" }}>3.</span>
              <span><strong style={{ color: "var(--text)" }}>Every comment</strong> lands in PostgreSQL with its scores; every window lands in window_stats.</span>
            </li>
            <li className="flex gap-3">
              <span className="font-mono font-bold" style={{ color: "var(--accent)" }}>4.</span>
              <span><strong style={{ color: "var(--text)" }}>The dashboard polls the API every 2–10 s</strong> — the sentiment line = window_stats rows; the donut & KPIs = comment counts; agreement = per-comment model scores; velocity = word counts across two 30-min halves.</span>
            </li>
          </ol>
          <div className="mt-4 rounded-xl border p-3 text-[11px]" style={{ borderColor: "var(--border-soft)", color: "var(--text-faint)" }}>
            Max window seen (30 min): <strong style={{ color: "var(--accent)" }}>{pipeline.data?.max_window ?? 0}</strong> comments in one minute
          </div>
        </Card>
      </div>
    </div>
  )
}
