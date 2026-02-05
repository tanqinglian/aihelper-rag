import { useState, useEffect } from 'react';
import { Card, Badge, Statistic, Typography, Button, Tag, Space, Row, Col, Alert, Progress, Tooltip } from 'antd';
import {
  ReloadOutlined, ApiOutlined, RobotOutlined, CheckCircleOutlined, CloseCircleOutlined,
  DatabaseOutlined, FileTextOutlined, CodeOutlined, FunctionOutlined
} from '@ant-design/icons';
import { monitoringApi } from '../api/client';

const { Text, Title } = Typography;

export default function MonitoringPage() {
  const [health, setHealth] = useState(null);
  const [ollama, setOllama] = useState(null);
  const [stats, setStats] = useState(null);
  const [lancedb, setLancedb] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchStatus = async () => {
    try {
      const [h, o, s, l] = await Promise.all([
        monitoringApi.health().catch(() => ({ status: 'error' })),
        monitoringApi.ollama().catch(e => ({ running: false, error: e.message })),
        monitoringApi.stats().catch(() => null),
        monitoringApi.lancedb().catch(() => null),
      ]);
      setHealth(h); setOllama(o); setStats(s); setLancedb(l); setLastUpdate(new Date());
    } catch {} finally { setLoading(false); }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return <div style={{ maxWidth: 900, margin: '0 auto', textAlign: 'center', paddingTop: 80 }}>
      <Text type="secondary">加载中...</Text>
    </div>;
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
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
        <Card title="索引统计" style={{ marginBottom: 16, background: '#fff', borderColor: '#d9f7be', boxShadow: '0 2px 8px rgba(82, 196, 26, 0.08)' }}
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

      {/* LanceDB 向量数据库统计 */}
      {lancedb && lancedb.tables?.length > 0 && (
        <Card
          title={
            <Space>
              <DatabaseOutlined style={{ color: '#52c41a' }} />
              <span>LanceDB 向量数据库</span>
              <Tag color="green">{(lancedb.total_size_bytes / 1024 / 1024).toFixed(2)} MB</Tag>
            </Space>
          }
          style={{ marginBottom: 16, background: '#fff', borderColor: '#d9f7be', boxShadow: '0 2px 8px rgba(82, 196, 26, 0.08)' }}
          styles={{ header: { borderColor: '#d9f7be', color: '#135200' } }}
        >
          {lancedb.tables.map(table => (
            <div key={table.name}>
              {/* 基本信息 */}
              <Row gutter={16} style={{ marginBottom: 16 }}>
                <Col span={6}>
                  <Statistic
                    title={<><CodeOutlined /> Chunk 总数</>}
                    value={table.chunk_count}
                    valueStyle={{ color: '#52c41a' }}
                  />
                </Col>
                <Col span={6}>
                  <Statistic
                    title={<><FileTextOutlined /> 文件数</>}
                    value={table.unique_files}
                  />
                </Col>
                <Col span={6}>
                  <Statistic
                    title="平均 Chunk/文件"
                    value={table.avg_chunks_per_file}
                    precision={1}
                  />
                </Col>
                <Col span={6}>
                  <Statistic
                    title="向量维度"
                    value={table.vector_dim}
                    suffix="D"
                  />
                </Col>
              </Row>

              {/* 内容统计 */}
              <div style={{ marginBottom: 16, padding: 12, background: '#f6ffed', borderRadius: 8 }}>
                <Text strong style={{ display: 'block', marginBottom: 8, color: '#135200' }}>
                  内容统计
                </Text>
                <Row gutter={16}>
                  <Col span={6}>
                    <Text type="secondary">总文本量</Text>
                    <div><Text strong>{(table.total_text_bytes / 1024 / 1024).toFixed(2)} MB</Text></div>
                  </Col>
                  <Col span={6}>
                    <Text type="secondary">最小长度</Text>
                    <div><Text strong>{table.content_stats.min_chars} chars</Text></div>
                  </Col>
                  <Col span={6}>
                    <Text type="secondary">最大长度</Text>
                    <div><Text strong>{table.content_stats.max_chars} chars</Text></div>
                  </Col>
                  <Col span={6}>
                    <Text type="secondary">平均长度</Text>
                    <div><Text strong>{table.content_stats.avg_chars} chars</Text></div>
                  </Col>
                </Row>
              </div>

              {/* Chunk 类型分布 */}
              {Object.keys(table.chunk_types || {}).length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <Text strong style={{ display: 'block', marginBottom: 12, color: '#135200' }}>
                    <FunctionOutlined /> Chunk 类型分布
                  </Text>
                  <Space direction="vertical" style={{ width: '100%' }} size={8}>
                    {Object.entries(table.chunk_types)
                      .sort((a, b) => b[1] - a[1])
                      .map(([type, count]) => {
                        const percent = (count / table.chunk_count * 100).toFixed(1);
                        const colors = {
                          'module_scope': '#52c41a',
                          'component': '#1890ff',
                          'function': '#722ed1',
                          'style': '#fa8c16',
                          'type': '#eb2f96',
                          'class': '#13c2c2',
                        };
                        return (
                          <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            <Tag color={colors[type] || 'default'} style={{ width: 100, textAlign: 'center' }}>
                              {type}
                            </Tag>
                            <Progress
                              percent={parseFloat(percent)}
                              strokeColor={colors[type] || '#52c41a'}
                              trailColor="#f0f0f0"
                              style={{ flex: 1 }}
                              format={() => `${count} (${percent}%)`}
                            />
                          </div>
                        );
                      })}
                  </Space>
                </div>
              )}

              {/* 元数据覆盖 */}
              {table.metadata_stats && Object.keys(table.metadata_stats).length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <Text strong style={{ display: 'block', marginBottom: 12, color: '#135200' }}>
                    元数据覆盖率
                  </Text>
                  <Row gutter={16}>
                    {Object.entries(table.metadata_stats).map(([key, val]) => {
                      const percent = (val.non_empty / val.total * 100).toFixed(0);
                      const labels = { functions: '函数信息', exports: '导出信息', imports: '依赖信息' };
                      return (
                        <Col span={8} key={key}>
                          <Tooltip title={`${val.non_empty} / ${val.total}`}>
                            <div style={{ textAlign: 'center', padding: 12, background: '#f6ffed', borderRadius: 8 }}>
                              <Progress
                                type="circle"
                                percent={parseFloat(percent)}
                                size={60}
                                strokeColor="#52c41a"
                                format={p => `${p}%`}
                              />
                              <div style={{ marginTop: 8 }}>
                                <Text type="secondary">{labels[key] || key}</Text>
                              </div>
                            </div>
                          </Tooltip>
                        </Col>
                      );
                    })}
                  </Row>
                </div>
              )}

              {/* 模块分布 Top 10 */}
              {Object.keys(table.modules_top10 || {}).length > 0 && (
                <div>
                  <Text strong style={{ display: 'block', marginBottom: 12, color: '#135200' }}>
                    模块分布 (Top 10)
                  </Text>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {Object.entries(table.modules_top10).map(([mod, count]) => (
                      <Tag key={mod} color="green">
                        {mod} <Text type="secondary">({count})</Text>
                      </Tag>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </Card>
      )}

      {/* 无数据提示 */}
      {lancedb && lancedb.tables?.length === 0 && (
        <Card style={{ background: '#fff', borderColor: '#d9f7be', textAlign: 'center', padding: 24 }}>
          <DatabaseOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />
          <Title level={5} type="secondary" style={{ marginTop: 16 }}>LanceDB 暂无数据</Title>
          <Text type="secondary">请先在 Training 页面索引项目</Text>
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
