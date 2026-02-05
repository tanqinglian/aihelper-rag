import { Outlet, useLocation } from 'react-router-dom';
import { Layout } from 'antd';
import { ProjectProvider } from './contexts/ProjectContext';
import Header from './components/Header';

export default function App() {
  const location = useLocation();
  const isChatPage = location.pathname === '/chat' || location.pathname === '/';

  return (
    <ProjectProvider>
      {isChatPage ? (
        <Outlet />
      ) : (
        <Layout style={{ minHeight: '100vh', background: '#f6ffed' }}>
          <Header />
          <Layout.Content style={{ padding: '24px', background: '#f6ffed' }}>
            <Outlet />
          </Layout.Content>
        </Layout>
      )}
    </ProjectProvider>
  );
}
