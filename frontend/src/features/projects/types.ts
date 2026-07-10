export interface Project {
  id: string;
  name: string;
  description: string | null;
  /** Brand-palette accent key (e.g. "violet") for the project card. */
  color: string;
  is_default: boolean;
  is_disabled: boolean;
  dataset_count: number;
  flow_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  color?: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  color?: string;
  is_disabled?: boolean;
}
