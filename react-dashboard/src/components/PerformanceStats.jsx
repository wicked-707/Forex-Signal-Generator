export default function PerformanceStats({ stats }) {
  if (!stats || stats.total_trades === 0) {
    return (
      <div className="stats-card stats-empty">
        <p>No closed live signals yet — this fills in once trades start closing out.</p>
      </div>
    );
  }

  const items = [
    { label: "Closed trades", value: stats.total_trades },
    { label: "Win rate", value: `${stats.win_rate_pct}%` },
    { label: "Avg R / trade", value: stats.avg_r },
    { label: "Total R", value: stats.total_r },
  ];

  return (
    <div className="stats-card">
      <h2>Live track record</h2>
      <p className="stats-note">
        Real, live-verified results — not a backtest.
      </p>
      <div className="stats-grid">
        {items.map((item) => (
          <div key={item.label} className="stats-item">
            <div className="stats-value">{item.value}</div>
            <div className="stats-label">{item.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
