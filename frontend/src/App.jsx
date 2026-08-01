import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

const TABS = [
  { id: "health", label: "System", icon: "⚡" },
  { id: "auth", label: "Auth", icon: "🔐" },
  { id: "financial", label: "A1 Financial", icon: "💰" },
  { id: "need", label: "A2 Need", icon: "🎯" },
  { id: "deal", label: "A3 Deal Hunter", icon: "🏷️" },
  { id: "alternatives", label: "A4 Alternatives", icon: "🔄" },
];

function ResultPanel({ loading, error, result }) {
  if (loading) return <div className="result loading">Running…</div>;
  if (error) return <div className="result error">{error}</div>;
  if (!result) return <div className="result empty">Response will appear here</div>;
  return (
    <pre className="result success">{JSON.stringify(result, null, 2)}</pre>
  );
}

function Field({ label, children, hint }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

function HealthTab() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      setResult(await api.health());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    run();
  }, []);

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>System Health</h2>
        <p>Checks that the FastAPI backend is up and responding.</p>
      </div>
      <button className="btn primary" onClick={run} disabled={loading}>
        Ping /health
      </button>
      <ResultPanel loading={loading} error={error} result={result} />
    </section>
  );
}

function AuthTab({ token, setToken, user, setUser }) {
  const [mode, setMode] = useState("login");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [form, setForm] = useState({
    name: "Test User",
    email: "test@budgethive.dev",
    password: "testpass123",
    monthly_income: 80000,
    monthly_savings_target: 20000,
    active_emis: 15000,
    recurring_bills: 10000,
  });

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  const handleAuth = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload =
        mode === "signup"
          ? {
              ...form,
              monthly_income: Number(form.monthly_income),
              monthly_savings_target: Number(form.monthly_savings_target),
              active_emis: Number(form.active_emis),
              recurring_bills: Number(form.recurring_bills),
            }
          : { email: form.email, password: form.password };

      const data = await (mode === "signup" ? api.signup : api.login)(payload);
      setToken(data.access_token);
      setUser(data.user);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchProfile = async () => {
    if (!token) return setError("Log in first");
    setLoading(true);
    setError(null);
    try {
      const data = await api.me(token);
      setUser(data);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    setResult(null);
    setError(null);
  };

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Auth & Profile</h2>
        <p>Signup collects financial onboarding data. Login to use your profile in agent tests.</p>
      </div>

      <div className="toggle-row">
        <button
          className={`toggle ${mode === "login" ? "active" : ""}`}
          onClick={() => setMode("login")}
        >
          Login
        </button>
        <button
          className={`toggle ${mode === "signup" ? "active" : ""}`}
          onClick={() => setMode("signup")}
        >
          Signup
        </button>
      </div>

      <div className="form-grid">
        {mode === "signup" && (
          <Field label="Name">
            <input value={form.name} onChange={set("name")} />
          </Field>
        )}
        <Field label="Email">
          <input type="email" value={form.email} onChange={set("email")} />
        </Field>
        <Field label="Password">
          <input type="password" value={form.password} onChange={set("password")} />
        </Field>
        {mode === "signup" && (
          <>
            <Field label="Monthly Income (₹)">
              <input type="number" value={form.monthly_income} onChange={set("monthly_income")} />
            </Field>
            <Field label="Savings Target (₹)">
              <input
                type="number"
                value={form.monthly_savings_target}
                onChange={set("monthly_savings_target")}
              />
            </Field>
            <Field label="Active EMIs (₹)">
              <input type="number" value={form.active_emis} onChange={set("active_emis")} />
            </Field>
            <Field label="Recurring Bills (₹)">
              <input type="number" value={form.recurring_bills} onChange={set("recurring_bills")} />
            </Field>
          </>
        )}
      </div>

      <div className="btn-row">
        <button className="btn primary" onClick={handleAuth} disabled={loading}>
          {mode === "signup" ? "Create Account" : "Login"}
        </button>
        <button className="btn" onClick={fetchProfile} disabled={loading || !token}>
          Fetch Profile
        </button>
        {token && (
          <button className="btn ghost" onClick={logout}>
            Logout
          </button>
        )}
      </div>

      {token && (
        <div className="status-chip ok">
          Logged in as {user?.name ?? user?.email ?? "…"}
        </div>
      )}

      <ResultPanel loading={loading} error={error} result={result} />
    </section>
  );
}

function FinancialTab({ token, user }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [useProfile, setUseProfile] = useState(!!token);
  const [useLlm, setUseLlm] = useState(false);
  const [form, setForm] = useState({
    purchase_price: 40000,
    monthly_income: 80000,
    monthly_savings_target: 20000,
    active_emis: 15000,
    recurring_bills: 10000,
  });

  const set = (key) => (e) =>
    setForm({ ...form, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const body = {
        purchase_price: Number(form.purchase_price),
        use_llm: useLlm,
      };
      if (!useProfile || !token) {
        body.monthly_income = Number(form.monthly_income);
        body.monthly_savings_target = Number(form.monthly_savings_target);
        body.active_emis = Number(form.active_emis);
        body.recurring_bills = Number(form.recurring_bills);
      }
      setResult(await api.financialEvaluate(body, useProfile ? token : null));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>A1 — Financial Agent</h2>
        <p>Checks affordability vs income, savings, EMIs, and bills. Rule-based by default; toggle LLM for Gemini.</p>
      </div>

      <div className="form-grid">
        <Field label="Purchase Price (₹)">
          <input type="number" value={form.purchase_price} onChange={set("purchase_price")} />
        </Field>
        <label className="checkbox-field">
          <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} />
          Use Gemini LLM (requires API key)
        </label>
        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={useProfile}
            onChange={(e) => setUseProfile(e.target.checked)}
            disabled={!token}
          />
          Use logged-in profile {token ? `(₹${user?.monthly_income?.toLocaleString()} income)` : "(login first)"}
        </label>
      </div>

      {(!useProfile || !token) && (
        <div className="form-grid">
          <Field label="Monthly Income (₹)">
            <input type="number" value={form.monthly_income} onChange={set("monthly_income")} />
          </Field>
          <Field label="Savings Target (₹)">
            <input type="number" value={form.monthly_savings_target} onChange={set("monthly_savings_target")} />
          </Field>
          <Field label="Active EMIs (₹)">
            <input type="number" value={form.active_emis} onChange={set("active_emis")} />
          </Field>
          <Field label="Recurring Bills (₹)">
            <input type="number" value={form.recurring_bills} onChange={set("recurring_bills")} />
          </Field>
        </div>
      )}

      <button className="btn primary" onClick={run} disabled={loading}>
        Evaluate Affordability
      </button>
      <ResultPanel loading={loading} error={error} result={result} />
    </section>
  );
}

function NeedTab() {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [questions, setQuestions] = useState(null);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [form, setForm] = useState({
    product_name: "Sony WH-1000XM5",
    category: "Electronics",
    price: 26990,
  });
  const [useHistory, setUseHistory] = useState(false);
  const [historySummary, setHistorySummary] = useState(
    "User bought 3 Electronics items in past 6 months. Bluetooth speaker (kept, used daily), Smart watch (returned), USB hub (kept, used weekly)."
  );

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  const generateQuestions = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await api.needQuestions({
        product_name: form.product_name,
        category: form.category,
        price: Number(form.price),
      });
      setQuestions(data);
      setAnswers({});
      setStep(2);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const evaluate = async () => {
    setLoading(true);
    setError(null);
    try {
      const body = {
        product_name: form.product_name,
        category: form.category,
        price: Number(form.price),
      };
      if (useHistory) {
        body.purchase_history_summary = historySummary;
      } else {
        body.user_answers = answers;
      }
      setResult(await api.needEvaluate(body));
      setStep(3);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setStep(1);
    setQuestions(null);
    setAnswers({});
    setResult(null);
    setError(null);
  };

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>A2 — Need vs Want Agent</h2>
        <p>Step 1: generate questions. Step 2: answer them (or use purchase history). Step 3: get scored verdict.</p>
      </div>

      <div className="steps">
        {[1, 2, 3].map((n) => (
          <span key={n} className={`step ${step >= n ? "done" : ""}`}>
            {n}. {n === 1 ? "Product" : n === 2 ? "Questions" : "Result"}
          </span>
        ))}
      </div>

      {step === 1 && (
        <>
          <div className="form-grid">
            <Field label="Product Name">
              <input value={form.product_name} onChange={set("product_name")} />
            </Field>
            <Field label="Category">
              <input value={form.category} onChange={set("category")} />
            </Field>
            <Field label="Price (₹)">
              <input type="number" value={form.price} onChange={set("price")} />
            </Field>
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={useHistory}
                onChange={(e) => setUseHistory(e.target.checked)}
              />
              Skip questions — use purchase history instead
            </label>
          </div>
          {useHistory && (
            <Field label="Purchase History Summary">
              <textarea
                rows={3}
                value={historySummary}
                onChange={(e) => setHistorySummary(e.target.value)}
              />
            </Field>
          )}
          <div className="btn-row">
            <button
              className="btn primary"
              onClick={useHistory ? evaluate : generateQuestions}
              disabled={loading}
            >
              {useHistory ? "Evaluate from History" : "Generate Questions"}
            </button>
          </div>
        </>
      )}

      {step === 2 && questions && (
        <>
          <p className="reason-text">{questions.reason_for_asking}</p>
          {questions.questions.map((q, i) => (
            <Field key={i} label={`Q${i + 1}: ${q.question}`}>
              <textarea
                rows={2}
                value={answers[q.question] ?? ""}
                onChange={(e) => setAnswers({ ...answers, [q.question]: e.target.value })}
                placeholder="Type your answer…"
              />
            </Field>
          ))}
          <div className="btn-row">
            <button className="btn" onClick={() => setStep(1)}>
              Back
            </button>
            <button className="btn primary" onClick={evaluate} disabled={loading}>
              Score Need vs Want
            </button>
          </div>
        </>
      )}

      {step === 3 && (
        <button className="btn" onClick={reset}>
          Start Over
        </button>
      )}

      <ResultPanel loading={loading} error={error} result={result} />
    </section>
  );
}

function AlternativesTab() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [form, setForm] = useState({
    product_name: "Samsung Galaxy S25 FE",
    category: "Smartphones",
    price: 55000,
    budget_ceiling: 70000,
    primary_use_case: "Flagship-like performance and camera",
  });

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const body = {
        product_name: form.product_name,
        category: form.category,
        price: Number(form.price),
      };
      if (form.budget_ceiling) body.budget_ceiling = Number(form.budget_ceiling);
      if (form.primary_use_case) body.primary_use_case = form.primary_use_case;
      setResult(await api.alternativesEvaluate(body));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>A4 — Alternatives Agent</h2>
        <p>Find lower-cost alternatives in the same price band for the product you are evaluating.</p>
      </div>

      <div className="form-grid">
        <Field label="Product Name">
          <input value={form.product_name} onChange={set("product_name")} />
        </Field>
        <Field label="Category">
          <input value={form.category} onChange={set("category")} />
        </Field>
        <Field label="Original Price (₹)">
          <input type="number" value={form.price} onChange={set("price")} />
        </Field>
        <Field label="Budget Ceiling (₹)">
          <input type="number" value={form.budget_ceiling} onChange={set("budget_ceiling")} />
        </Field>
        <Field label="Primary Use Case">
          <input value={form.primary_use_case} onChange={set("primary_use_case")} />
        </Field>
      </div>

      <div className="btn-row">
        <button className="btn primary" onClick={run} disabled={loading}>
          Find Alternatives
        </button>
      </div>

      <ResultPanel loading={loading} error={error} result={result} />
    </section>
  );
}

function DealTab() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [form, setForm] = useState({
    product_input: "Sony WH-1000XM5 Wireless Headphones",
    user_banks: "HDFC Bank, ICICI Bank",
    max_budget: 27000,
  });

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const body = {
        product_input: form.product_input,
        max_budget: Number(form.max_budget),
      };
      const banks = form.user_banks
        .split(",")
        .map((b) => b.trim())
        .filter(Boolean);
      if (banks.length) body.user_banks = banks;
      setResult(await api.dealHunterEvaluate(body));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const aiRec = result?.ai_recommendation;

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>A3 — Deal Hunter Agent</h2>
        <p>Scans Indian e-commerce platforms, compares prices, bank offers, and deal quality.</p>
      </div>

      <div className="form-grid">
        <Field label="Product Name or URL" hint="Try a fashion item or electronics product">
          <input value={form.product_input} onChange={set("product_input")} />
        </Field>
        <Field label="Your Banks (comma-separated)">
          <input value={form.user_banks} onChange={set("user_banks")} />
        </Field>
        <Field label="Max Budget (₹)">
          <input type="number" value={form.max_budget} onChange={set("max_budget")} />
        </Field>
      </div>

      <div className="btn-row">
        <button className="btn primary" onClick={run} disabled={loading}>
          Hunt Deals
        </button>
      </div>

      {result && !loading && !error && (
        <div className="deal-summary">
          <div className="deal-cards">
            <div className="deal-card">
              <span className="deal-label">Category</span>
              <span className="deal-value">{result.category}</span>
            </div>
            <div className="deal-card">
              <span className="deal-label">Best Platform</span>
              <span className="deal-value">{result.best_platform}</span>
            </div>
            <div className="deal-card">
              <span className="deal-label">Deal Score</span>
              <span className="deal-value">{result.overall_score}/100</span>
            </div>
            <div className="deal-card">
              <span className="deal-label">Verdict</span>
              <span className={`deal-value badge-${result.buy_now_or_wait?.toLowerCase()}`}>
                {result.buy_now_or_wait?.replace(/_/g, " ")}
              </span>
            </div>
          </div>
          {aiRec && (
            <div className="ai-rec">
              <h3>AI Recommendation</h3>
              <div
                className="ai-rec-body"
                dangerouslySetInnerHTML={{
                  __html: aiRec
                    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
                    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
                    .replace(/^### (.*)$/gm, "<h4>$1</h4>")
                    .replace(/^(\d+\. .*)/gm, "<p>$1</p>")
                    .replace(/\n/g, "<br/>"),
                }}
              />
            </div>
          )}
        </div>
      )}

      <ResultPanel loading={loading} error={error} result={result} />
    </section>
  );
}

export default function App() {
  const [tab, setTab] = useState("health");
  const [token, setToken] = useState(() => localStorage.getItem("bh_token"));
  const [user, setUser] = useState(null);

  const persistToken = useCallback((t) => {
    setToken(t);
    if (t) localStorage.setItem("bh_token", t);
    else localStorage.removeItem("bh_token");
  }, []);

  useEffect(() => {
    if (token) {
      api.me(token).then(setUser).catch(() => persistToken(null));
    }
  }, [token, persistToken]);

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="logo">🐝</span>
          <div>
            <h1>BudgetHive</h1>
            <p>Dev Console — test all built components</p>
          </div>
        </div>
        <div className="header-status">
          <span className={`dot ${token ? "ok" : ""}`} />
          {token ? `Logged in · ${user?.email ?? "…"}` : "Not logged in"}
        </div>
      </header>

      <nav className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`tab ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            <span className="tab-icon">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </nav>

      <main className="main">
        {tab === "health" && <HealthTab />}
        {tab === "auth" && (
          <AuthTab token={token} setToken={persistToken} user={user} setUser={setUser} />
        )}
        {tab === "financial" && <FinancialTab token={token} user={user} />}
        {tab === "need" && <NeedTab />}
        {tab === "deal" && <DealTab />}
        {tab === "alternatives" && <AlternativesTab />}
      </main>

      <footer className="footer">
        Backend: <code>http://localhost:8000</code> · API docs:{" "}
        <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">
          /docs
        </a>
      </footer>
    </div>
  );
}
