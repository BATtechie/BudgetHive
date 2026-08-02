import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api';

const CATEGORIES = [
  'Electronics', 'Smartphones', 'Laptops', 'Tablets', 'Headphones', 'Earphones',
  'Smartwatches', 'Wearables', 'Gaming Consoles', 'Appliances', 'Furniture',
  'Home', 'Accessories', 'Fashion', 'Books',
];

const PLATFORMS = [
  'Amazon.in', 'Flipkart', 'Croma', 'Reliance Digital', 'Myntra', 'Nykaa', 'Ajio', 'BigBasket', '1mg', 'PharmEasy',
];

const AGENTS = [
  { id: 'A1', key: 'A1_Financial', name: 'Financial Agent', weight: '25%', icon: '\u{1F4CB}',
    desc: 'Reads salary, savings target, active EMIs and recurring bills. Calculates disposable surplus and a budget guardrail.',
    example: '→ Safe to spend up to ₹14,500 this month without touching your ₹20,000 savings goal.' },
  { id: 'A2', key: 'A2_Need', name: 'Need vs Want', weight: '25%', icon: '\u{1F9E0}',
    desc: 'Cross-checks purchase history and how many similar items you already own.',
    example: '→ You already own 2 working earphones. Impulse probability: 83%.' },
  { id: 'A3', key: 'A3_DealHunter', name: 'Deal Hunter', weight: '20%', icon: '\u{1F3F7}',
    desc: 'Scans Amazon, Flipkart, Croma, Reliance Digital for the best current price, 90-day trend, bank offers and cashback.',
    example: '→ Best today: ₹12,499 on Flipkart. 11% below 90-day average.' },
  { id: 'A4', key: 'A4_Alternatives', name: 'Alternatives', weight: '15%', icon: '\u{1F500}',
    desc: 'Finds 2–3 substitutes with comparable specs, refurbished units or better value-for-money picks inside your ceiling.',
    example: '→ Refurbished M3 saves ₹35,000 with identical performance.' },
  { id: 'A5', key: 'A5_RegretPredictor', name: 'Regret Predictor', weight: '15%', icon: '\u{1F504}',
    desc: 'Learns from your own history — which categories you abandoned, how fast you stopped using them — to estimate regret.',
    example: '→ Bought a smartwatch in March, unused by day 18. Estimated regret: 72%.' },
];

const AGENT_LABELS = {
  A1_Financial: { id: 'A1', name: 'Financial Agent', icon: '\u{1F4CB}' },
  A2_Need: { id: 'A2', name: 'Need vs Want', icon: '\u{1F9E0}' },
  A3_DealHunter: { id: 'A3', name: 'Deal Hunter', icon: '\u{1F3F7}' },
  A4_Alternatives: { id: 'A4', name: 'Alternatives', icon: '\u{1F500}' },
  A5_RegretPredictor: { id: 'A5', name: 'Regret Predictor', icon: '\u{1F504}' },
};

const INVOCATION_RULES = [
  { scenario: 'Retail category (Smartphones, Laptops, etc.)', agents: 'A1 · A2 · A3 · A4 · A5' },
  { scenario: 'Has purchase history in category', agents: 'A1 · A2 · A5' },
  { scenario: 'No user answers & no purchase history', agents: 'A1 only' },
  { scenario: 'Non-retail category (Books, etc.)', agents: 'A1 · A2 (no A3/A4)' },
];

const WEIGHTS = [
  { label: 'A1 Financial safety', pct: 25 },
  { label: 'A2 Need vs Want', pct: 25 },
  { label: 'A5 Regret predictor', pct: 15 },
  { label: 'A3 Deal quality', pct: 20 },
  { label: 'A4 Alternatives', pct: 15 },
];

function VerdictIcon({ verdict }) {
  if (verdict === 'BUY') return <span>✔</span>;
  if (verdict === 'MAYBE') return <span>❓</span>;
  return <span>✖</span>;
}

function verdictReason(verdict) {
  if (verdict === 'BUY') return 'Go ahead. The numbers check out.';
  if (verdict === 'MAYBE') return 'Think it over. A few signals are mixed.';
  return "Don’t. Your future self will thank you.";
}

function LiveDemo() {
  const { user, token } = useAuth();
  const [form, setForm] = useState({
    product_name: '', product_url: '', product_category: 'Headphones',
    price: '', max_budget: '', primary_use_case: '',
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setLoading(true); setResult(null);
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
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const ranCount = result ? result.agents_ran.length : 0;
  const totalCount = result ? result.agent_results.length : 0;

  return (
    <div className="demo-grid">
      <div>
        {!user ? (
          <div className="demo-login-prompt">
            <p>Log in with demo credentials to try a live verdict.</p>
            <Link to="/login"><button className="btn btn-primary btn-lg">Log In to Try</button></Link>
            <p style={{ marginTop: 'var(--space-md)', fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
              demo@budgethive.com / demo1234
            </p>
          </div>
        ) : (
          <>
            {error && <div className="alert alert-error" style={{ marginBottom: 'var(--space-md)' }}>{error}</div>}
            <form className="demo-form" onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Product Name</label>
                <input className="form-input" type="text" required value={form.product_name}
                  onChange={set('product_name')} placeholder="Sony WH-1000XM5" />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Price (₹)</label>
                  <input className="form-input" type="number" required min={1} step="any"
                    value={form.price} onChange={set('price')} placeholder="26990" />
                </div>
                <div className="form-group">
                  <label className="form-label">Category</label>
                  <select className="form-input" value={form.product_category} onChange={set('product_category')}>
                    {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Product URL (optional)</label>
                <input className="form-input" type="url" value={form.product_url}
                  onChange={set('product_url')} placeholder="https://www.amazon.in/dp/..." />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Max Budget (optional)</label>
                  <input className="form-input" type="number" min={0} step="any"
                    value={form.max_budget} onChange={set('max_budget')} placeholder="30000" />
                </div>
                <div className="form-group">
                  <label className="form-label">Primary Use Case (optional)</label>
                  <input className="form-input" type="text" value={form.primary_use_case}
                    onChange={set('primary_use_case')} placeholder="Noise cancelling for work calls" />
                </div>
              </div>
              <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={loading}>
                {loading ? <><span className="spinner" /> Analyzing...</> : 'Get Verdict'}
              </button>
            </form>
          </>
        )}
      </div>

      <div>
        {loading && (
          <div className="demo-loading">
            <div className="spinner spinner-lg" />
            <p>Running agents — this may take a moment...</p>
          </div>
        )}

        {!loading && !result && user && (
          <div className="demo-placeholder">
            <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M32 8L52 20V44L32 56L12 44V20L32 8Z" stroke="currentColor" strokeWidth="2"/>
              <path d="M32 20L42 26V38L32 44L22 38V26L32 20Z" stroke="currentColor" strokeWidth="2"/>
            </svg>
            <p>Submit a product to see your verdict</p>
          </div>
        )}

        {!loading && !result && !user && (
          <div className="demo-placeholder">
            <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M32 8L52 20V44L32 56L12 44V20L32 8Z" stroke="currentColor" strokeWidth="2"/>
              <path d="M32 20L42 26V38L32 44L22 38V26L32 20Z" stroke="currentColor" strokeWidth="2"/>
            </svg>
            <p>Verdict results appear here</p>
          </div>
        )}

        {!loading && result && (
          <div className="verdict-result-card">
            <div className={`verdict-hero verdict-hero-${result.verdict.toLowerCase()}`}>
              <div className="verdict-hero-icon"><VerdictIcon verdict={result.verdict} /></div>
              <div className="verdict-hero-label">{result.verdict}</div>
              <div className="verdict-hero-reason">{verdictReason(result.verdict)}</div>
              <div className="verdict-hero-score">
                <div className="verdict-hero-score-value">{result.composite_score}</div>
                <div className="verdict-hero-score-label">SCORE /100</div>
              </div>
            </div>

            <div className="verdict-meta">
              <span>Confidence {result.confidence_percentage}%</span>
              <span>{result.product_name}</span>
            </div>

            <div className="pipeline-header">
              <span className="pipeline-title">Agent pipeline</span>
              <span className="pipeline-count">{ranCount} / {totalCount} complete</span>
            </div>

            <div className="pipeline-list">
              {result.agent_results.map((agent) => {
                const meta = AGENT_LABELS[agent.agent_name] || { id: '?', name: agent.agent_name, icon: '⚙' };
                const isSkipped = agent.score === null;
                return (
                  <div key={agent.agent_name} className={`pipeline-item ${isSkipped ? 'pipeline-item-skipped' : ''}`}>
                    <div className="pipeline-item-icon icon-badge icon-badge-primary">{meta.icon}</div>
                    <div className="pipeline-item-content">
                      <div className="pipeline-item-header">
                        <span className="pipeline-item-id">{meta.id}</span>
                        <span className="pipeline-item-name">· {meta.name}</span>
                      </div>
                      <div className="pipeline-item-reasoning">{agent.reasoning}</div>
                    </div>
                    {!isSkipped && <div className="pipeline-item-score">{agent.score}/100</div>}
                    {isSkipped && <div className="pipeline-item-score" style={{ color: 'var(--color-text-muted)' }}>Skipped</div>}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function Landing() {
  const { user } = useAuth();

  return (
    <>
      {/* ===== HERO ===== */}
      <section className="hero">
        <div className="section-label">BudgetHive</div>
        <h1>
          Stop impulse buying.<br />
          <em>Start smart spending.</em>
        </h1>
        <p className="hero-subtitle">
          BudgetHive analyzes every purchase against your finances, real market
          prices, and alternatives &mdash; then tells you whether to BUY, MAYBE, or SKIP.
        </p>
        <div className="hero-actions">
          {user ? (
            <Link to="/dashboard"><button className="btn btn-primary btn-lg">Go to Dashboard</button></Link>
          ) : (
            <>
              <Link to="/signup"><button className="btn btn-primary btn-lg">Get Started Free</button></Link>
              <Link to="/login"><button className="btn btn-secondary btn-lg">Log In</button></Link>
            </>
          )}
        </div>
      </section>

      {/* ===== PLATFORM TICKER ===== */}
      <div className="ticker">
        <div className="ticker-inner container">
          <span className="ticker-label">Watches prices across</span>
          {PLATFORMS.map(p => <span key={p} className="ticker-item">{p}</span>)}
        </div>
      </div>

      {/* ===== 1. PROBLEM SECTION ===== */}
      <section className="section">
        <div className="problem-grid">
          <div className="problem-text">
            <div className="section-label">The Problem</div>
            <h2>Buyer&rsquo;s remorse is a <em>multi-thousand-crore</em> problem.</h2>
            <p>
              Indians spend lakhs of crores online every year. A large share lands in a
              drawer within 60 days. We built BudgetHive because comparing prices was
              never the question.
            </p>
          </div>
          <div className="problem-cards">
            <div className="problem-card">
              <div className="icon-badge icon-badge-primary">{'\u{1F4C9}'}</div>
              <h4>Price &ne; decision</h4>
              <p>Every shopping app can find you a lower price. None will tell you not to buy.</p>
            </div>
            <div className="problem-card">
              <div className="icon-badge icon-badge-primary">{'\u{1F551}'}</div>
              <h4>Impulse is invisible</h4>
              <p>You added it 6 hours ago. That&rsquo;s a feeling, not a plan. Your app doesn&rsquo;t notice.</p>
            </div>
            <div className="problem-card">
              <div className="icon-badge icon-badge-primary">{'\u{1F504}'}</div>
              <h4>You forget your own regrets</h4>
              <p>The smartwatch in your drawer isn&rsquo;t in the checkout flow. It should be.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ===== 2. AGENT SHOWCASE ===== */}
      <section className="section">
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: 'var(--space-xl)', alignItems: 'start' }}>
          <div>
            <div className="section-label">The Hive</div>
            <h2 className="section-title">Five specialist agents. <em>One orchestrated brain.</em></h2>
          </div>
          <p className="section-subtitle" style={{ paddingTop: 'var(--space-lg)' }}>
            An orchestrator picks who runs based on the product and your profile &mdash;
            not every agent fires every time. Faster answers. Fewer API bills.
          </p>
        </div>

        <div className="agent-grid">
          {AGENTS.map((agent, i) => (
            <div key={agent.id} className="agent-showcase-card card-numbered">
              <span className="card-number">{String(i + 1).padStart(2, '0')}</span>
              <div className="agent-showcase-header">
                <div className="icon-badge icon-badge-primary">{agent.icon}</div>
                <div className="agent-showcase-meta">
                  <span className="agent-showcase-id">{agent.id}</span>
                  <span className="agent-showcase-name">{agent.name}</span>
                </div>
              </div>
              <span className="agent-showcase-weight">WEIGHT {agent.weight}</span>
              <p className="agent-showcase-desc">{agent.desc}</p>
              <div className="callout">{agent.example}</div>
            </div>
          ))}
          <div className="agent-showcase-card agent-judge-card card-numbered">
            <span className="card-number">06</span>
            <div className="agent-showcase-header">
              <div className="icon-badge icon-badge-primary">{'\u{1F3AF}'}</div>
              <div className="agent-showcase-meta">
                <span className="agent-showcase-id">A6</span>
                <span className="agent-showcase-name">Final Judge</span>
              </div>
            </div>
            <span className="agent-showcase-weight">JUDGE</span>
            <p className="agent-showcase-desc">
              Reads the weighted score and only the signals that were actually computed.
              Writes a plain-language verdict with reasons for and against.
            </p>
            <div className="callout">{'→'} SKIP &middot; Confidence 84% &mdash; high impulse + regret pattern + budget breach.</div>
          </div>
        </div>
      </section>

      {/* ===== 3. LIVE DEMO ===== */}
      <section className="section">
        <div className="section-label">Try It</div>
        <h2 className="section-title">Drop a product. <em>Get a verdict.</em></h2>
        <p className="section-subtitle" style={{ marginBottom: 'var(--space-xl)' }}>
          Every score, label, and reasoning string below comes from the real API &mdash; nothing is hardcoded.
        </p>
        <div className="demo-section">
          <LiveDemo />
        </div>
      </section>

      {/* ===== 4. HOW IT WORKS ===== */}
      <section className="section">
        <div className="section-label">The Flow</div>
        <h2 className="section-title">Not another chatbot. <em>A decision pipeline.</em></h2>
        <p className="section-subtitle">
          We don&rsquo;t fire every LLM at every question. The orchestrator picks the right
          team for the job &mdash; that&rsquo;s why answers land in seconds, not minutes.
        </p>

        <div className="flow-steps">
          <div className="flow-step card-numbered">
            <span className="card-number">01</span>
            <div className="icon-badge icon-badge-primary">{'\u{1F50D}'}</div>
            <h4>You drop a product</h4>
            <p>Paste a link or type a name. We parse category, model, and specs.</p>
          </div>
          <div className="flow-step card-numbered">
            <span className="card-number">02</span>
            <div className="icon-badge icon-badge-primary">{'\u{1F6E1}'}</div>
            <h4>Profile loads privately</h4>
            <p>Salary, savings goal and EMIs &mdash; pulled from your one-time onboarding.</p>
          </div>
          <div className="flow-step card-numbered">
            <span className="card-number">03</span>
            <div className="icon-badge icon-badge-primary">{'\u{2699}'}</div>
            <h4>Orchestrator dispatches</h4>
            <p>Only relevant agents run. Non-retail categories skip Deal Hunter &amp; Alternatives.</p>
          </div>
          <div className="flow-step card-numbered">
            <span className="card-number">04</span>
            <div className="icon-badge icon-badge-primary">{'\u{1F3AF}'}</div>
            <h4>One verdict, honestly</h4>
            <p>BUY, MAYBE or SKIP &mdash; with 2&ndash;3 real reasons pulled from the agents that ran.</p>
          </div>
        </div>

        <div className="invocation-table">
          <div className="invocation-header">
            <div className="section-label" style={{ marginBottom: 0 }}>Selective Invocation</div>
            <p style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', marginTop: 'var(--space-xs)' }}>When each agent gets called</p>
          </div>
          {INVOCATION_RULES.map((rule, i) => (
            <div key={i} className="invocation-row">
              <span className="invocation-scenario">{rule.scenario}</span>
              <span className="invocation-agents">{rule.agents}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ===== 5. SCORING + SCREENS ===== */}
      <section className="section">
        <div className="scoring-grid">
          <div>
            <div className="section-label">Weighted Scoring</div>
            <h2 className="section-title" style={{ fontSize: 'clamp(1.4rem, 3vw, 2rem)' }}>
              How the score becomes a verdict.
            </h2>
            <p className="section-subtitle">
              Each active agent contributes a signal. Their weights combine into a single
              0&ndash;100 score. When an agent doesn&rsquo;t run, its weight is redistributed
              among the ones that did &mdash; no invented reasons.
            </p>
            <div className="threshold-list">
              <div className="threshold-item">
                <span>Score &ge; 70</span>
                <span className="verdict-badge verdict-buy" style={{ padding: '4px 12px', fontSize: '0.78rem' }}>BUY</span>
              </div>
              <div className="threshold-item">
                <span>40 &ndash; 69</span>
                <span className="verdict-badge verdict-maybe" style={{ padding: '4px 12px', fontSize: '0.78rem' }}>MAYBE</span>
              </div>
              <div className="threshold-item">
                <span>&lt; 40</span>
                <span className="verdict-badge verdict-skip" style={{ padding: '4px 12px', fontSize: '0.78rem' }}>SKIP</span>
              </div>
            </div>
          </div>

          <div className="card" style={{ marginTop: 'var(--space-xl)' }}>
            <div className="section-label" style={{ marginBottom: 'var(--space-lg)' }}>Signal Weights</div>
            <div className="weight-bar-list">
              {WEIGHTS.map(w => (
                <div key={w.label} className="weight-bar-item">
                  <span className="weight-bar-label">{w.label}</span>
                  <div className="weight-bar-track">
                    <div className="weight-bar-fill" style={{ width: `${w.pct * 4}%` }} />
                  </div>
                  <span className="weight-bar-value">{w.pct}%</span>
                </div>
              ))}
            </div>
            <div className="callout" style={{ marginTop: 'var(--space-lg)' }}>
              When A5 doesn&rsquo;t run (no history match), its 15% redistributes across A1&ndash;A4
              proportionally. The judge only cites what actually ran.
            </div>
          </div>
        </div>

        <div style={{ marginTop: 'var(--space-3xl)' }}>
          <div className="section-label">The App</div>
          <h2 className="section-title">Five screens. <em>Zero clutter.</em></h2>
        </div>

        <div className="screens-grid">
          <div className="screen-preview">
            <div className="screen-preview-label">Onboarding</div>
            <div className="screen-preview-desc">Salary &middot; Savings goal &middot; EMIs &mdash; once.</div>
            <div className="screen-preview-rows">
              <div className="screen-preview-row">
                <span>Monthly income</span>
                <span className="screen-preview-row-value">{'₹'} 85,000</span>
              </div>
              <div className="screen-preview-row">
                <span>Savings target</span>
                <span className="screen-preview-row-value">{'₹'} 20,000</span>
              </div>
              <div className="screen-preview-row">
                <span>Active EMIs</span>
                <span className="screen-preview-row-value">{'₹'} 12,000/mo</span>
              </div>
            </div>
            <Link to="/signup" style={{ display: 'block', marginTop: 'var(--space-md)' }}>
              <button className="btn btn-primary btn-block">Enter the hive</button>
            </Link>
          </div>

          <div className="screen-preview">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div className="screen-preview-label">Watchlist</div>
              <span className="coming-soon-badge">Coming Soon</span>
            </div>
            <div className="screen-preview-desc">Skipped &amp; maybe items &mdash; tracked automatically.</div>
            <div className="screen-preview-rows">
              <div className="screen-preview-row">
                <span style={{ color: 'var(--color-text-muted)' }}>Price tracking for SKIP/MAYBE verdicts</span>
              </div>
              <div className="screen-preview-row">
                <span style={{ color: 'var(--color-text-muted)' }}>Alert when price drops below target</span>
              </div>
            </div>
          </div>

          <div className="screen-preview">
            <div className="screen-preview-label">Decision Log</div>
            <div className="screen-preview-desc">What you did &mdash; and what happened.</div>
            <div className="screen-preview-rows">
              <div className="screen-preview-row">
                <span>Purchase history with regret scores</span>
              </div>
              <div className="screen-preview-row">
                <span>Check-in reminders after purchase</span>
              </div>
              <div className="screen-preview-row">
                <span>Feeds the Regret Predictor agent</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===== CTA ===== */}
      <section className="section" style={{ textAlign: 'center', paddingBottom: 'var(--space-3xl)' }}>
        <h2 className="section-title">Ready to think before you buy?</h2>
        <div className="hero-actions">
          {user ? (
            <Link to="/dashboard"><button className="btn btn-primary btn-lg">Go to Dashboard</button></Link>
          ) : (
            <Link to="/signup"><button className="btn btn-primary btn-lg">Get Started Free</button></Link>
          )}
        </div>
      </section>
    </>
  );
}
