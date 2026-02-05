import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, Button, Select, Typography, Tag, Input, Tooltip, Divider, Space, Empty } from 'antd';
import {
  PlusOutlined, MenuFoldOutlined, MenuUnfoldOutlined, MessageOutlined,
  DeleteOutlined, SendOutlined, StopOutlined, SettingOutlined, DashboardOutlined,
  CodeOutlined, FileTextOutlined, CopyOutlined, CheckOutlined,
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { ChatProvider, useChatContext } from '../contexts/ChatContext';
import { useProjectContext } from '../contexts/ProjectContext';
import { useStreamingChat } from '../hooks/useStreamingChat';

const { Sider, Content } = Layout;
const { Text, Title } = Typography;
const { TextArea } = Input;

export default function ChatPage() {
  return (
    <ChatProvider>
      <ChatPageInner />
    </ChatProvider>
  );
}

function ChatPageInner() {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <Layout style={{ height: '100vh', background: '#f6ffed' }}>
      <Sider
        width={280}
        collapsedWidth={0}
        collapsed={collapsed}
        trigger={null}
        className="chat-sider"
        style={{ background: '#fff', borderRight: '1px solid #d9f7be', boxShadow: '2px 0 8px rgba(82, 196, 26, 0.06)' }}
      >
        <SidebarContent onCollapse={() => setCollapsed(true)} />
      </Sider>
      <Content style={{ display: 'flex', flexDirection: 'column', position: 'relative', background: '#f6ffed' }}>
        {collapsed && (
          <Button
            type="text"
            icon={<MenuUnfoldOutlined />}
            onClick={() => setCollapsed(false)}
            style={{ position: 'absolute', top: 16, left: 16, zIndex: 10, color: '#52c41a' }}
          />
        )}
        <ChatMainArea />
      </Content>
    </Layout>
  );
}

/* ===================== 侧边栏 ===================== */
function SidebarContent({ onCollapse }) {
  const navigate = useNavigate();
  const { projects, selectedProjectId, setSelectedProjectId } = useProjectContext();
  const { conversations, currentConversationId, setCurrentConversationId, createConversation, deleteConversation } = useChatContext();
  const indexedProjects = projects.filter(p => p.status === 'indexed');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: 12 }}>
      {/* 新建对话 + 收起 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <Button icon={<PlusOutlined />} block onClick={createConversation} style={{ textAlign: 'left' }}>
          新建对话
        </Button>
        <Tooltip title="收起侧边栏">
          <Button icon={<MenuFoldOutlined />} onClick={onCollapse} />
        </Tooltip>
      </div>

      {/* 项目选择器 */}
      <div style={{ marginBottom: 16 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>当前项目</Text>
        <Select
          value={selectedProjectId}
          onChange={setSelectedProjectId}
          style={{ width: '100%' }}
          placeholder="选择已索引的项目"
          options={indexedProjects.map(p => ({
            value: p.id,
            label: `${p.name} (${p.file_count} 文件)`,
          }))}
          notFoundContent="暂无已索引项目"
        />
      </div>

      <Divider style={{ margin: '0 0 12px', borderColor: '#d9f7be' }} />

      {/* 对话历史标题 */}
      <Text type="secondary" style={{ fontSize: 12, marginBottom: 8, display: 'block' }}>对话历史</Text>

      {/* 对话列表 */}
      <div style={{ flex: 1, overflowY: 'auto' }} className="sidebar-scroll">
        {conversations.length === 0 ? (
          <Text type="secondary" style={{ display: 'block', textAlign: 'center', marginTop: 24, fontSize: 12 }}>
            暂无对话记录
          </Text>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {conversations.map(conv => (
              <div
                key={conv.id}
                onClick={() => setCurrentConversationId(conv.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '8px 12px',
                  borderRadius: 8,
                  cursor: 'pointer',
                  background: conv.id === currentConversationId ? '#f6ffed' : 'transparent',
                  border: conv.id === currentConversationId ? '1px solid #b7eb8f' : '1px solid transparent',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={e => { if (conv.id !== currentConversationId) e.currentTarget.style.background = '#f6ffed'; }}
                onMouseLeave={e => { if (conv.id !== currentConversationId) e.currentTarget.style.background = 'transparent'; }}
              >
                <MessageOutlined style={{ color: '#52c41a', fontSize: 14, flexShrink: 0 }} />
                <span style={{
                  flex: 1,
                  fontSize: 13,
                  color: 'rgba(0,0,0,0.85)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}>{conv.title}</span>
                <Tooltip title="删除">
                  <Button
                    type="text"
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={e => { e.stopPropagation(); deleteConversation(conv.id); }}
                    style={{ color: 'rgba(0,0,0,0.25)', opacity: 0 }}
                    className="conv-delete-btn"
                    onMouseEnter={e => e.currentTarget.style.opacity = 1}
                  />
                </Tooltip>
              </div>
            ))}
          </div>
        )}
      </div>

      <Divider style={{ margin: '12px 0', borderColor: '#d9f7be' }} />

      {/* 底部导航 */}
      <Space direction="vertical" style={{ width: '100%' }} size={4}>
        <Button type="text" icon={<SettingOutlined />} block onClick={() => navigate('/training')}
          style={{ textAlign: 'left', color: 'rgba(0,0,0,0.65)' }}>
          训练管理
        </Button>
        <Button type="text" icon={<DashboardOutlined />} block onClick={() => navigate('/monitoring')}
          style={{ textAlign: 'left', color: 'rgba(0,0,0,0.65)' }}>
          服务监控
        </Button>
      </Space>
    </div>
  );
}

/* ===================== 聊天主区域 ===================== */
function ChatMainArea() {
  const { selectedProjectId, selectedProject } = useProjectContext();
  const { currentConversation, currentConversationId, createConversation, addMessage, updateConversationTitle } = useChatContext();
  const { isStreaming, streamingContent, streamingSources, error, sendMessage, cancelStream } = useStreamingChat();
  const [input, setInput] = useState('');
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);

  const messages = currentConversation?.messages || [];
  const hasMessages = messages.length > 0 || isStreaming;
  const canSend = !!selectedProjectId && selectedProject?.status === 'indexed';

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  const handleSend = async (question) => {
    const q = question || input.trim();
    if (!q || !canSend) return;
    setInput('');

    let convId = currentConversationId;
    if (!convId) {
      const c = createConversation();
      convId = c?.id;
    }

    // 显式传递 conversationId，避免状态异步更新问题
    addMessage({ role: 'user', content: q }, convId);
    if (messages.length === 0) updateConversationTitle(q, convId);

    await sendMessage(selectedProjectId, q, (result) => {
      addMessage({ role: 'assistant', content: result.content, sources: result.sources }, convId);
    });
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      {/* 消息区域 */}
      <div style={{ flex: 1, overflowY: 'auto', paddingBottom: 140 }}>
        {hasMessages ? (
          <>
            {messages.map((msg, idx) => (
              <MessageBubble key={idx} message={msg} />
            ))}
            {isStreaming && (
              <MessageBubble message={{
                role: 'assistant',
                content: streamingContent || '思考中...',
                sources: streamingSources,
              }} isStreaming />
            )}
          </>
        ) : (
          <EmptyWelcome projectName={selectedProject?.name} onExample={handleSend} />
        )}
        <div ref={bottomRef} />
      </div>

      {/* 错误提示 */}
      {error && (
        <div style={{
          position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)',
          background: '#fff2f0', border: '1px solid #ffccc7', color: '#ff4d4f',
          padding: '8px 16px', borderRadius: 8, fontSize: 13, maxWidth: 480,
        }}>
          {error}
        </div>
      )}

      {/* 输入区域 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0,
        background: 'linear-gradient(transparent, #f6ffed 30%)',
        padding: '40px 16px 24px',
      }}>
        <div style={{ maxWidth: 768, margin: '0 auto' }}>
          <div style={{
            display: 'flex', alignItems: 'flex-end', gap: 8,
            background: '#fff', border: '1px solid #b7eb8f',
            borderRadius: 12, padding: '8px 12px',
            boxShadow: '0 2px 8px rgba(82, 196, 26, 0.1)',
          }}>
            <TextArea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={canSend ? '输入你的问题... (Enter 发送, Shift+Enter 换行)' : '请先选择一个已索引的项目'}
              disabled={!canSend}
              autoSize={{ minRows: 1, maxRows: 6 }}
              variant="borderless"
              style={{ flex: 1, resize: 'none', fontSize: 14, background: 'transparent' }}
            />
            {isStreaming ? (
              <Button type="primary" danger icon={<StopOutlined />} onClick={cancelStream} />
            ) : (
              <Button type="primary" icon={<SendOutlined />} onClick={() => handleSend()}
                disabled={!canSend || !input.trim()} />
            )}
          </div>
          <Text type="secondary" style={{ display: 'block', textAlign: 'center', fontSize: 12, marginTop: 8 }}>
            Code RAG 基于本地代码库生成回答，结果可能不完全准确
          </Text>
        </div>
      </div>
    </>
  );
}

/* ===================== 消息气泡 ===================== */
function MessageBubble({ message, isStreaming }) {
  const isUser = message.role === 'user';
  return (
    <div className="message-enter" style={{
      padding: '24px 0',
      background: isUser ? 'transparent' : '#fff',
    }}>
      <div style={{ maxWidth: 768, margin: '0 auto', padding: '0 24px', display: 'flex', gap: 16 }}>
        {/* 头像 */}
        <div style={{
          width: 32, height: 32, borderRadius: 6, flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: isUser ? '#d9f7be' : 'linear-gradient(135deg, #52c41a, #73d13d)',
          color: isUser ? '#135200' : '#fff', fontSize: 14, fontWeight: 600,
        }}>
          {isUser ? 'U' : <CodeOutlined />}
        </div>

        {/* 内容 */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* 源文件引用 */}
          {!isUser && message.sources?.length > 0 && (
            <SourcesPanel sources={message.sources} />
          )}

          {isUser ? (
            <div style={{ fontSize: 15, lineHeight: 1.7, color: 'rgba(0,0,0,0.85)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {message.content}
            </div>
          ) : (
            <div className="markdown-body">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ node, inline, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '');
                    const code = String(children).replace(/\n$/, '');
                    if (!inline && (match || code.includes('\n'))) {
                      return <CodeBlock language={match?.[1] || ''} code={code} />;
                    }
                    return <code className={className} {...props}>{children}</code>;
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
              {isStreaming && <span className="typing-cursor" />}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ===================== 源文件面板 ===================== */
function SourcesPanel({ sources }) {
  const [expanded, setExpanded] = useState(false);
  if (!sources?.length) return null;
  const list = expanded ? sources : sources.slice(0, 3);
  return (
    <div style={{ marginBottom: 12 }}>
      <Button type="link" size="small" onClick={() => setExpanded(!expanded)}
        icon={<FileTextOutlined />}
        style={{ padding: 0, fontSize: 12, color: '#52c41a' }}>
        引用了 {sources.length} 个源文件 {sources.length > 3 && (expanded ? '▲' : '▼')}
      </Button>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
        {list.map((s, i) => (
          <Tag key={i} style={{ background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 6 }}>
            <FileTextOutlined style={{ marginRight: 4, color: '#52c41a' }} />
            <span style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', display: 'inline-block', verticalAlign: 'bottom' }}>
              {s.path}
            </span>
            <span style={{ color: '#52c41a', marginLeft: 6, fontWeight: 500 }}>{Math.round(s.score * 100)}%</span>
          </Tag>
        ))}
      </div>
    </div>
  );
}

/* ===================== 代码块 ===================== */
function CodeBlock({ language, code }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    try { await navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch {}
  };
  return (
    <div style={{ margin: '16px 0', borderRadius: 8, overflow: 'hidden', border: '1px solid #d9f7be' }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '6px 16px', background: '#f6ffed', fontSize: 12, color: '#135200',
      }}>
        <span>{language || 'code'}</span>
        <Button type="text" size="small" onClick={handleCopy}
          icon={copied ? <CheckOutlined /> : <CopyOutlined />}
          style={{ fontSize: 12, color: '#52c41a' }}>
          {copied ? '已复制' : '复制'}
        </Button>
      </div>
      <SyntaxHighlighter language={language} style={oneLight}
        customStyle={{ margin: 0, padding: 16, background: '#fff', fontSize: 13 }}>
        {code}
      </SyntaxHighlighter>
    </div>
  );
}

/* ===================== 空状态 ===================== */
function EmptyWelcome({ projectName, onExample }) {
  const examples = ['这个项目的主要功能是什么？', '项目中使用了哪些关键技术栈？', '帮我找到处理用户登录的代码', '解释一下项目的目录结构'];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', paddingBottom: 120 }}>
      <div style={{
        width: 64, height: 64, borderRadius: 16,
        background: 'linear-gradient(135deg, #52c41a, #73d13d)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 24,
        boxShadow: '0 8px 24px rgba(82, 196, 26, 0.3)',
      }}>
        <CodeOutlined style={{ fontSize: 32, color: '#fff' }} />
      </div>
      <Title level={3} style={{ color: '#135200', marginBottom: 8 }}>Code RAG</Title>
      <Text type="secondary" style={{ marginBottom: 32 }}>
        {projectName ? `已选择项目: ${projectName}，开始提问吧` : '请先在左侧选择一个已索引的项目'}
      </Text>
      {projectName && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, maxWidth: 560, width: '100%', padding: '0 16px' }}>
          {examples.map((q, i) => (
            <Button key={i} type="default" onClick={() => onExample(q)}
              style={{
                height: 'auto', padding: '12px 16px', textAlign: 'left',
                whiteSpace: 'normal', lineHeight: 1.5, borderRadius: 10,
                borderColor: '#b7eb8f', background: '#fff',
              }}>
              <MessageOutlined style={{ marginRight: 8, color: '#52c41a' }} />{q}
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}
