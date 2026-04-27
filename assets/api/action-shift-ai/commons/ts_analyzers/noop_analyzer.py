from commons.ts_analyzers.base_analyzer import BaseAnalyzer

# ----------------------- HTML / MD / JSON (Ignorados) -----------------------
class NoopAnalyzer(BaseAnalyzer):
    def extract(self, root, src: bytes):
        return None