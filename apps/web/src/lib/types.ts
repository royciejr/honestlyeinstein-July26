// Mirrors apps/api/app/schemas.py.

export interface Child {
  id: string;
  display_name: string;
  country: "UK" | "US";
  year_band: string | null;
  created_at: string;
}

export interface SkillProgress {
  slug: string;
  title: string;
  mastery_level: number;
  elo: number;
  next_review_at: string | null;
}

export interface ModuleProgress {
  slug: string;
  title: string;
  sort_order: number;
  unlocked: boolean;
  skills: SkillProgress[];
}

export interface Progress {
  child_id: string;
  modules: ModuleProgress[];
}

export interface PresignResponse {
  upload_id: string;
  s3_key: string;
  url: string;
  headers: Record<string, string>;
  expires_in: number;
}

export interface Upload {
  id: string;
  s3_key: string;
  status: "pending" | "marked" | "failed";
  marking_json: Record<string, unknown> | null;
  created_at: string;
  marked_at: string | null;
}
