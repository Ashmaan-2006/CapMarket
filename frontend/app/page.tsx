"use client";

import { useEffect, useMemo, useState } from "react";
import { Activity, BarChart3, Database, FileText, Play } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { AiReport, EtlJob, MetricPoint, PricePoint, Ticker, api } from "@/lib/api";

function formatPercent(value: string | null | undefined) {
  if (!value) return "n/a";
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function latest<T>(items: T[]) {
  return items.length ? items[items.length - 1] : null;
}

export default function DashboardPage() {
  const [tickers, setTickers] = useState<Ticker[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState("AAPL");
  const [prices, setPrices] = useState<PricePoint[]>([]);
  const [metrics, setMetrics] = useState<MetricPoint[]>([]);
  const [etlJobs, setEtlJobs] = useState<EtlJob[]>([]);
  const [reports, setReports] = useState<AiReport[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api
      .tickers()
      .then((data) => {
        setTickers(data);
        if (data[0]?.symbol) setSelectedSymbol(data[0].symbol);
      })
      .catch(() => setTickers([]));
    api.etlStatus().then(setEtlJobs).catch(() => setEtlJobs([]));
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([api.prices(selectedSymbol), api.metrics(selectedSymbol), api.reports(selectedSymbol)])
      .then(([priceData, metricData, reportData]) => {
        setPrices(priceData);
        setMetrics(metricData);
        setReports(reportData);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [selectedSymbol]);

  const latestMetric = useMemo(() => latest(metrics), [metrics]);
  const latestReport = reports[0];

  async function runEtl() {
    setLoading(true);
    setError(null);
    try {
      const job = await api.runEtl([selectedSymbol]);
      setEtlJobs((current) => [job, ...current]);
      const [priceData, metricData] = await Promise.all([
        api.prices(selectedSymbol),
        api.metrics(selectedSymbol)
      ]);
      setPrices(priceData);
      setMetrics(metricData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "ETL failed");
    } finally {
      setLoading(false);
    }
  }

  async function generateReport() {
    setLoading(true);
    setError(null);
    try {
      const report = await api.generateReport(selectedSymbol);
      setReports((current) => [report, ...current]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report generation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div>
            <h1 className="text-xl font-semibold tracking-normal">Capital Markets AI Reporting</h1>
            <p className="text-sm text-slate-600">ETL, analytics, and grounded analyst reports</p>
          </div>
          <div className="flex items-center gap-2">
            <select
              className="h-10 rounded border border-line bg-white px-3 text-sm"
              value={selectedSymbol}
              onChange={(event) => setSelectedSymbol(event.target.value)}
            >
              {[selectedSymbol, ...tickers.map((ticker) => ticker.symbol)]
                .filter((symbol, index, all) => all.indexOf(symbol) === index)
                .map((symbol) => (
                  <option key={symbol}>{symbol}</option>
                ))}
            </select>
            <button
              className="inline-flex h-10 items-center gap-2 rounded bg-ink px-3 text-sm font-medium text-white disabled:opacity-60"
              onClick={runEtl}
              disabled={loading}
              title="Run ETL"
            >
              <Play size={16} />
              ETL
            </button>
          </div>
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl gap-4 px-6 py-5 lg:grid-cols-[2fr_1fr]">
        <div className="rounded border border-line bg-white p-4">
          <div className="mb-3 flex items-center gap-2">
            <BarChart3 size={18} />
            <h2 className="text-base font-semibold">{selectedSymbol} Price History</h2>
          </div>
          <div className="h-[360px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={prices}>
                <CartesianGrid stroke="#e4e7e2" />
                <XAxis dataKey="price_date" minTickGap={32} tick={{ fontSize: 12 }} />
                <YAxis domain={["auto", "auto"]} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Line type="monotone" dataKey="close" stroke="#285c7a" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="grid gap-4">
          <div className="rounded border border-line bg-white p-4">
            <div className="mb-3 flex items-center gap-2">
              <Activity size={18} />
              <h2 className="text-base font-semibold">Stored Metrics</h2>
            </div>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-slate-500">Daily return</dt>
                <dd className="font-semibold">{formatPercent(latestMetric?.daily_return)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Weekly return</dt>
                <dd className="font-semibold">{formatPercent(latestMetric?.weekly_return)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">20d volatility</dt>
                <dd className="font-semibold">{formatPercent(latestMetric?.volatility_20d)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Drawdown</dt>
                <dd className="font-semibold">{formatPercent(latestMetric?.drawdown)}</dd>
              </div>
            </dl>
          </div>

          <div className="rounded border border-line bg-white p-4">
            <div className="mb-3 flex items-center gap-2">
              <Database size={18} />
              <h2 className="text-base font-semibold">ETL Status</h2>
            </div>
            <div className="space-y-2 text-sm">
              {etlJobs.slice(0, 4).map((job) => (
                <div key={job.id} className="flex items-center justify-between border-b border-line pb-2">
                  <span>{job.symbols.join(", ")}</span>
                  <span className="font-medium">{job.status}</span>
                </div>
              ))}
              {!etlJobs.length && <p className="text-slate-500">No ETL jobs yet.</p>}
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-4 px-6 pb-8 lg:grid-cols-[1fr_1fr]">
        <div className="rounded border border-line bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText size={18} />
              <h2 className="text-base font-semibold">AI Report</h2>
            </div>
            <button
              className="rounded border border-line px-3 py-2 text-sm font-medium disabled:opacity-60"
              onClick={generateReport}
              disabled={loading}
            >
              Generate
            </button>
          </div>
          {latestReport ? (
            <div className="space-y-3 text-sm">
              <p className="text-base font-medium">{latestReport.summary}</p>
              <div>
                <h3 className="mb-1 font-semibold">Trend Insights</h3>
                <ul className="list-disc space-y-1 pl-5">
                  {latestReport.trend_insights.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              {!!latestReport.risk_notes.length && (
                <div>
                  <h3 className="mb-1 font-semibold">Risk Notes</h3>
                  <ul className="list-disc space-y-1 pl-5">
                    {latestReport.risk_notes.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-500">Run ETL, then generate a report from stored metrics.</p>
          )}
        </div>

        <div className="rounded border border-line bg-white p-4">
          <h2 className="mb-3 text-base font-semibold">Operational State</h2>
          {error && <p className="rounded border border-negative/30 bg-red-50 p-3 text-sm text-negative">{error}</p>}
          {!error && (
            <p className="text-sm text-slate-600">
              {loading ? "Request in progress." : "Dashboard reads from stored API data and persisted report records."}
            </p>
          )}
        </div>
      </section>
    </main>
  );
}

