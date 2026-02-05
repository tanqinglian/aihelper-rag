/**
 * 项目上下文 - 管理全局项目状态
 */
import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { projectApi } from '../api/client';

const ProjectContext = createContext(null);

export function ProjectProvider({ children }) {
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // 加载项目列表
  const loadProjects = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await projectApi.list();
      setProjects(data.projects || []);

      // 如果没有选中项目，选择第一个已索引的项目
      if (!selectedProjectId && data.projects?.length > 0) {
        const indexed = data.projects.find((p) => p.status === 'indexed');
        if (indexed) {
          setSelectedProjectId(indexed.id);
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [selectedProjectId]);

  // 初始加载
  useEffect(() => {
    loadProjects();
  }, []);

  // 获取选中的项目
  const selectedProject = projects.find((p) => p.id === selectedProjectId);

  // 更新单个项目状态
  const updateProjectInList = useCallback((projectId, updates) => {
    setProjects((prev) =>
      prev.map((p) => (p.id === projectId ? { ...p, ...updates } : p))
    );
  }, []);

  const value = {
    projects,
    selectedProjectId,
    selectedProject,
    setSelectedProjectId,
    loading,
    error,
    refreshProjects: loadProjects,
    updateProjectInList,
  };

  return (
    <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>
  );
}

export function useProjectContext() {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error('useProjectContext must be used within ProjectProvider');
  }
  return context;
}
