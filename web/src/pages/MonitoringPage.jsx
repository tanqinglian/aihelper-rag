import { useState, useEffect } from 'react';
import { Card, Badge, Statistic, Typography, Button, Tag, Space, Row, Col, Alert } from 'antd';
import { ReloadOutlined, ApiOutlined, RobotOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { monitoringApi } from '../api/client';

const { Text, Title } = Typography;

export default function MonitoringPage() {
  const [health, setHealth] = useState(null);
  const [ollama, setOllama] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchStatus = async () => {
    try {
      const [h, o, s] = await Promise.all([
        monitoringApi.health().catch(() => ({ status: 'error' })),
        monitoringApi.ollama().catch(e => ({ running: false, error: e.message })),
        monitoringApi.stats().catch(() => null),
      ]);
      setHealth(h); setOllama(o); setStats(s); setLastUpdate(new Date());
    } catch {} finally { setLoading(false); }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return <div style={{ maxWidth: 800, margin: '0 auto', textAlign: 'center', paddingTop: 80 }}>
      <Text type="secondary">加载中...</Text>
    </div>;
  }

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <Title level={3} style={{ margin: 0, color: '#135200' }}>服务监控</Title>
          <Text type="secondary">
            查看系统服务状态
            {lastUpdate && <span style={{ marginLeft: 8, fontSize: 12 }}>(更新于 {lastUpdate.toLocaleTimeString()})</span>}
          </Text>
        </div>
        <Button icon={<ReloadOutlined />} onClick={fetchStatus}>刷新</Button>
      </div>

      {/* 服务状态 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card style={{ background: '#fff', borderColor: '#d9f7be', boxShadow: '0 2px 8px rgba(82, 196, 26, 0.08)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <Space>
                <ApiOutlined style={{ fontSize: 20, color: '#52c41a' }} />
                <Text strong style={{ color: '#135200' }}>API 服务</Text>
              </Space>
              <Badge status={health?.status === 'ok' ? 'success' : 'error'} text={
                <Text style={{ color: health?.status === 'ok' ? '#52c41a' : '#ff4d4f' }}>
                  {health?.status === 'ok' ? '运行中' : '离线'}
                </Text>
              } />
            </div>
            <Text type="secondary" style={{ fontSize: 13 }}>地址: localhost:8900</Text>
          </Card>
        </Col>
        <Col span={12}>
          <Card style={{ background: '#fff', borderColor: '#d9f7be', boxShadow: '0 2px 8px rgba(82, 196, 26, 0.08)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <Space>
                <RobotOutlined style={{ fontSize: 20, color: '#52c41a' }} />
                <Text strong style={{ color: '#135200' }}>Ollama LLM</Text>
              </Space>
              <Badge status={ollama?.running ? 'success' : 'error'} text={
                <Text style={{ color: ollama?.running ? '#52c41a' : '#ff4d4f' }}>
                  {ollama?.running ? '运行中' : '离线'}
                </Text>
              } />
            </div>
            <Text type="secondary" style={{ fontSize: 13 }}>地址: {ollama?.base_url || 'localhost:11434'}</Text>
            {ollama?.error && <div><Text type="danger" style={{ fontSize: 12 }}>{ollama.error}</Text></div>}
          </Card>
        </Col>
      </Row>

      {/* 模型状态 */}
      {ollama?.running && (
        <Card title="模型状态" style={{ marginBottom: 16, background: '#fff', borderColor: '#d9f7be', boxShadow: '0 2px 8px rgba(82, 196, 26, 0.08)' }}
          styles={{ header: { borderColor: '#d9f7be', color: '#135200' } }}>
          <Space direction="vertical" style={{ width: '100%' }} size={8}>
            <ModelRow name="Embedding 模型" model={ollama.required_embed_model} available={ollama.embed_model_available} />
            <ModelRow name="LLM 模型" model={ollama.required_llm_model} available={ollama.llm_model_available} />
          </Space>
          {(!ollama.embed_model_available || !ollama.llm_model_available) && (
            <Alert
              type="warning" showIcon style={{ marginTop: 16 }}
              message="缺少必要模型"
              description={
                <code style={{ display: 'block', marginTop: 8, padding: 8, background: '#f6ffed', borderRadius: 4, fontSize: 12 }}>
                  {!ollama.embed_model_available && `ollama pull ${ollama.required_embed_model}\n`}
                  {!ollama.llm_model_available && `ollama pull ${ollama.required_llm_model}`}
                </code>
              }
            />
          )}
        </Card>
      )}

      {/* 索引统计 */}
      {stats && (
        <Card title="索引统计" style={{ background: '#fff', borderColor: '#d9f7be', boxShadow: '0 2px 8px rgba(82, 196, 26, 0.08)' }}
          styles={{ header: { borderColor: '#d9f7be', color: '#135200' } }}>
          <Row gutter={16}>
            <Col span={6}><Statistic title="项目总数" value={stats.total_projects} /></Col>
            <Col span={6}><Statistic title="已索引" value={stats.indexed_projects} /></Col>
            <Col span={6}><Statistic title="文件总数" value={stats.total_indexed_files} /></Col>
            <Col span={6}><Statistic title="索引大小" value={`${(stats.total_index_size_bytes / 1024 / 1024).toFixed(1)} MB`} /></Col>
          </Row>
          {stats.projects_summary?.length > 0 && (
            <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid #d9f7be' }}>
              <Text type="secondary" style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>项目列表</Text>
              <Space direction="vertical" style={{ width: '100%' }} size={8}>
                {stats.projects_summary.map(p => (
                  <div key={p.id} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '8px 12px', background: '#f6ffed', borderRadius: 8,
                  }}>
                    <Text style={{ color: '#135200' }}>{p.name}</Text>
                    <Space>
                      <Text type="secondary" style={{ fontSize: 12 }}>{p.file_count} 文件</Text>
                      <Tag color={p.status === 'indexed' ? 'success' : p.status === 'indexing' ? 'processing' : 'default'}>
                        {p.status}
                      </Tag>
                    </Space>
                  </div>
                ))}
              </Space>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

function ModelRow({ name, model, available }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '8px 12px', background: '#f6ffed', borderRadius: 8,
    }}>
      <Space>
        <Text style={{ color: '#135200' }}>{name}</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>{model}</Text>
      </Space>
      <Tag color={available ? 'success' : 'error'} icon={available ? <CheckCircleOutlined /> : <CloseCircleOutlined />}>
        {available ? '可用' : '缺失'}
      </Tag>
    </div>
  );
}
