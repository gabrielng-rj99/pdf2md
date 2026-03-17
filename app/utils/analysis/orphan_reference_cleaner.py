"""
Módulo de limpeza de referências órfãs em texto Markdown.

Este módulo detecta e remove referências a figuras, imagens e outros elementos
que não possuem correspondência real no documento (ex: "*Figura 1*" quando
a figura foi removida ou nunca existiu).

Características:
- Detecção de padrões de referência a figuras
- Verificação de existência de imagens correspondentes
- Remoção segura de referências órfãs
- Preservação do contexto do texto

Funciona como pós-processamento do Markdown gerado.
"""

import re
import os
from dataclasses import dataclass, field
from typing import List, Set, Tuple, Optional, Dict
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class OrphanCleanerConfig:
    """Configuração do limpador de referências órfãs."""
    # Padrões de referência a figuras (regex)
    figure_patterns: List[str] = field(default_factory=lambda: [
        r'\*Figura\s+\d+\*',           # *Figura 1*
        r'\*\*Figura\s+\d+\*\*',       # **Figura 1**
        r'Figura\s+\d+[:\.]?',         # Figura 1: ou Figura 1.
        r'Fig\.\s*\d+[:\.]?',          # Fig. 1: ou Fig. 1.
        r'\(Figura\s+\d+\)',           # (Figura 1)
        r'\[Figura\s+\d+\]',           # [Figura 1]
    ])

    # Padrões de referência a tabelas
    table_patterns: List[str] = field(default_factory=lambda: [
        r'\*Tabela\s+\d+\*',           # *Tabela 1*
        r'\*\*Tabela\s+\d+\*\*',       # **Tabela 1**
        r'Tabela\s+\d+[:\.]?',         # Tabela 1:
        r'Tab\.\s*\d+[:\.]?',          # Tab. 1:
    ])

    # Padrões de referência a quadros
    frame_patterns: List[str] = field(default_factory=lambda: [
        r'\*Quadro\s+\d+\*',           # *Quadro 1*
        r'Quadro\s+\d+[:\.]?',         # Quadro 1:
    ])

    # Padrões de referência a gráficos
    chart_patterns: List[str] = field(default_factory=lambda: [
        r'\*Gráfico\s+\d+\*',          # *Gráfico 1*
        r'Gráfico\s+\d+[:\.]?',        # Gráfico 1:
        r'Graf\.\s*\d+[:\.]?',         # Graf. 1:
    ])

    # Comportamento
    remove_empty_lines_after: bool = True
    remove_surrounding_empty_lines: bool = True
    case_insensitive: bool = True

    # Tipos de referência a limpar
    clean_figures: bool = True
    clean_tables: bool = True
    clean_frames: bool = True
    clean_charts: bool = True


@dataclass
class OrphanReference:
    """Representa uma referência órfã detectada."""
    text: str
    line_number: int
    pattern_matched: str
    reference_type: str  # 'figure', 'table', 'frame', 'chart'
    context: str = ""    # Linhas ao redor para contexto


@dataclass
class CleaningResult:
    """Resultado da limpeza de referências órfãs."""
    original_content: str
    cleaned_content: str
    orphans_found: List[OrphanReference]
    lines_removed: int
    references_removed: int


class OrphanReferenceCleaner:
    """
    Limpa referências órfãs em documentos Markdown.

    Detecta e remove referências a figuras, tabelas e outros elementos
    que não possuem correspondência no documento.
    """

    def __init__(self, config: Optional[OrphanCleanerConfig] = None):
        """
        Inicializa o limpador.

        Args:
            config: Configuração opcional
        """
        self.config = config or OrphanCleanerConfig()
        self._compile_patterns()
        self._stats = {
            'documents_processed': 0,
            'references_removed': 0,
            'lines_removed': 0,
        }

    def _compile_patterns(self):
        """Compila os padrões regex."""
        flags = re.IGNORECASE if self.config.case_insensitive else 0

        self._patterns: Dict[str, List[re.Pattern]] = {
            'figure': [],
            'table': [],
            'frame': [],
            'chart': [],
        }

        if self.config.clean_figures:
            self._patterns['figure'] = [
                re.compile(p, flags) for p in self.config.figure_patterns
            ]

        if self.config.clean_tables:
            self._patterns['table'] = [
                re.compile(p, flags) for p in self.config.table_patterns
            ]

        if self.config.clean_frames:
            self._patterns['frame'] = [
                re.compile(p, flags) for p in self.config.frame_patterns
            ]

        if self.config.clean_charts:
            self._patterns['chart'] = [
                re.compile(p, flags) for p in self.config.chart_patterns
            ]

    def find_orphan_references(
        self,
        content: str,
        existing_images: Optional[Set[str]] = None
    ) -> List[OrphanReference]:
        """
        Encontra referências órfãs no conteúdo.

        Args:
            content: Conteúdo Markdown
            existing_images: Set opcional de nomes de imagens existentes

        Returns:
            Lista de referências órfãs encontradas
        """
        orphans = []
        lines = content.split('\n')

        # Encontrar todas as referências de imagem no markdown
        image_refs = self._extract_image_references(content)

        for line_num, line in enumerate(lines, start=1):
            for ref_type, patterns in self._patterns.items():
                for pattern in patterns:
                    matches = pattern.finditer(line)
                    for match in matches:
                        ref_text = match.group()

                        # Verificar se é uma referência órfã
                        is_orphan = self._is_orphan_reference(
                            ref_text, ref_type, line, image_refs, existing_images
                        )

                        if is_orphan:
                            # Capturar contexto (linhas ao redor)
                            context = self._get_context(lines, line_num - 1, 2)

                            orphan = OrphanReference(
                                text=ref_text,
                                line_number=line_num,
                                pattern_matched=pattern.pattern,
                                reference_type=ref_type,
                                context=context,
                            )
                            orphans.append(orphan)

        return orphans

    def _extract_image_references(self, content: str) -> Set[str]:
        """Extrai todas as referências de imagem do markdown."""
        # Padrão markdown para imagens: ![alt](path)
        pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
        refs = set()

        for match in pattern.finditer(content):
            alt_text = match.group(1)
            path = match.group(2)
            refs.add(path)
            if alt_text:
                refs.add(alt_text)

        return refs

    def _is_orphan_reference(
        self,
        ref_text: str,
        ref_type: str,
        line: str,
        image_refs: Set[str],
        existing_images: Optional[Set[str]]
    ) -> bool:
        """
        Determina se uma referência é órfã.

        Uma referência é considerada órfã se:
        1. A linha contém APENAS a referência (ou é quase vazia)
        2. Não há imagem correspondente no documento
        """
        # Verificar se a linha é quase vazia (apenas a referência)
        line_stripped = line.strip()
        ref_stripped = ref_text.strip()

        # Se a linha é só a referência
        if line_stripped == ref_stripped:
            return True

        # Se a linha tem muito pouco conteúdo além da referência
        remaining = line_stripped.replace(ref_stripped, '').strip()
        if len(remaining) < 5:  # Apenas pontuação ou espaços
            return True

        # Se temos lista de imagens existentes, verificar
        if existing_images is not None:
            # Extrair número da referência
            num_match = re.search(r'\d+', ref_text)
            if num_match:
                ref_num = num_match.group()
                # Verificar se existe imagem com esse número
                for img in existing_images:
                    if ref_num in img:
                        return False
                return True

        return False

    def _get_context(self, lines: List[str], line_idx: int, context_size: int) -> str:
        """Obtém linhas de contexto ao redor de uma linha."""
        start = max(0, line_idx - context_size)
        end = min(len(lines), line_idx + context_size + 1)
        context_lines = lines[start:end]
        return '\n'.join(f'{i+start+1}: {l}' for i, l in enumerate(context_lines))

    def clean(
        self,
        content: str,
        existing_images: Optional[Set[str]] = None,
        images_dir: Optional[str] = None
    ) -> CleaningResult:
        """
        Limpa referências órfãs do conteúdo.

        Args:
            content: Conteúdo Markdown
            existing_images: Set opcional de nomes de imagens existentes
            images_dir: Diretório de imagens para verificação automática

        Returns:
            CleaningResult com conteúdo limpo e informações
        """
        self._stats['documents_processed'] += 1

        # Se fornecido diretório, listar imagens existentes
        if images_dir and existing_images is None:
            existing_images = self._list_images_in_dir(images_dir)

        # Encontrar referências órfãs
        orphans = self.find_orphan_references(content, existing_images)

        if not orphans:
            return CleaningResult(
                original_content=content,
                cleaned_content=content,
                orphans_found=[],
                lines_removed=0,
                references_removed=0,
            )

        # Remover referências órfãs
        cleaned_content = self._remove_orphans(content, orphans)

        # Limpar linhas vazias extras se configurado
        if self.config.remove_surrounding_empty_lines:
            cleaned_content = self._clean_empty_lines(cleaned_content)

        # Atualizar estatísticas
        lines_removed = content.count('\n') - cleaned_content.count('\n')
        self._stats['references_removed'] += len(orphans)
        self._stats['lines_removed'] += lines_removed

        return CleaningResult(
            original_content=content,
            cleaned_content=cleaned_content,
            orphans_found=orphans,
            lines_removed=lines_removed,
            references_removed=len(orphans),
        )

    def _list_images_in_dir(self, images_dir: str) -> Set[str]:
        """Lista todas as imagens em um diretório."""
        images = set()
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'}

        try:
            dir_path = Path(images_dir)
            if dir_path.exists():
                for item in dir_path.iterdir():
                    if item.is_file() and item.suffix.lower() in image_extensions:
                        images.add(item.name)
                        images.add(str(item))
        except Exception as e:
            logger.warning(f"Erro ao listar imagens em {images_dir}: {e}")

        return images

    def _remove_orphans(self, content: str, orphans: List[OrphanReference]) -> str:
        """Remove referências órfãs do conteúdo."""
        lines = content.split('\n')

        # Marcar linhas para remoção
        lines_to_remove = set()
        for orphan in orphans:
            line_idx = orphan.line_number - 1
            if 0 <= line_idx < len(lines):
                line = lines[line_idx]

                # Se a linha é só a referência, remover toda a linha
                if line.strip() == orphan.text.strip():
                    lines_to_remove.add(line_idx)
                else:
                    # Remover apenas a referência da linha
                    lines[line_idx] = line.replace(orphan.text, '').strip()

        # Reconstruir conteúdo sem as linhas marcadas
        result_lines = [
            line for i, line in enumerate(lines)
            if i not in lines_to_remove
        ]

        return '\n'.join(result_lines)

    def _clean_empty_lines(self, content: str) -> str:
        """Remove linhas vazias excessivas."""
        # Substituir 3+ linhas vazias por 2
        content = re.sub(r'\n{3,}', '\n\n', content)

        # Remover linhas vazias no início/fim
        content = content.strip()

        return content

    def clean_file(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        images_dir: Optional[str] = None
    ) -> CleaningResult:
        """
        Limpa referências órfãs de um arquivo Markdown.

        Args:
            input_path: Caminho do arquivo de entrada
            output_path: Caminho do arquivo de saída (se None, sobrescreve)
            images_dir: Diretório de imagens para verificação

        Returns:
            CleaningResult
        """
        # Ler arquivo
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Se não fornecido diretório de imagens, tentar detectar
        if images_dir is None:
            input_dir = os.path.dirname(input_path)
            possible_images_dir = os.path.join(input_dir, 'images')
            if os.path.isdir(possible_images_dir):
                images_dir = possible_images_dir

        # Limpar
        result = self.clean(content, images_dir=images_dir)

        # Salvar
        out_path = output_path or input_path
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(result.cleaned_content)

        logger.info(f"Limpeza concluída: {result.references_removed} referências removidas")

        return result

    def get_stats(self) -> dict:
        """Retorna estatísticas de processamento."""
        return self._stats.copy()

    def reset_stats(self):
        """Reseta estatísticas."""
        self._stats = {
            'documents_processed': 0,
            'references_removed': 0,
            'lines_removed': 0,
        }


def get_orphan_cleaner(config: Optional[OrphanCleanerConfig] = None) -> OrphanReferenceCleaner:
    """Factory function para obter instância do limpador."""
    return OrphanReferenceCleaner(config)


def clean_orphan_references(
    content: str,
    existing_images: Optional[Set[str]] = None
) -> str:
    """
    Função utilitária para limpeza rápida.

    Args:
        content: Conteúdo Markdown
        existing_images: Set opcional de nomes de imagens

    Returns:
        Conteúdo limpo
    """
    cleaner = OrphanReferenceCleaner()
    result = cleaner.clean(content, existing_images)
    return result.cleaned_content


def find_figure_references(content: str) -> List[Tuple[str, int]]:
    """
    Encontra todas as referências a figuras no conteúdo.

    Args:
        content: Conteúdo a analisar

    Returns:
        Lista de tuplas (referência, número_linha)
    """
    references = []
    lines = content.split('\n')

    patterns = [
        re.compile(r'\*Figura\s+\d+\*', re.IGNORECASE),
        re.compile(r'\*\*Figura\s+\d+\*\*', re.IGNORECASE),
        re.compile(r'Figura\s+\d+[:\.]?', re.IGNORECASE),
        re.compile(r'Fig\.\s*\d+[:\.]?', re.IGNORECASE),
    ]

    for line_num, line in enumerate(lines, start=1):
        for pattern in patterns:
            for match in pattern.finditer(line):
                references.append((match.group(), line_num))

    return references


def has_orphan_figures(content: str, image_count: int = 0) -> bool:
    """
    Verifica rapidamente se o conteúdo tem figuras órfãs.

    Args:
        content: Conteúdo Markdown
        image_count: Número de imagens existentes

    Returns:
        True se há potenciais figuras órfãs
    """
    figure_refs = find_figure_references(content)

    if not figure_refs:
        return False

    # Se não há imagens mas há referências a figuras
    if image_count == 0 and len(figure_refs) > 0:
        return True

    # Se há mais referências do que imagens
    if len(figure_refs) > image_count * 2:  # Margem de segurança
        return True

    return False
