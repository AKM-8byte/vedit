"""Claude Code hook'u: .vedit.json dosyası yazıldığında/düzenlendiğinde doğrular.

Hata varsa çıkış kodu 2 ile mesajı stderr'e yazar; Claude bu mesajı görüp düzeltir.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main():
    try:
        sys.stderr.reconfigure(encoding="utf-8")
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return 0
    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ti.get("path") or ""
    if not path.endswith(".vedit.json") or not os.path.exists(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            proj = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[vedit] {path}: JSON bozuk: {e}", file=sys.stderr)
        return 2
    from vedit import model
    from vedit.lint import lint

    errors = model.validate(model.normalize(proj))
    if errors:
        print(f"[vedit] {path} geçersiz:\n" + "\n".join("- " + e for e in errors), file=sys.stderr)
        return 2
    issues = [i for i in lint(proj, os.path.dirname(os.path.abspath(path)), render_check=False)
              if i["level"] == "error"]
    if issues:
        print(f"[vedit] {path}:\n" + "\n".join(f"- {i['where']}: {i['msg']}" for i in issues),
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
