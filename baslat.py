"""DARKROOM başlatıcı (masaüstü uygulaması ve PyInstaller giriş noktası).

    DARKROOM.exe               uygulamayı açar
    DARKROOM.exe --selftest D  D klasörüne 2 sahnelik deneme videosu çizer (kurulum kontrolü)
"""
import multiprocessing
import os
import sys


def selftest(out):
    import json
    from promptvideo.pipeline import render_plan
    from promptvideo.theme import FONT_DIR
    base = os.path.dirname(FONT_DIR)
    plan_p = os.path.join(os.path.dirname(base), "ornekler", "demo_plan.json")
    with open(plan_p, encoding="utf-8") as f:
        plan = json.load(f)
    plan["scenes"] = plan["scenes"][1:3]
    return render_plan(plan, out, no_voice=True)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    # pencereli .exe'de konsol yok; print çağrıları hata vermesin
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    if "--selftest" in sys.argv:
        print(selftest(sys.argv[sys.argv.index("--selftest") + 1]))
        sys.exit(0)
    from promptvideo.app import run_app
    sys.exit(run_app())
