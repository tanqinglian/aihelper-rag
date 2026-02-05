"""代码预处理模块 - 清洗、分块、元数据提取、向量化文本优化"""
import re
from typing import Optional
from models import PreprocessorConfig, CodeChunk


class CodeCleaner:
    """代码清洗器 - 移除注释、调试语句、规范化空白"""

    DEBUG_PATTERNS = [
        r'^\s*console\.(log|debug|info|warn|error|trace|dir|table|time|timeEnd|group|groupEnd|assert|count|clear)\s*\([^;]*\);?\s*$',
        r'^\s*debugger\s*;?\s*$',
        r'^\s*alert\s*\([^;]*\)\s*;?\s*$',
    ]

    ESLINT_PATTERNS = [
        r'//\s*eslint-disable.*$',
        r'//\s*eslint-enable.*$',
        r'/\*\s*eslint-disable.*?\*/',
        r'//\s*@ts-ignore\s*$',
        r'//\s*@ts-nocheck\s*$',
        r'//\s*@ts-expect-error.*$',
        r'//\s*noinspection\s+.*$',
        r'//\s*prettier-ignore\s*$',
        r'//\s*TODO.*$',
        r'//\s*FIXME.*$',
        r'//\s*HACK.*$',
        r'//\s*XXX.*$',
    ]

    def __init__(self, config: PreprocessorConfig):
        self.config = config

    def clean(self, content: str, file_ext: str) -> str:
        """主清洗入口"""
        if self.config.remove_comments:
            content = self._remove_comments(content, file_ext)
        if self.config.remove_debug_statements:
            content = self._remove_debug_statements(content)
        if self.config.remove_eslint_comments:
            content = self._remove_eslint_comments(content)
        if self.config.normalize_whitespace:
            content = self._normalize_whitespace(content)
        return content

    def _remove_comments(self, content: str, file_ext: str) -> str:
        """移除所有注释"""
        if file_ext in ('.less', '.css'):
            content = re.sub(r'/\*[\s\S]*?\*/', '', content)
            return content

        content = re.sub(r'/\*[\s\S]*?\*/', '', content)

        lines = content.split('\n')
        result = []
        for line in lines:
            cleaned = self._remove_line_comment(line)
            result.append(cleaned)
        return '\n'.join(result)

    def _remove_line_comment(self, line: str) -> str:
        """移除行内注释，保留字符串中的 //"""
        result = []
        i = 0
        in_string = None

        while i < len(line):
            ch = line[i]

            if in_string:
                result.append(ch)
                if ch == '\\' and i + 1 < len(line):
                    result.append(line[i + 1])
                    i += 2
                    continue
                if ch == in_string:
                    in_string = None
                i += 1
                continue

            if ch in ('"', "'", '`'):
                in_string = ch
                result.append(ch)
                i += 1
                continue

            if ch == '/' and i + 1 < len(line) and line[i + 1] == '/':
                break

            result.append(ch)
            i += 1

        return ''.join(result)

    def _remove_debug_statements(self, content: str) -> str:
        """移除调试语句"""
        lines = content.split('\n')
        result = []
        for line in lines:
            is_debug = False
            for pattern in self.DEBUG_PATTERNS:
                if re.match(pattern, line, re.IGNORECASE):
                    is_debug = True
                    break
            if not is_debug:
                result.append(line)
        return '\n'.join(result)

    def _remove_eslint_comments(self, content: str) -> str:
        """移除 eslint 控制注释"""
        for pattern in self.ESLINT_PATTERNS:
            content = re.sub(pattern, '', content, flags=re.MULTILINE)
        return content

    def _normalize_whitespace(self, content: str) -> str:
        """规范化空白"""
        content = re.sub(r'\n{3,}', '\n\n', content)
        lines = [line.rstrip() for line in content.split('\n')]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return '\n'.join(lines)


class CodeChunker:
    """语义分块器 - 按函数/类/组件边界分割"""

    BLOCK_START_PATTERNS = [
        (r'^export\s+default\s+(?:async\s+)?function\s+([A-Z]\w*)', 'component'),
        (r'^export\s+default\s+(?:async\s+)?function\s+(\w+)', 'function'),
        (r'^export\s+default\s+class\s+(\w+)', 'class'),
        (r'^export\s+(?:async\s+)?function\s+([A-Z]\w*)', 'component'),
        (r'^export\s+(?:async\s+)?function\s+(\w+)', 'function'),
        (r'^export\s+class\s+(\w+)', 'class'),
        (r'^(?:async\s+)?function\s+([A-Z]\w*)\s*\(', 'component'),
        (r'^(?:async\s+)?function\s+(\w+)\s*\(', 'function'),
        (r'^class\s+(\w+)', 'class'),
        (r'^export\s+(?:const|let|var)\s+([A-Z]\w*)\s*[:=]', 'component'),
        (r'^export\s+(?:const|let|var)\s+(\w+)\s*[:=]', 'module_scope'),
        (r'^(?:const|let|var)\s+([A-Z]\w*)\s*[:=]\s*(?:\([^)]*\)|[^=])*\s*=>\s*(?:\{|\()', 'component'),
        (r'^(?:const|let|var)\s+(\w+)\s*[:=]\s*(?:async\s+)?(?:\([^)]*\)|[^=])*\s*=>\s*\{', 'function'),
        (r'^(?:const|let|var)\s+(\w+)\s*[:=]\s*function', 'function'),
        (r'^export\s+(?:interface|type)\s+(\w+)', 'type'),
        (r'^(?:interface|type)\s+(\w+)', 'type'),
    ]

    def __init__(self, config: PreprocessorConfig):
        self.config = config

    def chunk(self, content: str, file_path: str, file_ext: str) -> list[dict]:
        """主分块入口"""
        if self.config.chunk_strategy == "none":
            return [{"content": content, "type": "file", "start": 0, "end": len(content.split('\n')) - 1, "name": ""}]

        if file_ext in ('.less', '.css'):
            return self._chunk_style(content, file_path)

        return self._semantic_chunk(content, file_path, file_ext)

    def _semantic_chunk(self, content: str, file_path: str, file_ext: str) -> list[dict]:
        """语义分块 - 按函数/类/组件边界"""
        imports_block, body = self._extract_imports_block(content)
        blocks = self._find_top_level_blocks(body, file_ext)

        if not blocks:
            full_content = content
            if len(full_content) > self.config.chunk_max_chars:
                return self._sliding_window_chunk(content, file_path)
            return [{"content": full_content, "type": "module_scope", "start": 0, "end": len(content.split('\n')) - 1, "name": ""}]

        blocks = self._merge_small_blocks(blocks, imports_block)

        chunks = []
        import_lines = len(imports_block.split('\n')) if imports_block else 0

        for block in blocks:
            chunk_content = block["content"]
            if imports_block and block["type"] not in ("imports", "type"):
                imports_truncated = '\n'.join(imports_block.split('\n')[:20])
                if len(imports_block.split('\n')) > 20:
                    imports_truncated += '\n// ... more imports'
                chunk_content = imports_truncated + '\n\n' + block["content"]

            chunks.append({
                "content": chunk_content,
                "type": block["type"],
                "start": block["start"] + import_lines,
                "end": block["end"] + import_lines,
                "name": block.get("name", ""),
            })

        return chunks

    def _extract_imports_block(self, content: str) -> tuple[str, str]:
        """分离导入区域和主体代码"""
        lines = content.split('\n')
        import_end = 0
        in_multiline = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            if in_multiline:
                import_end = i + 1
                if stripped.endswith(';') or (stripped.endswith("'") or stripped.endswith('"')):
                    in_multiline = False
                continue

            if not stripped:
                if import_end > 0:
                    import_end = i + 1
                continue

            if (stripped.startswith('import ') or
                stripped.startswith('from ') or
                stripped.startswith("require(") or
                (stripped.startswith('const ') and 'require(' in stripped) or
                (stripped.startswith('import ') and not stripped.endswith(';'))):
                import_end = i + 1
                if not stripped.endswith(';') and not stripped.endswith("'") and not stripped.endswith('"'):
                    in_multiline = True
                continue

            if import_end > 0:
                break

        imports = '\n'.join(lines[:import_end])
        body = '\n'.join(lines[import_end:])
        return imports.strip(), body.strip()

    def _find_top_level_blocks(self, content: str, file_ext: str) -> list[dict]:
        """找到顶层代码块边界"""
        lines = content.split('\n')
        blocks = []
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if not stripped:
                i += 1
                continue

            matched = False
            for pattern, block_type in self.BLOCK_START_PATTERNS:
                match = re.match(pattern, stripped)
                if match:
                    name = match.group(1) if match.groups() else ""
                    end_line = self._find_block_end(lines, i)
                    block_content = '\n'.join(lines[i:end_line + 1])

                    blocks.append({
                        "content": block_content,
                        "type": block_type,
                        "start": i,
                        "end": end_line,
                        "name": name,
                    })
                    i = end_line + 1
                    matched = True
                    break

            if not matched:
                if stripped.startswith('export ') or stripped.startswith('module.exports'):
                    end_line = self._find_block_end(lines, i)
                    block_content = '\n'.join(lines[i:end_line + 1])
                    blocks.append({
                        "content": block_content,
                        "type": "module_scope",
                        "start": i,
                        "end": end_line,
                        "name": "",
                    })
                    i = end_line + 1
                else:
                    i += 1

        return blocks

    def _find_block_end(self, lines: list[str], start_line: int) -> int:
        """使用大括号深度追踪找到块结束位置"""
        depth = 0
        started = False
        paren_depth = 0

        for i in range(start_line, len(lines)):
            line = lines[i]
            cleaned = self._strip_strings(line)

            for ch in cleaned:
                if ch == '(':
                    paren_depth += 1
                elif ch == ')':
                    paren_depth -= 1
                elif ch == '{':
                    depth += 1
                    started = True
                elif ch == '}':
                    depth -= 1

            if started and depth == 0 and paren_depth <= 0:
                return i

        return len(lines) - 1

    def _strip_strings(self, line: str) -> str:
        """移除字符串内容，保留结构字符"""
        result = []
        i = 0
        in_string = None

        while i < len(line):
            ch = line[i]

            if in_string:
                if ch == '\\' and i + 1 < len(line):
                    i += 2
                    continue
                if ch == in_string:
                    in_string = None
                i += 1
                continue

            if ch in ('"', "'", '`'):
                in_string = ch
                i += 1
                continue

            if ch == '/' and i + 1 < len(line):
                if line[i + 1] == '/':
                    break
                if line[i + 1] == '*':
                    end = line.find('*/', i + 2)
                    if end >= 0:
                        i = end + 2
                    else:
                        break
                    continue

            result.append(ch)
            i += 1

        return ''.join(result)

    def _merge_small_blocks(self, blocks: list[dict], imports_block: str) -> list[dict]:
        """合并过小的块"""
        if not blocks:
            return blocks

        imports_len = len(imports_block) if imports_block else 0
        min_chars = self.config.chunk_min_chars

        merged = []
        current = None

        for block in blocks:
            effective_len = len(block["content"]) + imports_len

            if current is None:
                current = block.copy()
                continue

            current_effective_len = len(current["content"]) + imports_len

            if current_effective_len < min_chars and effective_len < min_chars:
                current["content"] = current["content"] + '\n\n' + block["content"]
                current["end"] = block["end"]
                current["type"] = "module_scope"
                names = [n for n in [current.get("name"), block.get("name")] if n]
                current["name"] = ", ".join(names) if names else ""
            else:
                merged.append(current)
                current = block.copy()

        if current:
            merged.append(current)

        return merged

    def _chunk_style(self, content: str, file_path: str) -> list[dict]:
        """CSS/Less 文件分块"""
        lines = content.split('\n')
        chunks = []
        current_chunk = []
        current_start = 0
        depth = 0

        for i, line in enumerate(lines):
            current_chunk.append(line)

            for ch in line:
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1

            if depth == 0 and current_chunk and line.strip().endswith('}'):
                chunk_content = '\n'.join(current_chunk)
                if chunk_content.strip():
                    chunks.append({
                        "content": chunk_content,
                        "type": "style",
                        "start": current_start,
                        "end": i,
                        "name": "",
                    })
                current_chunk = []
                current_start = i + 1

        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            if chunk_content.strip():
                chunks.append({
                    "content": chunk_content,
                    "type": "style",
                    "start": current_start,
                    "end": len(lines) - 1,
                    "name": "",
                })

        return self._merge_small_style_blocks(chunks)

    def _merge_small_style_blocks(self, blocks: list[dict]) -> list[dict]:
        """合并小的样式块"""
        if not blocks:
            return blocks

        merged = []
        current = None

        for block in blocks:
            if current is None:
                current = block.copy()
                continue

            if len(current["content"]) < self.config.chunk_min_chars:
                current["content"] = current["content"] + '\n\n' + block["content"]
                current["end"] = block["end"]
            else:
                merged.append(current)
                current = block.copy()

        if current:
            merged.append(current)

        return merged

    def _sliding_window_chunk(self, content: str, file_path: str) -> list[dict]:
        """滑动窗口分块作为备选"""
        lines = content.split('\n')
        chunks = []
        chunk_lines = 50
        overlap = self.config.chunk_overlap_lines

        i = 0
        chunk_idx = 0
        while i < len(lines):
            end = min(i + chunk_lines, len(lines))
            chunk_content = '\n'.join(lines[i:end])

            chunks.append({
                "content": chunk_content,
                "type": "module_scope",
                "start": i,
                "end": end - 1,
                "name": f"part_{chunk_idx}",
            })

            i = end - overlap if end < len(lines) else end
            chunk_idx += 1

        return chunks


class MetadataExtractor:
    """元数据提取器 - 从代码中提取结构信息"""

    FUNCTION_PATTERNS = [
        r'(?:export\s+)?(?:async\s+)?function\s+(\w+)',
        r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(?[^)]*\)?\s*=>',
        r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*function',
    ]

    CLASS_PATTERNS = [
        r'(?:export\s+)?class\s+(\w+)',
    ]

    COMPONENT_PATTERNS = [
        r'(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+([A-Z]\w*)',
        r'(?:export\s+)?(?:const|let)\s+([A-Z]\w*)\s*[:=]',
    ]

    IMPORT_PATTERNS = [
        r"import\s+.*?\s+from\s+['\"](.+?)['\"]",
        r"import\s+['\"](.+?)['\"]",
        r"require\s*\(\s*['\"](.+?)['\"]\s*\)",
    ]

    EXPORT_PATTERNS = [
        r'export\s+default\s+(?:function|class|const|let|var)?\s*(\w+)',
        r'export\s+(?:function|class|const|let|var)\s+(\w+)',
        r'export\s*\{([^}]+)\}',
    ]

    TYPE_PATTERNS = [
        r'(?:export\s+)?(?:interface|type)\s+(\w+)',
        r'(?:export\s+)?enum\s+(\w+)',
    ]

    def __init__(self, config: PreprocessorConfig):
        self.config = config

    def extract(self, content: str, file_ext: str) -> dict:
        """从完整文件提取元数据"""
        if not self.config.extract_metadata:
            return {}

        return {
            "functions": self._extract_functions(content),
            "classes": self._extract_classes(content),
            "components": self._extract_components(content),
            "imports": self._extract_imports(content),
            "exports": self._extract_exports(content),
            "types": self._extract_types(content),
        }

    def _extract_functions(self, content: str) -> list[str]:
        """提取函数名列表"""
        functions = []
        for pattern in self.FUNCTION_PATTERNS:
            matches = re.findall(pattern, content, re.MULTILINE)
            functions.extend(matches)
        return list(set(functions))

    def _extract_classes(self, content: str) -> list[str]:
        """提取类名"""
        classes = []
        for pattern in self.CLASS_PATTERNS:
            matches = re.findall(pattern, content, re.MULTILINE)
            classes.extend(matches)
        return list(set(classes))

    def _extract_components(self, content: str) -> list[str]:
        """提取 React 组件名"""
        components = []
        for pattern in self.COMPONENT_PATTERNS:
            matches = re.findall(pattern, content, re.MULTILINE)
            for m in matches:
                if m and m[0].isupper():
                    components.append(m)
        return list(set(components))

    def _extract_imports(self, content: str) -> list[str]:
        """提取导入依赖"""
        imports = []
        for pattern in self.IMPORT_PATTERNS:
            matches = re.findall(pattern, content, re.MULTILINE)
            imports.extend(matches)
        local_imports = [i for i in imports if i.startswith('.') or i.startswith('@/') or i.startswith('@')]
        return list(set(local_imports))

    def _extract_exports(self, content: str) -> list[str]:
        """提取导出信息"""
        exports = []
        for pattern in self.EXPORT_PATTERNS:
            matches = re.findall(pattern, content, re.MULTILINE)
            for m in matches:
                if isinstance(m, str):
                    if ',' in m:
                        exports.extend([e.strip() for e in m.split(',')])
                    elif m.strip():
                        exports.append(m.strip())
        return list(set([e for e in exports if e]))

    def _extract_types(self, content: str) -> list[str]:
        """提取 TypeScript 类型/接口名"""
        types = []
        for pattern in self.TYPE_PATTERNS:
            matches = re.findall(pattern, content, re.MULTILINE)
            types.extend(matches)
        return list(set(types))


class SmartTruncator:
    """智能截断器 - 按代码边界截断"""

    def __init__(self, max_chars: int = 2000):
        self.max_chars = max_chars

    def truncate(self, content: str) -> str:
        """智能截断 - 按完整行和代码块边界"""
        if len(content) <= self.max_chars:
            return content

        pos = content.rfind('\n', 0, self.max_chars)
        if pos == -1:
            pos = self.max_chars

        safe_pos = self._find_safe_truncation_point(content, pos)
        truncated = content[:safe_pos].rstrip()
        remaining = len(content) - safe_pos

        return truncated + f"\n// ... (truncated, {remaining} chars omitted)"

    def _find_safe_truncation_point(self, content: str, max_pos: int) -> int:
        """找到安全截断位置"""
        search_start = max(0, max_pos - 500)
        search_region = content[search_start:max_pos]

        blank_line = search_region.rfind('\n\n')
        if blank_line != -1:
            return search_start + blank_line + 1

        closing_brace = search_region.rfind('}\n')
        if closing_brace != -1:
            return search_start + closing_brace + 2

        semicolon = search_region.rfind(';\n')
        if semicolon != -1:
            return search_start + semicolon + 2

        newline = search_region.rfind('\n')
        if newline != -1:
            return search_start + newline + 1

        return max_pos


class EmbedTextBuilder:
    """向量化文本构建器 - 优化 embedding 输入"""

    @staticmethod
    def build(chunk: CodeChunk) -> str:
        """构建优化的 embed_text"""
        parts = []

        parts.append(f"File: {chunk.file_path}")

        if chunk.exports:
            parts.append(f"Exports: {', '.join(chunk.exports[:10])}")
        if chunk.functions:
            parts.append(f"Functions: {', '.join(chunk.functions[:10])}")
        if chunk.classes:
            parts.append(f"Classes: {', '.join(chunk.classes[:10])}")
        if chunk.imports:
            parts.append(f"Dependencies: {', '.join(chunk.imports[:10])}")

        parts.append(f"Type: {chunk.chunk_type}")
        parts.append("")
        parts.append(chunk.content)

        return '\n'.join(parts)


def preprocess_file(
    file_info: dict,
    config: PreprocessorConfig
) -> list[CodeChunk]:
    """
    预处理单个文件，返回多个 chunk

    输入: scan_files() 返回的 file_info dict
    输出: 多个 CodeChunk，每个将独立存入向量数据库
    """
    file_path = file_info.get("path", "")
    module = file_info.get("module", "")
    sub_module = file_info.get("sub_module", "")
    content = file_info.get("content", "")

    file_ext = ""
    if '.' in file_path:
        file_ext = '.' + file_path.rsplit('.', 1)[-1]

    cleaner = CodeCleaner(config)
    cleaned_content = cleaner.clean(content, file_ext)

    extractor = MetadataExtractor(config)
    metadata = extractor.extract(content, file_ext)

    chunker = CodeChunker(config)
    raw_chunks = chunker.chunk(cleaned_content, file_path, file_ext)

    truncator = SmartTruncator(config.max_chunk_chars)

    chunks = []
    for idx, raw_chunk in enumerate(raw_chunks):
        chunk_content = truncator.truncate(raw_chunk["content"])

        chunk = CodeChunk(
            chunk_id=f"{file_path}#chunk_{idx}",
            content=chunk_content,
            chunk_type=raw_chunk["type"],
            start_line=raw_chunk["start"],
            end_line=raw_chunk["end"],
            file_path=file_path,
            module=module,
            sub_module=sub_module,
            functions=metadata.get("functions", []),
            classes=metadata.get("classes", []),
            exports=metadata.get("exports", []),
            imports=metadata.get("imports", []),
        )

        chunk.embed_text = EmbedTextBuilder.build(chunk)
        chunks.append(chunk)

    return chunks


if __name__ == "__main__":
    test_code = '''
import React from 'react';
import { Button } from 'antd';
import './index.less';

// This is a comment
/* Multi-line
   comment */

/**
 * JSDoc comment
 */
export default function MyComponent({ name }) {
    // Debug statement
    console.log('debug', name);

    const handleClick = () => {
        alert('clicked');
    };

    return (
        <div>
            <Button onClick={handleClick}>{name}</Button>
        </div>
    );
}

export const helper = () => {
    debugger;
    return 'helper';
};
'''

    config = PreprocessorConfig()
    file_info = {
        "path": "components/MyComponent.jsx",
        "module": "components",
        "sub_module": "",
        "content": test_code,
    }

    chunks = preprocess_file(file_info, config)

    print(f"Generated {len(chunks)} chunks:\n")
    for chunk in chunks:
        print(f"--- Chunk: {chunk.chunk_id} ({chunk.chunk_type}) ---")
        print(f"Lines: {chunk.start_line}-{chunk.end_line}")
        print(f"Functions: {chunk.functions}")
        print(f"Exports: {chunk.exports}")
        print(f"\nEmbed text preview:\n{chunk.embed_text[:500]}...")
        print("\n")
