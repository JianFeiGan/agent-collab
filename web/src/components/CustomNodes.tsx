import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { WorkflowNode } from '../store/workflowStore';

const statusColors = {
  idle: '#6b7280',
  running: '#3b82f6',
  success: '#10b981',
  failed: '#ef4444',
};

export const TaskNode = memo(({ data, selected }: NodeProps<WorkflowNode>) => {
  const status = data.status || 'idle';
  const borderColor = statusColors[status];

  return (
    <div
      style={{
        padding: '10px 15px',
        border: `2px solid ${borderColor}`,
        borderRadius: '8px',
        background: selected ? '#f0f9ff' : '#ffffff',
        minWidth: '150px',
        boxShadow: selected ? '0 0 0 2px #3b82f6' : 'none',
      }}
    >
      <Handle type="target" position={Position.Top} />
      <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
        {data.label}
      </div>
      {data.agent && (
        <div style={{ fontSize: '12px', color: '#6b7280' }}>
          Agent: {data.agent}
        </div>
      )}
      {data.status && (
        <div
          style={{
            fontSize: '11px',
            color: borderColor,
            marginTop: '4px',
            fontWeight: '500',
          }}
        >
          {status.toUpperCase()}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
});

TaskNode.displayName = 'TaskNode';

export const ConditionNode = memo(({ data, selected }: NodeProps<WorkflowNode>) => {
  return (
    <div
      style={{
        padding: '10px 15px',
        border: '2px solid #8b5cf6',
        borderRadius: '8px',
        background: selected ? '#f5f3ff' : '#ffffff',
        minWidth: '150px',
        boxShadow: selected ? '0 0 0 2px #8b5cf6' : 'none',
      }}
    >
      <Handle type="target" position={Position.Top} />
      <div style={{ fontWeight: 'bold', marginBottom: '4px', color: '#8b5cf6' }}>
        ❓ {data.label}
      </div>
      {data.condition && (
        <div style={{ fontSize: '11px', color: '#6b7280' }}>
          {data.condition.field} {data.condition.operator} {data.condition.value}
        </div>
      )}
      <Handle
        type="source"
        position={Position.Bottom}
        id="then"
        style={{ left: '30%' }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="else"
        style={{ left: '70%' }}
      />
    </div>
  );
});

ConditionNode.displayName = 'ConditionNode';

export const LoopNode = memo(({ data, selected }: NodeProps<WorkflowNode>) => {
  return (
    <div
      style={{
        padding: '10px 15px',
        border: '2px solid #f59e0b',
        borderRadius: '8px',
        background: selected ? '#fffbeb' : '#ffffff',
        minWidth: '150px',
        boxShadow: selected ? '0 0 0 2px #f59e0b' : 'none',
      }}
    >
      <Handle type="target" position={Position.Top} />
      <div style={{ fontWeight: 'bold', marginBottom: '4px', color: '#f59e0b' }}>
        🔄 {data.label}
      </div>
      {data.loop && (
        <div style={{ fontSize: '11px', color: '#6b7280' }}>
          Type: {data.loop.type}
          {data.loop.items && ` | Items: ${data.loop.items}`}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
});

LoopNode.displayName = 'LoopNode';

export const nodeTypes = {
  task: TaskNode,
  condition: ConditionNode,
  loop: LoopNode,
};
