function formatDirection(direction) {
  return direction === "BUY" ? "🟢 BUY" : "🔴 SELL";
}

function StatusBadge({ status }) {
  const cls = status === "OPEN" ? "badge badge-open" : "badge badge-closed";
  return <span className={cls}>{status}</span>;
}

export default function SignalList({ signals }) {
  if (!signals || signals.length === 0) {
    return <p>No signals yet.</p>;
  }

  return (
    <table className="signal-table">
      <thead>
        <tr>
          <th>Time</th>
          <th>Direction</th>
          <th>Entry</th>
          <th>SL</th>
          <th>TP</th>
          <th>Status</th>
          <th>Result (R)</th>
        </tr>
      </thead>
      <tbody>
        {signals.map((s) => (
          <tr key={s.id}>
            <td>{new Date(s.signal_time).toLocaleString()}</td>
            <td>{formatDirection(s.direction)}</td>
            <td>{s.entry_price}</td>
            <td>{s.stop_loss}</td>
            <td>{s.take_profit}</td>
            <td><StatusBadge status={s.status} /></td>
            <td>{s.r_multiple ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
