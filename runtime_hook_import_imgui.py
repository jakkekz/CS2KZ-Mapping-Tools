# Runtime hook to ensure imgui is imported early so PyInstaller includes it
try:
    import imgui
    # Optionally import integrations used by the app
    try:
        from imgui.integrations import glfw as imgui_glfw
    except Exception:
        pass
except Exception:
    # If import fails at runtime, print to console for debugging
    import traceback
    traceback.print_exc()
