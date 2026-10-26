interface Props {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
}

export default function Pagination({ page, pageSize, total, onPage }: Props) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages === 1) return null;
  const first = (page - 1) * pageSize + 1;
  const last = Math.min(total, page * pageSize);
  return (
    <nav className="pagination" aria-label="Pages">
      <button type="button" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Previous
      </button>
      <span>
        {first.toLocaleString("en-CA")}–{last.toLocaleString("en-CA")} of {total.toLocaleString("en-CA")}
      </span>
      <button type="button" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Next
      </button>
    </nav>
  );
}
