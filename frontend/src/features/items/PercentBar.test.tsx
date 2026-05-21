import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PercentBar } from "./PercentBar";

describe("PercentBar — fill mode", () => {
  it("renders the numeric value", () => {
    render(<PercentBar pct={75} />);
    expect(screen.getByText("75%")).toBeInTheDocument();
  });

  it("renders over-100% value when pct exceeds T1 (divine overroll)", () => {
    render(<PercentBar pct={110} />);
    expect(screen.getByText("110%")).toBeInTheDocument();
  });

  it("renders 0% without error", () => {
    render(<PercentBar pct={0} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("hides value text when showValue=false", () => {
    render(<PercentBar pct={50} showValue={false} />);
    expect(screen.queryByText("50%")).not.toBeInTheDocument();
  });

  it("renders a T1 cap tick at 100% on the scale", () => {
    const { container } = render(<PercentBar pct={80} />);
    // The T1 cap tick has a title attribute
    const capTick = container.querySelector('[title="100% on this scale = T1 max"]');
    expect(capTick).not.toBeNull();
  });

  it("renders tier boundary markers when provided", () => {
    const { container } = render(<PercentBar pct={80} tierMarkers={[60, 40]} />);
    expect(container.querySelector('[title="T2 max: 60%"]')).not.toBeNull();
    expect(container.querySelector('[title="T3 max: 40%"]')).not.toBeNull();
  });
});

describe("PercentBar — null pct (no roll data)", () => {
  it("renders the no-data dash and no value span", () => {
    const { container } = render(<PercentBar pct={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
    // No percentage text should appear
    expect(container.querySelector(".tabular-nums")).toBeNull();
  });
});

describe("PercentBar — candle mode", () => {
  it("switches to candle mode when both bandMin and bandMax are provided", () => {
    const { container } = render(
      <PercentBar pct={70} bandMin={55} bandMax={82} tierLabel="test" />,
    );
    // Tier range band tooltip
    const band = container.querySelector('[title="Tier range: 55%–82% of T1"]');
    expect(band).not.toBeNull();
    // Roll tick tooltip
    const tick = container.querySelector('[title="Roll: 70% of T1 max"]');
    expect(tick).not.toBeNull();
    // T1 cap tick
    const cap = container.querySelector('[title="T1 max (100%)"]');
    expect(cap).not.toBeNull();
  });

  it("shows the numeric value in candle mode", () => {
    render(<PercentBar pct={70} bandMin={55} bandMax={82} />);
    expect(screen.getByText("70%")).toBeInTheDocument();
  });

  it("shows over-100% roll in candle mode (divine overroll)", () => {
    render(<PercentBar pct={108} bandMin={80} bandMax={100} />);
    expect(screen.getByText("108%")).toBeInTheDocument();
    // roll tick tooltip should reflect the overrolled value
    const { container } = render(<PercentBar pct={108} bandMin={80} bandMax={100} />);
    expect(container.querySelector('[title="Roll: 108% of T1 max"]')).not.toBeNull();
  });

  it("still shows tier markers in candle mode", () => {
    const { container } = render(
      <PercentBar pct={70} bandMin={55} bandMax={82} tierMarkers={[50, 30]} />,
    );
    expect(container.querySelector('[title="T2 max: 50%"]')).not.toBeNull();
    expect(container.querySelector('[title="T3 max: 30%"]')).not.toBeNull();
  });

  it("does not enter candle mode when only one of bandMin/bandMax is provided", () => {
    const { container } = render(<PercentBar pct={70} bandMin={55} />);
    // No candle band — falls back to fill mode
    expect(container.querySelector('[title^="Tier range"]')).toBeNull();
    expect(screen.getByText("70%")).toBeInTheDocument();
  });
});

describe("PercentBar — size variants", () => {
  it("renders size md without error", () => {
    render(<PercentBar pct={60} size="md" />);
    expect(screen.getByText("60%")).toBeInTheDocument();
  });

  it("renders size sm without error", () => {
    render(<PercentBar pct={60} size="sm" />);
    expect(screen.getByText("60%")).toBeInTheDocument();
  });
});
