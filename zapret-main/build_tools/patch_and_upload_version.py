#!/usr/bin/env python
"""
patch_and_upload_version.py --channel stable --version 16.2.0.0 --url https://... --notes "..." ^
                            --ssh-host root@X.X.X.X --ssh-key C:\id_ed25519 --remote /var/www/...

Если параметры не задать – покажет справку.
"""
from __future__ import annotations
import argparse, json, subprocess, sys, tempfile, pathlib, datetime, shlex

def run(cmd: list[str] | str):
    print(">", cmd if isinstance(cmd, str) else " ".join(shlex.quote(c) for c in cmd))
    res = subprocess.run(cmd, shell=isinstance(cmd, str))
    if res.returncode:
        sys.exit(res.returncode)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True, choices=["stable", "test"])
    ap.add_argument("--version", required=True)
    ap.add_argument("--url",     required=True)
    ap.add_argument("--notes",   required=True)
    ap.add_argument("--ssh-host", required=True)
    ap.add_argument("--ssh-key",  required=True)
    ap.add_argument("--remote",   required=True, help="директория на сервере, без имени файла")
    ap.add_argument("--json-url", default="https://zapretdpi.ru/version.json")
    args = ap.parse_args()

    tmp = pathlib.Path(tempfile.gettempdir()) / "version.json"

    # 1) скачиваем текущий JSON
    run(["curl", "-fsSL", args.json_url, "-o", tmp])

    data = json.loads(tmp.read_text(encoding="utf-8-sig"))

    # 2) патчим нужный блок
    data[args.channel] = {
        "version": args.version,
        "update_url": args.url,
        "release_notes": args.notes,
        "date": datetime.date.today().isoformat()
    }

    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")

    # 3) грузим обратно
    run([
        "scp", "-C", "-i", args.ssh_key,
        tmp,
        f"{args.ssh_host}:{args.remote}/version.json"
    ])
    print(f"✔ version.json обновлён: {args.channel} → {args.version}")

if __name__ == "__main__":
    main()
