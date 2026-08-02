import React from 'react';
import { Link } from 'react-router-dom';

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <span>&copy; {new Date().getFullYear()} BudgetHive</span>
        <div className="footer-links">
          <Link to="/">Home</Link>
          <Link to="/dashboard">Dashboard</Link>
        </div>
      </div>
    </footer>
  );
}
