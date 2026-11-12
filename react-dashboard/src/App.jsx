import { useEffect, useState } from "react";
import { fetchSignals, fetchPerformance } from "./api/client";
import SignalList from "./components/SignalList";
import PerformanceStats from "./components/PerformanceStats";
import "./index.css";

const REFRESH_MS = 30_000;

export default function App() {
  const [signals, setSignals] = useState([]);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [signalData, statsData] = await Promise.all([
          fetchSignals(),
          fetchPerformance(),
        ]);
        if (!cancelled) {
          setSignals(signalData);
          setStats(statsData);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    }

    load();
    const interval = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="app">
      <header>
        <h1>EUR/USD Signal Dashboard</h1>
      </header>

      {error && (
        <p className="error-banner">
          Couldn't reach the API ({error}). Check VITE_API_BASE_URL and that
          the Laravel app is running.
        </p>
      )}

      <PerformanceStats stats={stats} />

      <section>
        <h2>Recent signals</h2>
        <SignalList signals={signals} />
      </section>
    </div>
  );
}
