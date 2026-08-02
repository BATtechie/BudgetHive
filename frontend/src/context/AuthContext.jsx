import React, { createContext, useContext, useReducer, useEffect } from 'react';
import { api } from '../api';

const AuthContext = createContext(null);

const initialState = {
  user: null,
  token: localStorage.getItem('bh_token'),
  loading: true,
};

function authReducer(state, action) {
  switch (action.type) {
    case 'SET_USER':
      return { ...state, user: action.payload, loading: false };
    case 'LOGIN':
      localStorage.setItem('bh_token', action.payload.token);
      return { user: action.payload.user, token: action.payload.token, loading: false };
    case 'LOGOUT':
      localStorage.removeItem('bh_token');
      return { user: null, token: null, loading: false };
    case 'DONE_LOADING':
      return { ...state, loading: false };
    default:
      return state;
  }
}

export function AuthProvider({ children }) {
  const [state, dispatch] = useReducer(authReducer, initialState);

  useEffect(() => {
    if (!state.token) {
      dispatch({ type: 'DONE_LOADING' });
      return;
    }
    api.me(state.token)
      .then(user => dispatch({ type: 'SET_USER', payload: user }))
      .catch(() => {
        localStorage.removeItem('bh_token');
        dispatch({ type: 'LOGOUT' });
      });
  }, []);

  const login = async (email, password) => {
    const data = await api.login({ email, password });
    dispatch({ type: 'LOGIN', payload: { token: data.access_token, user: data.user } });
    return data;
  };

  const signup = async (body) => {
    const data = await api.signup(body);
    dispatch({ type: 'LOGIN', payload: { token: data.access_token, user: data.user } });
    return data;
  };

  const logout = () => dispatch({ type: 'LOGOUT' });

  return (
    <AuthContext.Provider value={{ ...state, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be inside AuthProvider');
  return ctx;
}
