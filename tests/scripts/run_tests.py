#!/usr/bin/env python3
"""
Script para executar todos os testes do projeto PDF-to-Markdown-with-Images

Este script orquestra a execução de testes unitários, de integração e e2e,
com relatórios detalhados e cobertura de código.

Uso:
    python3 run_tests.py                    # Executa todos os testes
    python3 run_tests.py --unit             # Apenas testes unitários
    python3 run_tests.py --integration      # Apenas testes de integração
    python3 run_tests.py --e2e              # Apenas testes e2e
    python3 run_tests.py --coverage         # Com relatório de cobertura
    python3 run_tests.py --verbose          # Saída verbosa
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path


class TestRunner:
    """Orquestrador de execução de testes"""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.tests_dir = self.project_root / "tests"
        self.results = {}

    def print_header(self, text):
        """Imprime um cabeçalho formatado"""
        print("\n" + "=" * 80)
        print(f"  {text}")
        print("=" * 80 + "\n")

    def print_section(self, text):
        """Imprime um cabeçalho de seção"""
        print(f"\n{text}")
        print("-" * 80)

    def run_command(self, cmd, description):
        """Executa um comando e retorna o resultado"""
        print(f"\n▶ {description}")
        print(f"  Comando: {' '.join(cmd)}\n")

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                capture_output=False,
                text=True,
            )
            return result.returncode == 0
        except Exception as e:
            print(f"✗ Erro ao executar: {e}")
            return False

    def run_unit_tests(self, verbose=False):
        """Executa testes unitários"""
        self.print_section("🧪 TESTES UNITÁRIOS")

        cmd = [
            "python", "-m", "pytest",
            "tests/unit",
            "-v" if verbose else "",
            "--tb=short",
        ]
        cmd = [c for c in cmd if c]  # Remove strings vazias

        success = self.run_command(cmd, "Executando testes unitários...")
        self.results["unit"] = success

        return success

    def run_integration_tests(self, verbose=False):
        """Executa testes de integração"""
        self.print_section("🔗 TESTES DE INTEGRAÇÃO")

        cmd = [
            "python", "-m", "pytest",
            "tests/integration",
            "-v" if verbose else "",
            "--tb=short",
        ]
        cmd = [c for c in cmd if c]

        success = self.run_command(cmd, "Executando testes de integração...")
        self.results["integration"] = success

        return success

    def run_e2e_tests(self, verbose=False):
        """Executa testes end-to-end"""
        self.print_section("🎯 TESTES END-TO-END")

        cmd = [
            "python", "-m", "pytest",
            "tests/e2e",
            "-v" if verbose else "",
            "--tb=short",
        ]
        cmd = [c for c in cmd if c]

        success = self.run_command(cmd, "Executando testes e2e...")
        self.results["e2e"] = success

        return success

    def run_all_tests(self, verbose=False):
        """Executa todos os testes"""
        self.print_section("📋 TODOS OS TESTES")

        cmd = [
            "python", "-m", "pytest",
            "tests",
            "-v" if verbose else "",
            "--tb=short",
            "-ra",
        ]
        cmd = [c for c in cmd if c]

        success = self.run_command(cmd, "Executando todos os testes...")
        self.results["all"] = success

        return success

    def run_with_coverage(self, verbose=False):
        """Executa testes com relatório de cobertura"""
        self.print_section("📊 TESTES COM COBERTURA")

        cmd = [
            "python", "-m", "pytest",
            "tests",
            "-v" if verbose else "",
            "--cov=app",
            "--cov-report=term-missing",
            "--cov-report=html",
            "--tb=short",
        ]
        cmd = [c for c in cmd if c]

        success = self.run_command(cmd, "Executando testes com cobertura...")
        self.results["coverage"] = success

        if success:
            print("\n✅ Relatório de cobertura gerado em: htmlcov/index.html")

        return success

    def validate_environment(self):
        """Valida o ambiente para execução de testes"""
        self.print_section("✓ VALIDAÇÃO DO AMBIENTE")

        checks = {
            "pytest": self._check_pytest(),
            "fastapi": self._check_fastapi(),
            "fitz": self._check_fitz(),
        }

        all_ok = all(checks.values())

        for package, status in checks.items():
            symbol = "✓" if status else "✗"
            print(f"  {symbol} {package}")

        if not all_ok:
            print("\n⚠ Alguns pacotes estão faltando. Instale com:")
            print("  pip install pytest fastapi python-multipart pymupdf")
            return False

        return True

    @staticmethod
    def _check_pytest():
        """Verifica se pytest está instalado"""
        try:
            import pytest
            return True
        except ImportError:
            return False

    @staticmethod
    def _check_fastapi():
        """Verifica se fastapi está instalado"""
        try:
            import fastapi
            return True
        except ImportError:
            return False

    @staticmethod
    def _check_fitz():
        """Verifica se fitz (pymupdf) está instalado"""
        try:
            import fitz
            return True
        except ImportError:
            return False

    def print_summary(self):
        """Imprime resumo dos testes"""
        self.print_header("📊 RESUMO DOS TESTES")

        if not self.results:
            print("Nenhum teste foi executado.")
            return

        total = len(self.results)
        passed = sum(1 for v in self.results.values() if v)
        failed = total - passed

        print(f"Total de suites: {total}")
        print(f"Passou: {passed} ✓")
        print(f"Falhou: {failed} ✗\n")

        for suite, status in self.results.items():
            symbol = "✓" if status else "✗"
            color_code = "\033[92m" if status else "\033[91m"
            reset_code = "\033[0m"
            print(f"  {color_code}{symbol}{reset_code} {suite}")

        print("\n" + "=" * 80)
        if failed == 0:
            print("  🎉 TODOS OS TESTES PASSARAM! 🎉")
        else:
            print(f"  ⚠ {failed} suite(s) falharam")
        print("=" * 80 + "\n")

        return failed == 0

    def run(self, unit=False, integration=False, e2e=False, coverage=False, verbose=False):
        """Executa testes conforme especificado"""
        self.print_header("🚀 PDF-TO-MARKDOWN-WITH-IMAGES - TEST SUITE")

        if not self.validate_environment():
            sys.exit(1)

        # Se nenhuma suite específica foi escolhida, executa todas
        if not any([unit, integration, e2e, coverage]):
            coverage = True  # Default: com cobertura

        try:
            if coverage:
                self.run_with_coverage(verbose)
            else:
                if unit:
                    self.run_unit_tests(verbose)
                if integration:
                    self.run_integration_tests(verbose)
                if e2e:
                    self.run_e2e_tests(verbose)
                if not any([unit, integration, e2e]):
                    self.run_all_tests(verbose)

        except KeyboardInterrupt:
            print("\n\n⚠ Execução interrompida pelo usuário")
            sys.exit(1)
        except Exception as e:
            print(f"\n✗ Erro durante execução: {e}")
            sys.exit(1)

        self.print_summary()

        # Retorna código de saída apropriado
        return 0 if all(self.results.values()) else 1


def main():
    """Função principal"""
    parser = argparse.ArgumentParser(
        description="Executar testes para PDF-to-Markdown-with-Images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python3 run_tests.py                    # Executa todos com cobertura
  python3 run_tests.py --unit             # Apenas testes unitários
  python3 run_tests.py --all --verbose    # Todos com saída verbosa
  python3 run_tests.py --coverage --unit  # Unit + cobertura
        """,
    )

    parser.add_argument(
        "--unit",
        action="store_true",
        help="Executar testes unitários",
    )
    parser.add_argument(
        "--integration",
        action="store_true",
        help="Executar testes de integração",
    )
    parser.add_argument(
        "--e2e",
        action="store_true",
        help="Executar testes end-to-end",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Executar todos os testes",
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Incluir relatório de cobertura",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Saída verbosa",
    )

    args = parser.parse_args()

    runner = TestRunner()

    if args.all:
        args.unit = True
        args.integration = True
        args.e2e = True

    exit_code = runner.run(
        unit=args.unit,
        integration=args.integration,
        e2e=args.e2e,
        coverage=args.coverage,
        verbose=args.verbose,
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
