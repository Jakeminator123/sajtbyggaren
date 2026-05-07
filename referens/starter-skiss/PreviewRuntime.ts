export type PreviewRuntimeKind = 'stackblitz' | 'local' | 'fly' | 'vm';

export interface PreviewFile {
  path: string;
  content: string;
}

export interface PreviewRuntimeConfig {
  kind: PreviewRuntimeKind;
  projectName: string;
  env?: Record<string, string>;
}

export interface PreviewSession {
  id: string;
  url: string;
  kind: PreviewRuntimeKind;
  createdAt: string;
}

export interface PreviewRuntime {
  readonly kind: PreviewRuntimeKind;
  start(files: PreviewFile[], config: PreviewRuntimeConfig): Promise<PreviewSession>;
  stop(sessionId: string): Promise<void>;
}
