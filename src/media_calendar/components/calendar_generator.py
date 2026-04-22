"""Static HTML calendar generator."""

from __future__ import annotations

from calendar import month_name
from datetime import date
from html import escape
from pathlib import Path
from typing import Iterable, Sequence

from media_calendar.components.deadline_store import (
    filter_upcoming_deadlines,
    load_deadlines,
    resolve_deadline_files,
)
from media_calendar.models import Deadline

DEFAULT_OUTPUT_PATH = Path("build/calendar.html")
DEFAULT_INDEX_PATH = Path("build/index.html")

CATEGORY_LABELS = {
    "festival_submission": "Festival Submission",
    "funding_round": "Funding Round",
    "lab_application": "Lab Application",
    "fellowship": "Fellowship",
    "industry_forum": "Industry Forum",
    "other": "Other",
}


def generate_calendar(
    deadline_files: Iterable[str | Path] | None = None,
    *,
    root_dir: str | Path | None = None,
    current_date: date | None = None,
) -> Path:
    """Read deadline YAML files and write a static HTML calendar page."""

    root = Path(root_dir) if root_dir is not None else Path.cwd()
    data_files = resolve_deadline_files(deadline_files, root=root)
    deadlines = filter_upcoming_deadlines(
        load_deadlines(data_files),
        current_date=current_date or date.today(),
    )
    html = _render_calendar_html(deadlines)

    output_path = root / DEFAULT_OUTPUT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    (root / DEFAULT_INDEX_PATH).write_text(html, encoding="utf-8")
    return output_path


def _render_calendar_html(deadlines: Sequence[Deadline]) -> str:
    category_options = "\n".join(
        f'<option value="{escape(category)}">{escape(label)}</option>'
        for category, label in CATEGORY_LABELS.items()
    )
    month_options = "\n".join(
        f'<option value="{month}">{escape(month_name[month])}</option>'
        for month in range(1, 13)
    )
    deadline_cards = "\n".join(
        _render_deadline_card(deadline) for deadline in deadlines
    )
    total_count = len(deadlines)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Goose Industry Calendar</title>
  <style>
    :root {{
      --bg: #f6f2e8;
      --surface: #fffdf8;
      --ink: #1b1f23;
      --muted: #5f665f;
      --line: #d8d0c3;
      --accent: #0d6b50;
      --accent-soft: #dcefe7;
      --warning: #8b2e1e;
      --shadow: 0 18px 40px rgba(27, 31, 35, 0.08);
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(13, 107, 80, 0.11), transparent 28%),
        linear-gradient(180deg, #fbf7ef 0%, var(--bg) 100%);
    }}

    main {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 40px 20px 64px;
    }}

    .hero {{
      background: rgba(255, 253, 248, 0.88);
      border: 1px solid rgba(216, 208, 195, 0.95);
      border-radius: 28px;
      padding: 32px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(6px);
    }}

    .eyebrow {{
      margin: 0 0 10px;
      color: var(--accent);
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-size: 0.8rem;
      font-weight: 700;
    }}

    h1 {{
      margin: 0;
      font-size: clamp(2.3rem, 5vw, 4rem);
      line-height: 0.95;
      color: #ff1493;
    }}

    .hero p {{
      max-width: 60ch;
      font-size: 1.05rem;
      color: var(--muted);
    }}

    .filters {{
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      margin: 28px 0 16px;
    }}

    label {{
      display: block;
      margin-bottom: 8px;
      font-size: 0.85rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--muted);
    }}

    select {{
      width: 100%;
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: var(--surface);
      color: var(--ink);
      font: inherit;
    }}

    .summary {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
      margin-bottom: 24px;
      color: var(--muted);
    }}

    .count-chip {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 10px 14px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-weight: 700;
    }}

    .grid {{
      display: grid;
      gap: 18px;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    }}

    .card {{
      background: rgba(255, 253, 248, 0.95);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 22px;
      box-shadow: var(--shadow);
    }}

    .card[hidden] {{
      display: none;
    }}

    .meta {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 16px;
    }}

    .pill {{
      border-radius: 999px;
      padding: 6px 10px;
      background: #efe7d6;
      font-size: 0.82rem;
      color: #5f4f2f;
    }}

    .deadline-date {{
      margin: 0 0 8px;
      color: var(--warning);
      font-weight: 700;
      font-size: 0.95rem;
      letter-spacing: 0.03em;
      text-transform: uppercase;
    }}

    .card h2 {{
      margin: 0 0 10px;
      font-size: 1.5rem;
      line-height: 1.1;
    }}

    .organization {{
      margin: 0 0 14px;
      color: var(--muted);
      font-size: 1rem;
    }}

    .description {{
      margin: 0 0 16px;
      color: var(--ink);
      line-height: 1.6;
    }}

    .details {{
      display: grid;
      gap: 8px;
      margin: 0 0 18px;
      color: var(--muted);
      font-size: 0.95rem;
    }}

    .details strong {{
      color: var(--ink);
    }}

    .card a {{
      color: var(--accent);
      text-decoration: none;
      font-weight: 700;
    }}

    .empty-state {{
      padding: 26px;
      border-radius: 22px;
      border: 1px dashed var(--line);
      background: rgba(255, 253, 248, 0.72);
      color: var(--muted);
      text-align: center;
    }}

    .goose-stage {{
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 30;
      overflow: hidden;
    }}

    .goose-guide {{
      position: absolute;
      top: 0;
      left: 0;
      width: 92px;
      height: 92px;
      transform: translate3d(20px, calc(100vh - 128px), 0);
      transition: transform 2.8s cubic-bezier(0.22, 0.9, 0.24, 1);
      will-change: transform;
    }}

    .goose-guide.is-waddling .goose {{
      animation: goose-waddle 0.42s ease-in-out infinite alternate;
    }}

    .goose-guide.is-seated .goose {{
      animation: goose-settle 0.9s ease-out forwards;
    }}

    .goose-shadow {{
      position: absolute;
      left: 18px;
      bottom: 10px;
      width: 50px;
      height: 12px;
      border-radius: 999px;
      background: rgba(27, 31, 35, 0.12);
      filter: blur(1.5px);
    }}

    .goose {{
      position: absolute;
      inset: 0;
      transform-origin: 50% 75%;
    }}

    .goose-body {{
      position: absolute;
      left: 20px;
      top: 28px;
      width: 46px;
      height: 34px;
      background: #fffdf8;
      border: 2px solid #2f3d36;
      border-radius: 58% 54% 48% 52%;
    }}

    .goose-wing {{
      position: absolute;
      left: 37px;
      top: 36px;
      width: 22px;
      height: 16px;
      background: #f3efe5;
      border: 2px solid #2f3d36;
      border-radius: 60% 70% 50% 70%;
      transform: rotate(-14deg);
    }}

    .goose-neck {{
      position: absolute;
      left: 49px;
      top: 10px;
      width: 12px;
      height: 28px;
      background: #fffdf8;
      border: 2px solid #2f3d36;
      border-bottom: 0;
      border-radius: 14px 14px 8px 8px;
      transform: rotate(10deg);
      transform-origin: bottom center;
    }}

    .goose-head {{
      position: absolute;
      left: 52px;
      top: 4px;
      width: 20px;
      height: 18px;
      background: #fffdf8;
      border: 2px solid #2f3d36;
      border-radius: 55% 50% 48% 52%;
    }}

    .goose-eye {{
      position: absolute;
      left: 64px;
      top: 11px;
      width: 3px;
      height: 3px;
      border-radius: 50%;
      background: #2f3d36;
    }}

    .goose-beak {{
      position: absolute;
      left: 68px;
      top: 11px;
      width: 12px;
      height: 8px;
      background: #f2a343;
      border: 2px solid #2f3d36;
      border-left: 0;
      clip-path: polygon(0 0, 100% 50%, 0 100%);
    }}

    .goose-leg {{
      position: absolute;
      top: 58px;
      width: 3px;
      height: 18px;
      background: #d8802b;
      border-radius: 3px;
      transform-origin: top center;
    }}

    .goose-leg.left {{
      left: 35px;
    }}

    .goose-leg.right {{
      left: 48px;
    }}

    .goose-guide.is-waddling .goose-leg.left {{
      animation: goose-step-left 0.42s ease-in-out infinite alternate;
    }}

    .goose-guide.is-waddling .goose-leg.right {{
      animation: goose-step-right 0.42s ease-in-out infinite alternate;
    }}

    .goose-feet {{
      position: absolute;
      left: -3px;
      bottom: -2px;
      width: 10px;
      height: 4px;
      border-radius: 10px;
      background: #d8802b;
    }}

    @keyframes goose-waddle {{
      from {{
        transform: translateY(0) rotate(-3deg);
      }}
      to {{
        transform: translateY(-3px) rotate(3deg);
      }}
    }}

    @keyframes goose-step-left {{
      from {{
        transform: rotate(14deg);
      }}
      to {{
        transform: rotate(-10deg);
      }}
    }}

    @keyframes goose-step-right {{
      from {{
        transform: rotate(-10deg);
      }}
      to {{
        transform: rotate(14deg);
      }}
    }}

    @keyframes goose-settle {{
      0% {{
        transform: rotate(0deg) translateY(0);
      }}
      55% {{
        transform: rotate(-4deg) translateY(-2px);
      }}
      100% {{
        transform: rotate(-7deg) translateY(0);
      }}
    }}

    @media (prefers-reduced-motion: reduce) {{
      .goose-guide,
      .goose-guide.is-waddling .goose,
      .goose-guide.is-waddling .goose-leg.left,
      .goose-guide.is-waddling .goose-leg.right,
      .goose-guide.is-seated .goose {{
        animation: none;
        transition-duration: 0.01ms;
      }}
    }}

    @media (max-width: 640px) {{
      main {{
        padding: 20px 14px 40px;
      }}

      .hero {{
        padding: 22px;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>Goose Industry Calendar</h1>
      <p>
        All key film and entertainment events and deadlines in one place...so Goose don't miss out on no tasty corn
      </p>

      <div class="filters">
        <div>
          <label for="category-filter">Category</label>
          <select id="category-filter">
            <option value="all">All Categories</option>
            {category_options}
          </select>
        </div>
        <div>
          <label for="month-filter">Month</label>
          <select id="month-filter">
            <option value="all">All Months</option>
            {month_options}
          </select>
        </div>
      </div>

      <div class="summary">
        <p id="results-copy">Showing <strong>{total_count}</strong> deadlines.</p>
        <div class="count-chip"><span id="visible-count">{total_count}</span> visible</div>
      </div>
    </section>

    <section style="margin-top: 24px;">
      <div id="deadline-grid" class="grid">
        {deadline_cards or '<div class="empty-state">No deadlines were found in the provided YAML files.</div>'}
      </div>
    </section>
  </main>

  <div class="goose-stage" aria-hidden="true">
    <div id="goose-guide" class="goose-guide">
      <div class="goose-shadow"></div>
      <div class="goose">
        <div class="goose-body"></div>
        <div class="goose-wing"></div>
        <div class="goose-neck"></div>
        <div class="goose-head"></div>
        <div class="goose-eye"></div>
        <div class="goose-beak"></div>
        <div class="goose-leg left"><div class="goose-feet"></div></div>
        <div class="goose-leg right"><div class="goose-feet"></div></div>
      </div>
    </div>
  </div>

  <script>
    const categoryFilter = document.getElementById('category-filter');
    const monthFilter = document.getElementById('month-filter');
    const cards = Array.from(document.querySelectorAll('.card'));
    const visibleCount = document.getElementById('visible-count');
    const resultsCopy = document.getElementById('results-copy');
    const gooseGuide = document.getElementById('goose-guide');
    let gooseArrivalTimeout = null;

    function applyFilters() {{
      const categoryValue = categoryFilter.value;
      const monthValue = monthFilter.value;
      let visible = 0;

      cards.forEach((card) => {{
        const matchesCategory =
          categoryValue === 'all' || card.dataset.category === categoryValue;
        const matchesMonth =
          monthValue === 'all' || card.dataset.month === monthValue;
        const shouldShow = matchesCategory && matchesMonth;
        card.hidden = !shouldShow;
        if (shouldShow) {{
          visible += 1;
        }}
      }});

      visibleCount.textContent = String(visible);
      resultsCopy.innerHTML = `Showing <strong>${{visible}}</strong> deadlines.`;
      settleGooseOnVisibleCard();
    }}

    function getVisibleCards() {{
      return cards.filter((card) => !card.hidden);
    }}

    function settleGooseOnVisibleCard() {{
      if (!gooseGuide) {{
        return;
      }}

      const visibleCards = getVisibleCards();
      const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const targetCard = visibleCards[0];

      if (!targetCard) {{
        gooseGuide.classList.remove('is-seated');
        gooseGuide.classList.add('is-waddling');
        gooseGuide.style.transform = `translate3d(20px, ${{Math.max(20, window.innerHeight - 128)}}px, 0)`;
        return;
      }}

      const rect = targetCard.getBoundingClientRect();
      const targetX = Math.min(
        window.innerWidth - 104,
        Math.max(16, rect.left + rect.width - 88)
      );
      const targetY = Math.min(
        window.innerHeight - 104,
        Math.max(12, rect.top - 18)
      );

      if (gooseArrivalTimeout) {{
        window.clearTimeout(gooseArrivalTimeout);
      }}

      gooseGuide.classList.remove('is-seated');
      gooseGuide.classList.add('is-waddling');
      gooseGuide.style.transform = `translate3d(${{targetX}}px, ${{targetY}}px, 0)`;

      if (prefersReducedMotion) {{
        gooseGuide.classList.remove('is-waddling');
        gooseGuide.classList.add('is-seated');
        return;
      }}

      gooseArrivalTimeout = window.setTimeout(() => {{
        gooseGuide.classList.remove('is-waddling');
        gooseGuide.classList.add('is-seated');
      }}, 2400);
    }}

    categoryFilter.addEventListener('change', applyFilters);
    monthFilter.addEventListener('change', applyFilters);
    window.addEventListener('resize', settleGooseOnVisibleCard);
    applyFilters();
  </script>
</body>
</html>
"""


def _render_deadline_card(deadline: Deadline) -> str:
    deadline_month = str(deadline.deadline_date.month)
    deadline_date = _format_date(deadline.deadline_date)
    early_deadline = _format_optional_date(deadline.early_deadline_date)
    event_window = _format_event_window(
        deadline.event_start_date, deadline.event_end_date
    )
    primary_label = _primary_date_label(deadline)
    tags = ", ".join(deadline.tags) if deadline.tags else "None"

    details = [
        f"<div><strong>Status:</strong> {escape(deadline.status.replace('_', ' ').title())}</div>",
        f"<div><strong>Year:</strong> {deadline.year}</div>",
        f"<div><strong>Early Deadline:</strong> {escape(early_deadline)}</div>",
        f"<div><strong>Event Window:</strong> {escape(event_window)}</div>",
        f"<div><strong>Eligibility:</strong> {escape(deadline.eligibility_notes or 'Not specified')}</div>",
        f"<div><strong>Tags:</strong> {escape(tags)}</div>",
    ]

    return f"""
      <article class="card" data-category="{escape(deadline.category)}" data-month="{deadline_month}">
        <div class="meta">
          <span class="pill">{escape(CATEGORY_LABELS.get(deadline.category, deadline.category.title()))}</span>
          <span class="pill">{escape(month_name[deadline.deadline_date.month])}</span>
        </div>
        <p class="deadline-date">{escape(primary_label)} {escape(deadline_date)}</p>
        <h2>{escape(deadline.name)}</h2>
        <p class="organization">{escape(deadline.organization)}</p>
        <p class="description">{escape(deadline.description)}</p>
        <div class="details">
          {"".join(details)}
        </div>
        <a href="{escape(deadline.url, quote=True)}" target="_blank" rel="noreferrer">View source page</a>
      </article>
    """.strip()


def _format_date(value: date) -> str:
    return value.strftime("%B %d, %Y")


def _format_optional_date(value: date | None) -> str:
    return _format_date(value) if value is not None else "None"


def _format_event_window(start: date | None, end: date | None) -> str:
    if start is None and end is None:
        return "Not specified"
    if start is not None and end is not None:
        return f"{_format_date(start)} to {_format_date(end)}"
    if start is not None:
        return _format_date(start)
    if end is not None:
        return _format_date(end)
    return "Not specified"  # pragma: no cover - defensive fallback


def _primary_date_label(deadline: Deadline) -> str:
    if deadline.event_start_date is not None and deadline.deadline_date == deadline.event_start_date:
        return "Event Starts"
    return "Deadline"
