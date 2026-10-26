// A row of on/off buttons for picking several values of one filter.

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
            <button
              key={value}
              type="button"
              className={`chip${on ? " on" : ""}`}
              aria-pressed={on}
              onClick={() => onToggle(value)}
            >
              {label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
