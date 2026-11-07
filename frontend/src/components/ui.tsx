/** Small shared UI atoms. */

export function StatusChip({ status }: { status: string }) {
  const label =
    status === "processed"
      ? "Processed"
      : status === "feasibility"
        ? "Feasibility"
        : status === "provisional"
          ? "Planned"
          : status;
  return (
    <span className={`status-chip status-${status}`} data-status={status}>
      {label}
    </span>
  );
}

export function MonoFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="mono-fact">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p className="error-note" role="status">
      {message}
    </p>
  );
}
