import { useState, useRef, useCallback } from 'react';
import { chatApi } from '../api/client';

export function useStreamingChat() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [streamingSources, setStreamingSources] = useState([]);
  const [error, setError] = useState(null);
  const abortControllerRef = useRef(null);

  const sendMessage = useCallback(async (projectId, question, onComplete) => {
    setIsStreaming(true);
    setStreamingContent('');
    setStreamingSources([]);
    setError(null);

    abortControllerRef.current = new AbortController();

    try {
      const response = await chatApi.askStream(projectId, question);

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let content = '';
      let sources = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        if (abortControllerRef.current?.signal.aborted) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'sources') {
                sources = data.data;
                setStreamingSources(sources);
              } else if (data.type === 'content') {
                content += data.data;
                setStreamingContent(content);
              } else if (data.type === 'done') {
                onComplete?.({ content, sources });
              }
            } catch {}
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message || '请求失败');
      }
    } finally {
      setIsStreaming(false);
      setStreamingContent('');
      setStreamingSources([]);
    }
  }, []);

  const cancelStream = useCallback(() => {
    abortControllerRef.current?.abort();
  }, []);

  return {
    isStreaming,
    streamingContent,
    streamingSources,
    error,
    sendMessage,
    cancelStream,
  };
}
