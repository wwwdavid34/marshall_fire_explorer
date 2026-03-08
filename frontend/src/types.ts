export interface ParcelProperties {
  ParcelNo: string;
  Condition: "Destroyed" | "Damaged" | "Unaffected";
  recovery_date: string | null;
  recovery_months_post_fire: number | null;
  recovery_llm: number | null;
  smile_curvature: number | null;
  smile_valid: boolean | null;
  building_ratio: number | null;
  used_footprint: boolean;
  StrNum: string | null;
  Street: string | null;
}

export interface CoherencePoint {
  mid_date: string;
  norm_coh: number | null;
  smoothed: number | null;
  months_post_fire: number;
}
