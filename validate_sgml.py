#!/usr/bin/env python3
"""
SGML/XML validator - проверяет открытие и закрытие тегов
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class ValidationError:
    """Ошибка валидации"""
    line: int
    message: str
    tag: str = ""


class SGMLValidator:
    """Валидатор SGML/XML файлов"""
    
    # Самозакрывающиеся теги (не требуют закрывающего тега)
    SELF_CLOSING_TAGS = {
        # HTML пустые элементы (но не 'link' - в DocBook это контейнерный тег!)
        'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
        'meta', 'param', 'source', 'track', 'wbr',
        # DocBook пустые элементы
        'colspec', 'spanspec', 'imagedata', 'xref', 'anchor',
        'footnoteref', 'primaryie', 'secondaryie',
        'tertiaryie', 'areaspec', 'co'
        # Примечание: 'indexterm' это контейнерный тег (содержит primary/secondary), не пустой!
    }
    
    # Теги, которые не должны содержать текст вне <para> (только блочные потомки)
    BLOCK_CONTAINERS = {
        'sect1', 'sect2', 'sect3', 'sect4', 'sect5',
        'section', 'simplesect',
        'chapter', 'appendix', 'preface',
        'refsect1', 'refsect2', 'refsect3',
        'listitem', 'varlistentry',
    }

    # Теги, которые должны содержать ровно один <title>
    TAGS_WITH_TITLE = {
        # Обычные секции
        'sect1', 'sect2', 'sect3', 'sect4', 'sect5',
        'section', 'simplesect',
        # Reference секции (для документации API)
        'refsect1', 'refsect2', 'refsect3',
        # Структурные элементы
        'chapter', 'appendix', 'preface',
        # Элементы с заголовками
        'figure', 'table', 'example',
        # Параграфы с заголовками
        'formalpara',
        # Адмонишны (примечания с заголовками)
        'note', 'warning', 'caution', 'tip', 'important'
    }
    
    # Известные DocBook и HTML теги (для обнаружения опечаток)
    KNOWN_TAGS = {
        # Структура документа
        'appendix', 'chapter', 'preface', 'section', 'sect1', 'sect2', 'sect3', 
        'sect4', 'sect5', 'simplesect', 'refentry', 'refmeta', 'refnamediv', 
        'refsect1', 'refsect2', 'refsect3', 'refentrytitle', 'refname', 
        'refpurpose', 'refmiscinfo', 'manvolnum',
        # Блочные элементы
        'para', 'formalpara', 'blockquote', 'note', 'warning', 'caution', 
        'important', 'tip', 'literallayout', 'screen', 'programlisting',
        # Списки
        'itemizedlist', 'orderedlist', 'listitem', 'variablelist', 
        'varlistentry', 'term',
        # Таблицы
        'table', 'informaltable', 'tgroup', 'thead', 'tbody', 'row', 'entry',
        'colspec', 'spanspec',
        # Встроенные элементы
        'emphasis', 'literal', 'quote', 'subscript', 'superscript', 'command',
        'filename', 'function', 'parameter', 'varname', 'type', 'symbol',
        'option', 'application', 'productname', 'productnumber', 'acronym',
        # Ссылки
        'link', 'ulink', 'xref', 'anchor',
        # Медиа
        'figure', 'mediaobject', 'imageobject', 'imagedata', 'textobject',
        'inlinemediaobject', 'phrase',
        # Индексирование
        'indexterm', 'primary', 'secondary', 'tertiary',
        # Метаданные
        'title', 'bookinfo', 'corpauthor', 'email',
        # HTML теги
        'div', 'span', 'p', 'a', 'img', 'br', 'hr',
        'ul', 'ol', 'li', 'dl', 'dt', 'dd',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'pre', 'code', 'strong', 'em', 'b', 'i'
    }
    
    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.errors: List[ValidationError] = []
        self.tag_stack: List[Tuple[str, int]] = []  # (tag_name, line_number)
        self.title_counts: dict = {}  # {parent_tag_info: count} - счетчик title для каждого родителя
        self.last_tag: Tuple[str, int] = ('', 0)  # (last_tag_name, line_number) для проверки подряд идущих тегов
        self.unknown_tags_seen: set = set()  # Для отслеживания уже показанных неизвестных тегов
    
    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        """Вычисляет расстояние Левенштейна между двумя строками"""
        if len(s1) < len(s2):
            return SGMLValidator._levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def _find_similar_tags(self, tag_name: str, max_distance: int = 2) -> List[str]:
        """Находит похожие известные теги (для подсказок при опечатках)"""
        similar = []
        for known_tag in self.KNOWN_TAGS:
            distance = self._levenshtein_distance(tag_name.lower(), known_tag.lower())
            if distance <= max_distance and distance > 0:
                similar.append((known_tag, distance))
        
        # Сортируем по расстоянию и возвращаем только имена тегов
        similar.sort(key=lambda x: x[1])
        return [tag for tag, _ in similar[:3]]  # Топ-3 похожих тега
        
    def validate(self) -> bool:
        """Валидирует файл, возвращает True если нет ошибок"""
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"❌ Ошибка чтения файла {self.filepath}: {e}")
            return False
        
        self._parse_tags(content)
        
        # Проверка незакрытых тегов
        if self.tag_stack:
            for tag_name, line_num in reversed(self.tag_stack):
                self.errors.append(ValidationError(
                    line=line_num,
                    message=f"Тег не закрыт",
                    tag=tag_name
                ))
        
        return len(self.errors) == 0
    
    def _parse_tags(self, content: str):
        """Парсит теги в контенте"""
        # Паттерн для комментариев и специальных конструкций
        comment_pattern = re.compile(r'<!--.*?-->', re.DOTALL)
        xml_decl_pattern = re.compile(r'<\?.*?\?>', re.DOTALL)
        doctype_pattern = re.compile(r'<!DOCTYPE[^>]*>', re.DOTALL)
        entity_pattern = re.compile(r'<!ENTITY[^>]*>', re.DOTALL)
        
        # Заменяем комментарии и спец. конструкции на пробелы той же длины
        # чтобы сохранить позиции в тексте
        def replace_with_spaces(match):
            return ' ' * len(match.group(0))
        
        clean_content = content
        clean_content = comment_pattern.sub(replace_with_spaces, clean_content)
        clean_content = xml_decl_pattern.sub(replace_with_spaces, clean_content)
        clean_content = doctype_pattern.sub(replace_with_spaces, clean_content)
        clean_content = entity_pattern.sub(replace_with_spaces, clean_content)
        
        # Паттерн для обычных тегов (многострочный режим)
        tag_pattern = re.compile(
            r'<(/?)([a-zA-Z][a-zA-Z0-9]*)'  # < и опциональный /, название тега
            r'(?:\s[^>]*?)?'  # опциональные атрибуты (могут быть на нескольких строках)
            r'(/?)>',  # опциональный / и >
            re.DOTALL
        )
        
        # Находим все теги с их позициями; между ними проверяем текстовые узлы
        prev_end = 0
        for match in tag_pattern.finditer(clean_content):
            # Текст между концом предыдущего тега и началом текущего
            text_start = prev_end
            text_end = match.start()
            if text_start < text_end:
                text_segment = clean_content[text_start:text_end]
                if text_segment.strip():
                    text_line = clean_content[:text_start].count('\n') + 1
                    self._check_bare_text(text_segment, text_line)
            prev_end = match.end()

            closing_slash = match.group(1)  # / в начале для закрывающего тега
            tag_name = match.group(2)
            self_closing = match.group(3)  # / в конце для самозакрывающегося
            full_tag = match.group(0)
            
            if not tag_name:
                continue
            
            # Определяем номер строки по позиции в тексте (теперь clean_content имеет те же позиции)
            line_num = clean_content[:match.start()].count('\n') + 1
            
            # Проверка на неизвестный тег
            if tag_name not in self.KNOWN_TAGS and tag_name not in self.unknown_tags_seen:
                self.unknown_tags_seen.add(tag_name)
                similar = self._find_similar_tags(tag_name)
                if similar:
                    suggestion = f". Возможно, вы имели в виду: {', '.join(similar)}"
                else:
                    suggestion = ""
                self.errors.append(ValidationError(
                    line=line_num,
                    message=f"Неизвестный тег '{tag_name}'{suggestion}",
                    tag=tag_name
                ))
            
            # Закрывающий тег
            if closing_slash:
                self._close_tag(tag_name, line_num)
            # Самозакрывающийся тег или известный пустой тег
            elif self_closing or tag_name.lower() in self.SELF_CLOSING_TAGS:
                self._validate_tag_attributes(full_tag, tag_name, line_num)
                pass  # Ничего не делаем
            # Открывающий тег
            else:
                self._validate_tag_attributes(full_tag, tag_name, line_num)
                # Проверка специальных правил для <title>
                if tag_name == 'title':
                    self._validate_title(line_num)
                
                # Проверка: не открывается ли тег того же уровня без закрытия предыдущего
                # Для sect1-sect5 проверяем, что не открывается sect того же уровня
                if tag_name.startswith('sect') and len(tag_name) == 5 and tag_name[-1].isdigit():
                    # Ищем последний открытый тег того же типа в стеке (с конца)
                    for i in range(len(self.tag_stack) - 1, -1, -1):
                        stacked_tag, stacked_line = self.tag_stack[i]
                        if stacked_tag == tag_name:
                            self.errors.append(ValidationError(
                                line=line_num,
                                message=f"Открывается новый <{tag_name}>, но предыдущий <{tag_name}> (строка {stacked_line}) ещё не закрыт",
                                tag=tag_name
                            ))
                            break
                
                self.tag_stack.append((tag_name, line_num))
                self.last_tag = (tag_name, line_num)

    def _check_bare_text(self, text: str, line_num: int):
        """Проверяет, что текстовый узел не находится напрямую внутри блочного контейнера"""
        if not self.tag_stack:
            return
        immediate_parent, _ = self.tag_stack[-1]
        if immediate_parent not in self.BLOCK_CONTAINERS:
            return
        # Находим номер строки первой непустой строки в текстовом фрагменте
        for i, line in enumerate(text.split('\n')):
            if line.strip():
                self.errors.append(ValidationError(
                    line=line_num + i,
                    message=f"Текст без тега <para> внутри <{immediate_parent}>: «{line.strip()[:60]}»",
                    tag=immediate_parent
                ))
                break

    def _validate_tag_attributes(self, full_tag: str, tag_name: str, line_num: int):
        """Проверяет базовую корректность атрибутов тега (парность кавычек)"""
        # Для закрывающих тегов атрибутов быть не должно, здесь проверяем только открывающие.
        # Убираем хвост "/>" или ">" и смотрим только на атрибутную часть.
        tag_body = full_tag[1:-1]
        if tag_body.endswith('/'):
            tag_body = tag_body[:-1]

        # Вырезаем имя тега вместе с ведущими пробелами.
        attrs_part = re.sub(r'^\s*[a-zA-Z][a-zA-Z0-9]*', '', tag_body, count=1)
        if not attrs_part.strip():
            return

        double_quotes = attrs_part.count('"')
        single_quotes = attrs_part.count("'")
        if double_quotes % 2 != 0 or single_quotes % 2 != 0:
            self.errors.append(ValidationError(
                line=line_num,
                message=f"Некорректные атрибуты у <{tag_name}>: непарные кавычки",
                tag=tag_name
            ))
    
    def _validate_title(self, line_num: int):
        """Проверяет правила использования тега <title>"""
        # Правило 1: Не может быть два <title> подряд
        if self.last_tag[0] == 'title':
            self.errors.append(ValidationError(
                line=line_num,
                message=f"Два тега <title> подряд (предыдущий на строке {self.last_tag[1]})",
                tag='title'
            ))
        
        # Правило 2: <title> должен быть внутри разрешённого родительского тега
        # Проверяем непосредственного родителя (последний тег в стеке)
        immediate_parent = None
        immediate_parent_line = None
        if self.tag_stack:
            immediate_parent, immediate_parent_line = self.tag_stack[-1]
        
        # Если непосредственный родитель не из разрешённых - это ошибка
        if immediate_parent and immediate_parent not in self.TAGS_WITH_TITLE:
            self.errors.append(ValidationError(
                line=line_num,
                message=f"Тег <title> не может быть непосредственным потомком <{immediate_parent}>. Разрешённые родители: {', '.join(sorted(self.TAGS_WITH_TITLE))}",
                tag='title'
            ))
            return
        
        # Если нет родителя вообще - это тоже ошибка
        if not immediate_parent:
            self.errors.append(ValidationError(
                line=line_num,
                message=f"Тег <title> должен находиться внутри: {', '.join(sorted(self.TAGS_WITH_TITLE))}",
                tag='title'
            ))
            return
        
        # Правило 3: В каждом родителе должен быть только один <title>
        parent_key = (immediate_parent, immediate_parent_line)
        if parent_key in self.title_counts:
            self.title_counts[parent_key] += 1
            self.errors.append(ValidationError(
                line=line_num,
                message=f"Больше одного <title> внутри <{immediate_parent}> (начало на строке {immediate_parent_line}). В каждом <{immediate_parent}> должен быть только один <title>",
                tag='title'
            ))
        else:
            self.title_counts[parent_key] = 1
    
    def _close_tag(self, tag_name: str, line_num: int):
        """Обрабатывает закрывающий тег"""
        if not self.tag_stack:
            self.errors.append(ValidationError(
                line=line_num,
                message=f"Закрывающий тег без открывающего",
                tag=tag_name
            ))
            return
        
        # Проверяем, соответствует ли закрывающий тег последнему открытому
        last_tag, last_line = self.tag_stack[-1]
        
        if last_tag == tag_name:
            # Удаляем счётчик title для закрываемого тега
            parent_key = (tag_name, last_line)
            if parent_key in self.title_counts:
                del self.title_counts[parent_key]
            
            self.tag_stack.pop()
            # Обновляем last_tag на предыдущий в стеке
            if self.tag_stack:
                self.last_tag = self.tag_stack[-1]
            else:
                self.last_tag = ('', 0)
        else:
            # Ищем соответствующий открывающий тег в стеке
            found_idx = None
            for idx, (stacked_tag, stacked_line) in enumerate(reversed(self.tag_stack)):
                if stacked_tag == tag_name:
                    found_idx = len(self.tag_stack) - 1 - idx
                    break
            
            if found_idx is not None:
                # Нашли тег, но между ними есть незакрытые теги
                for i in range(len(self.tag_stack) - 1, found_idx, -1):
                    unclosed_tag, unclosed_line = self.tag_stack[i]
                    self.errors.append(ValidationError(
                        line=line_num,
                        message=f"Закрывается </{tag_name}>, но внутри есть незакрытый <{unclosed_tag}> (открыт на строке {unclosed_line})",
                        tag=tag_name
                    ))
                    # Удаляем счётчик title для незакрытого тега
                    parent_key = (unclosed_tag, unclosed_line)
                    if parent_key in self.title_counts:
                        del self.title_counts[parent_key]
                
                # Удаляем счётчик для закрываемого тега
                _, closing_line = self.tag_stack[found_idx]
                parent_key = (tag_name, closing_line)
                if parent_key in self.title_counts:
                    del self.title_counts[parent_key]
                
                self.tag_stack = self.tag_stack[:found_idx]
                if self.tag_stack:
                    self.last_tag = self.tag_stack[-1]
                else:
                    self.last_tag = ('', 0)
            else:
                self.errors.append(ValidationError(
                    line=line_num,
                    message=f"Закрывающий тег '{tag_name}' без соответствующего открывающего (последний открытый: '{last_tag}')",
                    tag=tag_name
                ))
    
    def print_errors(self):
        """Печатает все найденные ошибки"""
        if not self.errors:
            print(f"✅ {self.filepath.name}: Ошибок не найдено")
            return
        
        print(f"\n❌ {self.filepath.name}: Найдено ошибок: {len(self.errors)}")
        print("─" * 80)
        
        # Сортируем ошибки по номеру строки
        sorted_errors = sorted(self.errors, key=lambda e: e.line)
        
        for error in sorted_errors:
            tag_info = f" <{error.tag}>" if error.tag else ""
            print(f"  Строка {error.line:4d}: {error.message}{tag_info}")


def validate_file(filepath: str) -> bool:
    """Валидирует один файл"""
    validator = SGMLValidator(filepath)
    is_valid = validator.validate()
    validator.print_errors()
    return is_valid


def validate_directory(directory: str, pattern: str = "**/*.sgml") -> Tuple[int, int]:
    """
    Валидирует все файлы в директории по паттерну
    Возвращает (количество_валидных, количество_невалидных)
    """
    dir_path = Path(directory)
    files = list(dir_path.glob(pattern))
    
    if not files:
        print(f"Файлы по паттерну '{pattern}' не найдены в {directory}")
        return 0, 0
    
    print(f"Найдено файлов: {len(files)}")
    print("=" * 80)
    
    valid_count = 0
    invalid_count = 0
    
    for filepath in sorted(files):
        is_valid = validate_file(str(filepath))
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1
    
    print("\n" + "=" * 80)
    print(f"Итого: ✅ {valid_count} валидных, ❌ {invalid_count} с ошибками")
    
    return valid_count, invalid_count


def _prompt_for_target() -> str:
    """Запрашивает путь к файлу/директории у пользователя (интерактивный режим)."""
    print("=" * 64)
    print("  SGML Validator")
    print("=" * 64)
    print()
    try:
        return input("Введите путь к файлу или директории: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def _pause():
    """Ждёт нажатия Enter, чтобы окно терминала не закрылось автоматически."""
    print()
    try:
        input("Нажмите Enter для выхода...")
    except (EOFError, KeyboardInterrupt):
        pass


def _print_usage():
    """Краткая справка по использованию из командной строки."""
    print("Использование:")
    print(f"  {sys.argv[0]} <файл.sgml>            - проверить один файл")
    print(f"  {sys.argv[0]} <директория>           - проверить все .sgml в директории")
    print(f"  {sys.argv[0]} <директория> <pattern> - проверить файлы по паттерну")
    print()
    print("Примеры:")
    print(f"  {sys.argv[0]} tantor/contrib/vector/vector.sgml")
    print(f"  {sys.argv[0]} tantor/contrib")
    print(f"  {sys.argv[0]} tantor/contrib '**/*.sgml'")


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
        target = _prompt_for_target()
        if not target:
            print("\n❌ Путь не указан.")
            _pause()
            sys.exit(1)
        pattern = "**/*.sgml"
        print()
    else:
        target = sys.argv[1]
        pattern = sys.argv[2] if len(sys.argv) > 2 else "**/*.sgml"

    target_path = Path(target)
    exit_code: int

    if target_path.is_file():
        is_valid = validate_file(target)
        exit_code = 0 if is_valid else 1
    elif target_path.is_dir():
        _, invalid = validate_directory(target, pattern)
        exit_code = 0 if invalid == 0 else 1
    else:
        print(f"❌ Путь не найден: {target}")
        exit_code = 1

    if interactive:
        _pause()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
