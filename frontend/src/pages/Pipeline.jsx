import { fetchPipeline, fetchSummary, fetchStreamStatus } from "../lib/api"
import { usePolling } from "../lib/hooks"
import { Card, SectionTitle, Skeleton, EmptyState } from "../components/UI"

function Explain({ children }) {
  return <p className="text-[11px] leading-relaxed" style={{ color: "var(--text-soft)" }}>{children}</p>
}

function Stat({ label, value, unit, tone = "var(--accent)", hint }) {
  return (
    <div className="rounded-xl border p-4" style={{ borderColor: "var(--border-soft)" }}>
      <div className="text-[11px] font-semibold" style={{ color: "var(--text-soft)" }}>{label}</div>
      <div className="mt-1 font-mono text-2xl font-extrabold" style={{ color: tone }}>
        {value}{unit && <span className="ml-1 text-[10px] font-normal" style={{ color: "var(--text-faint)" }}>{unit}</span>}
      </div>
      {hint && <div className="mt-1 text-[10.5px] leading-snug" style={{ color: "var(--text-faint)" }}>{hint}</div>}
    </div>
  )
}

export default function Pipeline() {
  const pipeline = usePolling(fetchPipeline, [], 5000)
  const summary = usePolling(fetchSummary, [], 6000)
  const stream = usePolling(fetchStreamStatus, [], 4000)

  const stages = pipeline.data?.stages ?? []
  const byName = (name) => stages.find((s) => s.name.includes(name))
  const kafkaRaw = byName("comments-raw")?.value
  const kafkaScored = byName("comments-scored")?.value
  const dbRows = byName("PostgreSQL · comments")?.value
  const perMin = pipeline.data?.flow_per_min ?? 0
  const backlog = kafkaRaw != null && kafkaScored != null ? kafkaRaw - kafkaScored : null

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-extrabold">Pipeline</h1>
        <p className="text-xs" style={{ color: "var(--text-soft)" }}>
          Every number, explained in plain English
        </p>
      </div>

      {/* the flow, with meaning */}
      <div className="grid gap-3 lg:grid-cols-2">
        <Card className="p-5">
          <SectionTitle title="What each stage does" detail="Follow one comment through the system" />
          <ol className="space-y-3 text-xs leading-relaxed">
            <li className="flex gap-3">
              <span className="font-mono font-bold" style={{ color: "var(--accent)" }}>1.</span>
              <span>
                <strong>Producer</strong> — replays the Kaggle datasets into Kafka. It idles until you hit
                <strong> "Go live"</strong> on the Dashboard, then streams a burst at ~40 comments/sec.
                <Explain>Think of it as a firehose of real comments you can turn on and off.</Explain>
              </span>
            </li>
            <li className="flex gap-3">
              <span className="font-mono font-bold" style={{ color: "var(--accent2)" }}>2.</span>
              <span>
                <strong>Kafka · comments-raw</strong> — the inbox where un-scored comments wait.
                <Explain>comments-raw counts every comment ever ingested (dataset replays + live fetches + topic streams).</Explain>
              </span>
            </li>
            <li className="flex gap-3">
              <span className="font-mono font-bold" style={{ color: "var(--accent3)" }}>3.</span>
              <span>
                <strong>Spark Streaming</strong> — the brain. Cleans each comment, scores it with three models
                (VADER + DistilBERT + the cardiffnlp LLM), and computes 1-minute sentiment windows.
                <Explain>"Comments/min" = how many Spark scored in the last minute. When it reads 0, the producer is idle — nothing new to score.</Explain>
              </span>
            </li>
            <li className="flex gap-3">
              <span className="font-mono font-bold" style={{ color: "var(--cyan)" }}>4.</span>
              <span>
                <strong>Kafka · comments-scored</strong> — the outbox of scored comments. Feeds the live feed page.
              </span>
            </li>
            <li className="flex gap-3">
              <span className="font-mono font-bold" style={{ color: "var(--positive)" }}>5.</span>
              <span>
                <strong>PostgreSQL</strong> — the database of record. Every scored comment + every 1-min window.
                <Explain>This count is your Dashboard's "Comments processed" KPI — the number that grows during a live demo.</Explain>
              </span>
            </li>
          </ol>
        </Card>

        <div className="space-y-4">
          <Card className="p-5">
            <SectionTitle title="Right now" detail="Live health of each stage" />
            <div className="grid gap-3 sm:grid-cols-2">
              <Stat
                label="Comments scored last minute"
                value={perMin}
                unit="/min"
                tone="var(--accent3)"
                hint={perMin === 0 ? "Spark is idle — hit 'Go live' on the Dashboard to start a burst" : "Spark is actively scoring"}
              />
              <Stat
                label="Backlog (waiting to be scored)"
                value={backlog != null ? Math.max(backlog, 0).toLocaleString() : "—"}
                unit={backlog != null ? "msgs" : ""}
                tone={backlog > 20000 ? "var(--negative)" : "var(--positive)"}
                hint={backlog > 20000 ? "Spark is draining a large burst — scores arrive in waves" : backlog != null && backlog > 0 ? "fresh comments waiting for their scores" : "fully caught up"}
              />
              <Stat
                label="DB rows (all-time scored)"
                value={dbRows != null ? dbRows.toLocaleString() : "—"}
                tone="var(--positive)"
                hint="grows by ~2,400 per Go-live burst · this is the dashboard counter"
              />
              <Stat
                label="LLM coverage"
                value={summary.data ? `${Math.round((summary.data.llm_scored / Math.max(summary.data.total, 1)) * 100)}%` : "—"}
                tone="var(--cyan)"
                hint={`${(summary.data?.llm_scored ?? 0).toLocaleString()} of ${(summary.data?.total ?? 0).toLocaleString()} rows carry the LLM verdict`}
              />
            </div>
          </Card>

          <Card className="p-5">
            <SectionTitle title="Spark health" detail="The #1 thing to check when numbers freeze" />
            {pipeline.data ? (
              <div className="space-y-2.5">
                <div className="flex items-center gap-3 rounded-xl border p-3" style={{ borderColor: "var(--border-soft)" }}>
                  <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: perMin > 0 ? "var(--positive)" : "#eab308" }} />
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-bold">{perMin > 0 ? "Scoring now" : "Idle — waiting for data"}</div>
                    <Explain>
                      {perMin > 0
                        ? "Spark consumed a micro-batch in the last 60s. Windows + scores are being written."
                        : "Zero comments/min just means no new comments arrived — press 'Go live' to feed it. If the Dashboard counter is ALSO frozen during a burst, restart Spark: rm -rf checkpoints/* && ./run_spark.sh"}
                    </Explain>
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-xl border p-3" style={{ borderColor: "var(--border-soft)" }}>
                  <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: (pipeline.data?.max_window ?? 0) > 0 ? "var(--positive)" : "var(--neutral)" }} />
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-bold">Peak minute: {pipeline.data?.max_window ?? 0} comments</div>
                    <Explain>The biggest 1-minute window Spark has ever aggregated — proof the windowing works.</Explain>
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-xl border p-3" style={{ borderColor: "var(--border-soft)" }}>
                  <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: stream.data?.live ? "var(--positive)" : "var(--border-soft)" }} />
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-bold">{stream.data?.live ? `Producer: LIVE burst (${stream.data.seconds_left}s left)` : "Producer: idle (by design)"}</div>
                    <Explain>The producer only streams when you ask — that's why counters stay stable between demo bursts.</Explain>
                  </div>
                </div>
              </div>
            ) : <Skeleton h={160} />}
          </Card>
        </div>
      </div>

      {/* raw stage counters, kept for transparency */}
      <Card className="p-5">
        <SectionTitle title="Raw stage counters" detail="The exact Kafka/DB numbers behind the explanations above" />
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
    </div>
  )
}
