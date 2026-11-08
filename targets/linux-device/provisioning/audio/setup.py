"""Masked Linux authentication for the shared private SSH recipe transport."""

import json
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "wifi"))
from ssh_transport import SshConsole


def main(settings):
    root = tk.Tk()
    root.title(settings["title"])
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=20)
    frame.grid()
    ttk.Label(frame, text="起動時のスピーカー音量を復元できるようにします").grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
    )
    ttk.Label(frame, text="Linuxのパスワードは保存しません。Wi-Fiパスワードの入力は不要です。").grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(0, 12)
    )
    ttk.Label(frame, text="実機Linuxのパスワード").grid(row=2, column=0, padx=(0, 12))
    password = tk.StringVar()
    entry = ttk.Entry(frame, textvariable=password, show="●", width=30)
    entry.grid(row=2, column=1)
    entry.focus_set()
    status = tk.StringVar(value="音量の保存とUSB再接続時の復元設定に管理者認証が必要です。")
    ttk.Label(frame, textvariable=status, wraplength=480).grid(row=3, column=0, columnspan=2, sticky="w", pady=14)
    result = {"ok": False, "state": "cancelled"}
    busy = False

    def progress(text):
        root.after(0, lambda: status.set(text))

    def finish(report):
        nonlocal result, busy
        result = report
        busy = False
        button.config(state="normal")
        Path(settings["resultFile"]).write_text(json.dumps(report), encoding="utf-8")
        status.set(
            "音量の保存・復元テストが完了しました。"
            if report.get("ok")
            else "設定できませんでした：" + report.get("error", "unknown")
        )
        if report.get("ok"):
            root.after(1500, root.destroy)

    def submit():
        nonlocal busy
        secret = password.get()
        if not secret:
            status.set("Linuxのパスワードを入力してください。")
            return
        password.set("")
        busy = True
        button.config(state="disabled")

        def work():
            nonlocal secret
            console = None
            try:
                console = SshConsole(settings)
                report = console.apply(
                    {
                        **settings,
                        "progressStart": "音量の保存とUSB再接続時の復元を設定しています…",
                        "progressApply": "音量を保存し、保存値の復元をテストしています…",
                    },
                    secret,
                    progress,
                )
            except Exception as error:
                report = {
                    "ok": False,
                    "state": "failed",
                    "error": str(error) if type(error) is RuntimeError else "音量設定の結果を確認できませんでした。",
                }
            finally:
                secret = ""
                if console:
                    console.close()
            root.after(0, lambda: finish(report))

        threading.Thread(target=work, daemon=True).start()

    button = ttk.Button(frame, text="音量の保存・復元を設定", command=submit)
    button.grid(row=4, column=1, sticky="e")
    root.protocol("WM_DELETE_WINDOW", lambda: status.set("設定完了までお待ちください。") if busy else root.destroy())
    root.mainloop()
    print(json.dumps(result), flush=True)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(json.loads(sys.argv[1])))
