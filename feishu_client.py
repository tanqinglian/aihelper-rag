"""飞书文档读取客户端"""
import os
import re
import httpx

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_BASE = "https://open.feishu.cn/open-apis"

_cached_token = {"value": None}


def get_tenant_access_token() -> str:
    resp = httpx.post(
        f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()["tenant_access_token"]


def _is_wiki_url(url: str) -> bool:
    return "/wiki/" in url


def _extract_token_from_url(url: str, pattern: str) -> str:
    match = re.search(pattern, url)
    if not match:
        raise ValueError(f"无法从 URL 提取文档 token: {url}")
    return match.group(1)


def _fetch_docx(doc_token: str, headers: dict) -> dict:
    """读取 docx 类型文档"""
    meta_resp = httpx.get(
        f"{FEISHU_BASE}/docx/v1/documents/{doc_token}",
        headers=headers,
        timeout=15.0,
    )
    meta_resp.raise_for_status()
    title = meta_resp.json().get("data", {}).get("document", {}).get("title", "未命名文档")

    content_resp = httpx.get(
        f"{FEISHU_BASE}/docx/v1/documents/{doc_token}/raw_content",
        headers=headers,
        timeout=15.0,
    )
    content_resp.raise_for_status()
    content = content_resp.json().get("data", {}).get("content", "")

    return {"title": title, "content": content, "token": doc_token}


def fetch_feishu_doc(url: str) -> dict:
    """
    获取飞书文档内容（支持 docx 和 wiki 链接）
    返回: {title, content, token}
    """
    token = get_tenant_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    if _is_wiki_url(url):
        # Wiki 链接：先查 node 拿 obj_token，再读内容
        wiki_token = _extract_token_from_url(url, r'/wiki/([A-Za-z0-9]+)')
        node_resp = httpx.get(
            f"{FEISHU_BASE}/wiki/v2/spaces/get_node",
            headers=headers,
            params={"token": wiki_token},
            timeout=15.0,
        )
        node_resp.raise_for_status()
        node = node_resp.json().get("data", {}).get("node", {})
        obj_token = node.get("obj_token", "")
        obj_type = node.get("obj_type", "docx")  # "docx" | "doc" | "sheet" ...

        if not obj_token:
            raise ValueError(f"Wiki 节点未返回 obj_token，请检查应用权限: {url}")

        if obj_type == "docx":
            return _fetch_docx(obj_token, headers)
        else:
            # 旧版 doc，raw_content 接口不同
            content_resp = httpx.get(
                f"{FEISHU_BASE}/doc/v2/{obj_token}/raw_content",
                headers=headers,
                timeout=15.0,
            )
            content_resp.raise_for_status()
            content = content_resp.json().get("data", {}).get("content", "")
            title = node.get("title", "未命名文档")
            return {"title": title, "content": content, "token": obj_token}
    else:
        # 普通 docx 链接
        doc_token = _extract_token_from_url(url, r'/(?:docx|docs|document)/([A-Za-z0-9]+)')
        return _fetch_docx(doc_token, headers)
