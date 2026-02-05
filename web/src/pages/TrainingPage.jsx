import { useState } from 'react';
import { Card, Button, Progress, Modal, Form, Input, Space, Tag, Typography, Collapse, Popconfirm, message } from 'antd';
import { PlusOutlined, SyncOutlined, DeleteOutlined, FolderOpenOutlined, SettingOutlined } from '@ant-design/icons';
import { useProjectContext } from '../contexts/ProjectContext';
import { projectApi, indexApi } from '../api/client';

const { Text, Title } = Typography;

const statusMap = {
  idle: { color: 'default', text: '未索引' },
  indexing: { color: 'processing', text: '索引中' },
  indexed: { color: 'success', text: '已索引' },
  error: { color: 'error', text: '失败' },
};

export default function TrainingPage() {
  const { projects, refreshProjects, updateProjectInList } = useProjectContext();
  const [showModal, setShowModal] = useState(false);
  const [indexingProjectId, setIndexingProjectId] = useState(null);
  const [indexProgress, setIndexProgress] = useState(null);

  const startIndexing = async (projectId) => {
    setIndexingProjectId(projectId);
    setIndexProgress({ type: 'scan_start', data: { message: '准备中...' } });
    updateProjectInList(projectId, { status: 'indexing' });

    try {
      const response = await fetch(indexApi.getIndexUrl(projectId), { method: 'POST' });
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6));
              setIndexProgress(event);
              if (event.type === 'complete') {
                updateProjectInList(projectId, {
                  status: 'indexed',
                  file_count: event.data.file_count,
                  index_size_bytes: event.data.index_size_bytes,
                });
              } else if (event.type === 'error') {
                updateProjectInList(projectId, { status: 'error' });
              }
            } catch {}
          }
        }
      }
    } catch {
      updateProjectInList(projectId, { status: 'error' });
    } finally {
      setTimeout(() => { setIndexingProjectId(null); setIndexProgress(null); refreshProjects(); }, 1000);
    }
  };

  const deleteProject = async (project) => {
    try {
      await projectApi.delete(project.id);
      message.success('已删除');
      refreshProjects();
    } catch (err) {
      message.error('删除失败: ' + err.message);
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <Title level={3} style={{ margin: 0, color: '#135200' }}>知识训练</Title>
          <Text type="secondary">管理项目并构建向量索引</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowModal(true)}>
          添加项目
        </Button>
      </div>

      <Space direction="vertical" style={{ width: '100%' }} size={16}>
        {projects.length === 0 ? (
          <Card style={{ textAlign: 'center', padding: 40, background: '#fff', borderColor: '#d9f7be' }}>
            <FolderOpenOutlined style={{ fontSize: 48, color: '#b7eb8f', marginBottom: 16 }} />
            <div><Text type="secondary">还没有项目，点击上方按钮添加</Text></div>
          </Card>
        ) : projects.map(project => (
          <ProjectCard
            key={project.id}
            project={project}
            isIndexing={indexingProjectId === project.id}
            progress={indexingProjectId === project.id ? indexProgress : null}
            onIndex={() => startIndexing(project.id)}
            onDelete={() => deleteProject(project)}
          />
        ))}
      </Space>

      <AddProjectModal
        open={showModal}
        onClose={() => setShowModal(false)}
        onCreated={(project) => { setShowModal(false); refreshProjects(); startIndexing(project.id); }}
      />
    </div>
  );
}

function ProjectCard({ project, isIndexing, progress, onIndex, onDelete }) {
  const st = statusMap[project.status] || statusMap.idle;

  const configItems = [{
    key: '1',
    label: <span><SettingOutlined style={{ marginRight: 8 }} />配置详情</span>,
    children: (
      <Space direction="vertical" size={4}>
        <Text type="secondary">文件类型: <Text style={{ color: 'rgba(0,0,0,0.65)' }}>{project.config.extensions.join(', ')}</Text></Text>
        <Text type="secondary">忽略目录: <Text style={{ color: 'rgba(0,0,0,0.65)' }}>{project.config.ignore_dirs.join(', ')}</Text></Text>
        <Text type="secondary">单文件上限: <Text style={{ color: 'rgba(0,0,0,0.65)' }}>{project.config.max_file_chars} 字符</Text></Text>
      </Space>
    ),
  }];

  return (
    <Card style={{ background: '#fff', borderColor: '#d9f7be', boxShadow: '0 2px 8px rgba(82, 196, 26, 0.08)' }} styles={{ body: { padding: 20 } }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
        <div style={{
          width: 40, height: 40, borderRadius: 8, background: '#f6ffed',
          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>
          <FolderOpenOutlined style={{ fontSize: 20, color: '#52c41a' }} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <Text strong style={{ fontSize: 15, color: '#135200' }}>{project.name}</Text>
            <Tag color={st.color}>{st.text}</Tag>
          </div>
          <Text type="secondary" style={{ fontSize: 13, wordBreak: 'break-all', display: 'block' }}>{project.source_dir}</Text>
          {project.status === 'indexed' && (
            <Text type="secondary" style={{ fontSize: 12, marginTop: 4, display: 'block' }}>
              {project.file_count} 文件 · {(project.index_size_bytes / 1024 / 1024).toFixed(1)} MB
            </Text>
          )}
        </div>
      </div>

      {/* 索引进度 */}
      {isIndexing && progress && (
        <div style={{ marginTop: 16, padding: 12, background: '#f6ffed', borderRadius: 8 }}>
          {progress.type === 'indexing' ? (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <Text type="secondary" ellipsis style={{ maxWidth: '70%', fontSize: 13 }}>{progress.data.current_file}</Text>
                <Text style={{ color: '#52c41a', fontWeight: 500 }}>{progress.data.percent}%</Text>
              </div>
              <Progress percent={progress.data.percent} showInfo={false} strokeColor="#52c41a" trailColor="#d9f7be" size="small" />
              <Text type="secondary" style={{ fontSize: 12, marginTop: 4, display: 'block' }}>
                {progress.data.current} / {progress.data.total} 文件 · 预计剩余 {progress.data.estimated_remaining_seconds}s
              </Text>
            </>
          ) : progress.type === 'complete' ? (
            <Text style={{ color: '#52c41a', fontSize: 13 }}>索引完成！共 {progress.data.file_count} 个文件</Text>
          ) : progress.type === 'error' ? (
            <Text style={{ color: '#ff4d4f', fontSize: 13 }}>{progress.data.message}</Text>
          ) : (
            <Text type="secondary" style={{ fontSize: 13 }}>{progress.data?.message || '处理中...'}</Text>
          )}
        </div>
      )}

      {/* 操作按钮 */}
      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        {project.status === 'indexed' ? (
          <Button size="small" icon={<SyncOutlined />} onClick={onIndex} disabled={isIndexing}>重新索引</Button>
        ) : (project.status === 'idle' || project.status === 'error') ? (
          <Button size="small" type="primary" onClick={onIndex} disabled={isIndexing}>
            {project.status === 'error' ? '重试' : '开始索引'}
          </Button>
        ) : null}
        <Popconfirm title="确定删除?" onConfirm={onDelete} disabled={isIndexing}>
          <Button size="small" danger icon={<DeleteOutlined />} disabled={isIndexing}>删除</Button>
        </Popconfirm>
      </div>

      {/* 配置折叠 */}
      <Collapse items={configItems} ghost size="small"
        style={{ marginTop: 12, background: 'transparent' }}
      />
    </Card>
  );
}

function AddProjectModal({ open, onClose, onCreated }) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      const config = {
        extensions: values.extensions.split(',').map(s => s.trim()).filter(Boolean),
        ignore_dirs: values.ignoreDirs.split(',').map(s => s.trim()).filter(Boolean),
        max_file_chars: parseInt(values.maxChars) || 6000,
      };
      const project = await projectApi.create({ name: values.name, source_dir: values.sourceDir, config });
      form.resetFields();
      onCreated(project);
    } catch (err) {
      if (err.message) message.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal title="添加新项目" open={open} onCancel={onClose} onOk={handleSubmit}
      confirmLoading={loading} okText="创建并开始索引" cancelText="取消" destroyOnClose>
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}
        initialValues={{
          extensions: '.js, .jsx, .ts, .tsx, .less, .css, .vue',
          ignoreDirs: 'node_modules, .umi, .git, dist, __pycache__',
          maxChars: '6000',
        }}>
        <Form.Item name="name" label="项目名称" rules={[{ required: true, message: '请输入项目名称' }]}>
          <Input placeholder="my-awesome-project" />
        </Form.Item>
        <Form.Item name="sourceDir" label="源码目录" rules={[{ required: true, message: '请输入源码目录' }]}
          extra="请输入绝对路径">
          <Input placeholder="/Users/yourname/project/src" />
        </Form.Item>
        <Collapse ghost items={[{
          key: '1',
          label: '高级配置',
          children: (
            <>
              <Form.Item name="extensions" label="文件类型 (逗号分隔)"><Input /></Form.Item>
              <Form.Item name="ignoreDirs" label="忽略目录 (逗号分隔)"><Input /></Form.Item>
              <Form.Item name="maxChars" label="单文件上限 (字符)"><Input type="number" /></Form.Item>
            </>
          ),
        }]} />
      </Form>
    </Modal>
  );
}
