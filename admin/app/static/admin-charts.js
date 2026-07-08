/**
 * Chart.js helpers for the Users dashboard.
 * Expects JSON in #user-chart-data and canvas ids chart-adoption, chart-activity, etc.
 */
(function () {
  function init() {
  const dataEl = document.getElementById("user-chart-data");
  if (!dataEl || typeof Chart === "undefined") {
    if (!dataEl) return;
    console.error("[admin-charts] Chart.js not loaded — check Content-Security-Policy script-src");
    return;
  }

  let payload;
  try {
    payload = JSON.parse(dataEl.textContent || "{}");
  } catch (_err) {
    console.error("[admin-charts] invalid chart JSON");
    return;
  }

  const styles = getComputedStyle(document.documentElement);
  const ink = styles.getPropertyValue("--ink").trim() || "#e9d8bd";
  const inkMuted = styles.getPropertyValue("--ink-muted").trim() || "#9c8e73";
  const ember = styles.getPropertyValue("--ember").trim() || "#e08a3c";
  const panel = styles.getPropertyValue("--panel-elevated").trim() || "#222028";
  const rule = styles.getPropertyValue("--rule").trim() || "#2f2b36";
  const ok = styles.getPropertyValue("--ok").trim() || "#6cbd7a";

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: reducedMotion ? false : undefined,
    plugins: {
      legend: {
        labels: { color: ink, boxWidth: 12 },
      },
    },
    scales: {
      x: {
        ticks: { color: inkMuted, maxRotation: 45, autoSkip: true, maxTicksLimit: 12 },
        grid: { color: rule },
      },
      y: {
        beginAtZero: true,
        ticks: { color: inkMuted, precision: 0 },
        grid: { color: rule },
      },
    },
  };

  function labels(rows) {
    return (rows || []).map((r) => String(r.day || "").slice(5));
  }

  function values(rows) {
    return (rows || []).map((r) => Number(r.n) || 0);
  }

  function makeChart(id, config) {
    const canvas = document.getElementById(id);
    if (!canvas) return;
    return new Chart(canvas, config);
  }

  makeChart("chart-adoption", {
    type: "bar",
    data: {
      labels: labels(payload.signups_by_day),
      datasets: [
        {
          type: "line",
          label: "Cumulative users",
          data: values(payload.cumulative_users),
          borderColor: ember,
          backgroundColor: "transparent",
          yAxisID: "y1",
          tension: 0.2,
          pointRadius: 0,
        },
        {
          type: "bar",
          label: "Daily signups",
          data: values(payload.signups_by_day),
          backgroundColor: "rgba(224, 138, 60, 0.45)",
          borderColor: ember,
          borderWidth: 1,
        },
      ],
    },
    options: {
      ...baseOptions,
      scales: {
        ...baseOptions.scales,
        y: { ...baseOptions.scales.y, position: "left" },
        y1: {
          beginAtZero: true,
          position: "right",
          grid: { drawOnChartArea: false, color: rule },
          ticks: { color: inkMuted, precision: 0 },
        },
      },
    },
  });

  makeChart("chart-activity", {
    type: "line",
    data: {
      labels: labels(payload.refresh_users_by_day),
      datasets: [
        {
          label: "Users refreshed",
          data: values(payload.refresh_users_by_day),
          borderColor: ember,
          backgroundColor: "rgba(224, 138, 60, 0.15)",
          fill: true,
          tension: 0.2,
        },
        {
          label: "Users logged in",
          data: values(payload.login_users_by_day),
          borderColor: ok,
          backgroundColor: "rgba(108, 189, 122, 0.12)",
          fill: true,
          tension: 0.2,
        },
      ],
    },
    options: baseOptions,
  });

  makeChart("chart-snapshots", {
    type: "bar",
    data: {
      labels: labels(payload.refresh_events_by_day),
      datasets: [
        {
          label: "Refresh events",
          data: values(payload.refresh_events_by_day),
          backgroundColor: "rgba(224, 138, 60, 0.5)",
          borderColor: ember,
          borderWidth: 1,
        },
        {
          label: "Gear history rows",
          data: values(payload.gear_history_by_day),
          backgroundColor: "rgba(108, 189, 122, 0.45)",
          borderColor: ok,
          borderWidth: 1,
        },
      ],
    },
    options: baseOptions,
  });

  makeChart("chart-resources", {
    type: "line",
    data: {
      labels: labels(payload.price_estimates_by_day),
      datasets: [
        {
          label: "Price estimates",
          data: values(payload.price_estimates_by_day),
          borderColor: ember,
          backgroundColor: "rgba(224, 138, 60, 0.12)",
          fill: true,
          tension: 0.2,
        },
        {
          label: "Shares created",
          data: values(payload.shares_by_day),
          borderColor: ok,
          backgroundColor: "rgba(108, 189, 122, 0.1)",
          fill: true,
          tension: 0.2,
        },
      ],
    },
    options: baseOptions,
  });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
