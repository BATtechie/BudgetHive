import React from 'react';
import { Outlet } from 'react-router-dom';
import Navbar from '../components/Navbar';
import Footer from '../components/Footer';
import ErrorBoundary from '../components/ErrorBoundary';

export default function MainLayout() {
  return (
    <>
      <Navbar />
      <ErrorBoundary>
        <main style={{ minHeight: 'calc(100vh - 60px - 120px)' }}>
          <Outlet />
        </main>
      </ErrorBoundary>
      <Footer />
    </>
  );
}
