// What the jobs list is filtered by, as a row of chips above the results:
// each one says a filter in words and takes it off with one click.

import { X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { activeFilters, withSortOnly } from "../jobFilters";
import type { Meta } from "../types";

interface Props {
  meta: Meta;
  params: URLSearchParams;
  setParams: (next: URLSearchParams) => void;
  /** The company's name when the list is narrowed to one company. */
  companyName?: string;
}

export default function ActiveFilters({ meta, params, setParams, companyName }: Props) {
  const active = activeFilters(meta, params, companyName);
  if (!active.length) return null;
  return (
    <div className="active-filters" aria-label="Filters in use">
      <AnimatePresence initial={false}>
        {active.map((a) => (
          <motion.button
            key={a.key}
            layout
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ duration: 0.15 }}
            type="button"
            className="active-filter"
            title={`Remove: ${a.label}`}
            onClick={() => setParams(a.remove())}
          >
            {a.label}
            <X size={13} aria-label="remove" />
          </motion.button>
        ))}
      </AnimatePresence>
      {active.length > 1 && (
        <button type="button" className="link" onClick={() => setParams(withSortOnly(params))}>
          Clear all
        </button>
      )}
    </div>
  );
}
