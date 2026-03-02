import { useState, useCallback, useRef, useEffect } from "react";
import type { TopicScore } from "../data/topicRadar";

function polarToCartesian(cx: number, cy: number, radius: number, angleDeg: number) {
  const angle = (Math.PI / 180) * angleDeg;
  return {
    x: cx + radius * Math.cos(angle),
    y: cy + radius * Math.sin(angle),
  };
}

interface ReadinessRadarTopicsProps {
  topics: TopicScore[];
  showLive?: boolean;
}

export function ReadinessRadarTopics({ topics, showLive = true }: ReadinessRadarTopicsProps) {
  const size = 320;
  const center = size / 2;
  const maxRadius = 114;
  const levels = [0.25, 0.5, 0.75, 1];
  const angleStep = 360 / topics.length;
  const startAngle = -90;

  const svgRef = useRef<SVGSVGElement>(null);
  const [tooltip, setTooltip] = useState<{
    index: number;
    anchorX: number;
    anchorY: number;
  } | null>(null);
  const [tooltipClosing, setTooltipClosing] = useState(false);

  const currentPoints = topics.map((t, i) =>
    polarToCartesian(center, center, maxRadius * Math.max(0, Math.min(1, t.current)), startAngle + i * angleStep)
  );
  const targetPoints = topics.map((t, i) =>
    polarToCartesian(center, center, maxRadius * Math.max(0, Math.min(1, t.target)), startAngle + i * angleStep)
  );
  const currentPath = currentPoints.map((p) => `${p.x},${p.y}`).join(" ");
  const targetPath = targetPoints.map((p) => `${p.x},${p.y}`).join(" ");

  const svgPointToClient = useCallback(
    (point: { x: number; y: number }) => {
      const svg = svgRef.current;
      if (!svg) return { x: 0, y: 0 };
      const rect = svg.getBoundingClientRect();
      return {
        x: rect.left + (point.x / size) * rect.width,
        y: rect.top + (point.y / size) * rect.height,
      };
    },
    [size]
  );

  const handleDotEnter = useCallback(
    (index: number, point: { x: number; y: number }) => {
      setTooltipClosing(false);
      const { x, y } = svgPointToClient(point);
      setTooltip({ index, anchorX: x, anchorY: y });
    },
    [svgPointToClient]
  );

  const handleDotLeave = useCallback(() => {
    setTooltipClosing(true);
  }, []);

  useEffect(() => {
    if (!tooltipClosing || tooltip == null) return;
    const id = window.setTimeout(() => {
      setTooltip(null);
      setTooltipClosing(false);
    }, 200);
    return () => window.clearTimeout(id);
  }, [tooltipClosing, tooltip]);

  return (
    <div
      className="radar-topic-wrap"
      onMouseLeave={handleDotLeave}
    >
      {showLive && <span className="radar-live-pill">Live</span>}
      <svg
        ref={svgRef}
        viewBox={`0 0 ${size} ${size}`}
        className="radar-svg radar-topic-svg"
        role="img"
        aria-label="Readiness radar by topic"
      >
        <defs>
          <radialGradient id="radarGlowTopics" cx="50%" cy="50%" r="60%">
            <stop offset="0%" stopColor="rgba(94, 123, 255, 0.25)" />
            <stop offset="100%" stopColor="rgba(94, 123, 255, 0)" />
          </radialGradient>
        </defs>
        <circle cx={center} cy={center} r={maxRadius + 16} fill="url(#radarGlowTopics)" />
        {levels.map((level) => {
          const pts = topics
            .map((_, i) => polarToCartesian(center, center, maxRadius * level, startAngle + i * angleStep))
            .map((p) => `${p.x},${p.y}`)
            .join(" ");
          return <polygon key={level} points={pts} className="radar-grid" />;
        })}
        {topics.map((t, i) => {
          const outer = polarToCartesian(center, center, maxRadius, startAngle + i * angleStep);
          const label = polarToCartesian(center, center, maxRadius + 28, startAngle + i * angleStep);
          return (
            <g key={t.name}>
              <line x1={center} y1={center} x2={outer.x} y2={outer.y} className="radar-axis" />
              <text x={label.x} y={label.y} className="radar-label" textAnchor="middle">
                {t.label}
              </text>
            </g>
          );
        })}
        <polygon points={targetPath} className="radar-shape radar-target" />
        <polygon points={currentPath} className="radar-shape radar-current-topic" />
        {currentPoints.map((p, i) => (
          <g key={`current-${i}`}>
            <circle
              cx={p.x}
              cy={p.y}
              r={16}
              className="radar-dot-hit"
              aria-hidden
              onMouseEnter={() => handleDotEnter(i, p)}
              onMouseLeave={handleDotLeave}
            />
            <circle
              cx={p.x}
              cy={p.y}
              r={4}
              className="radar-dot radar-dot-current"
            />
          </g>
        ))}
        {targetPoints.map((p, i) => (
          <g key={`target-${i}`}>
            <circle
              cx={p.x}
              cy={p.y}
              r={16}
              className="radar-dot-hit"
              aria-hidden
              onMouseEnter={() => handleDotEnter(i, p)}
              onMouseLeave={handleDotLeave}
            />
            <circle
              cx={p.x}
              cy={p.y}
              r={4}
              className="radar-dot radar-dot-target"
            />
          </g>
        ))}
      </svg>
      {tooltip != null && (() => {
        const t = topics[tooltip.index];
        const currentVal = Math.round(Math.max(0, Math.min(1, t.current)) * 100);
        const targetVal = Math.round(Math.max(0, Math.min(1, t.target)) * 100);
        return (
          <div
            className={`radar-tooltip ${tooltipClosing ? "radar-tooltip-closing" : ""}`}
            style={{
              left: tooltip.anchorX + 12,
              top: tooltip.anchorY - 10,
            }}
            role="tooltip"
          >
            <div className="radar-tooltip-title">{t.label}</div>
            <div className="radar-tooltip-row">
              <span className="radar-tooltip-swatch radar-tooltip-swatch-current" aria-hidden />
              <span>Current Mastery: {currentVal}</span>
            </div>
            <div className="radar-tooltip-row">
              <span className="radar-tooltip-swatch radar-tooltip-swatch-target" aria-hidden />
              <span>Target (Deadline): {targetVal}</span>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
