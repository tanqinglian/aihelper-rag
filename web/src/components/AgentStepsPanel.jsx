/**
 * Agent 推理步骤面板
 *
 * 可视化展示 Agent 的多轮推理过程
 */
import { Timeline, Tag, Collapse, Typography, Spin, Card } from 'antd';
import {
  SearchOutlined, ApiOutlined, FileSearchOutlined,
  CheckCircleOutlined, LoadingOutlined, BulbOutlined,
  CodeOutlined, FunctionOutlined
} from '@ant-design/icons';

const { Text, Paragraph } = Typography;

const STEP_CONFIG = {
  thinking: {
    icon: <BulbOutlined />,
    color: 'orange',
    label: '分析中'
  },
  tool_call: {
    icon: <SearchOutlined />,
    color: 'blue',
    label: '调用工具'
  },
  tool_result: {
    icon: <FileSearchOutlined />,
    color: 'green',
    label: '工具结果'
  },
  final_answer: {
    icon: <CheckCircleOutlined />,
    color: 'green',
    label: '最终答案'
  },
  error: {
    icon: <ApiOutlined />,
    color: 'red',
    label: '错误'
  }
};

const TOOL_LABELS = {
  multi_search: '多项目搜索',
  trace_api: 'API 追踪',
  get_file: '获取文件',
  search_function: '搜索函数'
};

function ToolCallDetail({ metadata }) {
  if (!metadata) return null;

  const toolName = metadata.tool;
  const args = metadata.arguments || {};

  return (
    <div style={{ marginTop: 8, padding: 12, background: '#f6ffed', borderRadius: 8, fontSize: 13 }}>
      <div style={{ marginBottom: 8 }}>
        <Tag color="blue" icon={<CodeOutlined />}>
          {TOOL_LABELS[toolName] || toolName}
        </Tag>
      </div>
      <div style={{ color: '#666' }}>
        {Object.entries(args).map(([key, value]) => (
          <div key={key} style={{ marginBottom: 4 }}>
            <Text type="secondary">{key}: </Text>
            <Text code style={{ fontSize: 12 }}>
              {typeof value === 'object' ? JSON.stringify(value) : String(value)}
            </Text>
          </div>
        ))}
      </div>
    </div>
  );
}

function ToolResultDetail({ metadata }) {
  if (!metadata?.result) return null;

  const result = metadata.result;
  const sources = metadata.sources || [];

  return (
    <Collapse
      ghost
      size="small"
      style={{ marginTop: 8 }}
      items={[
        {
          key: '1',
          label: (
            <Text type="secondary" style={{ fontSize: 12 }}>
              查看结果 ({sources.length} 个文件)
            </Text>
          ),
          children: (
            <div style={{ maxHeight: 200, overflow: 'auto' }}>
              {sources.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <Text strong style={{ fontSize: 12, color: '#135200' }}>相关文件:</Text>
                  <div style={{ marginTop: 4 }}>
                    {sources.slice(0, 10).map((s, i) => (
                      <Tag key={i} style={{ margin: '2px 4px 2px 0', fontSize: 11 }}>
                        {s.path || s.project_id}
                      </Tag>
                    ))}
                  </div>
                </div>
              )}
              <pre style={{
                fontSize: 11,
                background: '#fafafa',
                padding: 8,
                borderRadius: 4,
                maxHeight: 150,
                overflow: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all'
              }}>
                {JSON.stringify(result, null, 2).slice(0, 1500)}
                {JSON.stringify(result).length > 1500 && '...'}
              </pre>
            </div>
          )
        }
      ]}
    />
  );
}

export function AgentStepsPanel({ steps, isRunning, currentStep }) {
  if (!steps?.length && !isRunning) return null;

  // 过滤掉 thinking 步骤，只显示有意义的步骤
  const displaySteps = steps.filter(s => s.step_type !== 'thinking' || s.step_type === 'final_answer');

  return (
    <Card
      size="small"
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FunctionOutlined style={{ color: '#52c41a' }} />
          <span>推理过程</span>
          {isRunning && <Spin size="small" />}
        </div>
      }
      style={{
        marginBottom: 16,
        background: '#fafafa',
        border: '1px solid #d9f7be'
      }}
      styles={{ body: { padding: 12 } }}
    >
      <Timeline
        items={[
          ...displaySteps.map((step, idx) => {
            const config = STEP_CONFIG[step.step_type] || STEP_CONFIG.thinking;

            return {
              key: idx,
              dot: config.icon,
              color: config.color,
              children: (
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <Tag color={config.color} style={{ margin: 0 }}>
                      Round {step.round}
                    </Tag>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {config.label}
                    </Text>
                  </div>

                  {step.step_type === 'tool_call' && (
                    <ToolCallDetail metadata={step.metadata} />
                  )}

                  {step.step_type === 'tool_result' && (
                    <ToolResultDetail metadata={step.metadata} />
                  )}

                  {step.step_type === 'final_answer' && step.metadata && (
                    <div style={{ marginTop: 8 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        共 {step.metadata.total_rounds} 轮，使用工具: {step.metadata.tools_used?.join(', ') || '无'}
                      </Text>
                    </div>
                  )}
                </div>
              )
            };
          }),
          ...(isRunning && currentStep ? [{
            key: 'running',
            dot: <LoadingOutlined />,
            color: 'blue',
            children: (
              <Text type="secondary">
                {currentStep.content || '分析中...'}
              </Text>
            )
          }] : [])
        ]}
      />
    </Card>
  );
}

export default AgentStepsPanel;
