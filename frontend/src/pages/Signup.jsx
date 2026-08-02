import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: '',
    email: '',
    password: '',
    monthly_income: '',
    monthly_savings_target: '',
    active_emis: '',
    recurring_bills: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await signup({
        name: form.name,
        email: form.email,
        password: form.password,
        monthly_income: parseFloat(form.monthly_income),
        monthly_savings_target: parseFloat(form.monthly_savings_target),
        active_emis: form.active_emis ? parseFloat(form.active_emis) : 0,
        recurring_bills: form.recurring_bills ? parseFloat(form.recurring_bills) : 0,
      });
      navigate('/dashboard');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="card card-elevated auth-card" style={{ maxWidth: 480 }}>
        <h2>Create your account</h2>
        <p className="auth-subtitle">Set up your financial profile in one step</p>

        {error && <div className="alert alert-error">{error}</div>}

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="name">Full Name</label>
            <input
              id="name"
              className="form-input"
              type="text"
              required
              maxLength={100}
              value={form.name}
              onChange={set('name')}
              placeholder="Jane Doe"
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="s-email">Email</label>
            <input
              id="s-email"
              className="form-input"
              type="email"
              required
              value={form.email}
              onChange={set('email')}
              placeholder="you@example.com"
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="s-password">Password</label>
            <input
              id="s-password"
              className="form-input"
              type="password"
              required
              minLength={8}
              maxLength={72}
              value={form.password}
              onChange={set('password')}
              placeholder="8-72 characters"
            />
            <span className="form-hint">Between 8 and 72 characters</span>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label" htmlFor="income">Monthly Income</label>
              <input
                id="income"
                className="form-input"
                type="number"
                required
                min={0}
                step="any"
                value={form.monthly_income}
                onChange={set('monthly_income')}
                placeholder="50000"
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="savings">Savings Target</label>
              <input
                id="savings"
                className="form-input"
                type="number"
                required
                min={0}
                step="any"
                value={form.monthly_savings_target}
                onChange={set('monthly_savings_target')}
                placeholder="10000"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label" htmlFor="emis">Active EMIs</label>
              <input
                id="emis"
                className="form-input"
                type="number"
                min={0}
                step="any"
                value={form.active_emis}
                onChange={set('active_emis')}
                placeholder="0"
              />
              <span className="form-hint">Optional</span>
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="bills">Recurring Bills</label>
              <input
                id="bills"
                className="form-input"
                type="number"
                min={0}
                step="any"
                value={form.recurring_bills}
                onChange={set('recurring_bills')}
                placeholder="0"
              />
              <span className="form-hint">Optional</span>
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-block btn-lg"
            disabled={loading}
          >
            {loading ? <span className="spinner" /> : 'Create Account'}
          </button>
        </form>

        <p className="auth-footer">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}
