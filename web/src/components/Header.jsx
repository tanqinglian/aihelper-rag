import { useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import { MessageOutlined, SettingOutlined, DashboardOutlined, CodeOutlined } from '@ant-design/icons';

const menuItems = [
  { key: '/chat', icon: <MessageOutlined />, label: 'Chat' },
  { key: '/training', icon: <SettingOutlined />, label: '训练' },
  { key: '/monitoring', icon: <DashboardOutlined />, label: '监控' },
];

export default function Header() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout.Header style={{
      display: 'flex',
      alignItems: 'center',
      padding: '0 24px',
      background: '#fff',
      borderBottom: '1px solid #d9f7be',
      boxShadow: '0 2px 8px rgba(82, 196, 26, 0.08)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginRight: 40 }}>
        <div style={{
          width: 32,
          height: 32,
          borderRadius: 8,
          background: 'linear-gradient(135deg, #52c41a, #73d13d)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <CodeOutlined style={{ color: '#fff', fontSize: 18 }} />
        </div>
        <span style={{ fontSize: 18, fontWeight: 600, color: '#135200' }}>
          Code RAG
        </span>
      </div>

      <Menu
        mode="horizontal"
        selectedKeys={[location.pathname]}
        items={menuItems}
        onClick={({ key }) => navigate(key)}
        style={{
          flex: 1,
          background: 'transparent',
          borderBottom: 'none',
        }}
      />
    </Layout.Header>
  );
}
