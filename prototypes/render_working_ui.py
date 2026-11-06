"""Render the real desktop UI with synthetic data and isolated preferences.

Run from the project root: python prototypes/render_working_ui.py --render-dir prototypes/working_previews
"""

import argparse
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render-dir', type=Path, required=True)
    parser.add_argument('--size', default='1280x850')
    parser.add_argument('--scale', type=float, default=1)
    args = parser.parse_args()
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    os.environ['QT_SCALE_FACTOR'] = str(args.scale)
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication
    from app.ui import main_window
    from app.analytics.metrics import SelectedColumns
    from app.services.file_loader import load_file_preview
    from prototypes.ui_preview import demo_data, SLUGS

    scratch = ROOT / '.pytest-tmp-working-ui' / uuid4().hex
    scratch.mkdir(parents=True)
    settings = QSettings(str(scratch / 'render.ini'), QSettings.Format.IniFormat)
    settings.clear()
    main_window.QSettings = lambda *unused: settings
    application = QApplication([])
    if sys.platform == 'win32':
        for filename in ('segoeui.ttf', 'segoeuib.ttf', 'segoeuisl.ttf'):
            QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / filename))
    application.setFont(QFont('Segoe UI', 10))
    path = scratch / 'synthetic_demo.csv'
    demo_data().to_csv(path, index=False)
    window = main_window.MainWindow(language='ru')
    window._show_loaded_file(load_file_preview(path))
    window.selected_columns = SelectedColumns(date='date', revenue='revenue', expense='expense',
                                             category='category', description='description')
    window.detected_columns_label.setText(window._format_selected_columns_summary())
    window.analysis_options.balance_edit.setText('620000')
    results, errors = [], []
    worker = main_window.AnalysisWorker(str(path), window.selected_columns, 'day', 'monday', cash_balance=620000)
    worker.completed.connect(results.append)
    worker.failed.connect(errors.append)
    worker.run()
    if errors or not results:
        raise RuntimeError(errors)
    window._handle_analysis_completed(results[0])
    window.resize(*map(int, args.size.split('x')))
    window.show()
    args.render_dir.mkdir(parents=True, exist_ok=True)
    captures = []
    for theme in ('light', 'dark'):
        if window.theme != theme:
            window.sidebar.theme_button.click()
        for index in range(5):
            window.sidebar.nav_buttons[index].click()
            application.processEvents()
            application.processEvents()
            scroll = window.page_stack.currentWidget()
            filename = f'{index+1:02d}_{SLUGS[index]}_{theme}.png'
            if not window.grab().save(str(args.render_dir / filename)):
                raise RuntimeError(filename)
            captures.append(dict(screenshot=filename, theme=theme, page=index,
                                 size=[window.width(), window.height()], dpr=window.devicePixelRatioF(),
                                 horizontal_scroll_max=scroll.horizontalScrollBar().maximum(),
                                 vertical_scroll_max=scroll.verticalScrollBar().maximum()))
    window.sidebar.toggle_button.click()
    window.sidebar.nav_buttons[0].click()
    application.processEvents()
    window.grab().save(str(args.render_dir / '06_overview_dark_collapsed.png'))
    manifest = dict(synthetic_data=True, real_application=True, captures=captures)
    (args.render_dir / 'render_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False))
    window.close()


if __name__ == '__main__':
    main()
