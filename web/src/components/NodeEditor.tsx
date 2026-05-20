import { useCallback } from 'react';
import { useWorkflowStore } from '../store/workflowStore';

export function NodeEditor() {
  const { nodes, selectedNode, updateNode, removeNode } = useWorkflowStore();

  const node = nodes.find((n) => n.id === selectedNode);

  const handleLabelChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (selectedNode) {
        updateNode(selectedNode, { label: e.target.value });
      }
    },
    [selectedNode, updateNode]
  );

  const handleAgentChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      if (selectedNode) {
        updateNode(selectedNode, { agent: e.target.value });
      }
    },
    [selectedNode, updateNode]
  );

  const handlePromptChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      if (selectedNode) {
        updateNode(selectedNode, { prompt: e.target.value });
      }
    },
    [selectedNode, updateNode]
  );

  const handleDelete = useCallback(() => {
    if (selectedNode) {
      removeNode(selectedNode);
    }
  }, [selectedNode, removeNode]);

  if (!node) {
    return (
      <div style={{ color: '#94a3b8', textAlign: 'center', marginTop: '50px' }}>
        Select a node to edit
      </div>
    );
  }

  return (
    <div>
      <h3 style={{ margin: '0 0 15px 0', color: '#1e293b' }}>Node Editor</h3>

      {/* Label */}
      <div style={{ marginBottom: '15px' }}>
        <label
          style={{
            display: 'block',
            marginBottom: '5px',
            fontSize: '13px',
            color: '#475569',
          }}
        >
          Label
        </label>
        <input
          type="text"
          value={node.data.label}
          onChange={handleLabelChange}
          style={{
            width: '100%',
            padding: '8px',
            border: '1px solid #e2e8f0',
            borderRadius: '4px',
            fontSize: '13px',
          }}
        />
      </div>

      {/* Agent (for task nodes) */}
      {node.data.type === 'task' && (
        <>
          <div style={{ marginBottom: '15px' }}>
            <label
              style={{
                display: 'block',
                marginBottom: '5px',
                fontSize: '13px',
                color: '#475569',
              }}
            >
              Agent
            </label>
            <select
              value={node.data.agent || 'claude-code'}
              onChange={handleAgentChange}
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #e2e8f0',
                borderRadius: '4px',
                fontSize: '13px',
              }}
            >
              <option value="claude-code">Claude Code</option>
              <option value="codex">Codex</option>
              <option value="aider">Aider</option>
              <option value="opencode">OpenCode</option>
            </select>
          </div>

          <div style={{ marginBottom: '15px' }}>
            <label
              style={{
                display: 'block',
                marginBottom: '5px',
                fontSize: '13px',
                color: '#475569',
              }}
            >
              Prompt
            </label>
            <textarea
              value={node.data.prompt || ''}
              onChange={handlePromptChange}
              rows={4}
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #e2e8f0',
                borderRadius: '4px',
                fontSize: '13px',
                resize: 'vertical',
              }}
            />
          </div>
        </>
      )}

      {/* Condition (for condition nodes) */}
      {node.data.type === 'condition' && node.data.condition && (
        <div style={{ marginBottom: '15px' }}>
          <label
            style={{
              display: 'block',
              marginBottom: '5px',
              fontSize: '13px',
              color: '#475569',
            }}
          >
            Condition
          </label>
          <div
            style={{
              padding: '10px',
              background: '#f1f5f9',
              borderRadius: '4px',
              fontSize: '12px',
            }}
          >
            <div>Field: {node.data.condition.field}</div>
            <div>Operator: {node.data.condition.operator}</div>
            <div>Value: {node.data.condition.value}</div>
            <div>Then: {node.data.condition.then}</div>
            {node.data.condition.else && (
              <div>Else: {node.data.condition.else}</div>
            )}
          </div>
        </div>
      )}

      {/* Loop (for loop nodes) */}
      {node.data.type === 'loop' && node.data.loop && (
        <div style={{ marginBottom: '15px' }}>
          <label
            style={{
              display: 'block',
              marginBottom: '5px',
              fontSize: '13px',
              color: '#475569',
            }}
          >
            Loop Configuration
          </label>
          <div
            style={{
              padding: '10px',
              background: '#f1f5f9',
              borderRadius: '4px',
              fontSize: '12px',
            }}
          >
            <div>Type: {node.data.loop.type}</div>
            {node.data.loop.items && (
              <div>Items: {JSON.stringify(node.data.loop.items)}</div>
            )}
            {node.data.loop.condition && (
              <div>Condition: {node.data.loop.condition}</div>
            )}
            <div>Body: {node.data.loop.body.join(', ')}</div>
          </div>
        </div>
      )}

      {/* Status */}
      <div style={{ marginBottom: '15px' }}>
        <label
          style={{
            display: 'block',
            marginBottom: '5px',
            fontSize: '13px',
            color: '#475569',
          }}
        >
          Status
        </label>
        <div
          style={{
            padding: '8px',
            background:
              node.data.status === 'success'
                ? '#dcfce7'
                : node.data.status === 'failed'
                ? '#fee2e2'
                : node.data.status === 'running'
                ? '#dbeafe'
                : '#f1f5f9',
            borderRadius: '4px',
            fontSize: '13px',
            color:
              node.data.status === 'success'
                ? '#166534'
                : node.data.status === 'failed'
                ? '#991b1b'
                : node.data.status === 'running'
                ? '#1e40af'
                : '#475569',
          }}
        >
          {node.data.status?.toUpperCase() || 'IDLE'}
        </div>
      </div>

      {/* Result */}
      {node.data.result && (
        <div style={{ marginBottom: '15px' }}>
          <label
            style={{
              display: 'block',
              marginBottom: '5px',
              fontSize: '13px',
              color: '#475569',
            }}
          >
            Result
          </label>
          <pre
            style={{
              padding: '10px',
              background: '#f1f5f9',
              borderRadius: '4px',
              fontSize: '11px',
              overflow: 'auto',
              maxHeight: '150px',
            }}
          >
            {node.data.result}
          </pre>
        </div>
      )}

      {/* Delete button */}
      <button
        onClick={handleDelete}
        style={{
          width: '100%',
          padding: '10px',
          background: '#ef4444',
          color: 'white',
          border: 'none',
          borderRadius: '6px',
          cursor: 'pointer',
          fontSize: '13px',
        }}
      >
        🗑 Delete Node
      </button>
    </div>
  );
}
