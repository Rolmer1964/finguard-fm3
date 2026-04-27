import os
import sys
import types
import logging



def configure_logging():
    # Garante que o diretório `output/` existe
    os.makedirs("/tmp/output", exist_ok=True)

    # Cria handlers com encoding UTF-8
    stream_handler = logging.StreamHandler(sys.stdout)

    # Reconfigura o encoding do stream, se possível (Python 3.7+)
    if hasattr(stream_handler.stream, "reconfigure"):
        stream_handler.stream.reconfigure(encoding="utf-8")

    file_handler = logging.FileHandler("/tmp/output/execution.log", encoding="utf-8")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)-5s] | [%(pathname)s:%(lineno)d] - %(message)s",
        handlers=[stream_handler, file_handler]
    )

    # Redireciona stdout e stderr para o logger
    def make_stream_logger(level, logger):
        return types.SimpleNamespace(
            write=lambda msg: logger.log(level, msg.strip()) if msg.strip() else None,
            flush=lambda: None
        )

    sys.stdout = make_stream_logger(logging.INFO, logging.getLogger("stdout"))
    sys.stderr = make_stream_logger(logging.ERROR, logging.getLogger("stderr"))
