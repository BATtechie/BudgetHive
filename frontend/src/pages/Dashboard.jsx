import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api';

const CATEGORIES = [
  'Electronics', 'Smartphones', 'Laptops', 'Tablets', 'Headphones', 'Earphones',
  'Smartwatches', 'Wearables', 'Gaming Consoles', 'Appliances', 'Furniture',
  'Home', 'Accessories', 'Fashion', 'Books',
];

const AGENT_LABELS = {
  A1_Financial: 'Financial Health',
  A2_Need: 'Need Assessment',
  A3_DealHunter: 'Deal Hunter',
  A4_Alternatives: 'Alternatives',
  A5_RegretPredictor: 'Regret Predictor',
};

const TABS = ['overview', 'evaluate', 'history', 'purchases'];

function VerdictBadge({ verdict }) {
  const cls = verdict === 'BUY' ? 'verdict-buy' : verdict === 'MAYBE' ? 'verdict-maybe' : 'verdict-skip';
  return <span className={`verdict-badge ${cls}`}>{verdict}</span>;
}

function ScoreBar({ score, verdict }) {
  const cls = verdict === 'BUY' ? 'score-buy' : verdict === 'MAYBE' ? 'score-maybe' : 'score-skip';
  return (
    <div className="score-bar">
      <div className={`score-bar-fill ${cls}`} style={{ width: `${score}%` }} />
    </div>
  );
}

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

function formatPrice(n) {
  return '₹' + Number(n).toLocaleString('en-IN');
}

function StatCard({ label, value, sub, color }) {
  return (
    <div className="dash-stat-card">
      <span className="dash-stat-label">{label}</span>
      <span className="dash-stat-value" style={color ? { color } : {}}>{value}</span>
      {sub && <span className="dash-stat-sub">{sub}</span>}
    </div>
  );
}

function OverviewTab({ verdicts, purchases, user, onNavigate }) {
  const buyCount = verdicts.filter(v => v.verdict === 'BUY').length;
  const maybeCount = verdicts.filter(v => v.verdict === 'MAYBE').length;
  const skipCount = verdicts.filter(v => v.verdict === 'SKIP').length;
  const avgScore = verdicts.length
    ? Math.round(verdicts.reduce((s, v) => s + v.composite_score, 0) / verdicts.length)
    : 0;
  const totalSpent = purchases.reduce((s, p) => s + p.purchase_price, 0);
  const avgRegret = purchases.filter(p => p.regret_score != null);
  const regretAvg = avgRegret.length
    ? Math.round(avgRegret.reduce((s, p) => s + p.regret_score, 0) / avgRegret.length)
    : null;

  const disposable = (user?.monthly_income || 0) - (user?.monthly_savings_target || 0) - (user?.active_emis || 0) - (user?.recurring_bills || 0);

  return (
    <>
      <div className="dash-stats-grid">
        <StatCard label="Disposable / mo" value={formatPrice(Math.max(0, disposable))} />
        <StatCard label="Evaluations" value={verdicts.length} sub={`${buyCount} BUY · ${maybeCount} MAYBE · ${skipCount} SKIP`} />
        <StatCard label="Avg Score" value={`${avgScore}/100`} color={avgScore >= 70 ? 'var(--color-accent)' : avgScore >= 40 ? 'var(--color-primary)' : 'var(--color-danger)'} />
        <StatCard label="Purchases" value={purchases.length} sub={`Total: ${formatPrice(totalSpent)}`} />
      </div>

      {regretAvg !== null && (
        <div className="dash-regret-bar-wrap">
          <div className="dash-section-row">
            <span className="dash-section-label">AVG REGRET</span>
            <span className="dash-regret-num">{regretAvg}/100</span>
          </div>
          <div className="score-bar">
            <div
              className={`score-bar-fill ${regretAvg >= 60 ? 'score-skip' : regretAvg >= 30 ? 'score-maybe' : 'score-buy'}`}
              style={{ width: `${regretAvg}%` }}
            />
          </div>
        </div>
      )}

      <div className="dash-section-row" style={{ marginTop: 'var(--space-xl)' }}>
        <span className="dash-section-label">RECENT VERDICTS</span>
        {verdicts.length > 3 && (
          <button className="dash-link-btn" onClick={() => onNavigate('history')}>View all →</button>
        )}
      </div>

      {verdicts.length === 0 && (
        <div className="dash-empty">
          <p>No evaluations yet.</p>
          <button className="btn btn-primary" onClick={() => onNavigate('evaluate')}>Evaluate your first product</button>
        </div>
      )}

      <div className="dash-verdict-list">
        {verdicts.slice(0, 3).map(v => (
          <VerdictRow key={v.verdict_id} v={v} />
        ))}
      </div>

      {purchases.length > 0 && (
        <>
          <div className="dash-section-row" style={{ marginTop: 'var(--space-xl)' }}>
            <span className="dash-section-label">PURCHASE HISTORY</span>
            {purchases.length > 4 && (
              <button className="dash-link-btn" onClick={() => onNavigate('purchases')}>View all →</button>
            )}
          </div>
          <div className="dash-purchase-list">
            {purchases.slice(0, 4).map(p => (
              <PurchaseRow key={p.id} p={p} />
            ))}
          </div>
        </>
      )}
    </>
  );
}

function VerdictRow({ v }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`dash-verdict-row ${open ? 'open' : ''}`} onClick={() => setOpen(!open)}>
      <div className="dash-verdict-row-top">
        <div className="dash-verdict-row-left">
          <span className="dash-verdict-product">{v.product_name}</span>
          <span className="dash-verdict-meta">{v.product_name && v.created_at ? timeAgo(v.created_at) : ''} · Score {v.composite_score}</span>
        </div>
        <VerdictBadge verdict={v.verdict} />
      </div>
      {open && (
        <div className="dash-verdict-detail">
          <div className="dash-verdict-scores">
            <span>Confidence: {v.confidence_percentage}%</span>
            <ScoreBar score={v.composite_score} verdict={v.verdict} />
          </div>
          <div className="dash-agent-list">
            {v.agent_results.map(a => (
              <div key={a.agent_name} className="dash-agent-item">
                <div className="dash-agent-item-head">
                  <span>{AGENT_LABELS[a.agent_name] || a.agent_name}</span>
                  <span className="dash-agent-score">{a.score != null ? `${a.score}/100` : 'Skipped'}</span>
                </div>
                <p className="dash-agent-reasoning">{a.reasoning}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PurchaseRow({ p }) {
  const regretColor = p.regret_score >= 60 ? 'var(--color-danger)' : p.regret_score >= 30 ? 'var(--color-primary)' : 'var(--color-accent)';
  return (
    <div className="dash-purchase-row">
      <div className="dash-purchase-left">
        <span className="dash-purchase-name">{p.product_name}</span>
        <span className="dash-purchase-meta">
          {p.product_category} · {p.usage_duration_days ? `${p.usage_duration_days}d used` : 'Active'}
          {p.is_returned && ' · Returned'}
          {p.is_resold && ' · Resold'}
        </span>
      </div>
      <div className="dash-purchase-right">
        <span className="dash-purchase-price">{formatPrice(p.purchase_price)}</span>
        {p.regret_score != null && (
          <span className="dash-purchase-regret" style={{ color: regretColor }}>
            Regret {p.regret_score}
          </span>
        )}
      </div>
    </div>
  );
}

function EvaluateTab({ token, onDone }) {
  const [form, setForm] = useState({
    product_name: '', product_url: '', product_category: 'Electronics',
    price: '', max_budget: '', primary_use_case: '',
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    setResult(null);
    try {
      const body = {
        product_name: form.product_name,
        product_category: form.product_category,
        price: parseFloat(form.price),
      };
      if (form.product_url) body.product_url = form.product_url;
      if (form.max_budget) body.max_budget = parseFloat(form.max_budget);
      if (form.primary_use_case) body.primary_use_case = form.primary_use_case;

      const data = await api.verdictEvaluate(body, token);
      setResult(data);
      onDone();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dash-evaluate-layout">
      <div className="card card-elevated">
        <h3 className="dash-card-title">Evaluate a Purchase</h3>
        {error && <div className="alert alert-error" style={{ marginBottom: 'var(--space-md)' }}>{error}</div>}
        <form className="evaluate-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="product_name">Product Name</label>
            <input id="product_name" className="form-input" type="text" required value={form.product_name} onChange={set('product_name')} placeholder="Sony WH-1000XM5" />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label" htmlFor="price">Price</label>
              <input id="price" className="form-input" type="number" required min={1} step="any" value={form.price} onChange={set('price')} placeholder="26990" />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="category">Category</label>
              <select id="category" className="form-input" value={form.product_category} onChange={set('product_category')}>
                {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="product_url">Product URL (optional)</label>
            <input id="product_url" className="form-input" type="url" value={form.product_url} onChange={set('product_url')} placeholder="https://www.amazon.in/dp/..." />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label" htmlFor="max_budget">Max Budget (optional)</label>
              <input id="max_budget" className="form-input" type="number" min={0} step="any" value={form.max_budget} onChange={set('max_budget')} placeholder="30000" />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="use_case">Primary Use Case (optional)</label>
              <input id="use_case" className="form-input" type="text" value={form.primary_use_case} onChange={set('primary_use_case')} placeholder="Work calls" />
            </div>
          </div>
          <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={loading}>
            {loading ? <><span className="spinner" /> Analyzing...</> : 'Get Verdict'}
          </button>
        </form>
      </div>

      <div>
        {loading && (
          <div className="card card-elevated" style={{ textAlign: 'center', padding: 'var(--space-2xl)' }}>
            <div className="spinner spinner-lg" />
            <p style={{ marginTop: 'var(--space-md)', color: 'var(--color-text-muted)' }}>Running agents...</p>
          </div>
        )}
        {!loading && !result && (
          <div className="card card-elevated" style={{ textAlign: 'center', padding: 'var(--space-2xl)', color: 'var(--color-text-muted)' }}>
            <p>Submit a product to see your verdict</p>
          </div>
        )}
        {!loading && result && (
          <div className="card card-elevated verdict-result">
            <div className="verdict-result-header">
              <h3>{result.product_name}</h3>
              <VerdictBadge verdict={result.verdict} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.88rem' }}>
              <span>Composite Score: <strong>{result.composite_score}/100</strong></span>
              <span>Confidence: <strong>{result.confidence_percentage}%</strong></span>
            </div>
            <ScoreBar score={result.composite_score} verdict={result.verdict} />
            <div className="agent-results">
              {result.agent_results.map(agent => (
                <div key={agent.agent_name} className={`agent-card ${agent.score === null ? 'agent-skipped' : ''}`}>
                  <div className="agent-card-header">
                    <span className="agent-name">{AGENT_LABELS[agent.agent_name] || agent.agent_name}</span>
                    <span className="agent-score">{agent.score != null ? `${agent.score}/100` : 'Skipped'}</span>
                  </div>
                  <p className="agent-reasoning">{agent.reasoning}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function HistoryTab({ verdicts }) {
  if (!verdicts.length) return <div className="dash-empty"><p>No evaluations yet.</p></div>;
  return (
    <div className="dash-verdict-list">
      {verdicts.map(v => <VerdictRow key={v.verdict_id} v={v} />)}
    </div>
  );
}

function PurchasesTab({ purchases }) {
  if (!purchases.length) return <div className="dash-empty"><p>No purchases tracked yet.</p></div>;
  return (
    <div className="dash-purchase-list">
      {purchases.map(p => <PurchaseRow key={p.id} p={p} />)}
    </div>
  );
}

export default function Dashboard() {
  const { user, token } = useAuth();
  const [tab, setTab] = useState('overview');
  const [verdicts, setVerdicts] = useState([]);
  const [purchases, setPurchases] = useState([]);
  const [loadingData, setLoadingData] = useState(true);

  const fetchData = async () => {
    setLoadingData(true);
    try {
      const [v, p] = await Promise.all([
        api.verdictHistory(token).catch(() => []),
        api.getPurchaseHistory(token).catch(() => []),
      ]);
      setVerdicts(v || []);
      setPurchases(p || []);
    } finally {
      setLoadingData(false);
    }
  };

  useEffect(() => {
    if (token) fetchData();
  }, [token]);

  return (
    <div className="dashboard">
      <div className="dash-top-bar">
        <div>
          <h1 className="dash-title">Dashboard</h1>
          <p className="dash-subtitle">Welcome back, {user?.name?.split(' ')[0]}</p>
        </div>
        <button className="btn btn-primary" onClick={() => setTab('evaluate')}>
          + New Evaluation
        </button>
      </div>

      <div className="dash-tabs">
        {TABS.map(t => (
          <button
            key={t}
            className={`dash-tab ${tab === t ? 'active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t === 'overview' ? 'Overview' : t === 'evaluate' ? 'Evaluate' : t === 'history' ? 'History' : 'Purchases'}
          </button>
        ))}
      </div>

      {loadingData ? (
        <div style={{ textAlign: 'center', padding: 'var(--space-2xl)' }}>
          <div className="spinner spinner-lg" />
        </div>
      ) : (
        <div className="dash-content">
          {tab === 'overview' && <OverviewTab verdicts={verdicts} purchases={purchases} user={user} onNavigate={setTab} />}
          {tab === 'evaluate' && <EvaluateTab token={token} onDone={fetchData} />}
          {tab === 'history' && <HistoryTab verdicts={verdicts} />}
          {tab === 'purchases' && <PurchasesTab purchases={purchases} />}
        </div>
      )}
    </div>
  );
}
