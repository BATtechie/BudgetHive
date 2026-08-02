import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

function HiveLogo() {
  return (
    <svg viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M14 2L24.5 8.5V19.5L14 26L3.5 19.5V8.5L14 2Z" fill="#D4940A" opacity="0.9"/>
      <path d="M14 7L20 10.5V17.5L14 21L8 17.5V10.5L14 7Z" fill="#E8B84A"/>
      <path d="M14 11L17 12.75V16.25L14 18L11 16.25V12.75L14 11Z" fill="#FFF3D6"/>
    </svg>
  );
}

export default function Navbar() {
  const { user, logout } = useAuth();

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="navbar-brand">
          <HiveLogo />
          BudgetHive
        </Link>

        <div className="navbar-links">
          {user ? (
            <div className="navbar-user">
              <Link to="/dashboard" className="navbar-links">Dashboard</Link>
              <span className="navbar-user-name">{user.name}</span>
              <button className="navbar-logout" onClick={logout}>Log out</button>
            </div>
          ) : (
            <>
              <Link to="/login">Log in</Link>
              <Link to="/signup">
                <button className="btn btn-primary btn-sm">Sign up</button>
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
