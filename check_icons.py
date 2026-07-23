with open('frontend/assets/js/core.js', 'rb') as f:
    content = f.read()
import re
matches = list(re.finditer(rb"(users|megaphone|settings):\s*'([^']*)'", content))
for m in matches:
    name = m.group(1).decode()
    path = m.group(2)
    non_ascii = [(i, b) for i, b in enumerate(path) if b > 127]
    if non_ascii:
        print(f"{name}: Non-ASCII bytes found: {non_ascii}")
    else:
        print(f"{name}: OK (all ASCII)")
    print(f"  Length: {len(path)} bytes")
