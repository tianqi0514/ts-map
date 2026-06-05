import React from "react";
import {
  Cable,
  ChevronRight,
  Database,
  Eye,
  KeyRound,
  Map,
  Plus,
  RefreshCw,
  Settings,
  Trash2,
  X,
} from "lucide-react";
import type {
  ApiConnector,
  ConnectorTemplate,
  DataMapping,
  SyntheticPreviewResult,
} from "./types";
import { api } from "./api";

// ── 连接器列表 ──

export default function ConnectorPanel() {
  const [connectors, setConnectors] = React.useState<ApiConnector[]>([]);
  const [templates, setTemplates] = React.useState<ConnectorTemplate[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [editing, setEditing] = React.useState<ApiConnector | "new" | null>(null);
  const [previewing, setPreviewing] = React.useState<ApiConnector | null>(null);
  const [applyingTemplate, setApplyingTemplate] = React.useState(false);

  React.useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [connRes, tmplRes] = await Promise.all([
        api<ApiConnector[]>("/api/brain/connectors"),
        api<ConnectorTemplate[]>("/api/brain/templates"),
      ]);
      setConnectors(connRes.data ?? []);
      setTemplates(tmplRes.data ?? []);
    } finally {
      setLoading(false);
    }
  }

  async function deleteConnector(id: string) {
    if (!confirm("确定删除此连接器？关联的字段映射也会被删除。")) return;
    await api(`/api/brain/connectors/${id}`, { method: "DELETE" });
    await loadData();
  }

  async function applyTemplate(code: string) {
    setLoading(true);
    try {
      await api(`/api/brain/templates/${code}/apply`, { method: "POST" });
      setApplyingTemplate(false);
      await loadData();
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="resource-panel">
      <div className="toolbar">
        <h2>API 数据源连接器</h2>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button className="ghost-button" onClick={() => setApplyingTemplate(true)}>
            <Database size={16} />
            应用模板
          </button>
          <button className="icon-button" onClick={loadData} title="刷新">
            <RefreshCw size={16} />
          </button>
          <button className="primary-button" onClick={() => setEditing("new")}>
            <Plus size={16} />
            新建连接器
          </button>
        </div>
      </div>

      {connectors.length === 0 && !loading && (
        <div className="ontology-empty" style={{ marginTop: 40 }}>
          <Cable size={48} />
          <p>暂无 API 连接器</p>
          <div className="ontology-empty-actions">
            <button className="primary-button" onClick={() => setEditing("new")}>
              <Plus size={16} />
              创建连接器
            </button>
            <button className="ghost-button" onClick={() => setApplyingTemplate(true)}>
              <Database size={16} />
              应用预设模板
            </button>
          </div>
        </div>
      )}

      <div className="connector-grid">
        {connectors.map((conn) => (
          <div key={conn.id} className="connector-card">
            <div className="connector-card-header">
              <div className="connector-icon">
                <Cable size={20} />
              </div>
              <div className="connector-info">
                <strong>{conn.name}</strong>
                <code>{conn.code}</code>
              </div>
              <span className={`status-badge ${conn.status}`}>
                {conn.status === "active" ? "已启用" : conn.status}
              </span>
            </div>
            <p className="connector-desc">{conn.description || "暂无描述"}</p>
            <div className="connector-meta">
              <span className="method-tag">{conn.method}</span>
              <span className="url-tag">{conn.base_url}</span>
              <span className="auth-tag">
                <KeyRound size={12} />
                {conn.auth_type === "none" ? "无认证" : conn.auth_type}
              </span>
            </div>
            <div className="connector-actions">
              <button className="ghost-button small" onClick={() => setPreviewing(conn)}>
                <Eye size={14} />
                预览数据
              </button>
              <button className="ghost-button small" onClick={() => setEditing(conn)}>
                <Settings size={14} />
                配置
              </button>
              <button className="ghost-button small danger" onClick={() => deleteConnector(conn.id)}>
                <Trash2 size={14} />
                删除
              </button>
            </div>
          </div>
        ))}
      </div>

      {editing && (
        <ConnectorEditor
          connector={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSave={loadData}
        />
      )}

      {previewing && (
        <SyntheticPreviewDrawer
          connector={previewing}
          onClose={() => setPreviewing(null)}
        />
      )}

      {applyingTemplate && (
        <TemplateDrawer
          templates={templates}
          onApply={applyTemplate}
          onClose={() => setApplyingTemplate(false)}
        />
      )}
    </section>
  );
}

// ── 连接器编辑抽屉 ──

function ConnectorEditor({
  connector,
  onClose,
  onSave,
}: {
  connector: ApiConnector | null;
  onClose: () => void;
  onSave: () => void;
}) {
  const [code, setCode] = React.useState(connector?.code ?? "");
  const [name, setName] = React.useState(connector?.name ?? "");
  const [description, setDescription] = React.useState(connector?.description ?? "");
  const [baseUrl, setBaseUrl] = React.useState(connector?.base_url ?? "");
  const [method, setMethod] = React.useState(connector?.method ?? "GET");
  const [authType, setAuthType] = React.useState(connector?.auth_type ?? "none");
  const [authConfig, setAuthConfig] = React.useState(
    JSON.stringify(connector?.auth_config ?? {}, null, 2)
  );
  const [requestTemplate, setRequestTemplate] = React.useState(
    JSON.stringify(connector?.request_template ?? {}, null, 2)
  );
  const [error, setError] = React.useState("");

  // 字段映射
  const [mappings, setMappings] = React.useState<DataMapping[]>([]);
  const [showMappingEditor, setShowMappingEditor] = React.useState(false);

  React.useEffect(() => {
    if (connector) {
      loadMappings(connector.id);
    }
  }, [connector?.id]);

  async function loadMappings(connectorId: string) {
    const res = await api<DataMapping[]>(`/api/brain/connectors/${connectorId}/mappings`);
    setMappings(res.data ?? []);
  }

  async function save() {
    try {
      const authCfg = JSON.parse(authConfig);
      const reqTmpl = JSON.parse(requestTemplate);
      const payload = {
        code,
        name,
        description,
        base_url: baseUrl,
        method,
        auth_type: authType,
        auth_config: authCfg,
        request_template: reqTmpl,
      };

      if (connector) {
        await api(`/api/brain/connectors/${connector.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await api("/api/brain/connectors", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      setError("");
      onSave();
      onClose();
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <aside className="drawer wide">
      <div className="drawer-header">
        <div>
          <p className="crumb">API 连接器</p>
          <h2>{connector ? "编辑连接器" : "新建连接器"}</h2>
        </div>
        <button onClick={onClose}><X size={18} /></button>
      </div>
      <div className="form">
        <label>
          名称
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="如：合同管理系统" />
        </label>
        <label>
          编码
          <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="如：contract_system" />
        </label>
        <label>
          描述
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="描述这个连接器的数据源..." />
        </label>
        <div className="form-row">
          <label style={{ flex: 1 }}>
            请求方法
            <select value={method} onChange={(e) => setMethod(e.target.value)}>
              <option value="GET">GET</option>
              <option value="POST">POST</option>
              <option value="PUT">PUT</option>
            </select>
          </label>
          <label style={{ flex: 3 }}>
            基础 URL / 路径
            <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="/api/contracts/{contract_id}" />
          </label>
        </div>
        <label>
          认证方式
          <select value={authType} onChange={(e) => setAuthType(e.target.value)}>
            <option value="none">无认证</option>
            <option value="basic">Basic Auth</option>
            <option value="bearer">Bearer Token</option>
            <option value="apikey">API Key</option>
          </select>
        </label>
        <label>
          认证配置 JSON
          <textarea className="json-input" value={authConfig} onChange={(e) => setAuthConfig(e.target.value)} />
        </label>
        <label>
          请求模板 JSON
          <textarea className="json-input" value={requestTemplate} onChange={(e) => setRequestTemplate(e.target.value)} />
        </label>

        {connector && (
          <div className="mapping-section">
            <div className="mapping-header">
              <h4><Map size={16} /> 字段映射 ({mappings.length})</h4>
              <button className="ghost-button small" onClick={() => setShowMappingEditor(!showMappingEditor)}>
                {showMappingEditor ? "收起" : "管理映射"}
              </button>
            </div>
            {showMappingEditor && (
              <MappingEditor
                connectorId={connector.id}
                mappings={mappings}
                onChange={loadMappings}
              />
            )}
            {!showMappingEditor && mappings.length > 0 && (
              <div className="mapping-list-mini">
                {mappings.slice(0, 5).map((m) => (
                  <div key={m.id} className="mapping-row-mini">
                    <code>{m.source_field}</code>
                    <ChevronRight size={12} />
                    <span>{m.target_code}.{m.source_field.split(".").pop()}</span>
                    <span className="transform-tag">{m.transform}</span>
                  </div>
                ))}
                {mappings.length > 5 && <span className="muted">... 还有 {mappings.length - 5} 条</span>}
              </div>
            )}
          </div>
        )}

        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" onClick={save}>
          {connector ? "保存修改" : "创建连接器"}
        </button>
      </div>
    </aside>
  );
}

// ── 字段映射编辑器 ──

function MappingEditor({
  connectorId,
  mappings,
  onChange,
}: {
  connectorId: string;
  mappings: DataMapping[];
  onChange: (id: string) => void;
}) {
  const [newMapping, setNewMapping] = React.useState({
    source_field: "",
    target_type: "object",
    target_code: "",
    transform: "string",
    is_key: false,
    description: "",
  });

  async function addMapping() {
    if (!newMapping.source_field || !newMapping.target_code) return;
    await api(`/api/brain/connectors/${connectorId}/mappings`, {
      method: "POST",
      body: JSON.stringify(newMapping),
    });
    setNewMapping({
      source_field: "",
      target_type: "object",
      target_code: "",
      transform: "string",
      is_key: false,
      description: "",
    });
    onChange(connectorId);
  }

  async function removeMapping(id: string) {
    await api(`/api/brain/mappings/${id}`, { method: "DELETE" });
    onChange(connectorId);
  }

  return (
    <div className="mapping-editor">
      <div className="mapping-add-row">
        <input
          placeholder="源字段路径 (如 data.contract.amount)"
          value={newMapping.source_field}
          onChange={(e) => setNewMapping({ ...newMapping, source_field: e.target.value })}
        />
        <input
          placeholder="目标对象编码"
          value={newMapping.target_code}
          onChange={(e) => setNewMapping({ ...newMapping, target_code: e.target.value })}
        />
        <select
          value={newMapping.transform}
          onChange={(e) => setNewMapping({ ...newMapping, transform: e.target.value })}
        >
          <option value="string">string</option>
          <option value="int">int</option>
          <option value="float">float</option>
          <option value="money">money</option>
          <option value="date">date</option>
          <option value="datetime">datetime</option>
          <option value="bool">bool</option>
          <option value="enum">enum</option>
        </select>
        <label className="checkbox-inline">
          <input
            type="checkbox"
            checked={newMapping.is_key}
            onChange={(e) => setNewMapping({ ...newMapping, is_key: e.target.checked })}
          />
          主键
        </label>
        <button className="primary-button small" onClick={addMapping}>
          <Plus size={14} />
          添加
        </button>
      </div>
      <div className="mapping-table">
        {mappings.map((m) => (
          <div key={m.id} className="mapping-row">
            <code>{m.source_field}</code>
            <ChevronRight size={12} />
            <span>{m.target_code}</span>
            <span className="transform-tag">{m.transform}</span>
            {m.is_key && <span className="key-tag">主键</span>}
            <button className="icon-button tiny" onClick={() => removeMapping(m.id)}>
              <Trash2 size={12} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── 合成数据预览抽屉 ──

function SyntheticPreviewDrawer({
  connector,
  onClose,
}: {
  connector: ApiConnector;
  onClose: () => void;
}) {
  const [count, setCount] = React.useState(3);
  const [preview, setPreview] = React.useState<SyntheticPreviewResult | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  async function loadPreview() {
    setLoading(true);
    setError("");
    try {
      const res = await api<SyntheticPreviewResult>(
        `/api/brain/connectors/${connector.id}/preview`,
        {
          method: "POST",
          body: JSON.stringify({ connector_id: connector.id, count }),
        }
      );
      setPreview(res.data);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    loadPreview();
  }, []);

  return (
    <aside className="drawer wide">
      <div className="drawer-header">
        <div>
          <p className="crumb">合成数据预览</p>
          <h2>{connector.name}</h2>
        </div>
        <button onClick={onClose}><X size={18} /></button>
      </div>
      <div className="form">
        <div className="form-row" style={{ alignItems: "center" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            生成条数
            <input
              type="number"
              min={1}
              max={20}
              value={count}
              onChange={(e) => setCount(Math.min(20, Math.max(1, Number(e.target.value))))}
              style={{ width: 60 }}
            />
          </label>
          <button className="primary-button" onClick={loadPreview} disabled={loading}>
            <RefreshCw size={14} />
            {loading ? "生成中..." : "重新生成"}
          </button>
        </div>

        {error && <p className="form-error">{error}</p>}

        {preview && (
          <>
            <div className="preview-summary">
              <div className="preview-stat">
                <strong>{preview.mapping_summary.total_fields}</strong>
                <span>映射字段</span>
              </div>
              {Object.entries(preview.mapping_summary.by_type).map(([type, num]) => (
                <div key={type} className="preview-stat">
                  <strong>{num}</strong>
                  <span>{type}</span>
                </div>
              ))}
            </div>

            <h4>数据记录 ({preview.records.length})</h4>
            {preview.records.map((record, i) => (
              <div key={i} className="preview-record">
                <div className="preview-record-header">记录 #{i + 1}</div>
                <pre className="json-input">{JSON.stringify(record, null, 2)}</pre>
              </div>
            ))}
          </>
        )}
      </div>
    </aside>
  );
}

// ── 模板应用抽屉 ──

function TemplateDrawer({
  templates,
  onApply,
  onClose,
}: {
  templates: ConnectorTemplate[];
  onApply: (code: string) => void;
  onClose: () => void;
}) {
  return (
    <aside className="drawer">
      <div className="drawer-header">
        <div>
          <p className="crumb">预设模板</p>
          <h2>应用连接器模板</h2>
        </div>
        <button onClick={onClose}><X size={18} /></button>
      </div>
      <div className="template-list">
        {templates.map((tmpl) => (
          <div key={tmpl.code} className="template-card">
            <div className="template-card-header">
              <Database size={20} />
              <strong>{tmpl.name}</strong>
            </div>
            <p>{tmpl.description}</p>
            <div className="template-meta">
              <span>{tmpl.mapping_count} 个字段映射</span>
            </div>
            <button className="primary-button" onClick={() => onApply(tmpl.code)}>
              应用此模板
            </button>
          </div>
        ))}
        {templates.length === 0 && <p className="muted">暂无可用模板</p>}
      </div>
    </aside>
  );
}
