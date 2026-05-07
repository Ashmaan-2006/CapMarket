"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Database,
  FileText,
  Loader2,
  Play,
  RefreshCw,
  Search,
  TrendingDown,
  TrendingUp
} from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { AiReport, EtlJob, MetricPoint, PricePoint, Ticker, TopMover, api } from "@/lib/api";

function formatPercent(value: string | null | undefined) {
  if (!value) return "n/a";
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function formatCurrency(value: string | null | undefined) {
  if (!value) return "n/a";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2
  }).format(Number(value));
}

function formatNumber(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") return "n/a";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(Number(value));
}

function formatDate(value: string | null | undefined) {
  if (!value) return "n/a";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(
    new Date(value)
  );
}

function latest<T>(items: T[]) {
  return items.length ? items[items.length - 1] : null;
}

function statusClass(status: string) {
  if (status === "succeeded") return "text-positive";
  if (status === "failed") return "text-negative";
  if (status === "running") return "text-[#285c7a]";
  return "text-slate-600";
}

function topMoverIcon(direction: "gainers" | "losers") {
  return direction === "gainers" ? <TrendingUp size={16} /> : <TrendingDown size={16} />;
}

export default function DashboardPage() {
  const [tickers, setTickers] = useState<Ticker[]>([]);
  const [tickerQuery, setTickerQuery] = useState("AAPL");
  const [selectedSymbol, setSelectedSymbol] = useState("AAPL");
  const [prices, setPrices] = useState<PricePoint[]>([]);
  const [metrics, setMetrics] = useState<MetricPoint[]>([]);
  const [etlJobs, setEtlJobs] = useState<EtlJob[]>([]);
  const [reports, setReports] = useState<AiReport[]>([]);
  const [gainers, setGainers] = useState<TopMover[]>([]);
  const [losers, setLosers] = useState<TopMover[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [dataLoading, setDataLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<"etl" | "report" | null>(null);

  useEffect(() => {
    Promise.all([api.tickers(), api.etlStatus(), api.topMovers("gainers"), api.topMovers("losers")])
      .then(([tickerData, jobData, gainerData, loserData]) => {
        setTickers(tickerData);
        setEtlJobs(jobData);
        setGainers(gainerData);
        setLosers(loserData);
        if (tickerData[0]?.symbol) {
          setSelectedSymbol(tickerData[0].symbol);
          setTickerQuery(tickerData[0].symbol);
        }
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    let active = true;
    setDataLoading(true);
    setError(null);
    Promise.all([api.prices(selectedSymbol), api.metrics(selectedSymbol), api.reports(selectedSymbol)])
      .then(([priceData, metricData, reportData]) => {
        if (!active) return;
        setPrices(priceData);
        setMetrics(metricData);
        setReports(reportData);
      })
      .catch((err: Error) => {
        if (active) setError(err.message);
      })
      .finally(() => {
        if (active) setDataLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedSymbol]);

  const latestMetric = useMemo(() => latest(metrics), [metrics]);
  const latestPrice = useMemo(() => latest(prices), [prices]);
  const latestReport = reports[0];
  const knownSymbols = useMemo(
    () => [selectedSymbol, ...tickers.map((ticker) => ticker.symbol)].filter((symbol, index, all) => all.indexOf(symbol) === index),
    [selectedSymbol, tickers]
  );

  function submitTicker(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const symbol = tickerQuery.trim().toUpperCase();
    if (!symbol) return;
    setSelectedSymbol(symbol);
    setTickerQuery(symbol);
  }

  async function refreshDashboard(symbol = selectedSymbol) {
    const [priceData, metricData, reportData, jobData, gainerData, loserData] = await Promise.all([
      api.prices(symbol),
      api.metrics(symbol),
      api.reports(symbol),
      api.etlStatus(),
      api.topMovers("gainers"),
      api.topMovers("losers")
    ]);
    setPrices(priceData);
    setMetrics(metricData);
    setReports(reportData);
    setEtlJobs(jobData);
    setGainers(gainerData);
    setLosers(loserData);
  }

  async function runEtl() {
    setActionLoading("etl");
    setError(null);
    try {
      const job = await api.runEtl([selectedSymbol]);
      setEtlJobs((current) => [job, ...current]);
      await refreshDashboard(selectedSymbol);
    } catch (err) {
      setError(err instanceof Error ? err.message : "ETL failed");
    } finally {
      setActionLoading(null);
    }
  }

  async function generateReport() {
    setActionLoading("report");
    setError(null);
    try {
      const report = await api.generateReport(selectedSymbol);
      setReports((current) => [report, ...current.filter((item) => item.id !== report.id)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report generation failed");
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <main className="min-h-screen">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-normal">Capital Markets AI Reporting</h1>
            <p className="text-sm text-slate-600">Stored market analytics and grounded analyst reports</p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <form className="flex h-10 items-center rounded border border-line bg-white" onSubmit={submitTicker}>
              <Search className="ml-3 text-slate-500" size={16} />
              <input
                className="h-full w-32 bg-transparent px-2 text-sm uppercase outline-none"
                list="ticker-symbols"
                value={tickerQuery}
                onChange={(event) => setTickerQuery(event.target.value)}
                aria-label="Ticker symbol"
                suppressHydrationWarning
              />
              <datalist id="ticker-symbols">
                {knownSymbols.map((symbol) => (
                  <option key={symbol} value={symbol} />
                ))}
              </datalist>
              <button className="h-full border-l border-line px-3 text-sm font-medium" type="submit">
                Load
              </button>
            </form>
            <button
              className="inline-flex h-10 items-center justify-center gap-2 rounded bg-ink px-3 text-sm font-medium text-white disabled:opacity-60"
              onClick={runEtl}
              disabled={!!actionLoading || dataLoading}
              title="Run ETL"
            >
              {actionLoading === "etl" ? <Loader2 className="animate-spin" size={16} /> : <Play size={16} />}
              Run ETL
            </button>
          </div>
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl gap-4 px-6 py-5 lg:grid-cols-[2fr_1fr]">
        <div className="rounded border border-line bg-white p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <BarChart3 size={18} />
              <h2 className="text-base font-semibold">{selectedSymbol} Price History</h2>
            </div>
            <span className="text-sm text-slate-500">{prices.length} stored rows</span>
          </div>
          <div className="h-[360px]">
            {prices.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={prices}>
                  <CartesianGrid stroke="#e4e7e2" />
                  <XAxis dataKey="price_date" minTickGap={32} tick={{ fontSize: 12 }} />
                  <YAxis domain={["auto", "auto"]} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="close" stroke="#285c7a" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-slate-500">
                {dataLoading ? "Loading stored prices." : "No stored price data for this ticker."}
              </div>
            )}
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
                <dt className="text-slate-500">Close</dt>
                <dd className="font-semibold">{formatCurrency(latestPrice?.close)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Volume</dt>
                <dd className="font-semibold">{formatNumber(latestPrice?.volume)}</dd>
              </div>
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
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Database size={18} />
                <h2 className="text-base font-semibold">ETL Status</h2>
              </div>
              <RefreshCw size={16} className={dataLoading ? "animate-spin text-slate-500" : "text-slate-500"} />
            </div>
            <div className="space-y-2 text-sm">
              {etlJobs.slice(0, 4).map((job) => (
                <div key={job.id} className="grid grid-cols-[1fr_auto] gap-3 border-b border-line pb-2">
                  <span className="truncate">{job.symbols.join(", ")}</span>
                  <span className={`font-medium ${statusClass(job.status)}`}>{job.status}</span>
                </div>
              ))}
              {!etlJobs.length && <p className="text-slate-500">No ETL jobs yet.</p>}
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-4 px-6 pb-5 lg:grid-cols-[1fr_1fr]">
        <TopMoversPanel title="Top Gainers" direction="gainers" items={gainers} />
        <TopMoversPanel title="Top Losers" direction="losers" items={losers} />
      </section>

      <section className="mx-auto grid max-w-7xl gap-4 px-6 pb-8 lg:grid-cols-[1.5fr_1fr]">
        <div className="rounded border border-line bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText size={18} />
              <h2 className="text-base font-semibold">AI Report</h2>
            </div>
            <button
              className="inline-flex h-10 items-center gap-2 rounded border border-line px-3 text-sm font-medium disabled:opacity-60"
              onClick={generateReport}
              disabled={!!actionLoading || dataLoading}
            >
              {actionLoading === "report" ? <Loader2 className="animate-spin" size={16} /> : <FileText size={16} />}
              Generate
            </button>
          </div>
          {latestReport ? (
            <div className="space-y-4 text-sm">
              <div>
                <p className="text-base font-medium">{latestReport.summary}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {latestReport.report_type} report for {formatDate(latestReport.report_date)} via {latestReport.model}
                </p>
              </div>
              <ReportList title="Trend Insights" items={latestReport.trend_insights} />
              <ReportList title="Anomaly Explanations" items={latestReport.anomaly_explanations} />
              <ReportList title="Risk Notes" items={latestReport.risk_notes} />
            </div>
          ) : (
            <p className="text-sm text-slate-500">Run ETL, then generate a report from stored metrics.</p>
          )}
        </div>

        <div className="rounded border border-line bg-white p-4">
          <div className="mb-3 flex items-center gap-2">
            <AlertTriangle size={18} />
            <h2 className="text-base font-semibold">Operational State</h2>
          </div>
          {error && <p className="rounded border border-negative/30 bg-red-50 p-3 text-sm text-negative">{error}</p>}
          {!error && (
            <div className="space-y-3 text-sm text-slate-600">
              <p>{dataLoading ? "Refreshing dashboard data." : "Dashboard reads from persisted API data."}</p>
              <dl className="grid grid-cols-2 gap-3">
                <div>
                  <dt className="text-slate-500">Ticker</dt>
                  <dd className="font-semibold text-ink">{selectedSymbol}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Metric date</dt>
                  <dd className="font-semibold text-ink">{formatDate(latestMetric?.metric_date)}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Reports</dt>
                  <dd className="font-semibold text-ink">{reports.length}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Jobs</dt>
                  <dd className="font-semibold text-ink">{etlJobs.length}</dd>
                </div>
              </dl>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

function TopMoversPanel({
  title,
  direction,
  items
}: {
  title: string;
  direction: "gainers" | "losers";
  items: TopMover[];
}) {
  return (
    <div className="rounded border border-line bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        {topMoverIcon(direction)}
        <h2 className="text-base font-semibold">{title}</h2>
      </div>
      <div className="space-y-2 text-sm">
        {items.slice(0, 5).map((item) => (
          <div key={`${direction}-${item.symbol}`} className="grid grid-cols-[1fr_auto_auto] gap-3 border-b border-line pb-2">
            <span className="font-medium">{item.symbol}</span>
            <span className="text-slate-500">{formatDate(item.metric_date)}</span>
            <span className={direction === "gainers" ? "font-semibold text-positive" : "font-semibold text-negative"}>
              {formatPercent(item.daily_return)}
            </span>
          </div>
        ))}
        {!items.length && <p className="text-slate-500">No mover data available.</p>}
      </div>
    </div>
  );
}

function ReportList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <h3 className="mb-1 font-semibold">{title}</h3>
      <ul className="list-disc space-y-1 pl-5">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
