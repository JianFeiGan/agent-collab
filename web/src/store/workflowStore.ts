import { create } from 'zustand';
import type { Node, Edge } from '@xyflow/react';

export interface WorkflowNode extends Node {
  data: {
    label: string;
    type: 'task' | 'condition' | 'loop' | 'parallel';
    agent?: string;
    prompt?: string;
    condition?: {
      field: string;
      operator: string;
      value: any;
      then: string;
      else?: string;
    };
    loop?: {
      type: 'for_each' | 'while';
      items?: string | any[];
      condition?: string;
      body: string[];
    };
    status?: 'idle' | 'running' | 'success' | 'failed';
    result?: string;
  };
}

export interface WorkflowEdge extends Edge {
  animated?: boolean;
  style?: React.CSSProperties;
}

interface WorkflowState {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  selectedNode: string | null;
  isRunning: boolean;
  executionLog: string[];

  // Actions
  setNodes: (nodes: WorkflowNode[]) => void;
  setEdges: (edges: WorkflowEdge[]) => void;
  addNode: (node: WorkflowNode) => void;
  removeNode: (nodeId: string) => void;
  updateNode: (nodeId: string, data: Partial<WorkflowNode['data']>) => void;
  addEdge: (edge: WorkflowEdge) => void;
  removeEdge: (edgeId: string) => void;
  selectNode: (nodeId: string | null) => void;
  setRunning: (running: boolean) => void;
  addLog: (message: string) => void;
  clearLog: () => void;
  resetWorkflow: () => void;
}

export const useWorkflowStore = create<WorkflowState>((set) => ({
  nodes: [],
  edges: [],
  selectedNode: null,
  isRunning: false,
  executionLog: [],

  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),

  addNode: (node) =>
    set((state) => ({
      nodes: [...state.nodes, node],
    })),

  removeNode: (nodeId) =>
    set((state) => ({
      nodes: state.nodes.filter((n) => n.id !== nodeId),
      edges: state.edges.filter(
        (e) => e.source !== nodeId && e.target !== nodeId
      ),
    })),

  updateNode: (nodeId, data) =>
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.id === nodeId ? { ...n, data: { ...n.data, ...data } } : n
      ),
    })),

  addEdge: (edge) =>
    set((state) => ({
      edges: [...state.edges, edge],
    })),

  removeEdge: (edgeId) =>
    set((state) => ({
      edges: state.edges.filter((e) => e.id !== edgeId),
    })),

  selectNode: (nodeId) => set({ selectedNode: nodeId }),

  setRunning: (running) => set({ isRunning: running }),

  addLog: (message) =>
    set((state) => ({
      executionLog: [
        ...state.executionLog,
        `[${new Date().toLocaleTimeString()}] ${message}`,
      ],
    })),

  clearLog: () => set({ executionLog: [] }),

  resetWorkflow: () =>
    set({
      nodes: [],
      edges: [],
      selectedNode: null,
      isRunning: false,
      executionLog: [],
    }),
}));
