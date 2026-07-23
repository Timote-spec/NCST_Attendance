import re
from pathlib import Path

pattern = re.compile(r"<svg>\$\{([^}]+)\}</svg>")

for rel in ["frontend/assets/js/shared.js", "frontend/assets/js/admin.js"]:
    p = Path(rel)
    text = p.read_text(encoding="utf-8")
    if "const svg = App.svg;" not in text:
        text = text.replace(
            "  const I = App.ICON;\n",
            "  const I = App.ICON;\n  const svg = App.svg;\n",
            1,
        )

    def repl(m):
        return "${svg(" + m.group(1) + ")}"

    text, n = pattern.subn(repl, text)
    text = text.replace(
        '<div class="stat-icon"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24">${icon}</svg></div>',
        '<div class="stat-icon">${svg(icon)}</div>',
    )
    p.write_text(text, encoding="utf-8")
    print(f"{rel}: replaced {n} icons")
