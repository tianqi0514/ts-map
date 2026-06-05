import React from "react";
import ReactDOM from "react-dom/client";
import {
  Activity,
  ArrowLeft,
  BookOpen,
  Boxes,
  CircleDot,
  Copy,
  Database,
  Edit3,
  Eye,
  FileClock,
  GitBranch,
  GitFork,
  LayoutList,
  ListChecks,
  Network,
  Plus,
  RefreshCw,
  Scale,
  Search,
  Settings,
  Trash2,
  WandSparkles
} from "lucide-react";
import "./styles.css";

type SectionKey = "overview" | "objects" | "properties" | "relations" | "actions" | "scenarios" | "rules" | "graph" | "versions" | "settings";

type Space = {
  id: string;
  code: string;
  name: string;
  domain: string;
  description: string;
  status: string;
};

type ElementItem = {
  id: string;
  space_id: string;
  resource_type: string;
  code: string;
  name: string;
  description: string;
  status: string;
  version: number;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

type VersionRecord = {
  id: string;
  resource_type: string;
  resource_id: string;
  version: number;
  change_type: string;
  diff: Record<string, unknown>;
  snapshot: Record<string, unknown>;
  created_at: string;
};

type Summary = {
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  total: number;
};

type ApiResponse<T> = {
  success: boolean;
  data: T;
  error: string | null;
};

type OntologyData = {
  objects: ElementItem[];
  relations: ElementItem[];
  actions: ElementItem[];
  properties: ElementItem[];
  rules: ElementItem[];
  scenarios: ElementItem[];
  versions: VersionRecord[];
};

type ElementFormValue = {
  code: string;
  name: string;
  description: string;
  status: string;
  payload: Record<string, unknown>;
  references: Array<{ edge_type: string; target_type: string; target_id: string }>;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

const statusLabels: Record<string, string> = {
  draft: "草稿",
  pending: "待审核",
  active: "已启用",
  inactive: "已停用",
  deprecated: "已废弃"
};

const sectionItems: Array<{
  key: SectionKey;
  label: string;
  icon: React.ComponentType<{ size?: number }>;
}> = [
  { key: "overview", label: "概览", icon: Activity },
  { key: "objects", label: "对象", icon: Boxes },
  { key: "properties", label: "属性字典", icon: ListChecks },
  { key: "relations", label: "关系", icon: GitBranch },
  { key: "actions", label: "行为", icon: WandSparkles },
  { key: "scenarios", label: "场景", icon: LayoutList },
  { key: "rules", label: "规则", icon: Scale },
  { key: "graph", label: "本体图谱", icon: Network },
  { key: "versions", label: "版本记录", icon: FileClock },
  { key: "settings", label: "设置", icon: Settings }
];

const resourceTitle: Record<string, string> = {
  objects: "对象",
  properties: "属性",
  relations: "关系",
  actions: "行为",
  scenarios: "场景",
  rules: "规则"
};

const resourceDefaults: Record<string, Record<string, unknown>> = {
  objects: { key: "", fields: {} },
  properties: { object_code: "", data_type: "string", required: false },
  relations: { source_code: "", target_codes: [], cardinality: "" },
  actions: { hook: "", effect: "", rules: [] },
  scenarios: { contract_types: [], active_elements: [] },
  rules: { rule_type: "硬规则", condition: "", result: "", actions: [] }
};

function App() {
  const [spaces, setSpaces] = React.useState<Space[]>([]);
  const [selectedSpaceId, setSelectedSpaceId] = React.useState("");
  const [active, setActive] = React.useState<SectionKey>("overview");
  const [summary, setSummary] = React.useState<Summary>({ by_type: {}, by_status: {}, total: 0 });
  const [data, setData] = React.useState<OntologyData>({
    objects: [],
    relations: [],
    actions: [],
    properties: [],
    rules: [],
    scenarios: [],
    versions: []
  });
  const [keyword, setKeyword] = React.useState("");
  const [selected, setSelected] = React.useState<ElementItem | null>(null);
  const [editing, setEditing] = React.useState<ElementItem | "new" | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [health, setHealth] = React.useState<{ status: string; neo4j: boolean } | null>(null);
  const [creatingSpace, setCreatingSpace] = React.useState(false);
  const [deletingSpace, setDeletingSpace] = React.useState<Space | null>(null);
  const [showImportYaml, setShowImportYaml] = React.useState(false);
  const [importStatus, setImportStatus] = React.useState<string>("");

  const selectedSpace = spaces.find((space) => space.id === selectedSpaceId);

  React.useEffect(() => {
    bootstrap();
  }, []);

  React.useEffect(() => {
    if (selectedSpaceId) loadOntology(selectedSpaceId);
  }, [selectedSpaceId]);

  async function bootstrap() {
    const [spaceResponse, healthResponse] = await Promise.all([
      api<Space[]>("/api/spaces"),
      api<{ status: string; neo4j: boolean }>("/health").catch(() => null)
    ]);
    const ordered = [...spaceResponse.data].sort((a, b) =>
      a.code === "single_contract_ontology" ? -1 : b.code === "single_contract_ontology" ? 1 : 0
    );
    setSpaces(ordered);
    if (healthResponse) setHealth(healthResponse.data);
  }

  async function initializeTemplate() {
    await api<Space>("/api/spaces/initialize-contract-template", { method: "POST" });
    await bootstrap();
  }

  async function loadOntology(spaceId: string) {
    setLoading(true);
    try {
      const [summaryRes, objects, relations, actions, properties, rules, scenarios, versions] = await Promise.all([
        api<Summary>(`/api/spaces/${spaceId}/summary`),
        loadResource(spaceId, "objects"),
        loadResource(spaceId, "relations"),
        loadResource(spaceId, "actions"),
        loadResource(spaceId, "properties"),
        loadResource(spaceId, "rules"),
        loadResource(spaceId, "scenarios"),
        api<VersionRecord[]>(`/api/spaces/${spaceId}/versions`).then((res) => res.data)
      ]);
      setSummary(summaryRes.data);
      setData({ objects, relations, actions, properties, rules, scenarios, versions });
    } finally {
      setLoading(false);
    }
  }

  async function loadResource(spaceId: string, resource: string) {
    const response = await api<{ items: ElementItem[] }>(`/api/ontology/${spaceId}/${resource}?page_size=500`);
    return response.data.items;
  }

  async function saveElement(form: ElementFormValue) {
    if (!selectedSpaceId || !isCrudSection(active)) return;
    if (editing === "new") {
      await api(`/api/ontology/${selectedSpaceId}/${active}`, {
        method: "POST",
        body: JSON.stringify(form)
      });
    } else if (editing) {
      await api(`/api/ontology/${selectedSpaceId}/${active}/${editing.id}`, {
        method: "PUT",
        body: JSON.stringify(form)
      });
    }
    setEditing(null);
    await loadOntology(selectedSpaceId);
  }

  async function saveSpace(form: { code: string; name: string; domain: string; description: string }) {
    await api<Space>("/api/spaces", {
      method: "POST",
      body: JSON.stringify(form)
    });
    setCreatingSpace(false);
    await bootstrap();
  }

  async function deleteSpaceById(space: Space) {
    setLoading(true);
    try {
      await api(`/api/spaces/${space.id}`, { method: "DELETE" });
      setDeletingSpace(null);
      if (selectedSpaceId === space.id) {
        setSelectedSpaceId("");
        setSelected(null);
      }
      await bootstrap();
    } catch (e) {
      alert("❌ 删除失败: " + String(e));
    } finally {
      setLoading(false);
    }
  }

  async function importYaml(file: File) {
    setLoading(true);
    setImportStatus("正在上传...");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(`${API_BASE}/api/admin/import-yaml`, {
        method: "POST",
        body: formData
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || response.statusText);
      }
      const result = await response.json();
      setImportStatus("导入完成");
      setShowImportYaml(false);
      await bootstrap();
      const counts = result.data?.created || {};
      alert(`✅ 导入成功！\n对象: ${counts.objects || 0}\n属性: ${counts.properties || 0}\n关系: ${counts.relations || 0}\n行为: ${counts.actions || 0}\n规则: ${counts.rules || 0}`);
    } catch (e) {
      setImportStatus("导入失败");
      alert("❌ 导入失败: " + String(e));
    } finally {
      setLoading(false);
    }
  }

  async function deactivate(item: ElementItem) {
    if (!selectedSpaceId || !isCrudSection(active)) return;
    await api(`/api/ontology/${selectedSpaceId}/${active}/${item.id}/deactivate`, { method: "POST" });
    await loadOntology(selectedSpaceId);
  }

  async function copy(item: ElementItem) {
    if (!selectedSpaceId || !isCrudSection(active)) return;
    await api(`/api/ontology/${selectedSpaceId}/${active}/${item.id}/copy`, { method: "POST" });
    await loadOntology(selectedSpaceId);
  }

  const visibleItems = React.useMemo(() => {
    if (!isCrudSection(active)) return [];
    const items = data[active];
    if (!keyword) return items;
    return items.filter((item) => `${item.name}${item.code}${item.description}`.includes(keyword));
  }, [active, data, keyword]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">智</div>
          <div>
            <strong>传神智谱</strong>
            <span>本体管理</span>
          </div>
        </div>
        <div className="nav-root">
          <BookOpen size={18} />
          <span>智谱</span>
        </div>
        <nav>
          <button
            className={!selectedSpaceId ? "nav-item active" : "nav-item"}
            onClick={() => {
              setSelectedSpaceId("");
              setSelected(null);
              setEditing(null);
            }}
          >
            <Database size={17} />
            <span>本体列表</span>
          </button>
          {selectedSpaceId && (
            <>
              <div className="nav-divider">{selectedSpace?.name}</div>
              {sectionItems.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.key}
                    className={active === item.key ? "nav-item active" : "nav-item"}
                    onClick={() => {
                      setActive(item.key);
                      setSelected(null);
                      setEditing(null);
                    }}
                  >
                    <Icon size={17} />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </>
          )}
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <p className="crumb">{selectedSpace ? `智谱 / ${selectedSpace.name}` : "智谱 / 本体列表"}</p>
            <h1>{selectedSpace ? activeLabel(active) : "本体列表"}</h1>
          </div>
          <div className="top-actions">
            {selectedSpace && (
              <button className="ghost-button" onClick={() => setSelectedSpaceId("")}>
                <ArrowLeft size={16} />
                返回本体列表
              </button>
            )}
            <button className="ghost-button" onClick={initializeTemplate}>
              <Database size={16} />
              初始化验证本体
            </button>
            <span className={health?.neo4j ? "health ok" : "health warn"}>
              <CircleDot size={12} />
              Neo4j {health?.neo4j ? "已连接" : "未连接"}
            </span>
          </div>
        </header>

        {!selectedSpace ? (
          <OntologyList
            spaces={spaces}
            onSelect={setSelectedSpaceId}
            onNewSpace={() => setCreatingSpace(true)}
            onDeleteSpace={(space) => setDeletingSpace(space)}
            onImportYaml={() => setShowImportYaml(true)}
          />
        ) : active === "overview" ? (
          <Overview space={selectedSpace} summary={summary} data={data} onJump={setActive} />
        ) : active === "graph" ? (
          <OntologyGraph data={data} />
        ) : active === "versions" ? (
          <VersionTable versions={data.versions} loading={loading} />
        ) : active === "settings" ? (
          <SettingsPanel space={selectedSpace} />
        ) : isCrudSection(active) ? (
          <ResourcePanel
            title={resourceTitle[active]}
            items={visibleItems}
            keyword={keyword}
            loading={loading}
            onKeyword={setKeyword}
            onRefresh={() => loadOntology(selectedSpaceId)}
            onNew={() => setEditing("new")}
            onSelect={setSelected}
            onEdit={setEditing}
            onDeactivate={deactivate}
            onCopy={copy}
          />
        ) : null}
      </main>

      {selected && selectedSpaceId && (
        <DetailDrawer
          item={selected}
          ontologyData={data}
          spaceId={selectedSpaceId}
          onClose={() => setSelected(null)}
          onEdit={() => {
            setEditing(selected);
            setSelected(null);
          }}
        />
      )}

      {editing && isCrudSection(active) && (
        <EditDrawer
          item={editing === "new" ? null : editing}
          resource={active}
          onClose={() => setEditing(null)}
          onSave={saveElement}
        />
      )}

      {creatingSpace && (
        <CreateSpaceDrawer
          onClose={() => setCreatingSpace(false)}
          onSave={saveSpace}
        />
      )}

      {deletingSpace && (
        <DeleteSpaceConfirmDialog
          space={deletingSpace}
          onCancel={() => setDeletingSpace(null)}
          onConfirm={() => deleteSpaceById(deletingSpace)}
        />
      )}

      {showImportYaml && (
        <YamlImportDrawer
          onClose={() => setShowImportYaml(false)}
          onImport={importYaml}
          status={importStatus}
        />
      )}
    </div>
  );
}

function OntologyList({
  spaces,
  onSelect,
  onNewSpace,
  onDeleteSpace,
  onImportYaml
}: {
  spaces: Space[];
  onSelect: (id: string) => void;
  onNewSpace: () => void;
  onDeleteSpace: (space: Space) => void;
  onImportYaml: () => void;
}) {
  return (
    <section>
      <div className="ontology-list-toolbar">
        <h2>本体空间列表</h2>
        <div className="toolbar-actions">
          <button className="ghost-button" onClick={onImportYaml}>
            <Database size={16} />
            从YAML导入
          </button>
          <button className="primary-button" onClick={onNewSpace}>
            <Plus size={16} />
            新建本体空间
          </button>
        </div>
      </div>
      <div className="ontology-list">
        {spaces.length === 0 && (
          <div className="ontology-empty">
            <p>暂无本体空间</p>
            <div className="ontology-empty-actions">
              <button className="primary-button" onClick={onNewSpace}>
                <Plus size={16} />
                创建第一个空间
              </button>
              <button className="ghost-button" onClick={onImportYaml}>
                <Database size={16} />
                从YAML导入
              </button>
            </div>
          </div>
        )}
        {spaces.map((space) => (
          <div className="ontology-card-wrap" key={space.id}>
            <button className="ontology-card" onClick={() => onSelect(space.id)}>
              <div className="ontology-card-icon">
                <GitFork size={24} />
              </div>
              <div className="ontology-card-body">
                <strong>{space.name}</strong>
                <span>{space.domain}</span>
                <p>{space.description || "本体资产空间"}</p>
              </div>
              <div className="ontology-card-meta">
                <span className={`status-badge ${space.status}`}>{statusLabels[space.status] ?? space.status}</span>
              </div>
            </button>
            <button
              className="card-delete-btn"
              title="删除此空间（级联删除所有关联数据）"
              onClick={(e) => {
                e.stopPropagation();
                onDeleteSpace(space);
              }}
            >
              <Trash2 size={15} />
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}

function Overview({
  space,
  summary,
  data,
  onJump
}: {
  space: Space;
  summary: Summary;
  data: OntologyData;
  onJump: (key: SectionKey) => void;
}) {
  return (
    <section className="dashboard">
      <div className="workspace-band">
        <div>
          <p className="eyebrow">当前本体</p>
          <h2>{space.name}</h2>
          <p>{space.description}</p>
        </div>
        <div className="metric-strip">
          <Metric label="对象" value={summary.by_type.object ?? data.objects.length} />
          <Metric label="关系" value={summary.by_type.relation ?? data.relations.length} />
          <Metric label="行为" value={summary.by_type.action ?? data.actions.length} />
          <Metric label="规则" value={summary.by_type.rule ?? data.rules.length} />
        </div>
      </div>
      <div className="shortcut-grid">
        <Shortcut icon={Boxes} label="对象" value="实体类型与对象字段" onClick={() => onJump("objects")} />
        <Shortcut icon={GitBranch} label="关系" value="对象之间的业务连接" onClick={() => onJump("relations")} />
        <Shortcut icon={WandSparkles} label="行为" value="命中规则后的动作模板" onClick={() => onJump("actions")} />
        <Shortcut icon={Network} label="本体图谱" value="对象、属性、关系、行为、规则全景" onClick={() => onJump("graph")} />
      </div>
    </section>
  );
}

function Shortcut({
  icon: Icon,
  label,
  value,
  onClick
}: {
  icon: React.ComponentType<{ size?: number }>;
  label: string;
  value: string;
  onClick: () => void;
}) {
  return (
    <button className="shortcut" onClick={onClick}>
      <Icon size={22} />
      <strong>{label}</strong>
      <span>{value}</span>
    </button>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function ResourcePanel(props: {
  title: string;
  items: ElementItem[];
  keyword: string;
  loading: boolean;
  onKeyword: (value: string) => void;
  onRefresh: () => void;
  onNew: () => void;
  onSelect: (item: ElementItem) => void;
  onEdit: (item: ElementItem) => void;
  onDeactivate: (item: ElementItem) => void;
  onCopy: (item: ElementItem) => void;
}) {
  return (
    <section className="resource-panel">
      <div className="toolbar">
        <div className="search">
          <Search size={16} />
          <input
            value={props.keyword}
            placeholder={`搜索${props.title}`}
            onChange={(event) => props.onKeyword(event.target.value)}
          />
        </div>
        <button className="icon-button" onClick={props.onRefresh} title="刷新">
          <RefreshCw size={16} />
        </button>
        <button className="primary-button" onClick={props.onNew}>
          <Plus size={16} />
          新增{props.title}
        </button>
      </div>

      <div className="table-shell">
        <table>
          <thead>
            <tr>
              <th>名称</th>
              <th>编码</th>
              <th>定义摘要</th>
              <th>状态</th>
              <th>版本</th>
              <th>更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {props.loading ? (
              <tr>
                <td colSpan={7}>加载中...</td>
              </tr>
            ) : props.items.length === 0 ? (
              <tr>
                <td colSpan={7}>暂无数据</td>
              </tr>
            ) : (
              props.items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <button className="link-button" onClick={() => props.onSelect(item)}>
                      {item.name}
                    </button>
                  </td>
                  <td>{item.code}</td>
                  <td className="muted">{item.description || "-"}</td>
                  <td>
                    <span className={`status ${item.status}`}>{statusLabels[item.status] ?? item.status}</span>
                  </td>
                  <td>v{item.version}</td>
                  <td>{formatTime(item.updated_at)}</td>
                  <td>
                    <div className="row-actions">
                      <button title="查看" onClick={() => props.onSelect(item)}>
                        <Eye size={15} />
                      </button>
                      <button title="编辑" onClick={() => props.onEdit(item)}>
                        <Edit3 size={15} />
                      </button>
                      <button title="复制" onClick={() => props.onCopy(item)}>
                        <Copy size={15} />
                      </button>
                      <button title="停用" onClick={() => props.onDeactivate(item)}>
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function DetailDrawer({
  item,
  ontologyData,
  spaceId,
  onClose,
  onEdit
}: {
  item: ElementItem;
  ontologyData: OntologyData;
  spaceId: string;
  onClose: () => void;
  onEdit: () => void;
}) {
  const [impact, setImpact] = React.useState<Record<string, unknown> | null>(null);
  const resource = resourcePath(item.resource_type);

  React.useEffect(() => {
    if (!resource) return;
    api<Record<string, unknown>>(`/api/ontology/${spaceId}/${resource}/${item.id}/impact`).then((res) =>
      setImpact(res.data)
    );
  }, [item.id, resource, spaceId]);

  const objectProperties = ontologyData.properties.filter((property) => property.payload.object_code === item.code);
  const actionRules = ontologyData.rules.filter((rule) => {
    const actions = rule.payload.actions;
    return Array.isArray(actions) && actions.includes(item.code);
  });

  return (
    <aside className="drawer">
      <div className="drawer-header">
        <div>
          <p className="crumb">{resourceTypeLabel(item.resource_type)}</p>
          <h2>{item.name}</h2>
        </div>
        <button onClick={onClose}>关闭</button>
      </div>
      {resource && (
        <div className="drawer-actions">
          <button className="primary-button" onClick={onEdit}>
            <Edit3 size={16} />
            编辑
          </button>
        </div>
      )}
      <Section title="基本信息">
        <KeyValue label="编码" value={item.code} />
        <KeyValue label="状态" value={statusLabels[item.status] ?? item.status} />
        <KeyValue label="版本" value={`v${item.version}`} />
        <KeyValue label="定义" value={item.description || "-"} />
      </Section>
      {item.resource_type === "object" && (
        <Section title="对象属性">
          <MiniTable
            rows={objectProperties.map((property) => ({
              name: property.name,
              code: property.code,
              desc: String(property.payload.data_type ?? "")
            }))}
            empty="暂无属性"
          />
        </Section>
      )}
      {item.resource_type === "action" && (
        <Section title="关联规则">
          <MiniTable
            rows={actionRules.map((rule) => ({
              name: rule.name,
              code: rule.code,
              desc: `${rule.payload.rule_type ?? ""} ${rule.payload.condition ?? ""}`
            }))}
            empty="暂无规则"
          />
        </Section>
      )}
      <Section title="结构化字段">
        <pre>{JSON.stringify(item.payload, null, 2)}</pre>
      </Section>
      <Section title="影响范围">
        <ImpactView impact={impact} />
      </Section>
    </aside>
  );
}

function MiniTable({ rows, empty }: { rows: Array<{ name: string; code: string; desc: string }>; empty: string }) {
  if (rows.length === 0) return <p className="muted">{empty}</p>;
  return (
    <div className="mini-table">
      {rows.map((row) => (
        <div key={row.code}>
          <strong>{row.name}</strong>
          <code>{row.code}</code>
          <span>{row.desc}</span>
        </div>
      ))}
    </div>
  );
}

function ImpactView({ impact }: { impact: Record<string, unknown> | null }) {
  if (!impact) {
    return <p className="muted">加载影响范围中...</p>;
  }

  const incoming = (impact.incoming as Array<{ edge_type: string; source: { code: string; name: string; resource_type: string; status: string } | null }> | undefined) ?? [];
  const outgoing = (impact.outgoing as Array<{ edge_type: string; target: { code: string; name: string; resource_type: string; status: string } | null }> | undefined) ?? [];

  const hasData = incoming.length > 0 || outgoing.length > 0;
  if (!hasData) {
    return <p className="muted">暂无引用关系</p>;
  }

  return (
    <div className="impact-view">
      {incoming.length > 0 && (
        <div className="impact-group">
          <h4>被引用（{incoming.length}）</h4>
          <div className="impact-rows">
            {incoming.map((item, i) => (
              <div key={`in-${i}`} className="impact-row">
                <span className="impact-direction">←</span>
                <span className="impact-edge">{item.edge_type}</span>
                <span className="impact-target">
                  {item.source ? (
                    <>
                      <strong>{item.source.name}</strong>
                      <code>{item.source.code}</code>
                      <span className={`status-badge mini ${item.source.status}`}>{statusLabels[item.source.status] ?? item.source.status}</span>
                    </>
                  ) : (
                    "未知来源"
                  )}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      {outgoing.length > 0 && (
        <div className="impact-group">
          <h4>引用他人（{outgoing.length}）</h4>
          <div className="impact-rows">
            {outgoing.map((item, i) => (
              <div key={`out-${i}`} className="impact-row">
                <span className="impact-direction">→</span>
                <span className="impact-edge">{item.edge_type}</span>
                <span className="impact-target">
                  {item.target ? (
                    <>
                      <strong>{item.target.name}</strong>
                      <code>{item.target.code}</code>
                      <span className={`status-badge mini ${item.target.status}`}>{statusLabels[item.target.status] ?? item.target.status}</span>
                    </>
                  ) : (
                    "未知目标"
                  )}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function EditDrawer({
  item,
  resource,
  onClose,
  onSave
}: {
  item: ElementItem | null;
  resource: "objects" | "properties" | "relations" | "actions" | "scenarios" | "rules";
  onClose: () => void;
  onSave: (value: ElementFormValue) => void;
}) {
  const [code, setCode] = React.useState(item?.code ?? "");
  const [name, setName] = React.useState(item?.name ?? "");
  const [description, setDescription] = React.useState(item?.description ?? "");
  const [status, setStatus] = React.useState(item?.status ?? "draft");
  const [payloadText, setPayloadText] = React.useState(
    JSON.stringify(item?.payload ?? resourceDefaults[resource] ?? {}, null, 2)
  );
  const [error, setError] = React.useState("");

  function submit() {
    try {
      const payload = JSON.parse(payloadText);
      onSave({ code, name, description, status, payload, references: [] });
    } catch {
      setError("结构化字段必须是合法 JSON");
    }
  }

  return (
    <aside className="drawer">
      <div className="drawer-header">
        <div>
          <p className="crumb">{resourceTitle[resource]}</p>
          <h2>{item ? "编辑" : "新增"}</h2>
        </div>
        <button onClick={onClose}>关闭</button>
      </div>
      <div className="form">
        <label>
          名称
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label>
          编码
          <input value={code} onChange={(event) => setCode(event.target.value)} />
        </label>
        <label>
          状态
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="draft">草稿</option>
            <option value="pending">待审核</option>
            <option value="active">已启用</option>
            <option value="inactive">已停用</option>
          </select>
        </label>
        <label>
          自然语言定义
          <textarea value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <label>
          结构化字段 JSON
          <textarea
            className="json-input"
            value={payloadText}
            onChange={(event) => setPayloadText(event.target.value)}
          />
        </label>
        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" onClick={submit}>
          保存
        </button>
      </div>
    </aside>
  );
}

function OntologyGraph({ data }: { data: OntologyData }) {
  const { nodes: baseNodes, width, height } = React.useMemo(() => buildObjectRelationGraph(data), [data]);
  const [positions, setPositions] = React.useState<Record<string, GraphPosition>>({});
  const dragRef = React.useRef<GraphDragState | null>(null);
  const nodes = React.useMemo(
    () =>
      baseNodes.map((node) => ({
        ...node,
        ...(positions[node.id] ?? {})
      })),
    [baseNodes, positions]
  );
  const edges = React.useMemo(() => buildRelationEdges(data.relations, nodes), [data.relations, nodes]);
  const [selection, setSelection] = React.useState<GraphSelection | null>(
    nodes[0] ? { kind: "object", node: nodes[0] } : null
  );

  React.useEffect(() => {
    setPositions((current) => {
      const next: Record<string, GraphPosition> = {};
      for (const node of baseNodes) {
        next[node.id] = current[node.id] ?? { x: node.x, y: node.y };
      }
      return next;
    });
  }, [baseNodes]);

  React.useEffect(() => {
    setSelection((current) => {
      if (current?.kind === "object") {
        const node = nodes.find((item) => item.id === current.node.id);
        return node ? { kind: "object", node } : nodes[0] ? { kind: "object", node: nodes[0] } : null;
      }
      if (current?.kind === "relation") {
        const edge = edges.find((item) => item.id === current.edge.id);
        return edge ? { kind: "relation", edge } : nodes[0] ? { kind: "object", node: nodes[0] } : null;
      }
      return nodes[0] ? { kind: "object", node: nodes[0] } : null;
    });
  }, [edges, nodes]);

  function startDrag(event: React.PointerEvent<HTMLButtonElement>, node: ObjectGraphNode) {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      id: node.id,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: node.x,
      originY: node.y,
      moved: false
    };
  }

  function dragNode(event: React.PointerEvent<HTMLButtonElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
    setPositions((current) => ({
      ...current,
      [drag.id]: {
        x: Math.max(24, Math.min(width - GRAPH_NODE_WIDTH - 24, drag.originX + dx)),
        y: Math.max(24, Math.min(height - GRAPH_NODE_HEIGHT - 24, drag.originY + dy))
      }
    }));
  }

  function endDrag(event: React.PointerEvent<HTMLButtonElement>, node: ObjectGraphNode) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    dragRef.current = null;
    if (!drag.moved) setSelection({ kind: "object", node });
  }

  return (
    <section className="graph-workspace">
      <div className="graph-canvas">
        <div className="graph-stage" style={{ width, height }}>
          <svg className="graph-edges" width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
            <defs>
              <marker id="arrow-head" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
                <path d="M 0 0 L 8 4 L 0 8 z" />
              </marker>
            </defs>
            {edges.map((edge) => (
              <path
                key={edge.id}
                className={`graph-edge-line ${
                  selection?.kind === "relation" && selection.edge.id === edge.id ? "selected" : ""
                }`}
                d={edge.path}
                markerEnd="url(#arrow-head)"
              />
            ))}
          </svg>
          {edges.map((edge) => (
            <button
              key={edge.id}
              className={`graph-edge-button ${
                selection?.kind === "relation" && selection.edge.id === edge.id ? "selected" : ""
              }`}
              style={{ left: edge.labelX, top: edge.labelY }}
              onClick={() => setSelection({ kind: "relation", edge })}
            >
              {edge.label}
            </button>
          ))}
          {nodes.map((node) => (
            <button
              key={node.id}
              className={`graph-node object ${
                selection?.kind === "object" && selection.node.id === node.id ? "selected" : ""
              }`}
              style={{ left: node.x, top: node.y }}
              onPointerDown={(event) => startDrag(event, node)}
              onPointerMove={dragNode}
              onPointerUp={(event) => endDrag(event, node)}
              onPointerCancel={() => {
                dragRef.current = null;
              }}
              onClick={() => setSelection({ kind: "object", node })}
            >
              <strong>{node.name}</strong>
            </button>
          ))}
        </div>
      </div>
      <aside className="graph-inspector">
        <h3>{selection?.kind === "relation" ? "关系详情" : "对象详情"}</h3>
        {selection?.kind === "object" ? (
          <ObjectGraphInspector node={selection.node} data={data} />
        ) : selection?.kind === "relation" ? (
          <RelationGraphInspector edge={selection.edge} data={data} />
        ) : (
          <p className="muted">请选择对象或关系</p>
        )}
      </aside>
    </section>
  );
}

function ObjectGraphInspector({ node, data }: { node: ObjectGraphNode; data: OntologyData }) {
  const properties = data.properties.filter((property) => property.payload.object_code === node.code);
  return (
    <>
      <p className="node-kind">对象</p>
      <h2>{node.name}</h2>
      <code>{node.code}</code>
      <p>{node.description || "暂无定义"}</p>
      <Section title="对象属性">
        <MiniTable
          rows={properties.map((property) => ({
            name: propertyDisplayName(property),
            code: propertyDataTypeLabel(property.payload.data_type),
            desc: propertyDescription(property)
          }))}
          empty="暂无属性"
        />
      </Section>
    </>
  );
}

function RelationGraphInspector({ edge, data }: { edge: ObjectGraphEdge; data: OntologyData }) {
  const rules = findRulesForRelation(edge.relation, data.rules);
  return (
    <>
      <p className="node-kind">关系</p>
      <h2>{edge.relation.name}</h2>
      <code>{edge.relation.code}</code>
      <p>{edge.relation.description || "暂无定义"}</p>
      <Section title="关系端点">
        <KeyValue label="源对象" value={`${edge.source.name} (${edge.source.code})`} />
        <KeyValue label="目标对象" value={`${edge.target.name} (${edge.target.code})`} />
        <KeyValue label="基数" value={String(edge.relation.payload.cardinality ?? "-")} />
        <KeyValue label="可遍历" value={edge.relation.payload.traversable ? "是" : "否"} />
      </Section>
      <Section title="关联规则">
        <MiniTable
          rows={rules.map((rule) => ({
            name: rule.name,
            code: rule.code,
            desc: `${rule.payload.rule_type ?? ""} ${rule.payload.condition ?? rule.description ?? ""}`
          }))}
          empty="暂无关联规则"
        />
      </Section>
    </>
  );
}

type ObjectGraphNode = {
  id: string;
  code: string;
  name: string;
  description: string;
  payload: Record<string, unknown>;
  x: number;
  y: number;
};

type ObjectGraphEdge = {
  id: string;
  source: ObjectGraphNode;
  target: ObjectGraphNode;
  relation: ElementItem;
  label: string;
  path: string;
  labelX: number;
  labelY: number;
};

type GraphPosition = {
  x: number;
  y: number;
};

type GraphDragState = {
  id: string;
  pointerId: number;
  startX: number;
  startY: number;
  originX: number;
  originY: number;
  moved: boolean;
};

type GraphSelection =
  | {
      kind: "object";
      node: ObjectGraphNode;
    }
  | {
      kind: "relation";
      edge: ObjectGraphEdge;
    };

const GRAPH_NODE_WIDTH = 150;
const GRAPH_NODE_HEIGHT = 58;

function buildObjectRelationGraph(data: OntologyData): {
  nodes: ObjectGraphNode[];
  width: number;
  height: number;
} {
  const columns = 4;
  const columnGap = 260;
  const rowGap = 118;
  const nodes = data.objects.map((item, index) => ({
    id: item.id,
    code: item.code,
    name: item.name,
    description: item.description,
    payload: item.payload,
    x: 52 + (index % columns) * columnGap,
    y: 58 + Math.floor(index / columns) * rowGap
  }));

  return {
    nodes,
    width: Math.max(1180, columns * columnGap + 130),
    height: Math.max(680, Math.ceil(nodes.length / columns) * rowGap + 130)
  };
}

function buildRelationEdges(relations: ElementItem[], nodes: ObjectGraphNode[]) {
  const byCode = new Map(nodes.map((node) => [node.code, node]));
  const edges: ObjectGraphEdge[] = [];
  for (const relation of relations) {
    const sourceCode = String(relation.payload.source_code ?? "");
    const targetCodes = Array.isArray(relation.payload.target_codes)
      ? relation.payload.target_codes.map(String)
      : [String(relation.payload.target_code ?? "")].filter(Boolean);
    const source = byCode.get(sourceCode);
    if (!source) continue;
    for (const targetCode of targetCodes) {
      const target = byCode.get(targetCode);
      if (!target) continue;
      const sx = source.x + GRAPH_NODE_WIDTH;
      const sy = source.y + GRAPH_NODE_HEIGHT / 2;
      const tx = target.x;
      const ty = target.y + GRAPH_NODE_HEIGHT / 2;
      const sameRow = Math.abs(sy - ty) < 8;
      const bend = sameRow ? Math.max(60, Math.abs(tx - sx) / 2) : 120;
      const controlX = tx >= sx ? sx + bend : sx + Math.min(80, Math.abs(tx - sx) / 3);
      const path =
        tx >= sx
          ? `M ${sx} ${sy} C ${controlX} ${sy}, ${tx - bend} ${ty}, ${tx} ${ty}`
          : `M ${source.x} ${sy} C ${source.x - 90} ${sy}, ${target.x + GRAPH_NODE_WIDTH + 90} ${ty}, ${
              target.x + GRAPH_NODE_WIDTH
            } ${ty}`;
      edges.push({
        id: `${relation.id}-${target.code}`,
        source,
        target,
        relation,
        label: relation.name,
        path,
        labelX: (sx + tx) / 2,
        labelY: (sy + ty) / 2
      });
    }
  }
  const labelBuckets = new Map<string, number>();
  for (const edge of edges) {
    const bucket = `${Math.floor(edge.labelX / 180)}-${Math.round(edge.labelY / 36)}`;
    const count = labelBuckets.get(bucket) ?? 0;
    labelBuckets.set(bucket, count + 1);
    const direction = count % 2 === 0 ? 1 : -1;
    edge.labelY += direction * Math.ceil(count / 2) * 24;
  }
  return edges;
}

const propertyNameLabels: Record<string, string> = {
  contractNo: "合同编号",
  title: "合同名称",
  contractType: "合同类型",
  amount: "金额",
  signDate: "签署日期",
  effectiveCondition: "生效条件",
  status: "状态",
  relatedDisclosed: "关联关系已披露",
  policyVersion: "政策版本",
  entityId: "主体编号",
  name: "名称",
  role: "角色",
  taxId: "统一社会信用代码",
  regCapital: "注册资本",
  paidCapital: "实缴资本",
  establishedDate: "成立日期",
  businessStatus: "经营状态",
  creditScore: "信用评分",
  repId: "法定代表人编号",
  idMasked: "脱敏证件号",
  since: "任职开始日期",
  shId: "股东编号",
  holder: "持有人",
  holderType: "持有人类型",
  ratio: "持股比例",
  isUBO: "是否最终受益人",
  sigId: "签署人编号",
  authDocNo: "授权文件编号",
  authValidTo: "授权有效期",
  authStatus: "授权状态",
  qualId: "资质编号",
  qualType: "资质类型",
  certNo: "证书编号",
  validTo: "有效期至",
  clauseId: "条款编号",
  clauseType: "条款类型",
  text: "条款原文",
  mandatory: "是否强制",
  obId: "义务编号",
  obligor: "义务方",
  description: "说明",
  dueDate: "到期日期",
  ptId: "付款计划编号",
  stage: "阶段",
  paymentDays: "付款天数",
  payId: "付款编号",
  against: "对应计划",
  paidAt: "付款时间",
  delId: "交付物编号",
  qty: "数量",
  spec: "规格",
  msId: "里程碑编号",
  acceptanceCriteria: "验收标准",
  invId: "发票编号",
  type: "类型",
  issuedAt: "开票日期",
  policyId: "政策编号",
  version: "版本",
  effectiveFrom: "生效日期",
  mandatoryClauses: "强制条款",
  approvalMatrix: "审批矩阵",
  regId: "法规编号",
  jurisdiction: "适用地区",
  apId: "审批编号",
  approver: "审批人",
  decision: "审批结论",
  decidedAt: "审批时间",
  amId: "变更编号",
  scope: "变更范围",
  rfId: "风险编号",
  level: "风险等级",
  target: "指向对象",
  ruleType: "规则类型",
  evidence: "证据",
  atId: "附件编号",
  docType: "文档类型",
  uri: "文件地址",
  hash: "文件哈希"
};

function propertyDisplayName(property: ElementItem) {
  const fieldName = property.code.split(".").pop() ?? property.name;
  return propertyNameLabels[fieldName] ?? humanizeFieldName(fieldName);
}

function propertyDescription(property: ElementItem) {
  const fieldName = property.code.split(".").pop() ?? property.name;
  const name = propertyNameLabels[fieldName] ?? humanizeFieldName(fieldName);
  const required = property.payload.required ? "必填" : "可选";
  return `${name}字段，${required}`;
}

function propertyDataTypeLabel(value: unknown) {
  const raw = String(value ?? "");
  if (raw.startsWith("enum")) return raw.replace("enum", "枚举");
  if (raw.startsWith("decimal")) return "小数";
  const labels: Record<string, string> = {
    string: "文本",
    money: "金额",
    date: "日期",
    bool: "布尔",
    int: "整数",
    ref: "引用",
    "ref[]": "引用列表"
  };
  return labels[raw] ?? raw;
}

function humanizeFieldName(value: string) {
  return splitIdentifier(value).join(" ");
}

function findRulesForRelation(relation: ElementItem, rules: ElementItem[]) {
  const relationWords = splitIdentifier(relation.code);
  const ignoredWords = new Set(["has", "by", "via", "with"]);
  const tokens = [relation.code, relation.name, ...relationWords]
    .map((token) => token.toLowerCase())
    .filter((token) => token.length > 1 && !ignoredWords.has(token));

  return rules.filter((rule) => {
    const searchable = [
      rule.code,
      rule.name,
      rule.description,
      rule.payload.condition,
      rule.payload.result,
      rule.payload.rule_type,
      rule.payload.actions
    ]
      .flat()
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return tokens.some((token) => searchable.includes(token));
  });
}

function splitIdentifier(value: string) {
  return value
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/[_-]/g, " ")
    .split(/\s+/)
    .filter(Boolean);
}

function VersionTable({ versions, loading }: { versions: VersionRecord[]; loading: boolean }) {
  return (
    <section className="resource-panel">
      <div className="table-shell">
        <table>
          <thead>
            <tr>
              <th>资源类型</th>
              <th>资源 ID</th>
              <th>版本</th>
              <th>动作</th>
              <th>变更字段</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6}>加载中...</td>
              </tr>
            ) : versions.length === 0 ? (
              <tr>
                <td colSpan={6}>暂无版本记录</td>
              </tr>
            ) : (
              versions.map((version) => (
                <tr key={version.id}>
                  <td>{resourceTypeLabel(version.resource_type)}</td>
                  <td>{version.resource_id.slice(0, 8)}</td>
                  <td>v{version.version}</td>
                  <td>{version.change_type}</td>
                  <td>{Object.keys(version.diff ?? {}).join(", ") || "-"}</td>
                  <td>{formatTime(version.created_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="detail-section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="key-value">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function isCrudSection(value: SectionKey): value is "objects" | "properties" | "relations" | "actions" | "scenarios" | "rules" {
  return value === "objects" || value === "properties" || value === "relations" || value === "actions" || value === "scenarios" || value === "rules";
}

function resourcePath(type: string) {
  const map: Record<string, string> = {
    object: "objects",
    property: "properties",
    relation: "relations",
    action: "actions",
    scenario: "scenarios",
    rule: "rules"
  };
  return map[type] ?? "";
}

function resourceTypeLabel(type: string) {
  const map: Record<string, string> = {
    object: "对象",
    property: "属性",
    relation: "关系",
    action: "行为",
    scenario: "场景",
    rule: "规则"
  };
  return map[type] ?? type;
}

function activeLabel(key: SectionKey) {
  return sectionItems.find((item) => item.key === key)?.label ?? "概览";
}

async function api<T>(path: string, options: RequestInit = {}): Promise<ApiResponse<T>> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {})
    },
    ...options
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
    minute: "2-digit"
  }).format(new Date(value));
}

function CreateSpaceDrawer({
  onClose,
  onSave
}: {
  onClose: () => void;
  onSave: (value: { code: string; name: string; domain: string; description: string }) => void;
}) {
  const [code, setCode] = React.useState("");
  const [name, setName] = React.useState("");
  const [domain, setDomain] = React.useState("contract_review");
  const [description, setDescription] = React.useState("");
  const [error, setError] = React.useState("");

  function submit() {
    if (!code.trim() || code.length < 2) {
      setError("编码至少2个字符");
      return;
    }
    if (!name.trim()) {
      setError("名称必填");
      return;
    }
    setError("");
    onSave({ code, name, domain, description });
  }

  return (
    <aside className="drawer">
      <div className="drawer-header">
        <div>
          <p className="crumb">本体空间</p>
          <h2>新建本体空间</h2>
        </div>
        <button onClick={onClose}>关闭</button>
      </div>
      <div className="form">
        <label>
          空间名称
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="如：销售合同审核" />
        </label>
        <label>
          空间编码
          <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="如：sales_contract" />
        </label>
        <label>
          业务域
          <select value={domain} onChange={(e) => setDomain(e.target.value)}>
            <option value="contract_review">合同审核</option>
            <option value="risk_management">风险管理</option>
            <option value="compliance">合规管理</option>
            <option value="custom">自定义</option>
          </select>
        </label>
        <label>
          描述
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="描述这个本体空间的业务范围..." />
        </label>
        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" onClick={submit}>
          <Plus size={16} />
          创建空间
        </button>
      </div>
    </aside>
  );
}

function SettingsPanel({ space }: { space: Space | undefined }) {
  return (
    <section className="dashboard">
      <div className="workspace-band">
        <div>
          <p className="eyebrow">空间设置</p>
          <h2>{space?.name ?? "未选择空间"}</h2>
          <p>管理空间配置、成员权限和发布策略</p>
        </div>
      </div>
      <div className="shortcut-grid">
        <Shortcut icon={Database} label="空间信息" value="查看和编辑空间基本信息" onClick={() => {}} />
        <Shortcut icon={Settings} label="成员管理" value="添加和管理空间成员" onClick={() => {}} />
        <Shortcut icon={Scale} label="审批策略" value="配置发布审批流程" onClick={() => {}} />
        <Shortcut icon={FileClock} label="审计日志" value="查看空间操作记录" onClick={() => {}} />
      </div>
      {space && (
        <div className="settings-section">
          <h3>空间基本信息</h3>
          <div className="settings-card">
            <KeyValue label="空间编码" value={space.code} />
            <KeyValue label="业务域" value={space.domain} />
            <KeyValue label="状态" value={statusLabels[space.status] ?? space.status} />
            <KeyValue label="描述" value={space.description || "-"} />
          </div>
        </div>
      )}
    </section>
  );
}

function DeleteSpaceConfirmDialog({
  space,
  onCancel,
  onConfirm
}: {
  space: Space;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>⚠️ 确认删除空间</h3>
        </div>
        <div className="modal-body">
          <p>即将删除空间：<strong>{space.name}</strong>（{space.code}）</p>
          <p>此操作将级联删除该空间下的所有数据：</p>
          <ul>
            <li>所有对象、属性、关系、行为、规则</li>
            <li>所有引用边</li>
            <li>所有版本记录和审计日志</li>
            <li>Neo4j 图数据库中该空间的节点</li>
          </ul>
          <p className="form-error">此操作不可恢复！</p>
        </div>
        <div className="modal-footer">
          <button className="ghost-button" onClick={onCancel}>取消</button>
          <button className="primary-button danger" onClick={onConfirm}>
            <Trash2 size={16} />
            确认删除
          </button>
        </div>
      </div>
    </div>
  );
}

function YamlImportDrawer({
  onClose,
  onImport,
  status
}: {
  onClose: () => void;
  onImport: (file: File) => void;
  status: string;
}) {
  const [file, setFile] = React.useState<File | null>(null);
  const [preview, setPreview] = React.useState<string>("");
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0];
    if (!selected) return;
    setFile(selected);
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = String(ev.target?.result ?? "");
      setPreview(text.slice(0, 2000));
    };
    reader.readAsText(selected);
  }

  function handleImport() {
    if (file) onImport(file);
  }

  return (
    <aside className="drawer">
      <div className="drawer-header">
        <div>
          <p className="crumb">系统管理</p>
          <h2>从 YAML 导入本体</h2>
        </div>
        <button onClick={onClose}>关闭</button>
      </div>
      <div className="form">
        <div className="file-upload-zone" onClick={() => fileInputRef.current?.click()}>
          <input
            ref={fileInputRef}
            type="file"
            accept=".yaml,.yml"
            style={{ display: "none" }}
            onChange={handleFileChange}
          />
          {file ? (
            <div>
              <p><strong>📄 {file.name}</strong></p>
              <p className="muted">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
          ) : (
            <div>
              <p><strong>点击选择 YAML 文件</strong></p>
              <p className="muted">或拖拽文件到此处</p>
              <p className="muted">支持 .yaml / .yml</p>
            </div>
          )}
        </div>

        {preview && (
          <label>
            文件预览（前 2000 字符）
            <pre className="json-input" style={{ maxHeight: 200 }}>{preview}</pre>
          </label>
        )}

        {status && <p className="form-error">{status}</p>}

        <button
          className="primary-button"
          onClick={handleImport}
          disabled={!file}
        >
          <Database size={16} />
          {status ? "导入中..." : "开始导入"}
        </button>

        <div className="import-hint">
          <h4>📋 可用场景文件</h4>
          <ul>
            <li><code>contract-review.yaml</code> — 合同审核本体（20+对象 / 26关系 / 25规则）</li>
            <li><code>factoring-risk.yaml</code> — 保理业务风控（12对象 / 16关系 / 20规则）</li>
            <li><code>battery-scheduling.yaml</code> — 锂电池生产排程（16对象 / 20关系 / 21规则）</li>
          </ul>
        </div>
      </div>
    </aside>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
