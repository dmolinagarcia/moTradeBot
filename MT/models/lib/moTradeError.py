# -*- coding: utf-8 -*-

# ──────────────────────────────────────────────────────────────────────────────
# Gestión de excepciones
# ──────────────────────────────────────────────────────────────────────────────

class MoTradeError(Exception):
    """Excepción unificada con código de error y mensaje."""

    def __init__(self, code: int, message: str, *args):
        super().__init__(message, *args)
        self.code = code
        self.message = message

    def __str__(self):
        return f"[{self.code}] {self.message}"