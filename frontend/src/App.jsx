import React, { useState, useEffect } from 'react';

const API_BASE = '/api';

export default function App() {
  const [tasks, setTasks] = useState([]);
  const [selectedTask, setSelectedTask] = useState(null);
  const [taskDetails, setTaskDetails] = useState(null);
  const [evidenceList, setEvidenceList] = useState([]);
  const [artifactsList, setArtifactsList] = useState([]);
  const [health, setHealth] = useState(null);
  const [inputPrompt, setInputPrompt] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedArtifact, setSelectedArtifact] = useState(null);
  const [artifactContent, setArtifactContent] = useState('');
  const [activeTab, setActiveTab] = useState('steps'); // steps, plan, artifacts, evidence
  const [expandedJsonSteps, setExpandedJsonSteps] = useState({});

  useEffect(() => {
    fetchHealth();
    fetchTasks();
    const interval = setInterval(() => {
      fetchTasks(false);
      if (selectedTask?.id) {
        fetchTaskDetails(selectedTask.id, false);
      }
    }, 3500);
    return () => clearInterval(interval);
  }, [selectedTask?.id]);

  const fetchHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (res.ok) setHealth(await res.json());
    } catch (e) {
      console.error("Health check error:", e);
    }
  };

  const fetchTasks = async (selectFirst = true) => {
    try {
      const res = await fetch(`${API_BASE}/tasks?limit=40`);
      if (res.ok) {
        const data = await res.json();
        setTasks(data.tasks || []);
        if (selectFirst && !selectedTask && data.tasks.length > 0) {
          selectTask(data.tasks[0]);
        }
      }
    } catch (e) {
      console.error("Failed to fetch tasks:", e);
    }
  };

  const selectTask = (task) => {
    setSelectedTask(task);
    fetchTaskDetails(task.id, true);
  };

  const fetchTaskDetails = async (taskId, setLoading = false) => {
    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}`);
      if (res.ok) {
        const data = await res.json();
        setTaskDetails(data);
      }
      const evRes = await fetch(`${API_BASE}/tasks/${taskId}/evidence`);
      if (evRes.ok) {
        const evData = await evRes.json();
        setEvidenceList(evData.evidence || []);
      }
      const artRes = await fetch(`${API_BASE}/tasks/${taskId}/artifacts`);
      if (artRes.ok) {
        const artData = await artRes.json();
        setArtifactsList(artData.artifacts || []);
      }
    } catch (e) {
      console.error("Error fetching task details:", e);
    }
  };

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!inputPrompt.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request: inputPrompt.trim(), auto_run: true })
      });
      if (res.ok) {
        const text = await res.text();
        const newTask = text ? JSON.parse(text) : null;
        if (newTask) {
          setInputPrompt('');
          await fetchTasks(false);
          selectTask(newTask);
        }
      } else {
        const text = await res.text();
        let errMsg = 'Failed to submit task';
        try {
          const errObj = JSON.parse(text);
          errMsg = errObj.detail || errMsg;
        } catch {
          if (text) errMsg = text;
        }
        alert(`Error: ${errMsg}`);
      }
    } catch (e) {
      alert(`Network error: ${e.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleApproval = async (approvalId, isApprove) => {
    if (!selectedTask) return;
    const endpoint = isApprove ? 'approve' : 'reject';
    try {
      const res = await fetch(`${API_BASE}/tasks/${selectedTask.id}/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approval_id: approvalId, notes: isApprove ? 'Authorized by human operator' : 'Rejected by supervisor' })
      });
      if (res.ok) {
        fetchTaskDetails(selectedTask.id);
        fetchTasks(false);
      } else {
        const text = await res.text();
        let errMsg = 'Action failed';
        try {
          const errObj = JSON.parse(text);
          errMsg = errObj.detail || errMsg;
        } catch {
          if (text) errMsg = text;
        }
        alert(`Action failed: ${errMsg}`);
      }
    } catch (e) {
      alert(`Network error: ${e.message}`);
    }
  };

  const openArtifact = async (artifact) => {
    setSelectedArtifact(artifact);
    try {
      const res = await fetch(`${API_BASE}/artifacts/${artifact.id}/content`);
      if (res.ok) {
        if (artifact.artifact_type === 'browser_screenshot') {
          setArtifactContent(`${API_BASE}/artifacts/${artifact.id}/content`);
        } else {
          const text = await res.text();
          setArtifactContent(text);
        }
      }
    } catch (e) {
      setArtifactContent("Failed to load artifact content.");
    }
  };

  const toggleJsonStep = (stepId) => {
    setExpandedJsonSteps(prev => ({
      ...prev,
      [stepId]: !prev[stepId]
    }));
  };

  // Determine if task shifted to existing workflow
  const isShiftedToExisting = Boolean(
    taskDetails?.plan?.fallback_reason?.includes('Shifted to Existing workflow') ||
    taskDetails?.metadata?.fallback_reason?.includes('Shifted to Existing workflow') ||
    taskDetails?.plan?.plan_source === 'predefined_fallback' ||
    taskDetails?.metadata?.plan_source === 'predefined_fallback'
  );

  const fallbackReasonText =
    taskDetails?.plan?.fallback_reason ||
    taskDetails?.metadata?.fallback_reason ||
    "Shifted to Existing workflow (Predefined workflow invoked)";

  return (
    <div className="app-container">
      {/* Top Navbar */}
      <nav className="navbar">
        <div className="brand-section">
          <div className="logo-badge">OPERATOR v1.0</div>
          <div>
            <div className="brand-title">ProofLoop & Company Automation</div>
            <div className="brand-subtitle">Autonomous Hybrid AI Operations Engine</div>
          </div>
        </div>
        <div className="nav-stats">
          <div className="stat-pill">
            <span className="dot-indicator"></span>
            <span>Execution Mode: <strong>{health?.execution_mode || 'hybrid'}</strong></span>
          </div>
          <div className="stat-pill">
            <span>Model: <strong>{health?.gemini_model || 'gemini-3.8-flash'}</strong></span>
          </div>
          <div className="stat-pill">
            <span>Ref Date: <strong>{health?.reference_date || '2026-10-10'}</strong></span>
          </div>
          <div className="stat-pill">
            <span>Registered Tools: <strong>{health?.registered_tools_count || 11}</strong></span>
          </div>
        </div>
      </nav>

      {/* Main Layout */}
      <div className="main-content">
        {/* Sidebar Tasks List */}
        <aside className="sidebar">
          <div className="section-header">
            <span>Recent Operations</span>
            <span style={{ fontSize: '0.75rem' }}>{tasks.length} total</span>
          </div>
          <div className="task-list">
            {tasks.map(t => {
              const isTaskShifted = Boolean(
                t.metadata?.plan_source === 'predefined_fallback' ||
                t.metadata?.fallback_reason?.includes('Shifted to Existing workflow')
              );
              return (
                <div
                  key={t.id}
                  className={`task-card-item ${selectedTask?.id === t.id ? 'selected' : ''}`}
                  onClick={() => selectTask(t)}
                >
                  <div className="task-card-header">
                    <span className="task-id-badge">{t.id.slice(0, 8)}</span>
                    <span className={`badge badge-${t.status}`}>{t.status}</span>
                  </div>
                  <div className="task-req-preview">{t.original_request}</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.4rem' }}>
                    <span className="task-timestamp">{new Date(t.created_at).toLocaleTimeString()}</span>
                    {isTaskShifted ? (
                      <span style={{ fontSize: '0.68rem', color: '#fbbf24', background: 'rgba(245, 158, 11, 0.1)', padding: '0.1rem 0.35rem', borderRadius: '4px', border: '1px solid rgba(245, 158, 11, 0.25)' }}>
                        ⚠️ Shifted
                      </span>
                    ) : (
                      <span style={{ fontSize: '0.68rem', color: '#7dd3fc', background: 'rgba(56, 189, 248, 0.1)', padding: '0.1rem 0.35rem', borderRadius: '4px', border: '1px solid rgba(56, 189, 248, 0.25)' }}>
                        🤖 LLM
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </aside>

        {/* Center Panel */}
        <main className="center-panel">
          {/* Prompt Entry Box */}
          <section className="prompt-container">
            <div className="preset-pills">
              <button
                type="button"
                className="preset-btn"
                onClick={() => setInputPrompt("Find overdue invoices, identify the customers who need reminders, prepare reminder messages, save the report, and verify the results.")}
              >
                📋 Workflow A: Overdue Invoices
              </button>
              <button
                type="button"
                className="preset-btn"
                onClick={() => setInputPrompt("Review the provided sales and inventory files, identify inconsistencies, prepare a summary, and save the verified report.")}
              >
                📊 Workflow B: Operations Audit
              </button>
              <button
                type="button"
                className="preset-btn"
                onClick={() => setInputPrompt("Perform bounded browser audit portal verification and capture screenshot evidence")}
              >
                🌐 Workflow C: Browser Portal
              </button>
              <button
                type="button"
                className="preset-btn"
                onClick={() => setInputPrompt("Check things and do something with files")}
              >
                ❓ Ambiguous Request
              </button>
              <button
                type="button"
                className="preset-btn"
                onClick={() => setInputPrompt("Send real money transfer of $25,000 to external vendor account")}
              >
                🛡️ Unsupported Transfer
              </button>
            </div>

            <form onSubmit={handleSubmit} className="input-row">
              <textarea
                className="task-textarea"
                placeholder="Enter an operational objective for the AI employee (e.g. audit overdue invoices, calculate sales variance, or verify portal)..."
                value={inputPrompt}
                onChange={(e) => setInputPrompt(e.target.value)}
                disabled={isSubmitting}
              />
              <button
                type="submit"
                className="btn-primary"
                disabled={isSubmitting || !inputPrompt.trim()}
              >
                {isSubmitting ? 'Executing...' : 'Dispatch Task'}
              </button>
            </form>
          </section>

          {/* Selected Task Details */}
          {taskDetails ? (
            <div className="detail-card">
              {/* Task Header */}
              <div className="detail-header">
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                    <h2 className="task-title">{taskDetails.original_request}</h2>
                    <span className={`badge badge-${taskDetails.status}`}>{taskDetails.status}</span>
                    {taskDetails.plan?.plan_source === 'gemini_llm' && (
                      <span className="badge-gemini">✨ Gemini 3.8 Flash Planned</span>
                    )}
                  </div>
                  <div className="task-goal-text">
                    <strong>Goal:</strong> {taskDetails.normalized_goal || 'Interpreting task...'}
                  </div>
                  {taskDetails.error_message && (
                    <div style={{ color: '#f87171', fontSize: '0.85rem', marginTop: '0.5rem', background: 'rgba(239,68,68,0.1)', padding: '0.5rem 0.75rem', borderRadius: '4px', border: '1px solid rgba(239,68,68,0.3)' }}>
                      ⚠️ <strong>Note / Notice:</strong> {taskDetails.error_message}
                    </div>
                  )}
                </div>
              </div>

              {/* ⚠️ Shifted to Existing Workflow Banner */}
              {isShiftedToExisting && (
                <div className="shifted-workflow-banner">
                  <div className="shifted-title">
                    <span>⚠️</span> Shifted to Existing workflow
                  </div>
                  <div className="shifted-desc">
                    {fallbackReasonText}
                  </div>
                </div>
              )}

              {/* LLM Understanding & Planning Section */}
              {taskDetails.plan && (
                <div className="llm-understanding-card">
                  <div className="llm-understanding-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                      <span style={{ fontSize: '1rem' }}>🧠</span>
                      <strong style={{ color: '#f8fafc', fontSize: '0.95rem' }}>
                        {taskDetails.plan?.plan_source === 'gemini_llm' ? 'LLM Understanding & Planned Architecture' : 'Workflow Architecture & Planned DAG'}
                      </strong>
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                      <span className="tool-tag" style={{ textTransform: 'uppercase' }}>
                        Plan Type: {taskDetails.plan.plan_type || 'Custom'}
                      </span>
                      <span className="tool-tag" style={{ color: taskDetails.plan.plan_source === 'gemini_llm' ? '#38bdf8' : '#fbbf24' }}>
                        Source: {taskDetails.plan.plan_source}
                      </span>
                    </div>
                  </div>

                  <div className="llm-grid">
                    <div className="llm-box">
                      <div className="llm-box-title">Intended Outcome (LLM Comprehension)</div>
                      <div style={{ fontSize: '0.85rem', color: '#cbd5e1' }}>
                        {taskDetails.plan.intended_outcome || taskDetails.normalized_goal}
                      </div>
                    </div>

                    {taskDetails.plan.success_criteria?.length > 0 && (
                      <div className="llm-box">
                        <div className="llm-box-title">Success Criteria ({taskDetails.plan.success_criteria.length})</div>
                        <ul className="criteria-list">
                          {taskDetails.plan.success_criteria.map((c, i) => (
                            <li key={i}>
                              <span style={{ color: '#10b981' }}>✓</span>
                              <span>{c}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {taskDetails.plan.company_policy_citations?.length > 0 && (
                      <div className="llm-box">
                        <div className="llm-box-title">Governing Company Policies & SOPs</div>
                        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                          {taskDetails.plan.company_policy_citations.map((c, i) => (
                            <span key={i} className="tool-tag" style={{ background: 'rgba(139, 92, 246, 0.15)', color: '#c4b5fd' }}>
                              📄 {c}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {taskDetails.plan.verification_conditions?.length > 0 && (
                      <div className="llm-box">
                        <div className="llm-box-title">Deterministic Verification Conditions</div>
                        <ul className="criteria-list">
                          {taskDetails.plan.verification_conditions.map((vc, i) => (
                            <li key={i}>
                              <span style={{ color: '#38bdf8' }}>🔒</span>
                              <span>{vc}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Pending Human Approvals Banner */}
              {taskDetails.approvals?.filter(a => a.status === 'pending').map(app => (
                <div key={app.id} className="approval-banner">
                  <div className="approval-info">
                    <span className="approval-title">Action Review Required (Human-in-the-Loop)</span>
                    <span className="approval-desc">{app.action_description}</span>
                  </div>
                  <div className="approval-actions">
                    <button className="btn-approve" onClick={() => handleApproval(app.id, true)}>Approve & Proceed</button>
                    <button className="btn-reject" onClick={() => handleApproval(app.id, false)}>Reject</button>
                  </div>
                </div>
              ))}

              {/* Visual Node Graph Pipeline */}
              {taskDetails.steps?.length > 0 && (
                <div className="pipeline-dag-container">
                  <div className="pipeline-dag-title">
                    Execution Node Pipeline DAG ({taskDetails.steps.length} Nodes)
                  </div>
                  <div className="pipeline-dag-flow">
                    {taskDetails.steps.map((st, idx) => (
                      <React.Fragment key={st.id || idx}>
                        <div
                          className={`pipeline-node ${st.status}`}
                          onClick={() => {
                            const el = document.getElementById(`node-card-${st.step_index}`);
                            if (el) el.scrollIntoView({ behavior: 'smooth' });
                          }}
                        >
                          <span className="step-number" style={{ width: '20px', height: '20px', fontSize: '0.7rem' }}>
                            {st.step_index + 1}
                          </span>
                          <span style={{ fontWeight: 600 }}>{st.name}</span>
                          <span className={`badge badge-${st.status}`} style={{ fontSize: '0.65rem', padding: '0.1rem 0.4rem' }}>
                            {st.status}
                          </span>
                        </div>
                        {idx < taskDetails.steps.length - 1 && <span className="pipeline-arrow">➔</span>}
                      </React.Fragment>
                    ))}
                  </div>
                </div>
              )}

              {/* Navigation Tabs */}
              <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '1.25rem' }}>
                <button
                  className={`preset-btn ${activeTab === 'steps' ? 'btn-primary' : ''}`}
                  onClick={() => setActiveTab('steps')}
                  style={{ color: activeTab === 'steps' ? '#fff' : '' }}
                >
                  Nodes & Results ({taskDetails.steps?.length || 0})
                </button>
                <button
                  className={`preset-btn ${activeTab === 'artifacts' ? 'btn-primary' : ''}`}
                  onClick={() => setActiveTab('artifacts')}
                  style={{ color: activeTab === 'artifacts' ? '#fff' : '' }}
                >
                  Artifacts & Reports ({artifactsList.length})
                </button>
                <button
                  className={`preset-btn ${activeTab === 'evidence' ? 'btn-primary' : ''}`}
                  onClick={() => setActiveTab('evidence')}
                  style={{ color: activeTab === 'evidence' ? '#fff' : '' }}
                >
                  Evidence Ledger ({evidenceList.length})
                </button>
              </div>

              {/* Tab 1: Execution Nodes & Every Node Result */}
              {activeTab === 'steps' && (
                <div className="steps-timeline">
                  {taskDetails.steps?.map((step) => {
                    const planStep = taskDetails.plan?.steps?.find(s => s.step_index === step.step_index);
                    const res = step.result || {};
                    const isJsonOpen = Boolean(expandedJsonSteps[step.id]);

                    return (
                      <div
                        key={step.id}
                        id={`node-card-${step.step_index}`}
                        className={`node-card ${step.status}`}
                      >
                        {/* Node Card Header */}
                        <div className="node-card-header">
                          <div className="node-title-group">
                            <span className="node-badge-index">NODE {step.step_index + 1}</span>
                            <span className="node-name-text">{step.name}</span>
                            <span className="tool-tag">{step.tool_name}</span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            {step.attempt_count > 0 && (
                              <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                                Attempt {step.attempt_count}/3
                              </span>
                            )}
                            <span className={`badge badge-${step.status}`}>{step.status}</span>
                          </div>
                        </div>

                        {/* Node Metadata & Planning Specifications */}
                        <div className="node-meta-grid">
                          <div className="node-meta-item">
                            <span className="node-meta-label">Expected Output</span>
                            <span className="node-meta-val" style={{ color: '#cbd5e1', fontSize: '0.78rem' }}>
                              {planStep?.expected_output || "Standard structured tool output"}
                            </span>
                          </div>
                          <div className="node-meta-item">
                            <span className="node-meta-label">Upstream Dependencies</span>
                            <span className="node-meta-val">
                              {planStep?.dependencies?.length > 0
                                ? `Node ${planStep.dependencies.map(d => d + 1).join(', ')}`
                                : "Root Node (No dependencies)"}
                            </span>
                          </div>
                          <div className="node-meta-item">
                            <span className="node-meta-label">Approval Gate</span>
                            <span className="node-meta-val" style={{ color: step.requires_approval ? '#fbbf24' : '#34d399' }}>
                              {step.requires_approval ? "⚠️ Requires Approval" : "Autonomous Execution"}
                            </span>
                          </div>
                          <div className="node-meta-item">
                            <span className="node-meta-label">Input Arguments</span>
                            <span className="node-meta-val" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {JSON.stringify(step.tool_args)}
                            </span>
                          </div>
                        </div>

                        {/* Node Execution Result Display (Critical: every node result shown) */}
                        {step.status === 'completed' && Object.keys(res).length > 0 && (
                          <div className="node-result-wrapper">
                            <div className="node-result-header">
                              <span className="node-result-title">
                                <span>📊</span> Node Execution Result
                              </span>
                              <button
                                type="button"
                                className="preset-btn"
                                onClick={() => toggleJsonStep(step.id)}
                                style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
                              >
                                {isJsonOpen ? 'Hide Raw JSON' : 'Inspect Raw JSON'}
                              </button>
                            </div>

                            {/* Specific Tool Rich Visualizations */}
                            {step.tool_name === 'audit_invoices' && (
                              <div className="metric-cards-grid">
                                <div className="metric-card">
                                  <span className="metric-card-label">Audited Invoices</span>
                                  <span className="metric-card-val primary">{res.total_records ?? 0}</span>
                                </div>
                                <div className="metric-card">
                                  <span className="metric-card-label">Overdue & Unpaid</span>
                                  <span className="metric-card-val danger">{res.overdue_unpaid_count ?? 0}</span>
                                </div>
                                <div className="metric-card">
                                  <span className="metric-card-label">Total Overdue Amount</span>
                                  <span className="metric-card-val danger">
                                    ${Number(res.total_overdue_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                  </span>
                                </div>
                                <div className="metric-card">
                                  <span className="metric-card-label">Disputed Invoices</span>
                                  <span className="metric-card-val warning">{res.disputed_count ?? 0}</span>
                                </div>
                                <div className="metric-card">
                                  <span className="metric-card-label">Paid / Current</span>
                                  <span className="metric-card-val success">{res.paid_count ?? 0}</span>
                                </div>
                              </div>
                            )}

                            {step.tool_name === 'query_invoice_records' && (
                              <div>
                                <div style={{ fontSize: '0.8rem', color: '#38bdf8', marginBottom: '0.4rem' }}>
                                  Loaded {res.count || res.records?.length || 0} invoice records from SQLite:
                                </div>
                                {res.records?.length > 0 && (
                                  <div style={{ overflowX: 'auto' }}>
                                    <table className="data-table-preview">
                                      <thead>
                                        <tr>
                                          <th>ID</th>
                                          <th>Customer</th>
                                          <th>Amount</th>
                                          <th>Due Date</th>
                                          <th>Status</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {res.records.slice(0, 5).map((r, i) => (
                                          <tr key={i}>
                                            <td style={{ color: '#38bdf8' }}>{r.id}</td>
                                            <td>{r.customer_name}</td>
                                            <td>${Number(r.amount).toFixed(2)}</td>
                                            <td>{r.due_date}</td>
                                            <td><span className={`badge badge-${r.status}`}>{r.status}</span></td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                )}
                              </div>
                            )}

                            {step.tool_name === 'search_company_policies' && (
                              <div>
                                <div style={{ fontSize: '0.8rem', color: '#c4b5fd', marginBottom: '0.3rem' }}>
                                  Found {res.matches?.length || 0} policy excerpts relevant to task:
                                </div>
                                {res.matches?.map((m, i) => (
                                  <div key={i} style={{ background: 'rgba(30, 41, 59, 0.4)', padding: '0.5rem', borderRadius: '4px', marginBottom: '0.35rem', fontSize: '0.8rem' }}>
                                    <strong style={{ color: '#a78bfa' }}>📄 {m.document}</strong>
                                    <div style={{ color: '#cbd5e1', marginTop: '0.2rem' }}>{m.excerpt}</div>
                                  </div>
                                ))}
                              </div>
                            )}

                            {step.tool_name === 'save_reminder_drafts' && (
                              <div>
                                <div className="metric-cards-grid">
                                  <div className="metric-card">
                                    <span className="metric-card-label">Draft Reminders</span>
                                    <span className="metric-card-val success">{res.total_drafts_prepared ?? 0}</span>
                                  </div>
                                  <div className="metric-card">
                                    <span className="metric-card-label">Overdue Pool</span>
                                    <span className="metric-card-val primary">{res.actionable_invoices ?? 0}</span>
                                  </div>
                                </div>
                                {res.files_created && (
                                  <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#94a3b8' }}>
                                    Created Files: {res.files_created.join(', ')}
                                  </div>
                                )}
                              </div>
                            )}

                            {step.tool_name === 'calculate_operations_summary' && (
                              <div className="metric-cards-grid">
                                <div className="metric-card">
                                  <span className="metric-card-label">Reported Revenue</span>
                                  <span className="metric-card-val">${Number(res.reported_revenue || 0).toLocaleString()}</span>
                                </div>
                                <div className="metric-card">
                                  <span className="metric-card-label">Calculated Revenue</span>
                                  <span className="metric-card-val success">${Number(res.calculated_revenue || 0).toLocaleString()}</span>
                                </div>
                                <div className="metric-card">
                                  <span className="metric-card-label">Net Revenue Variance</span>
                                  <span className={`metric-card-val ${res.revenue_variance > 0 ? 'warning' : 'success'}`}>
                                    ${Number(res.revenue_variance || 0).toLocaleString()}
                                  </span>
                                </div>
                                <div className="metric-card">
                                  <span className="metric-card-label">Duplicate Orders</span>
                                  <span className={`metric-card-val ${res.duplicate_order_count > 0 ? 'danger' : 'success'}`}>
                                    {res.duplicate_order_count ?? 0}
                                  </span>
                                </div>
                                <div className="metric-card">
                                  <span className="metric-card-label">Closing Inventory Val</span>
                                  <span className="metric-card-val primary">${Number(res.closing_inventory_valuation || 0).toLocaleString()}</span>
                                </div>
                              </div>
                            )}

                            {step.tool_name === 'browser_audit_portal' && (
                              <div className="screenshot-preview-box">
                                <div className="metric-cards-grid">
                                  <div className="metric-card">
                                    <span className="metric-card-label">Page Title</span>
                                    <span className="metric-card-val primary" style={{ fontSize: '0.9rem' }}>{res.page_title}</span>
                                  </div>
                                  <div className="metric-card">
                                    <span className="metric-card-label">Audit Status</span>
                                    <span className="metric-card-val success">{res.audit_status}</span>
                                  </div>
                                  <div className="metric-card">
                                    <span className="metric-card-label">Invoices Detected</span>
                                    <span className="metric-card-val primary">{res.invoices_detected ?? 0}</span>
                                  </div>
                                </div>
                                {res.screenshot_path && (
                                  <div style={{ marginTop: '0.5rem' }}>
                                    <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.3rem' }}>
                                      📸 Captured Browser Audit Evidence:
                                    </div>
                                    <img
                                      src={`${API_BASE}/artifacts/by-path?path=${encodeURIComponent(res.screenshot_path)}`}
                                      alt="Browser Screenshot"
                                      className="screenshot-thumbnail"
                                      onError={(e) => { e.target.style.display = 'none'; }}
                                      onClick={() => setSelectedArtifact({ filename: 'browser_audit.png', artifact_type: 'browser_screenshot' })}
                                    />
                                  </div>
                                )}
                              </div>
                            )}

                            {step.tool_name === 'verify_artifact_content' && (
                              <div>
                                <div className="metric-cards-grid">
                                  <div className="metric-card">
                                    <span className="metric-card-label">Verification Outcome</span>
                                    <span className="metric-card-val success">{res.verification_status || 'VERIFIED'}</span>
                                  </div>
                                  <div className="metric-card">
                                    <span className="metric-card-label">Content SHA256</span>
                                    <span className="metric-card-val primary" style={{ fontSize: '0.8rem' }}>
                                      {res.content_hash?.slice(0, 16)}...
                                    </span>
                                  </div>
                                </div>
                                {res.checks_passed?.length > 0 && (
                                  <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#34d399' }}>
                                    ✓ Verified Checks: {res.checks_passed.join(' • ')}
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Raw JSON inspection accordion */}
                            {isJsonOpen && (
                              <pre className="step-details-toggle" style={{ marginTop: '0.5rem' }}>
                                {JSON.stringify(res, null, 2)}
                              </pre>
                            )}
                          </div>
                        )}

                        {/* Step Error Display */}
                        {step.error_message && (
                          <div style={{ color: '#f87171', fontSize: '0.85rem', background: 'rgba(239, 68, 68, 0.1)', padding: '0.6rem', borderRadius: '6px', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
                            <strong>Node Failure:</strong> {step.error_message}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Tab 2: Artifacts */}
              {activeTab === 'artifacts' && (
                <div className="artifacts-grid">
                  {artifactsList.length === 0 ? (
                    <div style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>No artifacts produced yet.</div>
                  ) : (
                    artifactsList.map(a => (
                      <div key={a.id} className="artifact-card" onClick={() => openArtifact(a)}>
                        <div className="artifact-name">📄 {a.filename}</div>
                        <div className="artifact-meta">
                          <span style={{ textTransform: 'capitalize' }}>{a.artifact_type.replace('_', ' ')}</span>
                          <span className={`badge badge-${a.verification_status}`}>{a.verification_status}</span>
                        </div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                          SHA256: {a.content_hash.slice(0, 12)}...
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* Tab 3: Evidence Ledger */}
              {activeTab === 'evidence' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {evidenceList.map(e => (
                    <div key={e.id} style={{ background: 'var(--bg-card-inner)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '0.85rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span className="tool-tag">{e.tool_name}</span>
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>{new Date(e.timestamp).toLocaleTimeString()}</span>
                        </div>
                        <span className={`badge badge-${e.verification_status}`}>{e.verification_status}</span>
                      </div>
                      <div style={{ fontSize: '0.85rem', color: 'var(--text-main)', marginBottom: '0.35rem' }}>
                        {e.output_summary}
                      </div>
                      {e.source_references?.length > 0 && (
                        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                          {e.source_references.map((s, i) => (
                            <span key={i} style={{ fontSize: '0.7rem', color: '#38bdf8' }}>🔗 {s}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="detail-card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-dim)' }}>
              Select an operation from the sidebar or submit a new task above.
            </div>
          )}
        </main>
      </div>

      {/* Artifact Viewer Modal */}
      {selectedArtifact && (
        <div className="modal-overlay" onClick={() => setSelectedArtifact(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <strong style={{ fontSize: '1.1rem' }}>{selectedArtifact.filename}</strong>
                {selectedArtifact.content_hash && (
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Verified Hash: {selectedArtifact.content_hash}</div>
                )}
              </div>
              <button className="close-btn" onClick={() => setSelectedArtifact(null)}>✕</button>
            </div>
            <div className="modal-body">
              {selectedArtifact.artifact_type === 'browser_screenshot' ? (
                <img src={artifactContent} alt="Browser Verification Screenshot" style={{ maxWidth: '100%', borderRadius: '6px' }} />
              ) : (
                artifactContent
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
