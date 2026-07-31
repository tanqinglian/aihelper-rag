import { useState, useRef, useEffect } from 'react';
import { Input, Button, Alert, Typography, Space, Divider, Tag, Spin, Tooltip } from 'antd';
import { LinkOutlined, ThunderboltOutlined, CopyOutlined, CheckOutlined, LoadingOutlined, DeleteOutlined, PlusOutlined, HistoryOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const { Title, Text } = Typography;
const BASE_URL = 'http://localhost:8900';

const stepTypeConfig = {
  thinking:    { color: 'processing', label: '分析中' },
  tool_call:   { color: 'warning',    label: '检索代码' },
  tool_result: { color: 'success',    label: '找到结果' },
  error:       { color: 'error',      label: '错误' },
  final_answer:{ color: 'success',    label: '完成' },
};

function formatDate(iso) {
  const d = new Date(iso);
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const mi = String(d.getMinutes()).padStart(2, '0');
  return `${mm}-${dd} ${hh}:${mi}`;
}

export default function DesignPage() {
  const [feishuUrl, setFeishuUrl] = useState('');
  const [docInfo, setDocInfo] = useState(null);
  const [fetchLoading, setFetchLoading] = useState(false);
  const [fetchError, setFetchError] = useState('');

  const [generating, setGenerating] = useState(false);
  const [agentSteps, setAgentSteps] = useState([]);
  const [document, setDocument] = useState('');
  const [currentTitle, setCurrentTitle] = useState('');
  const [copied, setCopied] = useState(false);

  const [histories, setHistories] = useState([]);
  const [activeId, setActiveId] = useState(null);

  const outputRef = useRef(null);
  const ctrlRef = useRef(null);

  // 加载历史
  const loadHistory = async () => {
    try {
      const resp = await fetch(`${BASE_URL}/design/history`);
      const data = await resp.json();
      setHistories(data);
    } catch {}
  };

  useEffect(() => { loadHistory(); }, []);

  // 获取飞书文档
  const handleFetchDoc = async () => {
    if (!feishuUrl.trim()) return;
    setFetchLoading(true);
    setFetchError('');
    setDocInfo(null);
    try {
      const resp = await fetch(`${BASE_URL}/design/fetch-doc?url=${encodeURIComponent(feishuUrl)}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || '获取失败');
      setDocInfo(data);
    } catch (e) {
      setFetchError(e.message);
    } finally {
      setFetchLoading(false);
    }
  };

  // 生成详细设计
  const handleGenerate = () => {
    if (!docInfo) return;
    setGenerating(true);
    setAgentSteps([]);
    setDocument('');
    setActiveId(null);

    const ctrl = new AbortController();
    ctrlRef.current = ctrl;

    fetch(`${BASE_URL}/design/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ feishu_url: feishuUrl }),
      signal: ctrl.signal,
    }).then(resp => {
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      const read = () => reader.read().then(({ done, value }) => {
        if (done) { setGenerating(false); loadHistory(); return; }
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const msg = JSON.parse(line.slice(6));
            if (msg.type === 'step') {
              setAgentSteps(prev => [...prev, msg.data]);
            } else if (msg.type === 'complete') {
              setDocument(msg.data.document);
              setCurrentTitle(docInfo?.title || '');
              setGenerating(false);
              loadHistory();
            }
          } catch {}
        }
        read();
      }).catch(() => { setGenerating(false); loadHistory(); });

      read();
    }).catch(() => { setGenerating(false); loadHistory(); });
  };

  const handleStop = () => {
    ctrlRef.current?.abort();
    setGenerating(false);
  };

  // 点击历史记录
  const handleSelectHistory = async (id) => {
    try {
      const resp = await fetch(`${BASE_URL}/design/history/${id}`);
      const data = await resp.json();
      setDocument(data.document);
      setCurrentTitle(data.title);
      setActiveId(id);
      setAgentSteps([]);
    } catch {}
  };

  // 删除历史记录
  const handleDeleteHistory = async (e, id) => {
    e.stopPropagation();
    await fetch(`${BASE_URL}/design/history/${id}`, { method: 'DELETE' });
    if (activeId === id) {
      setDocument('');
      setCurrentTitle('');
      setActiveId(null);
    }
    loadHistory();
  };

  // 新建
  const handleNew = () => {
    setDocument('');
    setCurrentTitle('');
    setActiveId(null);
    setAgentSteps([]);
    setDocInfo(null);
    setFeishuUrl('');
    setFetchError('');
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(document);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [agentSteps]);

  const hasResult = document.length > 0;

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 64px)', overflow: 'hidden' }}>

      {/* 左侧：历史 + 输入 */}
      <div style={{
        width: 300,
        flexShrink: 0,
        borderRight: '1px solid #d9f7be',
        display: 'flex',
        flexDirection: 'column',
        background: '#fff',
        overflow: 'hidden',
      }}>
        {/* 顶栏 */}
        <div style={{ padding: '16px 16px 8px', borderBottom: '1px solid #f0f0f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Text strong style={{ color: '#135200', fontSize: 14 }}>
            <HistoryOutlined style={{ marginRight: 6 }} />历史记录
          </Text>
          <Button size="small" icon={<PlusOutlined />} onClick={handleNew} style={{ fontSize: 12 }}>
            新建
          </Button>
        </div>

        {/* 历史列表 */}
        <div style={{ flex: 1, overflowY: 'auto' }} className="sidebar-scroll">
          {histories.length === 0 ? (
            <div style={{ padding: '24px 16px', textAlign: 'center', color: '#bbb', fontSize: 12 }}>
              暂无记录
            </div>
          ) : (
            histories.map(h => (
              <div
                key={h.id}
                onClick={() => handleSelectHistory(h.id)}
                style={{
                  padding: '10px 14px',
                  cursor: 'pointer',
                  borderBottom: '1px solid #f6ffed',
                  background: activeId === h.id ? '#f6ffed' : 'transparent',
                  borderLeft: activeId === h.id ? '3px solid #52c41a' : '3px solid transparent',
                  transition: 'background 0.15s',
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  gap: 8,
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, color: '#262626', fontWeight: activeId === h.id ? 600 : 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {h.title}
                  </div>
                  <div style={{ fontSize: 11, color: '#aaa', marginTop: 2 }}>
                    {formatDate(h.created_at)}
                  </div>
                </div>
                <Tooltip title="删除">
                  <DeleteOutlined
                    onClick={(e) => handleDeleteHistory(e, h.id)}
                    style={{ color: '#ccc', fontSize: 12, flexShrink: 0, marginTop: 3 }}
                    onMouseEnter={e => e.currentTarget.style.color = '#ff4d4f'}
                    onMouseLeave={e => e.currentTarget.style.color = '#ccc'}
                  />
                </Tooltip>
              </div>
            ))
          )}
        </div>

        {/* 底部：输入区 */}
        <div style={{ borderTop: '1px solid #d9f7be', padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <Text strong style={{ fontSize: 12, color: '#135200' }}>飞书需求链接</Text>
          <Space.Compact style={{ width: '100%' }}>
            <Input
              size="small"
              prefix={<LinkOutlined style={{ color: '#bbb' }} />}
              placeholder="粘贴飞书文档链接..."
              value={feishuUrl}
              onChange={e => setFeishuUrl(e.target.value)}
              onPressEnter={handleFetchDoc}
            />
            <Button
              size="small"
              type="primary"
              loading={fetchLoading}
              onClick={handleFetchDoc}
              style={{ background: '#52c41a', borderColor: '#52c41a' }}
            >
              获取
            </Button>
          </Space.Compact>

          {fetchError && <Alert type="error" message={fetchError} showIcon style={{ fontSize: 11 }} />}

          {docInfo && (
            <div style={{ background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 6, padding: '8px 10px' }}>
              <Text strong style={{ fontSize: 12, color: '#135200' }}>{docInfo.title}</Text>
              <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 2 }}>
                共 {docInfo.content.length} 字
              </Text>
            </div>
          )}

          <Button
            type="primary"
            icon={generating ? <LoadingOutlined /> : <ThunderboltOutlined />}
            onClick={generating ? handleStop : handleGenerate}
            disabled={!docInfo && !generating}
            style={{
              background: generating ? '#ff4d4f' : '#52c41a',
              borderColor: generating ? '#ff4d4f' : '#52c41a',
            }}
          >
            {generating ? '停止生成' : '生成详细设计'}
          </Button>

          {agentSteps.length > 0 && (
            <div ref={outputRef} style={{ maxHeight: 200, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
              {agentSteps.map((step, i) => {
                const cfg = stepTypeConfig[step.step_type] || { color: 'default', label: step.step_type };
                return (
                  <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                    <Tag color={cfg.color} style={{ fontSize: 10, marginTop: 1, flexShrink: 0, lineHeight: '16px', padding: '0 4px' }}>
                      {cfg.label}
                    </Tag>
                    <Text style={{ fontSize: 11, color: '#555', lineHeight: 1.5 }}>{step.content}</Text>
                  </div>
                );
              })}
              {generating && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingLeft: 2 }}>
                  <Spin size="small" />
                  <Text style={{ fontSize: 11, color: '#999' }}>思考中...</Text>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 右侧：设计文档 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{
          padding: '12px 24px',
          borderBottom: '1px solid #f0f0f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#fff',
        }}>
          <Text strong style={{ color: '#135200' }}>
            {currentTitle ? `设计文档：${currentTitle}` : '设计文档'}
          </Text>
          {hasResult && (
            <Button
              size="small"
              icon={copied ? <CheckOutlined /> : <CopyOutlined />}
              onClick={handleCopy}
              type={copied ? 'primary' : 'default'}
              style={copied ? { background: '#52c41a', borderColor: '#52c41a' } : {}}
            >
              {copied ? '已复制' : '复制全文'}
            </Button>
          )}
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '24px 32px' }}>
          {!hasResult && !generating && (
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#bbb', gap: 12 }}>
              <FileTextIcon />
              <Text style={{ color: '#bbb', fontSize: 14 }}>
                从历史记录中选择，或输入飞书链接生成新文档
              </Text>
            </div>
          )}

          {(hasResult || generating) && (
            <div className="design-doc-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {document || (generating ? '*正在生成设计文档...*' : '')}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function FileTextIcon() {
  return (
    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#d9d9d9" strokeWidth="1.5">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="16" y1="13" x2="8" y2="13"/>
      <line x1="16" y1="17" x2="8" y2="17"/>
      <polyline points="10 9 9 9 8 9"/>
    </svg>
  );
}
