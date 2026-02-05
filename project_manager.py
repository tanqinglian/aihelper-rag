"""项目管理模块"""
import os
import json
from datetime import datetime
from typing import Optional
from models import Project, ProjectConfig, ProjectStatus


class ProjectManager:
    """项目管理器 - 处理项目的 CRUD 操作"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.projects_file = os.path.join(data_dir, "projects.json")
        self.indexes_dir = os.path.join(data_dir, "indexes")
        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保必要的目录存在"""
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.indexes_dir, exist_ok=True)
        if not os.path.exists(self.projects_file):
            self._save_projects([])

    def _load_projects(self) -> list[dict]:
        """从文件加载项目列表"""
        try:
            with open(self.projects_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("projects", [])
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_projects(self, projects: list[dict]):
        """保存项目列表到文件"""
        with open(self.projects_file, "w", encoding="utf-8") as f:
            json.dump({"projects": projects}, f, ensure_ascii=False, indent=2, default=str)

    def list_projects(self) -> list[Project]:
        """获取所有项目"""
        projects_data = self._load_projects()
        return [Project(**p) for p in projects_data]

    def get_project(self, project_id: str) -> Optional[Project]:
        """根据 ID 获取项目"""
        projects = self._load_projects()
        for p in projects:
            if p["id"] == project_id:
                return Project(**p)
        return None

    def create_project(self, name: str, source_dir: str, config: Optional[ProjectConfig] = None) -> Project:
        """创建新项目"""
        project = Project(
            name=name,
            source_dir=source_dir,
            config=config or ProjectConfig()
        )

        projects = self._load_projects()
        projects.append(project.model_dump())
        self._save_projects(projects)

        return project

    def update_project(self, project_id: str, **updates) -> Optional[Project]:
        """更新项目"""
        projects = self._load_projects()

        for i, p in enumerate(projects):
            if p["id"] == project_id:
                for key, value in updates.items():
                    if value is not None:
                        if key == "config" and isinstance(value, ProjectConfig):
                            p[key] = value.model_dump()
                        else:
                            p[key] = value
                projects[i] = p
                self._save_projects(projects)
                return Project(**p)

        return None

    def delete_project(self, project_id: str) -> bool:
        """删除项目及其索引"""
        projects = self._load_projects()

        for i, p in enumerate(projects):
            if p["id"] == project_id:
                # 删除 ChromaDB collection
                from indexer import delete_project_index
                delete_project_index(project_id)

                # 删除旧版 JSON 索引文件（如果存在）
                index_path = self.get_index_path(project_id)
                if os.path.exists(index_path):
                    os.remove(index_path)

                # 从列表中移除
                projects.pop(i)
                self._save_projects(projects)
                return True

        return False

    def get_index_path(self, project_id: str) -> str:
        """获取项目索引文件路径"""
        return os.path.join(self.indexes_dir, f"{project_id}.json")

    def load_index(self, project_id: str) -> list[dict]:
        """加载项目索引"""
        index_path = self.get_index_path(project_id)
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("documents", [])
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_index(self, project_id: str, documents: list[dict], project_name: str = "") -> int:
        """保存项目索引，返回文件大小"""
        index_path = self.get_index_path(project_id)

        index_data = {
            "project_id": project_id,
            "project_name": project_name,
            "indexed_at": datetime.now().isoformat(),
            "document_count": len(documents),
            "documents": documents
        }

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False)

        return os.path.getsize(index_path)

    def set_project_status(self, project_id: str, status: ProjectStatus, **extra):
        """更新项目状态"""
        updates = {"status": status.value}
        updates.update(extra)
        return self.update_project(project_id, **updates)


# 全局实例
project_manager = ProjectManager()
