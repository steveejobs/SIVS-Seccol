"""Extração limitada de PDFs externos em processo isolado.

O processo HTTP nunca entrega PDFs não confiáveis diretamente ao parser. O
worker recebe somente um arquivo temporário, não herda segredos da aplicação e
é encerrado por tempo, CPU, memória e tamanho de saída quando a plataforma
oferece esses limites.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


MAX_PAGES = 120
MAX_TEXT_PER_PAGE = 8_000
MAX_TOTAL_TEXT = 50_000
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 48 * 1024 * 1024
MAX_RESULT_BYTES = 2 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 30


class PDFSandboxError(ValueError):
    """PDF rejeitado, inválido ou acima dos limites de processamento."""


def _worker_limits():
    if os.name == "nt":
        return
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


def _minimal_environment(temporary_directory: Path) -> dict[str, str]:
    allowed = ("SYSTEMROOT", "WINDIR")
    environment = {key: os.environ[key] for key in allowed if os.environ.get(key)}
    environment.update({
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
        "TMP": str(temporary_directory),
        "TEMP": str(temporary_directory),
    })
    return environment


def extract_pdf_pages(body: bytes, document_name: str, *, include_images: bool = False,
                      timeout: int = DEFAULT_TIMEOUT_SECONDS) -> list[dict]:
    if not isinstance(body, bytes) or not body.startswith(b"%PDF-"):
        raise PDFSandboxError("O documento não possui assinatura PDF válida")
    if timeout < 1 or timeout > 60:
        raise PDFSandboxError("Limite de tempo do parser inválido")

    with tempfile.TemporaryDirectory(prefix="sivs-pdf-") as directory_name:
        directory = Path(directory_name)
        source = directory / "source.pdf"
        result_path = directory / "result.json"
        image_directory = directory / "images"
        source.write_bytes(body)
        image_directory.mkdir()
        command = [
            sys.executable, str(Path(__file__).resolve()), "--worker",
            str(source), str(result_path), str(image_directory),
        ]
        if include_images:
            command.append("--images")
        kwargs = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.PIPE,
            "env": _minimal_environment(directory),
            "timeout": timeout,
            "check": False,
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            kwargs["preexec_fn"] = _worker_limits
        try:
            completed = subprocess.run(command, **kwargs)
        except subprocess.TimeoutExpired as exc:
            raise PDFSandboxError("O PDF excedeu o tempo seguro de processamento") from exc
        if completed.returncode != 0:
            detail = (completed.stderr or b"").decode("utf-8", "replace")[:300].strip()
            raise PDFSandboxError(detail or "O PDF foi recusado pelo parser isolado")
        if not result_path.is_file() or result_path.stat().st_size > MAX_RESULT_BYTES:
            raise PDFSandboxError("O resultado do PDF excedeu o limite seguro")
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PDFSandboxError("O parser isolado devolveu um resultado inválido") from exc
        if not isinstance(result, list) or len(result) > MAX_PAGES:
            raise PDFSandboxError("O parser isolado excedeu o limite de páginas")

        total_images = 0
        pages = []
        for raw_page in result:
            if not isinstance(raw_page, dict):
                raise PDFSandboxError("O parser isolado devolveu uma página inválida")
            page = {
                "document": str(document_name)[:240],
                "page": int(raw_page.get("page") or 0),
                "text": str(raw_page.get("text") or "")[:MAX_TEXT_PER_PAGE],
                "hasImages": bool(raw_page.get("hasImages")),
            }
            images = []
            for relative_name in raw_page.get("images") or []:
                candidate = (image_directory / str(relative_name)).resolve()
                if candidate.parent != image_directory.resolve() or not candidate.is_file():
                    raise PDFSandboxError("O parser isolado devolveu uma imagem inválida")
                size = candidate.stat().st_size
                total_images += size
                if size > MAX_IMAGE_BYTES or total_images > MAX_TOTAL_IMAGE_BYTES:
                    raise PDFSandboxError("As imagens do PDF excederam o limite seguro")
                images.append(candidate.read_bytes())
            if images:
                page["_images"] = images
            pages.append(page)
        return pages


def _extract_worker(source: Path, result_path: Path, image_directory: Path,
                    include_images: bool) -> None:
    import logging
    from pypdf import PdfReader

    logging.disable(logging.CRITICAL)
    reader = PdfReader(source, strict=True)
    pages = []
    total_text = 0
    total_image_bytes = 0
    page_count = min(len(reader.pages), MAX_PAGES)
    for index in range(page_count):
        page = reader.pages[index]
        try:
            text = (page.extract_text() or "").strip()[:MAX_TEXT_PER_PAGE]
        except Exception:
            text = ""
        try:
            page_images = list(page.images)
        except Exception:
            page_images = []
        item = {
            "page": index + 1,
            "text": text,
            "hasImages": bool(page_images),
            "images": [],
        }
        total_text += len(text)
        if include_images and index < 40 and len(text) < 80:
            for image_index, image in enumerate(page_images[:3]):
                data = bytes(image.data)
                if len(data) > MAX_IMAGE_BYTES:
                    continue
                if total_image_bytes + len(data) > MAX_TOTAL_IMAGE_BYTES:
                    break
                filename = f"page-{index + 1}-{image_index + 1}.bin"
                (image_directory / filename).write_bytes(data)
                item["images"].append(filename)
                total_image_bytes += len(data)
        if text or page_images:
            pages.append(item)
        if total_text >= MAX_TOTAL_TEXT:
            break
    result_path.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("source", type=Path)
    parser.add_argument("result", type=Path)
    parser.add_argument("images_directory", type=Path)
    parser.add_argument("--images", action="store_true")
    args = parser.parse_args()
    if not args.worker:
        return 2
    try:
        _extract_worker(args.source, args.result, args.images_directory, args.images)
        return 0
    except Exception as exc:
        print(f"PDF rejeitado: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
