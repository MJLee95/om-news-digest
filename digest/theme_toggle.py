"""Light / Dark / System toggle shared by the archive index and the web copies of each issue.

Pages define their colors as CSS variables for light mode, then for dark mode under
both `@media (prefers-color-scheme: dark)` (when no explicit choice) and `[data-theme="dark"]`.
"""

# Runs in <head> so the saved choice applies before first paint (no flash).
HEAD_JS = """<script>
try { const t = localStorage.getItem('theme'); if (t === 'light' || t === 'dark') document.documentElement.dataset.theme = t; } catch (e) {}
</script>"""

CSS = """
.theme-toggle{position:fixed;top:12px;right:12px;z-index:50;display:flex;align-items:center;gap:6px;
  border:1px solid var(--toggle-line);background:var(--toggle-bg);color:var(--toggle-ink);border-radius:999px;
  padding:7px 13px;font:600 13px/1 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;cursor:pointer;
  box-shadow:0 2px 10px rgba(0,0,0,.18)}
.theme-toggle:hover{border-color:var(--toggle-ink)}
.theme-toggle .ic{font-size:14px}
"""

BUTTON = '<button class="theme-toggle" id="themeToggle" type="button"></button>'

BODY_JS = """<script>
(() => {
  const btn = document.getElementById('themeToggle');
  const ORDER = ['system', 'light', 'dark'];
  const LABEL = {system: ['◐', 'System'], light: ['☀︎', 'Light'], dark: ['☾', 'Dark']};
  let mode = 'system';
  try { mode = localStorage.getItem('theme') || 'system'; } catch (e) {}
  if (!ORDER.includes(mode)) mode = 'system';
  const apply = () => {
    if (mode === 'system') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = mode;
    const [ic, label] = LABEL[mode];
    btn.innerHTML = `<span class="ic">${ic}</span>${label}`;
    btn.title = `Theme: ${label} (click to change)`;
    btn.setAttribute('aria-label', `Color theme: ${label}. Click to change.`);
  };
  btn.onclick = () => {
    mode = ORDER[(ORDER.indexOf(mode) + 1) % ORDER.length];
    try { mode === 'system' ? localStorage.removeItem('theme') : localStorage.setItem('theme', mode); } catch (e) {}
    apply();
  };
  apply();
})();
</script>"""


def themed_vars(light: dict, dark: dict) -> str:
    """CSS that sets `--name` variables for light, and for dark via system preference or explicit choice."""
    decl = lambda d: ";".join(f"--{k}:{v}" for k, v in d.items())
    return (f":root{{{decl(light)}}}\n"
            f"@media (prefers-color-scheme:dark){{:root:not([data-theme=\"light\"]){{{decl(dark)}}}}}\n"
            f":root[data-theme=\"dark\"]{{{decl(dark)}}}\n")
