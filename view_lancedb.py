"""LanceDB 数据可视化预览工具"""
import os
import sys
import lancedb
from config import LANCEDB_DIR


def main():
    print("=" * 60)
    print("LanceDB 数据预览")
    print("=" * 60)

    if not os.path.exists(LANCEDB_DIR):
        print(f"\n❌ LanceDB 目录不存在: {LANCEDB_DIR}")
        print("请先通过 Web 界面索引项目")
        return

    db = lancedb.connect(LANCEDB_DIR)
    tables = db.table_names()

    if not tables:
        print(f"\n❌ 没有找到任何索引表")
        print("请先通过 Web 界面索引项目")
        return

    print(f"\n📊 找到 {len(tables)} 个项目索引:\n")

    for name in tables:
        table = db.open_table(name)
        count = table.count_rows()

        print(f"┌{'─' * 58}┐")
        print(f"│ 表名: {name:<50} │")
        print(f"│ 文档数: {count:<48} │")
        print(f"├{'─' * 58}┤")

        # 获取样本数据
        sample = table.search().limit(3).to_list()

        if sample:
            print("│ 样本数据:                                                │")
            for i, doc in enumerate(sample, 1):
                path = doc.get('path', 'N/A')[:45]
                chunk_id = doc.get('chunk_id', 'N/A')
                chunk_type = doc.get('chunk_type', 'file')
                functions = doc.get('functions', '')[:30]
                content_len = len(doc.get('content', ''))

                print(f"│                                                          │")
                print(f"│  [{i}] {path:<53}│")
                print(f"│      Chunk: {chunk_id[:40]:<46}│")
                print(f"│      Type: {chunk_type:<47}│")
                if functions:
                    print(f"│      Functions: {functions:<42}│")
                print(f"│      Content: {content_len} chars{' ' * 36}│")

        print(f"└{'─' * 58}┘")
        print()

    # 交互式查询
    if len(sys.argv) > 1:
        query = ' '.join(sys.argv[1:])
        print(f"\n🔍 搜索: {query}")
        print("-" * 60)

        for name in tables:
            table = db.open_table(name)

            # 需要向量来搜索，这里只展示表结构
            print(f"\n[{name}] 使用 API 搜索需要先获取查询向量")

    print("\n💡 提示:")
    print("  - 通过 Web 界面 (http://localhost:5173) 进行问答")
    print("  - 或使用 CLI: python cli.py")
    print("  - 查看详细文档: python view_lancedb.py --help")


def show_schema():
    """显示表结构"""
    db = lancedb.connect(LANCEDB_DIR)
    tables = db.table_names()

    for name in tables:
        table = db.open_table(name)
        print(f"\n表 {name} 的 Schema:")
        print(table.schema)


def export_sample(table_name: str, output_file: str = "sample.json"):
    """导出样本数据"""
    import json

    db = lancedb.connect(LANCEDB_DIR)
    table = db.open_table(table_name)

    sample = table.search().limit(10).to_list()

    # 移除向量字段（太大）
    for doc in sample:
        if 'vector' in doc:
            del doc['vector']

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)

    print(f"已导出到 {output_file}")


if __name__ == "__main__":
    if "--schema" in sys.argv:
        show_schema()
    elif "--export" in sys.argv:
        idx = sys.argv.index("--export")
        if idx + 1 < len(sys.argv):
            export_sample(sys.argv[idx + 1])
        else:
            print("用法: python view_lancedb.py --export <table_name>")
    elif "--help" in sys.argv:
        print("LanceDB 预览工具")
        print()
        print("用法:")
        print("  python view_lancedb.py          # 查看所有表和样本")
        print("  python view_lancedb.py --schema # 查看表结构")
        print("  python view_lancedb.py --export <table_name>  # 导出样本数据")
    else:
        main()
