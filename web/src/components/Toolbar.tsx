import { useCallback } from 'react';
import type { WorkflowNode } from '../store/workflowStore';
import { useWorkflowStore } from '../store/workflowStore';

interface ToolbarProps {
  nodes: WorkflowNode[];
  setNodes: (nodes: WorkflowNode[]) => void;
}

export function Toolbar({ nodes, setNodes }: ToolbarProps) {
  const { addNode, isRunning, setRunning, addLog } = useWorkflowStore();

  const onDragStart = useCallback(
    (event: React.DragEvent, nodeType: string) => {
      event.dataTransfer.setData('application/reactflow', nodeType);
      event.dataTransfer.effectAllowed = 'move';
    },
    []
  );

  const addNewNode = useCallback(
    (type: string) => {
      const id = `${type}_${Date.now()}`;
      const newNode: WorkflowNode = {
        id,
        type: type as any,
        position: {
          x: Math.random() * 400 + 100,
          y: Math.random() * 400 + 100,
        },
        data: {
          label: `New ${type}`,
          type: type as any,
          status: 'idle',
          ...(type === 'task' && { agent: 'claude-code', prompt: '' }),
          ...(type === 'condition' && {
            condition: {
              field: '',
              operator: 'eq',
              value: '',
              then: '',
              else: '',
            },
          }),
          ...(type === 'loop' && {
            loop: {
              type: 'for_each',
              items: [],
              body: [],
            },
          }),
        },
      };
      addNode(newNode);
    },
    [addNode]
  );

  const handleRun = useCallback(() => {
    setRunning(true);
    addLog('Starting workflow execution...');
    // Simulate execution
    setTimeout(() => {
      setRunning(false);
      addLog('Workflow execution completed!');
    }, 3000);
  }, [setRunning, addLog]);

  const handleStop = useCallback(() => {
    setRunning(false);
    addLog('Workflow execution stopped.');
  }, [setRunning, addLog]);

  const handleExport = useCallback(() => {
    const workflow = {
      name: 'My Workflow',
      agents: {},
      tasks: nodes
        .filter((n) => n.data.type === 'task')
        .map((n) => ({
          id: n.id,
          agent: n.data.agent || 'claude-code',
          prompt: n.data.prompt || '',
        })),
      conditions: nodes
        .filter((n) => n.data.type === 'condition')
        .map((n) => ({
          id: n.id,
          condition: n.data.condition,
        })),
      loops: nodes
        .filter((n) => n.data.type === 'loop')
        .map((n) => ({
          id: n.id,
          loop: n.data.loop,
        })),
    };
    const blob = new Blob([JSON.stringify(workflow, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'workflow.json';
    a.click();
    URL.revokeObjectURL(url);
  }, [nodes]);

  return (
    <div>
      <h3 style={{ margin: '0 0 15px 0', color: '#1e293b' }}>Toolbar</h3>

      {/* Node palette */}
      <div style={{ marginBottom: '20px' }}>
        <h4 style={{ margin: '0 0 10px 0', color: '#475569', fontSize: '14px' }}>
          Add Nodes
        </h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div
            draggable
            onDragStart={(e) => onDragStart(e, 'task')}
            onClick={() => addNewNode('task')}
            style={{
              padding: '10px',
              background: '#3b82f6',
              color: 'white',
              borderRadius: '6px',
              cursor: 'grab',
              textAlign: 'center',
              fontSize: '13px',
            }}
          >
            ⚡ Task Node
          </div>
          <div
            draggable
            onDragStart={(e) => onDragStart(e, 'condition')}
            onClick={() => addNewNode('condition')}
            style={{
              padding: '10px',
              background: '#8b5cf6',
              color: 'white',
              borderRadius: '6px',
              cursor: 'grab',
              textAlign: 'center',
              fontSize: '13px',
            }}
          >
            ❓ Condition Node
          </div>
          <div
            draggable
            onDragStart={(e) => onDragStart(e, 'loop')}
            onClick={() => addNewNode('loop')}
            style={{
              padding: '10px',
              background: '#f59e0b',
              color: 'white',
              borderRadius: '6px',
              cursor: 'grab',
              textAlign: 'center',
              fontSize: '13px',
            }}
          >
            🔄 Loop Node
          </div>
        </div>
      </div>

      {/* Actions */}
      <div style={{ marginBottom: '20px' }}>
        <h4 style={{ margin: '0 0 10px 0', color: '#475569', fontSize: '14px' }}>
          Actions
        </h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <button
            onClick={isRunning ? handleStop : handleRun}
            style={{
              padding: '10px',
              background: isRunning ? '#ef4444' : '#10b981',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '13px',
            }}
          >
            {isRunning ? '⏹ Stop' : '▶ Run'}
          </button>
          <button
            onClick={handleExport}
            style={{
              padding: '10px',
              background: '#6366f1',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '13px',
            }}
          >
            📥 Export YAML
          </button>
        </div>
      </div>

      {/* Stats */}
      <div
        style={{
          padding: '10px',
          background: '#f1f5f9',
          borderRadius: '6px',
          fontSize: '12px',
        }}
      >
        <div>Nodes: {nodes.length}</div>
        <div>
          Tasks: {nodes.filter((n) => n.data.type === 'task').length}
        </div>
        <div>
          Conditions: {nodes.filter((n) => n.data.type === 'condition').length}
        </div>
        <div>
          Loops: {nodes.filter((n) => n.data.type === 'loop').length}
        </div>
      </div>
    </div>
  );
}
