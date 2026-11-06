// Marks the words of a search in text, so you can see why a job matched.
// Reads the same syntax as the search box: words, "exact phrases", OR, and
// word starts (analy*). A plain word also marks its common endings
// ("engineer" marks "engineers" and "engineering"), close to how the search
// itself matches; only a starred word marks any word starting with it.

import type { ReactNode } from "react";

// Endings a plain word may carry, and the end of a word.
const ENDINGS = "(?:s|es|ed|ing|ings|er|ers|al|ally)?";
const END = "(?![\\p{L}\\p{N}])";

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** A pattern for the search's words and phrases, or null when there's nothing to mark. */
export function searchPattern(query: string | null | undefined): RegExp | null {
  if (!query?.trim()) return null;
  const terms: string[] = [];
  for (const m of query.matchAll(/"([^"]+)"|(\S+)/g)) {
    const phrase = m[1]?.trim();
    if (phrase) {
      terms.push(`${phrase.split(/\s+/).map(escape).join("\\s+")}${END}`);
      continue;
    }
    const word = (m[2] ?? "").replace(/^[-+(]+|[)]+$/g, "");
    if (!word || ["OR", "AND", "NOT", "NEAR"].includes(word)) continue;
    const starred = word.endsWith("*");
    const bare = word.replace(/\*+$/, "").replace(/[^\p{L}\p{N}#+.-]/gu, "");
    if (bare.length < 2) continue;
    terms.push(starred ? `${escape(bare)}[\\p{L}\\p{N}]*` : `${escape(bare)}${ENDINGS}${END}`);
  }
  if (!terms.length) return null;
  // Longest first, so a phrase wins over one of its words.
  terms.sort((a, b) => b.length - a.length);
  return new RegExp(`(?<![\\p{L}\\p{N}])(?:${terms.join("|")})`, "giu");
}

/** *text* with every match of *pattern* wrapped in <mark>. */
export function Highlight({ text, pattern }: { text: string; pattern: RegExp | null }): ReactNode {
  if (!pattern || !text) return text;
  const out: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(pattern)) {
    const at = m.index ?? 0;
    if (!m[0]) continue;
    if (at > last) out.push(text.slice(last, at));
    out.push(<mark key={at}>{m[0]}</mark>);
    last = at + m[0].length;
  }
  if (!out.length) return text;
  if (last < text.length) out.push(text.slice(last));
  return <>{out}</>;
}
