import gc
import time
import weakref
from pathlib import Path
import pytest
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import QApplication
from healthpro.gui import MainWindow
from healthpro.core import Cancelled
from healthpro.demo import create_demo


@pytest.fixture(scope='module')
def app():
    app=QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def drain(app,condition,timeout=8):
    until=time.monotonic()+timeout
    while not condition() and time.monotonic()<until:
        app.processEvents()
        time.sleep(.005)
    app.processEvents()
    assert condition(),'Qt job did not complete in time'


@pytest.fixture
def win(app):
    w=MainWindow()
    w.show()
    app.processEvents()
    yield w
    if w.worker:
        w.worker.requestInterruption()
        drain(app,lambda:w.worker is None)
    w.close()
    w.deleteLater()
    app.processEvents()


def load(win,app):
    path=create_demo()
    win.process_zip(str(path))
    drain(app,lambda:win.worker is None)
    assert win.index is not None


def test_import_selection_export_and_reset(win,app,tmp_path):
    load(win,app)
    assert not win.execute_button.isEnabled()
    win.set_sources(True)
    assert win.execute_button.isEnabled()
    assert not win.overlap_details.isVisible()
    assert '不自动去重' in win.overlap_details.text()
    win.destination.setText(str(tmp_path))
    win.start_export()
    drain(app,lambda:win.worker is None)
    assert win.result and win.result.rows==217
    assert '导出完成' in win.status_label.text()
    ref=weakref.ref(win.index)
    win.reset();gc.collect()
    assert win.index is None and win.result is None and ref() is None


def test_import_error_recoverable(win,app,tmp_path):
    win.process_zip(str(tmp_path/'missing.zip'))
    drain(app,lambda:win.worker is None)
    assert win.index is None
    assert '操作未完成' in win.status_label.text()
    assert win.browse_button.isEnabled()
    load(win,app)
    assert win.index.total_records==217


def test_export_failure_not_success(win,app,tmp_path):
    load(win,app);win.set_sources(True)
    win.destination.setText(str(tmp_path/'missing'))
    win.start_export();drain(app,lambda:win.worker is None)
    assert win.result is None and '操作未完成' in win.status_label.text()
    assert win.execute_button.isEnabled()


def test_reverse_dates_disable_export(win,app):
    load(win,app);win.set_sources(True)
    win.date_start.setDate(QDate(2030,1,1))
    assert not win.execute_button.isEnabled()
    assert '不能晚于' in win.selection_hint.text()


def slow_operation(cancel,progress):
    until=time.monotonic()+5
    while time.monotonic()<until:
        if cancel():raise Cancelled()
        time.sleep(.005)
    raise RuntimeError('test cancellation timed out')


def test_reentry_blocked_and_cancel(win,app):
    win.start_job('scan',slow_operation)
    worker=win.worker
    assert not win.process_zip('other.zip')
    assert win.worker is worker
    assert not win.browse_button.isEnabled()
    win.cancel_job();drain(app,lambda:win.worker is None)
    assert '已取消' in win.status_label.text()


def test_close_waits_for_worker(win,app):
    win.start_job('scan',slow_operation)
    win.close()
    assert win.close_pending
    drain(app,lambda:win.worker is None)
    assert not win.isVisible()


def test_keyboard_and_search(win,app):
    load(win,app)
    assert win.browse_button.focusPolicy()!=Qt.FocusPolicy.NoFocus
    assert win.open_action.shortcut().toString()
    win.search.setText('iPhone')
    assert sum(not win.source_list.item(i).isHidden() for i in range(win.source_list.count()))==1
    win.set_sources(True)
    assert len(win.selected_sources())==3


def test_themes_render(win,app,tmp_path):
    load(win,app);win.set_sources(True)
    for mode in [1,2]:
        win.set_theme_mode(mode);app.processEvents()
        assert win.grab().save(str(tmp_path/f'theme-{mode}.png'))


def test_ring_avoids_idle_and_determinate_animation_ticks(win,app):
    ring=win.ring
    assert not ring.timer.isActive()
    ring.set_state('scan',None)
    assert ring.timer.isActive()
    ring.set_state('scan',45)
    assert not ring.timer.isActive()
    ring.set_theme(False,True)
    assert ring.progress==45 and ring.animation.state()==ring.animation.State.Stopped
    ring.set_state('export',None)
    assert not ring.timer.isActive()
    ring.set_theme(True,False)
    assert ring.timer.isActive()
    ring.set_state('success',100)
    assert ring.progress==100 and not ring.timer.isActive()
    ring.set_state('scan',None)
    win.hide();app.processEvents()
    assert not ring.timer.isActive() and not win.resource_hud.timer.isActive()


def test_monitor_nonblocking_normalized_and_failure(win,monkeypatch):
    from types import SimpleNamespace
    import psutil
    hud=win.resource_hud
    calls=[]
    hud.cores=8
    hud.total_memory=1024**3
    monkeypatch.setattr(hud.process,'cpu_percent',lambda interval: calls.append(interval) or 160)
    monkeypatch.setattr(hud.process,'memory_info',lambda: SimpleNamespace(rss=128*1024**2))
    hud.sample()
    assert calls==[None] and hud.cpu_label.text()=='20.0%'
    assert hud.ram_label.text()=='128 MB' and hud.ram_ring.pct==12.5
    def fail(interval): raise psutil.AccessDenied()
    monkeypatch.setattr(hud.process,'cpu_percent',fail)
    hud.sample()
    assert hud.cpu_label.text()==hud.ram_label.text()=='—'
    assert hud.cpu_ring.pct==hud.ram_ring.pct==0


def test_accessibility_live_changes_and_close_cleanup(win,app,monkeypatch):
    win.ring.set_state('scan',None)
    monkeypatch.setattr(win.materials,'preferences',lambda: 7)
    win.refresh_accessibility();app.processEvents()
    assert win.toolbar.solid and win.status_card.solid and win.canvas.solid
    assert not win.ring.timer.isActive()
    monkeypatch.setattr(win.materials,'preferences',lambda: 0)
    win.refresh_accessibility();app.processEvents()
    assert not win.toolbar.solid and win.ring.timer.isActive()
    win.close();app.processEvents()
    assert not win.preference_timer.isActive() and not win.resource_hud.timer.isActive()
    assert not win.toolbar.sync_timer.isActive() and not win.status_card.sync_timer.isActive()


def test_simplified_controls_and_terminal_ring(win,app,tmp_path):
    from PyQt6.QtTest import QTest
    assert not win.advanced_options.isVisible()
    win.options_toggle.click()
    assert win.privacy.isVisible() and win.excel_safe.isVisible()
    assert win.privacy.isChecked() and win.excel_safe.isChecked()
    hits=[]
    win.ring.clicked.disconnect()
    win.ring.clicked.connect(lambda: hits.append(True))
    QTest.keyClick(win.ring,Qt.Key.Key_Return)
    QTest.keyClick(win.ring,Qt.Key.Key_Space)
    assert len(hits)==2
    load(win,app)
    assert win.ring.phase=='ready' and win.ring.progress==100
    win.select_all.click()
    assert len(win.selected_sources())==3 and win.select_all.text()=='取消全选'
    win.select_all.click()
    assert not win.selected_sources()
    for theme in (1,2,0):
        win.set_theme_mode(theme);app.processEvents()
        assert win.execute_button.height()>=40
    win.process_zip(str(tmp_path/'missing.zip'))
    drain(app,lambda:win.worker is None)
    assert win.ring.phase=='error' and win.ring.progress==0


def test_capsule_corners_in_both_states_and_themes(win,app):
    from PyQt6.QtCore import QPoint
    from PyQt6.QtGui import QImage, QRegion
    from PyQt6.QtWidgets import QWidget
    button=win.execute_button
    for dark in (False,True):
        button.set_theme(dark)
        for enabled in (False,True):
            button.setEnabled(enabled);app.processEvents()
            canvas=QImage(button.size(),QImage.Format.Format_ARGB32)
            canvas.fill(Qt.GlobalColor.transparent)
            button.render(canvas,QPoint(),QRegion(),QWidget.RenderFlag.DrawChildren)
            assert canvas.pixelColor(3,3).alpha()==0
            assert canvas.pixelColor(button.width()//2,5).alpha()>240


def test_calendar_leap_day_year_navigation_and_cancel(win,app):
    from PyQt6.QtTest import QTest
    field=win.date_start
    field.setDate(QDate(2024,2,29));field.open_calendar();app.processEvents()
    popup=field.popup
    assert any(day.day==QDate(2024,2,29) for day in popup.days)
    popup.shift_month(1)
    assert popup.month==QDate(2024,3,1)
    popup.shift_month(-3)
    assert popup.month==QDate(2023,12,1)
    popup.year_picker.setCurrentIndex(popup.year_picker.findData(2026))
    popup.month_picker.setCurrentIndex(10)
    assert popup.month==QDate(2026,11,1)
    QTest.keyClick(popup,Qt.Key.Key_Escape)
    assert field.date()==QDate(2024,2,29) and not popup.isVisible()
    field.open_calendar();app.processEvents()
    popup=field.popup
    button=next(day for day in popup.days if day.day==QDate(2024,2,29))
    QTest.keyClick(button,Qt.Key.Key_Right)
    assert popup.month==QDate(2024,3,1)
    selected=app.focusWidget()
    assert selected.day==QDate(2024,3,1)
    QTest.keyClick(selected,Qt.Key.Key_Return)
    assert field.date()==QDate(2024,3,1) and not popup.isVisible()


def test_ring_focus_and_overlap_details_are_not_permanent(win,app):
    from PyQt6.QtTest import QTest
    win.ring.clicked.disconnect()
    win.search.setFocus();win.ring.setFocus(Qt.FocusReason.TabFocusReason)
    app.processEvents()
    assert win.ring.keyboard_focus
    QTest.mouseClick(win.ring,Qt.MouseButton.LeftButton)
    assert not win.ring.keyboard_focus
    load(win,app);win.set_sources(True)
    assert not win.overlap_details.isVisible()
    win.details_button.click()
    assert win.overlap_details.isVisible() and '不要直接跨来源相加' in win.overlap_details.text()
    win.details_button.click()
    assert not win.overlap_details.isVisible()


def test_native_path_callback_cancel_and_destination(win,app,tmp_path):
    from healthpro.materials import NativeMaterials
    native=NativeMaterials()
    values=[]
    native._path_done=values.append
    native._path_selected(None)
    app.processEvents()
    assert values==[''] and native._path_done is None
    native._path_done=win.accept_destination_path
    native._path_selected(str(tmp_path).encode('utf-8'))
    app.processEvents()
    assert win.destination.text()==str(tmp_path)


def test_native_theme_transitions_update_window_and_replace_glass(win,app,monkeypatch):
    class FakeNative:
        def __init__(self):
            self.next=0
            self.live={}
            self.modes=[]
        def hp_accessibility(self): return 0
        def hp_window_appearance(self,view,mode): self.modes.append(mode)
        def hp_glass_attach(self,view):
            self.next+=1;self.live[self.next]=None;return self.next
        def hp_glass_kind(self,handle): return 2
        def hp_glass_sync(self,handle,dark): self.live[handle]=dark
        def hp_glass_detach(self,handle): del self.live[handle]
    native=FakeNative()
    monkeypatch.setattr(win.materials,'lib',native)
    for mode in (1,2,1,2,0):
        previous=(win.toolbar.handle,win.status_card.handle)
        was_dark=win.canvas.dark
        win.set_theme_mode(mode);app.processEvents()
        assert native.modes[-1]==mode
        assert len(native.live)==2 and all(dark==win.canvas.dark for dark in native.live.values())
        if was_dark!=win.canvas.dark:
            assert win.toolbar.handle not in previous and win.status_card.handle not in previous
        count=native.next
        win.apply_theme();app.processEvents()
        assert native.next==count  # ordinary refresh must not recreate/flicker
    win.close();app.processEvents()
    assert not native.live
