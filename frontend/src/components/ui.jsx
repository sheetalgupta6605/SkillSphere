import { useEffect } from "react";

export function SearchInput({ value, onChange, placeholder = "Search", label = "Search" }) {
  return <label className="shared-search"><span className="sr-only">{label}</span><span aria-hidden="true">⌕</span><input type="search" aria-label={label} placeholder={placeholder} value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

function formatStatusContent(content) {
  if (content == null) return null;
  if (typeof content === "string" || typeof content === "number" || typeof content === "boolean") {
    return content;
  }
  if (Array.isArray(content)) {
    const list = content
      .map(formatStatusContent)
      .filter((item) => item !== null && item !== "");
    if (!list.length) return null;
    return list.map((item, index) => (
      <span key={index}>
        {index > 0 && " • "}
        {item}
      </span>
    ));
  }
  if (typeof content === "object") {
    if (content.$$typeof) {
      return content; // React element
    }
    const text = content.msg || content.message || content.detail || content.error;
    if (text) return formatStatusContent(text);
    try {
      return JSON.stringify(content);
    } catch {
      return "Notice";
    }
  }
  return String(content);
}

export function StatusMessage({ tone = "error", children }) {
  if (!children) return null;
  const formatted = formatStatusContent(children);
  if (!formatted) return null;
  return <div className={tone === "success" ? "success-box" : "error-box"} role={tone === "error" ? "alert" : "status"}>{formatted}</div>;
}

export function LoadingIndicator({ label = "Loading…" }) {
  return <div className="shared-loading" role="status" aria-live="polite"><span className="loading-spinner" aria-hidden="true" />{label}</div>;
}

export function DataTable({ columns, rows, rowKey = "id", emptyMessage = "No records to show." }) {
  if (!rows.length) return <div className="table-empty">{emptyMessage}</div>;
  return <div className="table-scroll"><table className="shared-table"><thead><tr>{columns.map((column) => <th key={column.key || column.header} scope="col">{column.header}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={row[rowKey] ?? index}>{columns.map((column) => <td key={column.key || column.header}>{column.render ? column.render(row) : row[column.key]}</td>)}</tr>)}</tbody></table></div>;
}

export function Pagination({ page, pageCount, onChange }) {
  if (!pageCount || pageCount < 2) return null;
  const first = Math.max(1, Math.min(page - 2, pageCount - 4));
  const visiblePages = Array.from({ length: Math.min(5, pageCount) }, (_, index) => first + index);
  return <nav className="pagination" aria-label="Pages"><button disabled={page <= 1} onClick={() => onChange(page - 1)}>← Previous</button><div className="page-numbers">{visiblePages.map((number) => <button key={number} aria-current={number === page ? "page" : undefined} className={number === page ? "active" : ""} onClick={() => onChange(number)}>{number}</button>)}</div><span>Page {page} of {pageCount}</span><button disabled={page >= pageCount} onClick={() => onChange(page + 1)}>Next →</button></nav>;
}

export function ConfirmDialog({ open, title, message, confirmLabel = "Confirm", busy = false, onCancel, onConfirm }) {
  useEffect(() => {
    if (!open) return undefined;
    function handleKeyDown(event) { if (event.key === "Escape" && !busy) onCancel(); }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, busy, onCancel]);
  if (!open) return null;
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) onCancel(); }}><section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-dialog-title"><h2 id="confirm-dialog-title">{title}</h2><p>{message}</p><div className="dialog-actions"><button className="secondary-button" disabled={busy} onClick={onCancel}>Cancel</button><button className="primary-button" disabled={busy} onClick={onConfirm}>{busy ? "Please wait…" : confirmLabel}</button></div></section></div>;
}
