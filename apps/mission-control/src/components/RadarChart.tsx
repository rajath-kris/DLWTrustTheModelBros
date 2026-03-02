import type { ReadinessAxes } from "../types";

interface RadarChartProps {
  axes: ReadinessAxes;
  /** Optional target series (e.g. goal/deadline); drawn as a second polygon. */
  targetAxes?: Partial<ReadinessAxes> | null;
}

interface AxisConfig {
  key: keyof ReadinessAxes;
  label: string;
}

const AXES: AxisConfig[] = [
  { key: "concept_mastery", label: "Mastery" },
  { key: "deadline_pressure", label: "Deadline" },
  { key: "retention_risk", label: "Retention" },
  { key: "problem_transfer", label: "Transfer" },
  { key: "consistency", label: "Consistency" },
];

function polarToCartesian(cx: number, cy: number, radius: number, angleDeg: number) {
  const angle = (Math.PI / 180) * angleDeg;
  return {
    x: cx + radius * Math.cos(angle),
    y: cy + radius * Math.sin(angle),
  };
}

export function RadarChart({ axes, targetAxes }: RadarChartProps) {
  const size = 320;
  const center = size / 2;
  const maxRadius = 114;

  const levels = [0.25, 0.5, 0.75, 1];
  const angleStep = 360 / AXES.length;
  const startAngle = -90;

  const dataPoints = AXES.map((axis, index) => {
    const value = Math.max(0, Math.min(1, axes[axis.key]));
    return polarToCartesian(center, center, maxRadius * value, startAngle + index * angleStep);
  });

  const polygonPath = dataPoints.map((point) => `${point.x},${point.y}`).join(" ");

  const targetPoints =
    targetAxes &&
    AXES.map((axis, index) => {
      const raw = targetAxes[axis.key];
      const value = typeof raw === "number" ? Math.max(0, Math.min(1, raw)) : 0.8;
      return polarToCartesian(center, center, maxRadius * value, startAngle + index * angleStep);
    });
  const targetPath = targetPoints?.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="radar-svg" role="img" aria-label="Readiness radar chart">
      <defs>
        <radialGradient id="radarGlow" cx="50%" cy="50%" r="60%">
          <stop offset="0%" stopColor="rgba(31, 190, 247, 0.35)" />
          <stop offset="100%" stopColor="rgba(31, 190, 247, 0)" />
        </radialGradient>
      </defs>

      <circle cx={center} cy={center} r={maxRadius + 16} fill="url(#radarGlow)" />

      {levels.map((level) => {
        const points = AXES.map((_, index) => {
          const point = polarToCartesian(center, center, maxRadius * level, startAngle + index * angleStep);
          return `${point.x},${point.y}`;
        }).join(" ");
        return <polygon key={level} points={points} className="radar-grid" />;
      })}

      {AXES.map((axis, index) => {
        const outer = polarToCartesian(center, center, maxRadius, startAngle + index * angleStep);
        const label = polarToCartesian(center, center, maxRadius + 24, startAngle + index * angleStep);
        return (
          <g key={axis.key}>
            <line x1={center} y1={center} x2={outer.x} y2={outer.y} className="radar-axis" />
            <text x={label.x} y={label.y} className="radar-label" textAnchor="middle">
              {axis.label}
            </text>
          </g>
        );
      })}

      <polygon points={polygonPath} className="radar-shape" />
      {targetPath && <polygon points={targetPath} className="radar-shape radar-target" />}
      {dataPoints.map((point, index) => (
        <circle key={AXES[index].key} cx={point.x} cy={point.y} r={4.2} className="radar-dot" />
      ))}
    </svg>
  );
}
