from PyQt6.QtWidgets import QApplication


def copy_text(data: str = "") -> bool:
    """Preserve the clipboard when there is no text to copy."""
    if not data:
        return False
    QApplication.clipboard().setText(data)
    return True
