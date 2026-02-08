export function HeatmapLegend() {
  const steps = [
    { value: -5, label: '-5%', color: 'rgb(220, 38, 38)' },
    { value: -2.5, label: '-2.5%', color: 'rgb(160, 69, 69)' },
    { value: 0, label: '0%', color: 'rgb(100, 100, 100)' },
    { value: 2.5, label: '+2.5%', color: 'rgb(69, 160, 69)' },
    { value: 5, label: '+5%', color: 'rgb(34, 197, 94)' },
  ];

  return (
    <div className="flex flex-col gap-2 p-4 bg-card border border-border rounded-lg">
      <div className="text-sm font-medium text-muted-foreground">Daily % Change</div>
      <div className="flex items-center gap-2">
        <div className="flex-1 h-6 rounded-md overflow-hidden flex">
          {steps.map((step, i) => (
            <div
              key={i}
              className="flex-1"
              style={{ backgroundColor: step.color }}
            />
          ))}
        </div>
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Loss</span>
        <span>Gain</span>
      </div>
      <div className="flex justify-between text-xs text-muted-foreground mt-1">
        {steps.map((step, i) => (
          <span key={i}>{step.label}</span>
        ))}
      </div>
    </div>
  );
}
