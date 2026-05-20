import { useCallback, useRef } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type NodeTypes,
  type EdgeTypes,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { useWorkflowStore, type WorkflowNode } from '../store/workflowStore';
import { nodeTypes } from './CustomNodes';
import { Toolbar } from './Toolbar';
import { NodeEditor } from './NodeEditor';
import { ExecutionPanel } from './ExecutionPanel';

const initialNodes: WorkflowNode[] = [
  {
    id: '1',
    type: 'task',
    position: { x: 250, y: 50 },
    data: {
      label: 'Setup Backend',
      type: 'task',
      agent: 'claude-code',
      prompt: 'Create a FastAPI backend with health endpoint',
      status: 'idle',
    },
  },
  {
    id: '2',
    type: 'task',
    position: { x: 100, y: 200 },
    data: {
      label: 'Setup Frontend',
      type: 'task',
      agent: 'claude-code',
      prompt: 'Create a React frontend with routing',
      status: 'idle',
    },
  },
  {
    id: '3',
    type: 'task',
    position: { x: 400, y: 200 },
    data: {
      label: 'Write Tests',
      type: 'task',
      agent: 'codex',
      prompt: 'Write unit tests for backend and frontend',
      status: 'idle',
    },
  },
  {
    id: '4',
    type: 'condition',
    position: { x: 250, y: 350 },
    data: {
      label: 'Check Tests',
      type: 'condition',
      condition: {
        field: 'tests_passed',
        operator: 'eq',
        value: true,
        then: '5',
        else: '3',
      },
    },
  },
  {
    id: '5',
    type: 'task',
    position: { x: 250, y: 500 },
    data: {
      label: 'Deploy',
      type: 'task',
      agent: 'claude-code',
      prompt: 'Deploy the application',
      status: 'idle',
    },
  },
];

const initialEdges = [
  {
    id: 'e1-2',
    source: '1',
    target: '2',
    animated: true,
    style: { stroke: '#3b82f6' },
  },
  {
    id: 'e1-3',
    source: '1',
    target: '3',
    animated: true,
    style: { stroke: '#3b82f6' },
  },
  {
    id: 'e2-4',
    source: '2',
    target: '4',
    animated: true,
    style: { stroke: '#3b82f6' },
  },
  {
    id: 'e3-4',
    source: '3',
    target: '4',
    animated: true,
    style: { stroke: '#3b82f6' },
  },
  {
    id: 'e4-5-then',
    source: '4',
    target: '5',
    sourceHandle: 'then',
    animated: true,
    style: { stroke: '#10b981' },
    label: 'Yes',
  },
  {
    id: 'e4-3-else',
    source: '4',
    target: '3',
    sourceHandle: 'else',
    animated: true,
    style: { stroke: '#ef4444' },
    label: 'No',
    markerEnd: { type: MarkerType.ArrowClosed },
  },
];

export function WorkflowEditor() {
  const { nodes: storeNodes, edges: storeEdges, selectNode } = useWorkflowStore();
  const [nodes, setNodes, onNodesChange] = useNodesState(
    storeNodes.length > 0 ? storeNodes : initialNodes
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState(
    storeEdges.length > 0 ? storeEdges : initialEdges
  );
  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) =>
        addEdge(
          {
            ...params,
            animated: true,
            style: { stroke: '#3b82f6' },
          },
          eds
        )
      );
    },
    [setEdges]
  );

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: WorkflowNode) => {
      selectNode(node.id);
    },
    [selectNode]
  );

  const onPaneClick = useCallback(() => {
    selectNode(null);
  }, [selectNode]);

  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      {/* Left sidebar - Toolbar */}
      <div
        style={{
          width: '250px',
          background: '#f8fafc',
          borderRight: '1px solid #e2e8f0',
          padding: '10px',
        }}
      >
        <Toolbar nodes={nodes} setNodes={setNodes} />
      </div>

      {/* Main canvas */}
      <div ref={reactFlowWrapper} style={{ flex: 1 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes as NodeTypes}
          fitView
          style={{ background: '#f1f5f9' }}
        >
          <Background />
          <Controls />
          <MiniMap
            nodeStrokeColor="#3b82f6"
            nodeColor="#dbeafe"
            nodeBorderRadius={2}
          />
        </ReactFlow>
      </div>

      {/* Right sidebar - Node Editor */}
      <div
        style={{
          width: '300px',
          background: '#f8fafc',
          borderLeft: '1px solid #e2e8f0',
          padding: '10px',
        }}
      >
        <NodeEditor />
      </div>

      {/* Bottom panel - Execution */}
      <div
        style={{
          position: 'fixed',
          bottom: 0,
          left: '250px',
          right: '300px',
          height: '200px',
          background: '#1e293b',
          borderTop: '1px solid #334155',
          padding: '10px',
          overflow: 'auto',
        }}
      >
        <ExecutionPanel />
      </div>
    </div>
  );
}
