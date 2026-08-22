#!/usr/bin/env python3
"""Otimiza imagens sem sobrescrever os arquivos de origem."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError as exc:  # pragma: no cover - mensagem operacional
    raise SystemExit(
        "Pillow não está instalado. Execute: python -m pip install -r tools/requirements.txt"
    ) from exc


SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".avif"}


@dataclass
class Result:
    source: Path
    destination: Path | None
    original_bytes: int
    optimized_bytes: int | None
    status: str

    @property
    def saved_bytes(self) -> int:
        if self.optimized_bytes is None:
            return 0
        return max(0, self.original_bytes - self.optimized_bytes)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("input", type=Path, help="arquivo ou diretório de origem")
    command.add_argument("--output", type=Path, help="diretório de saída (padrão: <origem>/optimized)")
    command.add_argument("--format", choices=("webp", "avif", "jpeg", "png", "keep"), default="webp")
    command.add_argument("--quality", type=int, default=82, help="qualidade entre 1 e 100")
    command.add_argument("--max-size", type=int, default=2200, help="maior dimensão em pixels")
    command.add_argument("--dry-run", action="store_true", help="mostra o plano sem gravar")
    command.add_argument("--force", action="store_true", help="substitui resultados já existentes")
    command.add_argument("--keep-larger", action="store_true", help="mantém resultado mesmo se ficar maior")
    return command


def image_paths(source: Path, output: Path) -> list[Path]:
    if source.is_file():
        return [source] if source.suffix.lower() in SUPPORTED_SUFFIXES else []
    output_resolved = output.resolve()
    return sorted(
        path
        for path in source.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_SUFFIXES
        and output_resolved not in path.resolve().parents
    )


def destination_for(source: Path, input_root: Path, output: Path, format_name: str) -> Path:
    relative = Path(source.name) if input_root.is_file() else source.relative_to(input_root)
    suffix = source.suffix.lower() if format_name == "keep" else ".jpg" if format_name == "jpeg" else f".{format_name}"
    return (output / relative).with_suffix(suffix)


def save_options(format_name: str, quality: int) -> dict[str, object]:
    if format_name in {"webp", "avif", "jpeg"}:
        return {"quality": quality, "optimize": True}
    if format_name == "png":
        return {"optimize": True, "compress_level": 9}
    return {}


def optimize_one(
    source: Path,
    destination: Path,
    format_name: str,
    quality: int,
    max_size: int,
    dry_run: bool,
    force: bool,
    keep_larger: bool,
) -> Result:
    original_bytes = source.stat().st_size
    if destination.exists() and not force:
        return Result(source, destination, original_bytes, destination.stat().st_size, "já existe")
    if dry_run:
        return Result(source, destination, original_bytes, None, "simulação")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        effective_format = opened.format.lower() if format_name == "keep" and opened.format else format_name
        if effective_format in {"jpg", "jpeg"} and image.mode not in {"RGB", "L"}:
            background = Image.new("RGB", image.size, "white")
            if "A" in image.getbands():
                background.paste(image, mask=image.getchannel("A"))
            else:
                background.paste(image)
            image = background
        image.save(destination, format=effective_format.upper(), **save_options(effective_format, quality))

    optimized_bytes = destination.stat().st_size
    if optimized_bytes >= original_bytes and not keep_larger:
        destination.unlink()
        return Result(source, None, original_bytes, optimized_bytes, "descartada: não ficou menor")
    return Result(source, destination, original_bytes, optimized_bytes, "otimizada")


def human_size(size: int | None) -> str:
    if size is None:
        return "—"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def main() -> int:
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parser().parse_args()
    source = args.input.resolve()
    if not source.exists():
        raise SystemExit(f"Origem não encontrada: {source}")
    if not 1 <= args.quality <= 100:
        raise SystemExit("--quality deve estar entre 1 e 100")
    if args.max_size < 64:
        raise SystemExit("--max-size deve ser ao menos 64")

    default_output = source.parent / f"{source.stem}-optimized" if source.is_file() else source / "optimized"
    output = (args.output or default_output).resolve()
    if output == source or (source.is_dir() and source.resolve() in output.parents and output.name == source.name):
        raise SystemExit("A saída precisa ser diferente da origem")

    paths = image_paths(source, output)
    if not paths:
        print("Nenhuma imagem raster compatível encontrada.")
        return 0

    results: list[Result] = []
    for path in paths:
        destination = destination_for(path, source, output, args.format)
        try:
            result = optimize_one(
                path, destination, args.format, args.quality, args.max_size,
                args.dry_run, args.force, args.keep_larger,
            )
        except (OSError, ValueError) as exc:
            result = Result(path, None, path.stat().st_size, None, f"erro: {exc}")
        results.append(result)
        relative = path.name if source.is_file() else path.relative_to(source)
        # Keep CLI output compatible with the default Windows CP1252 console.
        print(f"{relative}: {result.status} ({human_size(result.original_bytes)} -> {human_size(result.optimized_bytes)})")

    optimized = sum(result.status == "otimizada" for result in results)
    failures = sum(result.status.startswith("erro:") for result in results)
    print(
        f"Resumo: {len(results)} analisada(s), {optimized} otimizada(s), "
        f"{human_size(sum(result.saved_bytes for result in results))} economizados."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
