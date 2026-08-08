"""UI Modularization Tests.

Verifies that all UI modules can be successfully imported and lack circular dependencies.
"""

import sys

def test_ui_imports():
    # Attempt to import all UI modules to verify they compile and have resolved imports
    import ui.sidebar
    import ui.chat
    import ui.sql_viewer
    import ui.results
    import ui.charts
    import ui.settings
    import ui.timeline
    
    assert hasattr(ui.sidebar, "render_sidebar")
    assert hasattr(ui.chat, "render_chat_tab")
    assert hasattr(ui.sql_viewer, "render_sql_executor_tab")
    assert hasattr(ui.sql_viewer, "render_sql_code")
    assert hasattr(ui.results, "render_results_table")
    assert hasattr(ui.charts, "render_visualizations_tab")
    assert hasattr(ui.charts, "render_recommended_chart")
    assert hasattr(ui.settings, "render_api_key_settings")
    assert hasattr(ui.timeline, "render_timeline")

def test_no_circular_dependency():
    # Verify app is not in sys.modules when importing UI modules to ensure no top-level app imports
    if "app" in sys.modules:
        del sys.modules["app"]
        
    import ui.sidebar
    import ui.chat
    import ui.sql_viewer
    import ui.results
    import ui.charts
    import ui.settings
    import ui.timeline
    
    assert "app" not in sys.modules
