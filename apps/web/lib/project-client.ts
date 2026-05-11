// Client-side API for project operations

export interface Project {
  id: string;
  name: string;
  category?: string;
  description?: string;
  thumbnail_path?: string;
  demo_url?: string | null;
  created_at: string;
  updated_at: string;
}

export type PersistedFile = { name: string; content: string } | Record<string, unknown>;

export type PersistedMessage =
  | {
      id?: string;
      role?: string;
      content?: string;
      timestamp?: string | Date;
      attachments?: unknown;
    }
  | Record<string, unknown>;

export interface ProjectData {
  project_id: string;
  chat_id?: string;
  demo_url?: string;
  current_code?: string;
  files: PersistedFile[];
  messages: PersistedMessage[];
  meta?: Record<string, unknown> | null;
}

export interface ProjectWithData {
  project: Project;
  data: ProjectData | null;
}

// Get all projects
export async function getProjects(): Promise<Project[]> {
  const response = await fetch("/api/projects");
  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || "Failed to get projects");
  }

  return data.projects;
}

// Get single project with data
export async function getProject(id: string): Promise<ProjectWithData> {
  const response = await fetch(`/api/projects/${id}`);
  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || "Failed to get project");
  }

  return { project: data.project, data: data.data };
}

// Create new project
export async function createProject(
  name: string,
  category?: string,
  description?: string,
): Promise<Project> {
  const response = await fetch("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, category, description }),
  });
  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || "Failed to create project");
  }

  return data.project;
}

// Update project
export async function updateProject(id: string, updates: Partial<Project>): Promise<Project> {
  const response = await fetch(`/api/projects/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || "Failed to update project");
  }

  return data.project;
}

// Delete project
export async function deleteProject(id: string): Promise<void> {
  const response = await fetch(`/api/projects/${id}`, {
    method: "DELETE",
  });
  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || "Failed to delete project");
  }
}

// Save project data (chat state, files, etc.)
export async function saveProjectData(
  projectId: string,
  data: {
    chatId?: string;
    /** Canonical preview URL (preferred over deprecated `demoUrl`). */
    previewUrl?: string;
    /** @deprecated Prefer `previewUrl` in new code. */
    // TODO(after-wave-5): drop after deadline 2026-Q3 if no inbound payloads.
    demoUrl?: string;
    currentCode?: string;
    files?: PersistedFile[];
    messages?: PersistedMessage[];
    meta?: Record<string, unknown> | null;
  },
): Promise<void> {
  const response = await fetch(`/api/projects/${projectId}/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const result = await response.json();

  if (!result.success) {
    throw new Error(result.error || "Failed to save project data");
  }
}

// Upload image
export async function uploadImage(
  projectId: string,
  file: File,
): Promise<{ url: string; filename: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`/api/projects/${projectId}/upload`, {
    method: "POST",
    body: formData,
  });
  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || "Failed to upload image");
  }

  return { url: data.image.url, filename: data.image.filename };
}
