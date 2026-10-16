import { Checkbox } from "@/components/ui/checkbox";

interface CheckboxGroupProps {
  options: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
  idPrefix: string;
}

/** 字符串多选组，用于类别、部门、编辑者选择。 */
export function CheckboxGroup({ options, selected, onChange, idPrefix }: CheckboxGroupProps) {
  const toggle = (value: string, checked: boolean) => {
    if (checked) {
      onChange([...selected, value]);
    } else {
      onChange(selected.filter((item) => item !== value));
    }
  };

  if (options.length === 0) {
    return <p className="text-sm text-[#999]">暂无选项</p>;
  }

  return (
    <div className="flex flex-wrap gap-x-5 gap-y-2 rounded-md border border-[#e0e0e0] p-3">
      {options.map((option, index) => {
        const id = `${idPrefix}-${index}`;
        return (
          <label key={option} htmlFor={id} className="flex items-center gap-2 cursor-pointer text-sm">
            <Checkbox
              id={id}
              checked={selected.includes(option)}
              onCheckedChange={(checked) => toggle(option, checked === true)}
            />
            <span>{option}</span>
          </label>
        );
      })}
    </div>
  );
}
