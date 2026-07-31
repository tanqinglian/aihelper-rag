/**
 * 路由配置
 */
import { createBrowserRouter, Navigate } from 'react-router-dom';
import App from './App';
import ChatPage from './pages/ChatPage';
import TrainingPage from './pages/TrainingPage';
import MonitoringPage from './pages/MonitoringPage';
import DesignPage from './pages/DesignPage';

const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      {
        index: true,
        element: <Navigate to="/chat" replace />,
      },
      {
        path: 'chat',
        element: <ChatPage />,
      },
      {
        path: 'design',
        element: <DesignPage />,
      },
      {
        path: 'training',
        element: <TrainingPage />,
      },
      {
        path: 'monitoring',
        element: <MonitoringPage />,
      },
    ],
  },
]);

export default router;
