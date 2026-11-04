"""Exercise a frozen application's worker and export using synthetic data only."""
import json
from pathlib import Path
from PyQt6.QtCore import QTimer
from . import __version__


def run_smoke(app, window, report_path):
    report_path = Path(report_path)
    state = {"phase": "import", "success": False, "app_version": __version__}
    timer = QTimer(window)
    # Synthetic accessibility transitions must not be overwritten by OS polling.
    window.preference_timer.stop()
    transitions = [2, 1, 2, 1, 2, 0]

    def finish(error=None):
        timer.stop()
        if error:
            state["error"] = error
            state["success"] = False
        window.close()
        state["cleanup"] = not any(surface.handle for surface in (window.toolbar, window.status_card))
        state["success"] = state["success"] and state["cleanup"]
        report_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        app.exit(0 if state["success"] else 1)

    def check():
        if window.worker:
            return
        if state["phase"].startswith("material-"):
            step = int(state["phase"].split("-")[1])
            surfaces = (window.toolbar, window.status_card)
            if window.materials.lib:
                lib = window.materials.lib
                window_match = bool(lib.hp_window_appearance_matches(int(window.winId()), window.theme_mode))
                if window.accessibility_flags & 5:
                    valid = all(surface.handle is None for surface in surfaces)
                else:
                    valid = all(surface.handle and lib.hp_glass_valid(surface.handle)
                                and lib.hp_glass_appearance_matches(surface.handle, window.canvas.dark)
                                for surface in surfaces)
                state.setdefault("appearance_checks", []).append({"mode": window.theme_mode,
                    "dark": window.canvas.dark, "solid": window.canvas.solid,
                    "window": window_match, "glass": bool(valid)})
                if not valid or not window_match:
                    finish("Native window/material appearance, geometry or accessibility fallback failed")
                    return
            if step == 0:
                state["materials"] = [surface.backend for surface in surfaces]
            if step < len(transitions):
                window.set_theme_mode(transitions[step])
            elif step == len(transitions):
                window.accessibility_flags = 7
                window.apply_theme()
            elif step == len(transitions)+1:
                window.accessibility_flags = window.materials.preferences()
                window.set_theme_mode(2)
                window.apply_theme()
                window.resize(900, 680)
            else:
                state["success"] = state.get("exported") == 217
                finish()
                return
            state["phase"] = f"material-{step+1}"
            return
        if state["phase"] == "import":
            if not window.index:
                finish(window.status_label.text())
                return
            state["phase"] = "export"
            state["indexed"] = window.index.total_records
            window.set_sources(True)
            window.start_export()
        elif state["phase"] == "export":
            if not window.result:
                finish(window.status_label.text())
                return
            state.update(exported=window.result.rows,
                         directory=str(window.result.directory))
            window.set_theme_mode(1)
            window.resize(1200, 820)
            state["phase"] = "material-0"

    def timeout():
        if not timer.isActive():
            return
        import faulthandler
        with report_path.with_suffix(".stack.txt").open("w") as output:
            faulthandler.dump_traceback(file=output)
        finish("Timed out after 20 seconds")

    window.load_demo()
    timer.timeout.connect(check)
    timer.start(500 if window.materials.lib else 50)
    QTimer.singleShot(20000, timeout)
