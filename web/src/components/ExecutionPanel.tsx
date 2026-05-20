import { useWorkflowStore } from '../store/workflowStore';

export function ExecutionPanel() {
  const { executionLog, clearLog, isRunning } = useWorkflowStore();

  return (
    <div style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '12px' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '10px',
        }}
      >
        <h4 style={{ margin: 0, color: '#f8fafc' }}>
          📋 Execution Log
          {isRunning && (
            <span
              style={{
                marginLeft: '10px',
                fontSize: '11px',
                color: '#3b82f6',
              }}
            >
              ● Running
            </span>
          )}
        </h4>
        <button
          onClick={clearLog}
          style={{
            padding: '4px 8px',
            background: '#475569',
            color: '#e2e8f0',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '11px',
          }}
        >
          Clear
        </button>
      </div>

      <div
        style={{
          background: '#0f172a',
          padding: '10px',
          borderRadius: '6px',
          maxHeight: '140px',
          overflow: 'auto',
        }}
      >
        {executionLog.length === 0 ? (
          <div style={{ color: '#64748b' }}>
            No execution logs yet. Click "Run" to start.
          </div>
        ) : (
          executionLog.map((log, index) => (
            <div
              key={index}
              style={{
                padding: '2px 0',
                borderBottom: '1px solid #1e293b',
              }}
            >
              {log}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
