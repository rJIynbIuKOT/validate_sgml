#!/usr/bin/env python3
"""
graph_sect.py - Визуализация структуры секций в SGML/XML файлах

Извлекает и отображает иерархию тегов sect из документа с правильными отступами.
"""

import re
import sys
from pathlib import Path


def extract_sect_structure(filepath: str) -> list:
    """
    Извлекает структуру секций из файла
    
    Args:
        filepath: Путь к SGML/XML файлу
        
    Returns:
        Список кортежей (level, tag_line) где level - уровень вложенности (1-5)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Ошибка чтения файла {filepath}: {e}", file=sys.stderr)
        return []
    
    # Паттерн для поиска sect тегов (открывающих и закрывающих)
    # Ищем: <sect1...>, </sect1>, <sect2...>, </sect2> и т.д.
    sect_pattern = re.compile(
        r'^.*?(</?sect[1-5][^>]*>).*$',
        re.MULTILINE
    )
    
    result = []
    
    for match in sect_pattern.finditer(content):
        line = match.group(0)  # Полная строка
        tag = match.group(1)    # Сам тег
        
        # Определяем уровень секции (1-5)
        level_match = re.search(r'sect([1-5])', tag)
        if level_match:
            level = int(level_match.group(1))
            
            # Убираем все начальные пробелы и табы
            clean_line = line.lstrip()
            
            result.append((level, clean_line))
    
    return result


def print_sect_structure(sect_list: list, show_line_numbers: bool = False):
    """
    Печатает структуру секций с отступами
    
    Args:
        sect_list: Список кортежей (level, line)
        show_line_numbers: Показывать ли номера строк
    """
    if not sect_list:
        print("⚠️  Секции не найдены в файле")
        return
    
    for idx, (level, line) in enumerate(sect_list, 1):
        # Отступ = (level - 1) пробелов
        # sect1 = 0, sect2 = 1, sect3 = 2, sect4 = 3, sect5 = 4
        indent = ' ' * (level - 1)
        
        if show_line_numbers:
            print(f"{idx:3d}: {indent}{line}")
        else:
            print(f"{indent}{line}")


def print_compact_structure(sect_list: list):
    """
    Печатает компактную структуру (только теги без содержимого)
    
    Args:
        sect_list: Список кортежей (level, line)
    """
    if not sect_list:
        print("⚠️  Секции не найдены в файле")
        return
    
    for level, line in sect_list:
        # Извлекаем только тег (без атрибутов для открывающих)
        tag_match = re.search(r'(</?sect[1-5])(?:[^>]*)?(>)', line)
        if tag_match:
            # Для закрывающих тегов: </sect1>
            # Для открывающих: <sect1> (без атрибутов)
            if line.strip().startswith('</'):
                tag = tag_match.group(1) + tag_match.group(2)
            else:
                # Для открывающих тегов показываем с атрибутами
                full_tag_match = re.search(r'<sect[1-5][^>]*>', line)
                tag = full_tag_match.group(0) if full_tag_match else line.strip()
            
            indent = ' ' * (level - 1)
            print(f"{indent}{tag}")


def print_tree_structure(sect_list: list):
    """
    Печатает древовидную структуру с символами дерева
    
    Args:
        sect_list: Список кортежей (level, line)
    """
    if not sect_list:
        print("⚠️  Секции не найдены в файле")
        return
    
    for level, line in sect_list:
        # Определяем символ для дерева (level - 1 для отступа)
        if level == 1:
            prefix = "├─"
        elif level == 2:
            prefix = " ├─"
        elif level == 3:
            prefix = "  ├─"
        elif level == 4:
            prefix = "   ├─"
        else:  # level 5
            prefix = "    ├─"
        
        # Извлекаем title если есть
        title_match = re.search(r'<title>(.*?)</title>', line)
        if title_match:
            title = title_match.group(1)
            tag_type = "opening" if not line.strip().startswith('</') else "closing"
            
            if tag_type == "opening":
                print(f"{prefix} sect{level}: {title}")
        else:
            # Показываем просто тег
            tag_match = re.search(r'</?sect[1-5]', line)
            if tag_match:
                tag = tag_match.group(0)
                if line.strip().startswith('</'):
                    print(f"{prefix} {tag}>")
                else:
                    print(f"{prefix} {tag}...>")


def save_to_file(sect_list: list, output_path: str):
    """
    Сохраняет структуру секций в файл
    
    Args:
        sect_list: Список кортежей (level, line)
        output_path: Путь к выходному файлу
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for level, line in sect_list:
                # Отступ = (level - 1) пробелов
                indent = ' ' * (level - 1)
                f.write(f"{indent}{line}\n")
        return True
    except Exception as e:
        print(f"❌ Ошибка записи в файл {output_path}: {e}", file=sys.stderr)
        return False


def _print_usage():
    """Краткая справка по использованию из командной строки."""
    print("Использование:")
    print(f"  {sys.argv[0]} <файл.sgml> [опции]")
    print()
    print("Опции:")
    print("  -n, --numbers   Показывать номера строк")
    print("  -c, --compact   Компактный вывод (только теги)")
    print("  -t, --tree      Древовидная структура")
    print()
    print("Результат автоматически сохраняется в sect.sgml")
    print()
    print("Примеры:")
    print(f"  {sys.argv[0]} document.sgml")
    print(f"  {sys.argv[0]} document.sgml -n")
    print(f"  {sys.argv[0]} document.sgml --compact")
    print(f"  {sys.argv[0]} document.sgml --tree")


def _prompt_interactively() -> tuple[str, str]:
    """Запрашивает путь и режим вывода у пользователя (интерактивный режим)."""
    print("=" * 64)
    print("  Graph Sect - визуализация структуры sect-тегов")
    print("=" * 64)
    print()
    try:
        target = input("Введите путь к файлу .sgml: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return "", ""

    if not target:
        return "", ""

    print()
    print("Режимы вывода:")
    print("  [Enter] - обычный с отступами")
    print("  -n      - с номерами строк")
    print("  -c      - компактный (только теги)")
    print("  -t      - древовидная структура")
    try:
        mode = input("Выберите режим: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        mode = ""

    return target, mode


def _pause():
    """Ждёт нажатия Enter, чтобы окно терминала не закрылось автоматически."""
    print()
    try:
        input("Нажмите Enter для выхода...")
    except (EOFError, KeyboardInterrupt):
        pass


def _run(filepath: str, show_numbers: bool, compact_mode: bool, tree_mode: bool) -> int:
    """Выполняет основную логику скрипта. Возвращает код возврата."""
    file_path = Path(filepath)
    if not file_path.exists():
        print(f"❌ Файл не найден: {filepath}", file=sys.stderr)
        return 1

    if not file_path.is_file():
        print(f"❌ Путь не является файлом: {filepath}", file=sys.stderr)
        return 1

    print(f"📄 Файл: {file_path.name}")
    print("─" * 80)

    sect_list = extract_sect_structure(filepath)

    if not sect_list:
        return 0

    if tree_mode:
        print_tree_structure(sect_list)
    elif compact_mode:
        print_compact_structure(sect_list)
    else:
        print_sect_structure(sect_list, show_numbers)

    print()
    print(f"📊 Всего секций: {len(sect_list)}")

    level_counts: dict = {}
    for level, _ in sect_list:
        level_counts[level] = level_counts.get(level, 0) + 1

    print("\nСтатистика по уровням:")
    for level in sorted(level_counts.keys()):
        count = level_counts[level]
        print(f"  sect{level}: {count} строк")

    script_dir = Path(__file__).parent
    output_file = script_dir / "sect.sgml"

    print()
    if save_to_file(sect_list, str(output_file)):
        print(f"💾 Результат сохранён в: {output_file}")
    else:
        print("⚠️  Не удалось сохранить результат в файл", file=sys.stderr)

    return 0


def main():
    """Главная функция"""
    # Интерактивный режим включается, если скрипт запущен без аргументов
    # И stdin подключён к терминалу (TTY) — например, через "Запустить как приложение".
    # В CI/неинтерактивных средах stdin не TTY → показываем справку и выходим.
    interactive = len(sys.argv) < 2 and sys.stdin.isatty()

    if len(sys.argv) < 2 and not interactive:
        _print_usage()
        sys.exit(1)

    if interactive:
        filepath, mode = _prompt_interactively()
        if not filepath:
            print("\n❌ Путь не указан.")
            _pause()
            sys.exit(1)
        show_numbers = mode in ('-n', '--numbers')
        compact_mode = mode in ('-c', '--compact')
        tree_mode = mode in ('-t', '--tree')
        print()
    else:
        filepath = sys.argv[1]
        show_numbers = '-n' in sys.argv or '--numbers' in sys.argv
        compact_mode = '-c' in sys.argv or '--compact' in sys.argv
        tree_mode = '-t' in sys.argv or '--tree' in sys.argv

    exit_code = _run(filepath, show_numbers, compact_mode, tree_mode)

    if interactive:
        _pause()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
