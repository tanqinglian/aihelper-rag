/**
 * Agent 多轮推理 Hook
 */
import { useState, useRef, useCallback } from 'react';
import { agentApi } from '../api/client';

export function useAgentChat() {
  const [isRunning, setIsRunning] = useState(false);
  const [steps, setSteps] = useState([]);
  const [currentStep, setCurrentStep] = useState(null);
  const [finalAnswer, setFinalAnswer] = useState('');
  const [sources, setSources] = useState([]);
  const [error, setError] = useState(null);
  const abortControllerRef = useRef(null);

  const runAgent = useCallback(async (projectIds, question, onComplete) => {
    setIsRunning(true);
    setSteps([]);
    setCurrentStep(null);
    setFinalAnswer('');
    setSources([]);
    setError(null);

    abortControllerRef.current = new AbortController();

    try {
      const response = await agentApi.askAgent(projectIds, question, 5);

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      const allSteps = [];
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'step') {
                const step = data.data;
                allSteps.push(step);
                setSteps([...allSteps]);
                setCurrentStep(step);

              } else if (data.type === 'complete') {
                setFinalAnswer(data.data.answer);
                setSources(data.data.sources || []);
                onComplete?.({
                  answer: data.data.answer,
                  sources: data.data.sources,
                  steps: allSteps
                });
              }
            } catch (e) {
              console.error('Parse error:', e);
            }
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message || 'Agent 请求失败');
        console.error('Agent error:', err);
      }
    } finally {
      setIsRunning(false);
      setCurrentStep(null);
    }
  }, []);

  const cancelAgent = useCallback(() => {
    abortControllerRef.current?.abort();
    setIsRunning(false);
  }, []);

  const reset = useCallback(() => {
    setSteps([]);
    setCurrentStep(null);
    setFinalAnswer('');
    setSources([]);
    setError(null);
  }, []);

  return {
    isRunning,
    steps,
    currentStep,
    finalAnswer,
    sources,
    error,
    runAgent,
    cancelAgent,
    reset,
  };
}

export default useAgentChat;
