"""快速索引脚本 - 只索引100个文件用于验证"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from indexer import scan_files, get_embedding
from config import SOURCE_DIR, INDEX_PATH

def main():
    start = time.time()
    files = scan_files(SOURCE_DIR)[:100]
    print(f'[1/2] 处理 {len(files)} 个文件...', flush=True)
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)

    index = []
    skipped = 0
    for i, f in enumerate(files):
        embed_text = f"文件路径: {f['path']}\n模块: {f['module']}\n\n{f['content']}"
        try:
            emb = get_embedding(embed_text)
            index.append({
                'path': f['path'],
                'module': f['module'],
                'sub_module': f['sub_module'],
                'content': f['content'][:3000],
                'embedding': emb,
            })
        except Exception as e:
            skipped += 1
        if (i + 1) % 20 == 0:
            print(f'  进度: {i + 1}/{len(files)}', flush=True)

    with open(INDEX_PATH, 'w', encoding='utf-8') as fp:
        json.dump(index, fp, ensure_ascii=False)

    print(f'[2/2] 完成! 索引了 {len(index)} 个文件, 跳过 {skipped} 个', flush=True)
    print(f'耗时: {time.time() - start:.1f}s', flush=True)

if __name__ == '__main__':
    main()
