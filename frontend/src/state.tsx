// App-wide state: reference data, the previous visit (for "new" markers),
// and the running scan, polled while it runs.

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "./api";
import type { Meta, ScanState, TaskState } from "./types";

interface AppState {
  meta: Meta | null;
  /** Start of the previous visit; jobs first seen after it are "new". */
  previousVisit: string | null;
  scan: ScanState | null;
  /** Bumps when a scan finishes, so pages reload their data. */
  dataVersion: number;
  startScan: (companyId?: number) => Promise<void>;
  scanError: string | null;
  /** The running background chore (filling sizes, finding boards), polled while it runs. */
  task: TaskState | null;
  watchTask: (state: TaskState) => void;
  /** What the last scan found, until dismissed: jobs on your list and every new posting. */
  scanDone: ScanDone | null;
  dismissScanDone: () => void;
  /** Reload every page's data and the counts (after a change made outside a page's own list). */
  refresh: () => void;
}

export interface ScanDone {
  /** New jobs that pass the default Jobs filters (Canada, your roles), one per job posted for several places. */
  found: number;
  /** Every new posting the scan stored. */
  postings: number;
  closed: number;
  failed: number;
  since: string;
}

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [previousVisit, setPreviousVisit] = useState<string | null>(null);
  const [scan, setScan] = useState<ScanState | null>(null);
  const [dataVersion, setDataVersion] = useState(0);
  const [scanError, setScanError] = useState<string | null>(null);
  const wasRunning = useRef(false);
  const [task, setTask] = useState<TaskState | null>(null);
  const [scanDone, setScanDone] = useState<ScanDone | null>(null);
  const taskWasRunning = useRef(false);

  useEffect(() => {
    if (!task?.running) {
      if (taskWasRunning.current) {
        taskWasRunning.current = false;
        setDataVersion((v) => v + 1);
      }
      return;
    }
    taskWasRunning.current = true;
    const timer = window.setTimeout(() => {
      api.currentTask().then(setTask).catch(() => undefined);
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [task]);

  useEffect(() => {
    api.visit().then((v) => setPreviousVisit(v.previous)).catch(() => undefined);
    api.currentScan().then(setScan).catch(() => undefined);
    api.currentTask().then(setTask).catch(() => undefined);
  }, []);

  useEffect(() => {
    api.meta().then(setMeta).catch(() => undefined);
  }, [dataVersion]);

  // Poll every 2 seconds while a scan runs; reload data when it ends.
  useEffect(() => {
    if (!scan?.running) {
      if (wasRunning.current) {
        wasRunning.current = false;
        setDataVersion((v) => v + 1);
        // Say what it found: how many new jobs the Jobs page would show.
        const since = scan?.started_at;
        if (since && !scan?.error) {
          api
            .jobs(new URLSearchParams({ new_since: since, page_size: "1" }))
            .then((page) =>
              setScanDone({
                found: page.total,
                postings: scan.jobs_new,
                closed: scan.jobs_closed,
                failed: scan.boards_failed,
                since,
              }),
            )
            .catch(() => undefined);
        }
      }
      return;
    }
    wasRunning.current = true;
    const timer = window.setTimeout(() => {
      api.currentScan().then(setScan).catch(() => undefined);
    }, 2000);
    return () => window.clearTimeout(timer);
  }, [scan]);

  const startScan = useCallback(async (companyId?: number) => {
    setScanError(null);
    setScanDone(null);
    try {
      setScan(await api.startScan(companyId));
    } catch (error) {
      setScanError(error instanceof Error ? error.message : String(error));
    }
  }, []);

  return (
    <AppContext.Provider
      value={{
        meta,
        previousVisit,
        scan,
        dataVersion,
        startScan,
        scanError,
        task,
        watchTask: setTask,
        scanDone,
        dismissScanDone: () => setScanDone(null),
        refresh: () => setDataVersion((v) => v + 1),
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp(): AppState {
  const state = useContext(AppContext);
  if (!state) throw new Error("useApp must be used inside AppProvider");
  return state;
}

/** Load data with *load* whenever *key* changes; `reload()` fetches again. */
export function useLoad<T>(load: () => Promise<T>, key: string) {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const loadRef = useRef(load);
  loadRef.current = load;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    loadRef
      .current()
      .then((value) => {
        if (!cancelled) {
          setData(value);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [key, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, setData, error, loading, reload };
}
