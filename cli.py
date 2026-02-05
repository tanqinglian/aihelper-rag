"""命令行交互工具"""
from generator import generate


def main():
    print("=" * 50)
    print("  代码知识库问答系统 (Code RAG)")
    print("  输入问题，按回车获取回答")
    print("  输入 q 退出")
    print("=" * 50)

    while True:
        try:
            question = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n退出")
            break

        if not question:
            continue
        if question.lower() == "q":
            print("退出")
            break

        print("\n检索并生成中...\n")
        try:
            answer = generate(question)
            print(answer)
        except Exception as e:
            print(f"错误: {e}")


if __name__ == "__main__":
    main()
