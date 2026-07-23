from pathlib import Path

p = Path("frontend/assets/js/core.js")
text = p.read_text(encoding="utf-8", errors="replace")

replacements = [
    ('if (!ts) return "\ufffd";', 'if (!ts) return "\\u2014";'),
    ('if (!d) return "\ufffd";', 'if (!d) return "\\u2014";'),
    ('return t || "\ufffd";', 'return t || "\\u2014";'),
    ('text = "Loading\ufffd"', 'text = "Loading\\u2026"'),
    ("pageSize + 1}\ufffd${Math.min", "pageSize + 1}\\u2013${Math.min"),
    ("<span class='text-muted'>\ufffd</span>", "<span class='text-muted'>\\u2026</span>"),
    ("NCST \ufffd Application", "NCST - Application"),
    (
        'return `<div class="alert alert-${type}"><span>${icons[type] || icons.info}</span>',
        'return `<div class="alert alert-${type}"><span>${svg(icons[type] || icons.info)}</span>',
    ),
]
for old, new in replacements:
    text = text.replace(old, new)

p.write_text(text, encoding="utf-8")
print("core.js encoding fixed")
