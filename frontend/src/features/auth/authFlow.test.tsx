import { renderToStaticMarkup } from 'react-dom/server';
import { StaticRouter } from 'react-router-dom/server';
import { describe, expect, it } from 'vitest';
import { LoginPage } from '../../pages/LoginPage';
import { Header } from '../../layouts/Header';
import { Sidebar } from '../../layouts/Sidebar';
import { AuthProvider } from '../../context/AuthContext';

describe('Authentication & Role Presentation', () => {
  it('renders LoginPage with all 3 demo persona presets', () => {
    const markup = renderToStaticMarkup(
      <AuthProvider>
        <StaticRouter location="/login">
          <LoginPage />
        </StaticRouter>
      </AuthProvider>
    );

    expect(markup).toContain('MedOrchestrate');
    expect(markup).toContain('Hospital ID / Email');
    expect(markup).toContain('Password');
    expect(markup).toContain('Attending Physician (Doctor)');
    expect(markup).toContain('doctor@demo.local');
    expect(markup).toContain('Medical Superintendent');
    expect(markup).toContain('superintendent@demo.local');
    expect(markup).toContain('Patient (Eleanor Vance)');
    expect(markup).toContain('patient@demo.local');
    expect(markup).toContain('JWT Bearer RBAC Active');
  });

  it('renders Header with system health and staff identity', () => {
    const markup = renderToStaticMarkup(
      <AuthProvider>
        <StaticRouter location="/dashboard">
          <Header />
        </StaticRouter>
      </AuthProvider>
    );

    expect(markup).toContain('Metro General Hospital');
    expect(markup).toContain('Central Medical Ward &amp; ICU Network');
  });

  it('renders Sidebar with strict doctor clinical navigation links', () => {
    const markup = renderToStaticMarkup(
      <AuthProvider>
        <StaticRouter location="/dashboard">
          <Sidebar />
        </StaticRouter>
      </AuthProvider>
    );

    expect(markup).toContain('MedOrchestrate');
    expect(markup).toContain('Dashboard');
    expect(markup).toContain('Patients');
    expect(markup).toContain('Transfers');
    expect(markup).not.toContain('Hospitals');
    expect(markup).not.toContain('Ambulances');
    expect(markup).not.toContain('Beds');
  });
});
