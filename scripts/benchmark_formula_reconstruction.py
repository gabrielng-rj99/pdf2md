#!/usr/bin/env python3
"""
Script de benchmark para medir o impacto de performance
do módulo de reconstrução de fórmulas.

Executa o processamento do PDF aula1.pdf com e sem
o módulo de reconstrução habilitado, comparando tempos.

Uso:
    python scripts/benchmark_formula_reconstruction.py
"""

import os
import sys
import time
import tempfile
import shutil
from typing import Tuple, Dict
from dataclasses import dataclass

# Adicionar raiz do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class BenchmarkResult:
    """Resultado de um benchmark."""
    name: str
    time_seconds: float
    output_size_bytes: int
    num_pages: int
    extra_info: Dict


def run_benchmark_with_reconstruction(pdf_path: str, output_dir: str) -> BenchmarkResult:
    """
    Executa benchmark COM reconstrução de fórmulas habilitada.
    """
    # Importar módulos
    from app.services.pdf2md_service import process_pdf
    from app.utils import formula_reconstruction

    # Garantir que está habilitado
    original_enabled = formula_reconstruction.FORMULA_RECONSTRUCTION_ENABLED
    formula_reconstruction.FORMULA_RECONSTRUCTION_ENABLED = True

    # Resetar instância global
    formula_reconstruction._reconstructor = None

    # Executar
    start_time = time.perf_counter()

    try:
        md_file, img_dir = process_pdf(pdf_path, output_dir)
    finally:
        # Restaurar estado original
        formula_reconstruction.FORMULA_RECONSTRUCTION_ENABLED = original_enabled

    end_time = time.perf_counter()

    # Coletar métricas
    md_path = os.path.join(output_dir, md_file)
    output_size = os.path.getsize(md_path) if os.path.exists(md_path) else 0

    # Contar páginas processadas (aproximado pelo conteúdo)
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
        num_pages = content.count('---') + 1

    # Estatísticas do reconstrutor
    reconstructor = formula_reconstruction.get_reconstructor()
    stats = reconstructor.get_stats()

    return BenchmarkResult(
        name="COM reconstrução",
        time_seconds=end_time - start_time,
        output_size_bytes=output_size,
        num_pages=num_pages,
        extra_info={
            'fragments_processed': stats.get('fragments_processed', 0),
            'reconstructions_made': stats.get('reconstructions_made', 0),
        }
    )


def run_benchmark_without_reconstruction(pdf_path: str, output_dir: str) -> BenchmarkResult:
    """
    Executa benchmark SEM reconstrução de fórmulas.
    """
    # Importar módulos
    from app.services.pdf2md_service import process_pdf
    from app.utils import formula_reconstruction

    # Desabilitar
    original_enabled = formula_reconstruction.FORMULA_RECONSTRUCTION_ENABLED
    formula_reconstruction.FORMULA_RECONSTRUCTION_ENABLED = False

    # Resetar instância global
    formula_reconstruction._reconstructor = None

    # Executar
    start_time = time.perf_counter()

    try:
        md_file, img_dir = process_pdf(pdf_path, output_dir)
    finally:
        # Restaurar estado original
        formula_reconstruction.FORMULA_RECONSTRUCTION_ENABLED = original_enabled

    end_time = time.perf_counter()

    # Coletar métricas
    md_path = os.path.join(output_dir, md_file)
    output_size = os.path.getsize(md_path) if os.path.exists(md_path) else 0

    # Contar páginas
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
        num_pages = content.count('---') + 1

    return BenchmarkResult(
        name="SEM reconstrução",
        time_seconds=end_time - start_time,
        output_size_bytes=output_size,
        num_pages=num_pages,
        extra_info={}
    )


def format_time(seconds: float) -> str:
    """Formata tempo em formato legível."""
    if seconds < 1:
        return f"{seconds * 1000:.2f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    else:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.2f}s"


def format_size(bytes_size: int) -> str:
    """Formata tamanho em formato legível."""
    if bytes_size < 1024:
        return f"{bytes_size}B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.2f}KB"
    else:
        return f"{bytes_size / (1024 * 1024):.2f}MB"


def print_results(result1: BenchmarkResult, result2: BenchmarkResult):
    """Imprime comparação de resultados."""
    print("\n" + "=" * 70)
    print("RESULTADOS DO BENCHMARK")
    print("=" * 70)

    print(f"\n{'Métrica':<35} {'SEM recon.':<15} {'COM recon.':<15} {'Diff':<15}")
    print("-" * 70)

    # Tempo
    time_diff = result1.time_seconds - result2.time_seconds
    time_diff_pct = (time_diff / result2.time_seconds * 100) if result2.time_seconds > 0 else 0
    print(f"{'Tempo total':<35} {format_time(result2.time_seconds):<15} {format_time(result1.time_seconds):<15} {time_diff_pct:+.1f}%")

    # Tamanho
    size_diff = result1.output_size_bytes - result2.output_size_bytes
    size_diff_pct = (size_diff / result2.output_size_bytes * 100) if result2.output_size_bytes > 0 else 0
    print(f"{'Tamanho do MD':<35} {format_size(result2.output_size_bytes):<15} {format_size(result1.output_size_bytes):<15} {size_diff_pct:+.1f}%")

    # Páginas
    print(f"{'Páginas processadas':<35} {result2.num_pages:<15} {result1.num_pages:<15} -")

    # Informações extras do COM reconstrução
    if result1.extra_info:
        print(f"\n{'Estatísticas da reconstrução:':<35}")
        print(f"  {'Fragmentos processados:':<33} {result1.extra_info.get('fragments_processed', 0)}")
        print(f"  {'Reconstruções realizadas:':<33} {result1.extra_info.get('reconstructions_made', 0)}")

    print("\n" + "=" * 70)

    # Recomendação
    print("\n📊 ANÁLISE:")
    overhead_ms = (result1.time_seconds - result2.time_seconds) * 1000

    if overhead_ms < 100:
        print(f"   ✅ Overhead IRRELEVANTE ({overhead_ms:.1f}ms)")
        print("   → Recomendação: MANTER O MÓDULO HABILITADO")
    elif overhead_ms < 500:
        print(f"   ⚠️  Overhead BAIXO ({overhead_ms:.1f}ms)")
        print("   → Recomendação: Manter habilitado, mas monitorar")
    elif overhead_ms < 2000:
        print(f"   ⚠️  Overhead MODERADO ({overhead_ms:.1f}ms)")
        print("   → Recomendação: Considerar desabilitar para PDFs muito grandes")
    else:
        print(f"   ❌ Overhead SIGNIFICATIVO ({overhead_ms:.1f}ms)")
        print("   → Recomendação: DESABILITAR O MÓDULO")

    print()


def main():
    """Função principal do benchmark."""
    print("=" * 70)
    print("BENCHMARK: Reconstrução de Fórmulas Fragmentadas")
    print("=" * 70)

    # Verificar se o PDF existe
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pdf_path = os.path.join(project_root, "aula1.pdf")

    if not os.path.exists(pdf_path):
        print(f"\n❌ Erro: PDF não encontrado: {pdf_path}")
        print("   Certifique-se de que o arquivo aula1.pdf está na raiz do projeto.")
        sys.exit(1)

    print(f"\n📄 PDF: {pdf_path}")
    print(f"   Tamanho: {format_size(os.path.getsize(pdf_path))}")

    # Criar diretórios temporários
    temp_dir_with = tempfile.mkdtemp(prefix="pdf2md_bench_with_")
    temp_dir_without = tempfile.mkdtemp(prefix="pdf2md_bench_without_")

    try:
        # Benchmark SEM reconstrução (baseline)
        print("\n🔄 Executando benchmark SEM reconstrução de fórmulas...")
        result_without = run_benchmark_without_reconstruction(pdf_path, temp_dir_without)
        print(f"   ✓ Concluído em {format_time(result_without.time_seconds)}")

        # Benchmark COM reconstrução
        print("\n🔄 Executando benchmark COM reconstrução de fórmulas...")
        result_with = run_benchmark_with_reconstruction(pdf_path, temp_dir_with)
        print(f"   ✓ Concluído em {format_time(result_with.time_seconds)}")

        # Imprimir resultados
        print_results(result_with, result_without)

        # Salvar MDs para comparação manual se quiser
        print("📁 Arquivos de saída salvos em:")
        print(f"   SEM reconstrução: {temp_dir_without}")
        print(f"   COM reconstrução: {temp_dir_with}")

        # Perguntar se quer manter os arquivos
        try:
            response = input("\n🗑️  Limpar arquivos temporários? [S/n]: ").strip().lower()
            if response in ('', 's', 'y', 'sim', 'yes'):
                shutil.rmtree(temp_dir_with, ignore_errors=True)
                shutil.rmtree(temp_dir_without, ignore_errors=True)
                print("   ✓ Arquivos removidos")
            else:
                print("   ℹ️  Arquivos mantidos para análise")
        except (KeyboardInterrupt, EOFError):
            print("\n   ℹ️  Arquivos mantidos")

    except Exception as e:
        print(f"\n❌ Erro durante benchmark: {e}")
        import traceback
        traceback.print_exc()

        # Limpar em caso de erro
        shutil.rmtree(temp_dir_with, ignore_errors=True)
        shutil.rmtree(temp_dir_without, ignore_errors=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
