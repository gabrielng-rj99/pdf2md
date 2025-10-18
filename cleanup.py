#!/usr/bin/env python3
"""
Script para limpar a pasta output/ de arquivos temporários.

Uso:
    python3 cleanup.py          # Remove todos os arquivos de output/
    python3 cleanup.py --help   # Mostra ajuda
"""

import os
import shutil
import sys
from pathlib import Path


def cleanup_output_dir(output_dir: str = "output", verbose: bool = True) -> None:
    """
    Limpa a pasta output/ removendo todos os arquivos temporários.

    Args:
        output_dir: Diretório a ser limpo (padrão: "output")
        verbose: Se True, mostra o que está sendo removido
    """
    output_path = Path(output_dir)

    if not output_path.exists():
        if verbose:
            print(f"⚠️  Pasta '{output_dir}' não existe.")
        return

    if not output_path.is_dir():
        if verbose:
            print(f"❌ '{output_dir}' não é uma pasta.")
        return

    removed_count = 0
    removed_size = 0

    # Listar tudo na pasta
    for item in output_path.iterdir():
        # Não remover .gitkeep
        if item.name == ".gitkeep":
            continue

        try:
            if item.is_file():
                file_size = item.stat().st_size
                removed_size += file_size
                item.unlink()
                if verbose:
                    print(f"  🗑️  Arquivo removido: {item.name} ({file_size / 1024:.1f} KB)")
                removed_count += 1

            elif item.is_dir():
                dir_size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                removed_size += dir_size
                shutil.rmtree(item)
                if verbose:
                    print(f"  🗑️  Pasta removida: {item.name}/ ({dir_size / 1024:.1f} KB)")
                removed_count += 1

        except Exception as e:
            print(f"  ❌ Erro ao remover {item.name}: {e}")

    # Resumo
    if verbose:
        if removed_count > 0:
            print(f"\n✅ Limpeza concluída!")
            print(f"   Itens removidos: {removed_count}")
            print(f"   Espaço liberado: {removed_size / 1024 / 1024:.1f} MB")
        else:
            print(f"\n✅ Pasta já está limpa!")


def main():
    """Função principal."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return

    if "--quiet" in sys.argv or "-q" in sys.argv:
        cleanup_output_dir(verbose=False)
    else:
        print("🧹 Limpando pasta output/...\n")
        cleanup_output_dir(verbose=True)


if __name__ == "__main__":
    main()
