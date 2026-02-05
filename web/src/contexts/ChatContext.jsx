import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useProjectContext } from './ProjectContext';

const STORAGE_KEY = 'code-rag-conversations';

const ChatContext = createContext(null);

function loadFromStorage() {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    return data ? JSON.parse(data) : {};
  } catch {
    return {};
  }
}

function saveToStorage(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {}
}

export function ChatProvider({ children }) {
  const [conversationsByProject, setConversationsByProject] = useState(() => loadFromStorage());
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const { selectedProjectId } = useProjectContext();

  // 持久化到 localStorage
  useEffect(() => {
    saveToStorage(conversationsByProject);
  }, [conversationsByProject]);

  // 当前项目的对话列表
  const conversations = conversationsByProject[selectedProjectId] || [];

  // 当前对话
  const currentConversation = conversations.find(c => c.id === currentConversationId) || null;

  // 创建新对话
  const createConversation = useCallback(() => {
    if (!selectedProjectId) return null;

    const newConv = {
      id: Date.now().toString(),
      title: '新对话',
      messages: [],
      createdAt: new Date().toISOString(),
    };

    setConversationsByProject(prev => ({
      ...prev,
      [selectedProjectId]: [newConv, ...(prev[selectedProjectId] || [])],
    }));
    setCurrentConversationId(newConv.id);
    return newConv;
  }, [selectedProjectId]);

  // 添加消息
  const addMessage = useCallback((message, conversationId = null) => {
    const targetConvId = conversationId || currentConversationId;
    if (!selectedProjectId || !targetConvId) return;

    setConversationsByProject(prev => ({
      ...prev,
      [selectedProjectId]: (prev[selectedProjectId] || []).map(conv =>
        conv.id === targetConvId
          ? { ...conv, messages: [...conv.messages, message] }
          : conv
      ),
    }));
  }, [selectedProjectId, currentConversationId]);

  // 更新对话标题
  const updateConversationTitle = useCallback((title, conversationId = null) => {
    const targetConvId = conversationId || currentConversationId;
    if (!selectedProjectId || !targetConvId) return;

    const trimmed = title.length > 30 ? title.slice(0, 30) + '...' : title;
    setConversationsByProject(prev => ({
      ...prev,
      [selectedProjectId]: (prev[selectedProjectId] || []).map(conv =>
        conv.id === targetConvId
          ? { ...conv, title: trimmed }
          : conv
      ),
    }));
  }, [selectedProjectId, currentConversationId]);

  // 删除对话
  const deleteConversation = useCallback((conversationId) => {
    if (!selectedProjectId) return;

    setConversationsByProject(prev => ({
      ...prev,
      [selectedProjectId]: (prev[selectedProjectId] || []).filter(c => c.id !== conversationId),
    }));
    if (currentConversationId === conversationId) {
      setCurrentConversationId(null);
    }
  }, [selectedProjectId, currentConversationId]);

  // 切换项目时重置当前对话
  useEffect(() => {
    setCurrentConversationId(null);
  }, [selectedProjectId]);

  const value = {
    conversations,
    currentConversation,
    currentConversationId,
    setCurrentConversationId,
    createConversation,
    addMessage,
    updateConversationTitle,
    deleteConversation,
  };

  return (
    <ChatContext.Provider value={value}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChatContext() {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChatContext must be used within ChatProvider');
  }
  return context;
}
