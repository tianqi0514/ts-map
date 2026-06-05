import React from "react";
import {
  Activity,
  Cable,
  Clock,
  Play,
  Scale,
  Settings,
  Zap,
} from "lucide-react";
import type { Space } from "./types";
import ConnectorPanel from "./ConnectorPanel";
import RuleEnginePanel from "./RuleEnginePanel";

export type BrainTab = "overview" | "connectors" | "rule-engine" | "executions";

const brainTabs: Array<{
  key: BrainTab;
  label: string;
  icon: React.ComponentType<{ size?: number }>;
}> = [
  { key: "overview", label: "概览", icon: Activity },
  { key: "connectors", label: "API 连接器", icon: Cable },
  { key: "rule-engine", label: "规则引擎", icon: Scale },
  { key: "executions", label: "执行历史", icon: Clock },
];

export default function BrainModule({ spaces }: { spaces: Space[] }) {
  const [activeTab, setActiveTab] = React.useState<BrainTab>("overview");

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}
    >
      <div className="brain-tabs"
      >
        {brainTabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              className={activeTab === tab.key ? "brain-tab active" : "brain-tab"}
              onClick={() => setActiveTab(tab.key)}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>
      <div style={{ flex: 1, overflow: "auto", padding: 20 }}
      >
        {activeTab === "overview" && <BrainOverview spaces={spaces} onNavigate={setActiveTab} />}
        {activeTab === "connectors" && <ConnectorPanel />}
        {activeTab === "rule-engine" && <RuleEnginePanel spaces={spaces} />}
        {activeTab === "executions" && <BrainExecutions spaces={spaces} />}
      </div>
    </div>
  );
}

function BrainOverview({
  spaces,
  onNavigate,
}: {
  spaces: Space[];
  onNavigate: (tab: BrainTab) => void;
}) {
  return (
    <section className="dashboard"
    >
      <div className="workspace-band"
      >
        <div>
          <p className="eyebrow">传神智脑</p>
          <h2>业务数据连接器与规则引擎</h2>
          <p>连接外部业务系统，基于本体规则进行数据验证与推理</p>
        </div>
      </div>
      <div className="shortcut-grid"
      >
        <button className="shortcut" onClick={() => onNavigate("connectors")}
        >
          <Cable size={22} />
          <strong>API 连接器</strong>
          <span>配置外部数据源连接器与字段映射</span>
        </button>
        <button className="shortcut" onClick={() => onNavigate("rule-engine")}
        >
          <Scale size={22} />
          <strong>规则引擎</strong>
          <span>用测试数据验证本体规则的命中情况</span>
        </button>
        <button className="shortcut" onClick={() => onNavigate("executions")}
        >
          <Clock size={22} />
          <strong>执行历史</strong>
          <span>查看规则引擎的历史执行记录与推理轨迹</span>
        </button>
      </div>
      <div className="settings-section"
      >
        <h3>可用本体空间</h3>
        {spaces.length === 0 ? (
          <p className="muted">暂无本体空间，请先在「智谱」模块创建或导入本体</p>
        ) : (
          <div className="space-list-mini"
          >
            {spaces.map((space) => (
              <div key={space.id} className="space-item-mini"
              >
                <strong>{space.name}</strong>
                <code>{space.code}</code>
                <span className={`status-badge ${space.status}`}
                >
                  {space.status === "active" ? "已启用" : space.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function BrainExecutions({ spaces }: { spaces: Space[] }) {
  const [selectedSpaceId, setSelectedSpaceId] = React.useState(spaces[0]?.id ?? "");
  const [executions, setExecutions] = React.useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    if (selectedSpaceId) loadExecutions();
  }, [selectedSpaceId]);

  async function loadExecutions() {
    setLoading(true);
    try {
      const res = await api<Array<Record<string, unknown>>>(
        `/api/brain/rule-engine/executions/${selectedSpaceId}?limit=50`
      );
      setExecutions(res.data ?? []);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="resource-panel"
    >
      <div className="toolbar"
      >
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}
        >
          空间
          <select
            value={selectedSpaceId}
            onChange={(e) => setSelectedSpaceId(e.target.value)}
          >
            {spaces.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </label>
        <button className="icon-button" onClick={loadExecutions} title="刷新"
        >
          <Settings size={16} />
        </button>
      </div>

      {loading ? (
        <p className="muted">加载中...</p>
      ) : executions.length === 0 ? (
        <div className="ontology-empty" style={{ marginTop: 40 }}
        >
          <Clock size={48} />
          <p>暂无执行记录</p>
          <p className="muted">在「规则引擎」页面执行测试后将在此显示历史记录</p>
        </div>
      ) : (
        <div className="execution-list"
        >
          {executions.map((exec: Record<string, unknown>) => (
            <div key={String(exec.id)} className="execution-card"
            >
              <div className="execution-header"
              >
                <span className="execution-id">{String(exec.id).slice(0, 8)}</span>
                <span className={`status-badge ${exec.status}`}
                >
                  {String(exec.status)}
                </span>
                <span className="execution-time">
                  {formatTime(String(exec.created_at))}
                </span>
              </div>
              <div className="execution-stats"
              >
                <span>命中: {Number(exec.hit_count)}</span>
                <span>阻断: {Number(exec.block_count)}</span>
                <span>建议: {Number(exec.suggest_count)}</span>
              </div>
              <div className="execution-summary"
              >
                {Object.entries(exec.input_summary as Record<string, unknown>).slice(0, 5).map(([k, v]) => (
                  <code key={k}>{k}: {String(v).slice(0, 30)}</code>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

async function api<T>(path: string, options: RequestInit = {}): Promise<{ success: boolean; data: T; error: string | null }> {
  const API_BASE = import.meta.env.VITE_API_BASE ?? "";
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json();
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}
