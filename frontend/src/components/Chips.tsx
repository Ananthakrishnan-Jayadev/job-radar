// A row of on/off buttons for picking several values of one filter.

import { motion } from "motion/react";

interface Props {
  legend: string;
  options: { value: string; label: string }[];
  selected: string[];
  onToggle: (value: string) => void;
}

export default function Chips({ legend, options, selected, onToggle }: Props) {
  return (
    <fieldset className="chips">
      <legend>{legend}</legend>
      <div>
        {options.map(({ value, label }) => {
          const on = selected.includes(value);
          return (
            <motion.button
              key={value}
              whileTap={{ scale: 0.93 }}
              transition={{ type: "spring", stiffness: 600, damping: 30 }}
              type="button"
              className={`chip${on ? " on" : ""}`}
              aria-pressed={on}
              onClick={() => onToggle(value)}
            >
              {label}
            </motion.button>
          );
        })}
      </div>
    </fieldset>
  );
}
