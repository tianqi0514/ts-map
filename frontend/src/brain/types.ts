// ── Brain 模块类型 ──

export type Space = {
  id: string;
  code: string;
  name: string;
  domain: string;
  description: string;
  status: string;
};

export type BrainTab = "overview" | "connectors" | "rule-engine" | "executions";

export type ApiConnector = {
  id: string;
  code: string;
  name: string;
  description: string;
  base_url: string;
  method: string;
  headers: Record<string, string>;
  auth_type: string;
  auth_config: Record<string, unknown>;
  request_template: Record<string, unknown>;
  space_id: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type DataMapping = {
  id: string;
  connector_id: string;
  source_field: string;
  target_type: string;
  target_code: string;
  transform: string;
  is_key: boolean;
  description: string;
  created_at: string;
  updated_at: string;
};

export type ConnectorTemplate = {
  code: string;
  name: string;
  description: string;
  mapping_count: number;
};

export type RuleHitResult = {
  rule_id: string;
  rule_code: string;
  rule_name: string;
  rule_type: string;
  priority: number;
  condition: string;
  matched: boolean;
  result: string;
  severity: string;
  reasoning: Array<Record<string, unknown>>;
};

export type RuleEngineResult = {
  space_id: string;
  input_data: Record<string, unknown>;
  total_rules: number;
  hit_count: number;
  block_count: number;
  hits: RuleHitResult[];
  execution_time_ms: number;
};

export type RuleExecutionRecord = {
  id: string;
  space_id: string;
  input_summary: Record<string, unknown>;
  status: string;
  hit_count: number;
  block_count: number;
  suggest_count: number;
  trace: Array<Record<string, unknown>>;
  created_at: string;
};

export type SyntheticPreviewResult = {
  connector_id: string;
  connector_name: string;
  records: Array<Record<string, unknown>>;
  mapping_summary: {
    total_fields: number;
    by_type: Record<string, number>;
    by_object: Record<string, number>;
  };
};
