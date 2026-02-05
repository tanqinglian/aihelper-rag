/**
 * 路由配置
 */
import { createBrowserRouter, Navigate } from 'react-router-dom';
import App from './App';
import ChatPage from './pages/ChatPage';
import TrainingPage from './pages/TrainingPage';
import MonitoringPage from './pages/MonitoringPage';

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
